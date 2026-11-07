"""Spider da UFSM - Universidade Federal de Santa Maria (código e-MEC 582)."""

import logging
import re
import unicodedata
from collections import Counter

import requests

from sauf_scraper.censo.casamento import aplicar_codigos, codigos_confirmados
from sauf_scraper.core.models import (
    Curso,
    Fonte,
    Grau,
    LoteIngestao,
    Modalidade,
    Opcao,
    juntar_por_grau,
    montar_chave_curso,
    semestres_de_texto,
)
from sauf_scraper.parsers.ufsm import (
    CursoListado,
    DetalhesCurso,
    Habilitacao,
    SobreCurso,
    extrair_detalhes,
    extrair_lista,
    extrair_sobre,
)
from sauf_scraper.spiders.base import Spider

logger = logging.getLogger(__name__)

URL_ROBOTS = "https://www.ufsm.br/robots.txt"
UF = "RS"

# Pasta do campus na URL -> cidade.
CIDADES = {
    "santa-maria": "Santa Maria",
    "cachoeira-do-sul": "Cachoeira do Sul",
    "frederico-westphalen": "Frederico Westphalen",
    "palmeira-das-missoes": "Palmeira das Missões",
}

_GRAUS = {
    "bacharelado": Grau.BACHARELADO,
    "licenciatura": Grau.LICENCIATURA,
    "tecnologico": Grau.TECNOLOGICO,
    "tecnologo": Grau.TECNOLOGICO,
}
_MODALIDADES = {
    "presencial": Modalidade.PRESENCIAL,
    "semipresencial": Modalidade.SEMIPRESENCIAL,
    "a distancia": Modalidade.EAD,
    "ead": Modalidade.EAD,
}
# Grau no título: "Licenciatura em Teatro", "Tecnologia em Alimentos" (prefixo, como na
# UTFPR) e "Dança – Bacharelado", "Jornalismo Bacharelado" (sufixo, com ou sem traço).
_PREFIXO_GRAU = re.compile(r"^(bacharelado|licenciatura|tecnologia) em\s+", re.IGNORECASE)
_SUFIXO_GRAU = re.compile(r"\s*(?:[–-]\s*)?\b(bacharelado|licenciatura)\s*$", re.IGNORECASE)


class UfsmSpider(Spider):
    chave = "ufsm"
    codigo_emec = 582

    def coletar(self) -> LoteIngestao:
        lista = extrair_lista(self.http.get(URL_ROBOTS).text)

        codigos = codigos_confirmados(self.chave)
        cursos = []
        for item in lista:
            if item.campus not in CIDADES:
                logger.warning("campus desconhecido", extra={"dados": {"url": item.url}})
                continue
            # O HttpEducado já espera o delay entre uma página e outra.
            detalhes = extrair_detalhes(self.http.get(item.url).text)
            curso = montar_curso(item, detalhes, self._sobre(item))
            cursos.append(aplicar_codigos(curso, codigos.get(curso.chave, [])))

        contagem = Counter(c.chave for c in cursos)
        repetidas = sorted(chave for chave, n in contagem.items() if n > 1)
        if repetidas:
            raise ValueError(f"chaves de curso repetidas: {repetidas}")

        return LoteIngestao(
            execucao_id=self.execucao_id,
            fonte=Fonte(url=URL_ROBOTS),
            codigo_emec_instituicao=self.codigo_emec,
            cursos=cursos,
        )

    def _sobre(self, item: CursoListado) -> SobreCurso:
        """Página "Sobre o curso". Nem todo curso tem (404): aí sobre e mercado ficam null."""
        try:
            return extrair_sobre(self.http.get(item.url + "sobre-o-curso/").text)
        except requests.HTTPError as erro:
            status = erro.response.status_code if erro.response is not None else None
            logger.info(
                "curso sem página sobre", extra={"dados": {"url": item.url, "status": status}}
            )
            return SobreCurso()


def montar_curso(item: CursoListado, detalhes: DetalhesCurso, sobre: SobreCurso) -> Curso:
    """Junta a página principal (habilitações) e a página "Sobre o curso" num Curso."""
    cidade = CIDADES[item.campus]
    titulo = detalhes.titulo or item.pasta.replace("-", " ").title()
    turno = " ou ".join(_distintos(h.turno.capitalize() for h in detalhes.habilitacoes)) or None
    duracao = duracao_do_curso(detalhes.habilitacoes)
    return Curso(
        # A chave usa o título com o grau ("Dança – Bacharelado"), para o bacharelado e a
        # licenciatura do mesmo campus (páginas diferentes) não terem a mesma chave.
        chave=montar_chave_curso("ufsm", titulo, cidade),
        url_origem=item.url,
        nome=nome_sem_grau(titulo),
        opcoes=opcoes_do_curso(detalhes.habilitacoes),
        modalidade=modalidade_do_curso(detalhes.habilitacoes),
        turno=turno,
        sobre=sobre.sobre,
        mercado_trabalho=sobre.mercado_trabalho,
        duracao_texto=duracao,
        duracao_semestres=semestres_de_texto(duracao),
        cidade=cidade,
        uf=UF,
        # Os codigos_emec vêm da tabela de casamento (spiders/dados/ufsm_codigos.csv).
    )


def nome_sem_grau(titulo: str) -> str:
    """'Licenciatura em Teatro' -> 'Teatro'; 'Jornalismo Bacharelado' -> 'Jornalismo'.
    'Licenciatura Intercultural Indígena' fica igual (o grau é o nome do curso)."""
    nome = _SUFIXO_GRAU.sub("", _PREFIXO_GRAU.sub("", titulo)).strip()
    return nome or titulo


def opcoes_do_curso(habilitacoes: list[Habilitacao]) -> list[Opcao]:
    """Uma Opcao por grau, com os turnos das habilitações desse grau ("Diurno ou Noturno")."""
    opcoes = []
    for habilitacao in habilitacoes:
        grau = _GRAUS.get(_normalizar(habilitacao.grau).split(" ")[0])
        if grau:
            opcoes.append(Opcao(grau=grau, turno=habilitacao.turno.capitalize()))
    return juntar_por_grau(opcoes)


def duracao_de(habilitacao: Habilitacao) -> str | None:
    """8 períodos semestrais -> '8 semestres'; 5 períodos anuais -> '5 anos'."""
    if not habilitacao.periodos:
        return None
    unidade = "anos" if _normalizar(habilitacao.regime).startswith("anual") else "semestres"
    return f"{habilitacao.periodos} {unidade}"


def duracao_do_curso(habilitacoes: list[Habilitacao]) -> str | None:
    """Mesma duração em todas as habilitações -> '8 semestres'. Durações diferentes -> o
    texto lista cada uma ("Bacharelado Diurno: 8 semestres; ...") e os semestres ficam sem
    valor, como na UEL."""
    duracoes = _distintos(duracao_de(h) for h in habilitacoes)
    if len(duracoes) <= 1:
        return duracoes[0] if duracoes else None
    return "; ".join(
        f"{h.grau.capitalize()} {h.turno.capitalize()}: {duracao_de(h)}"
        for h in habilitacoes
        if duracao_de(h)
    )


def modalidade_do_curso(habilitacoes: list[Habilitacao]) -> Modalidade | None:
    modalidades = _distintos(_MODALIDADES.get(_normalizar(h.modalidade)) for h in habilitacoes)
    return modalidades[0] if len(modalidades) == 1 else None


def _distintos(valores) -> list:
    resultado = []
    for valor in valores:
        if valor and valor not in resultado:
            resultado.append(valor)
    return resultado


def _normalizar(texto: str | None) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())
