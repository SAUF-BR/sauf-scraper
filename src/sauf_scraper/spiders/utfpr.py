"""Spider da UTFPR - Universidade Tecnológica Federal do Paraná (código e-MEC 588).

O site é Plone/Volto: os dados vêm da API JSON pública, que responde no mesmo caminho
da página com o prefixo /++api++/. O link guardado para o estudante é o da página pública.
"""

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
    montar_chave_curso,
    semestres_de_texto,
)
from sauf_scraper.parsers.utfpr import (
    CursoListado,
    DetalhesCurso,
    campi_da_lista,
    extrair_detalhes,
    extrair_lista,
)
from sauf_scraper.spiders.base import Spider

SITE = "https://www.utfpr.edu.br"
API = f"{SITE}/++api++"
URL_LISTA = f"{SITE}/cursos/graduacao"  # página pública (crédito da fonte)
URL_BUSCA = f"{API}/cursos/coordenacoes/graduacao/@search?path.depth=2&b_size=1000"
UF = "PR"  # todos os campi ficam no Paraná

logger = logging.getLogger(__name__)

# "Licenciatura em Matemática" -> "Matemática": o grau vai nas opções e o nome fica igual
# ao do Censo, o que ajuda o casamento.
_PREFIXOS_GRAU = (
    ("bacharelado em ", Grau.BACHARELADO),
    ("licenciatura em ", Grau.LICENCIATURA),
    ("tecnologia em ", Grau.TECNOLOGICO),
)


class UtfprSpider(Spider):
    chave = "utfpr"
    codigo_emec = 588

    def coletar(self) -> LoteIngestao:
        busca = self.http.get(URL_BUSCA).json()
        campi = campi_da_lista(busca)

        codigos = codigos_confirmados(self.chave)
        cursos = []
        for item in extrair_lista(busca):
            detalhes = self._detalhes(item)
            curso = montar_curso(item, detalhes, campi.get(item.campus, item.campus))
            cursos.append(aplicar_codigos(curso, codigos.get(curso.chave, [])))

        contagem = Counter(c.chave for c in cursos)
        repetidas = sorted(chave for chave, n in contagem.items() if n > 1)
        if repetidas:
            raise ValueError(f"chaves de curso repetidas: {repetidas}")

        return LoteIngestao(
            execucao_id=self.execucao_id,
            fonte=Fonte(url=URL_LISTA),
            codigo_emec_instituicao=self.codigo_emec,
            cursos=cursos,
        )

    def _detalhes(self, item: CursoListado) -> DetalhesCurso | None:
        """Página "Apresentação" do curso. None se ela não for pública (ex.: 401)."""
        try:
            # O HttpEducado já espera o delay entre uma requisição e outra.
            detalhes = extrair_detalhes(self.http.get(para_api(item.url) + "/apresentacao").json())
            if not (detalhes.sobre or detalhes.turno) and detalhes.filhos:
                # Algumas coordenações põem o conteúdo numa página filha ("listing").
                detalhes = extrair_detalhes(self.http.get(para_api(detalhes.filhos[0])).json())
            return detalhes
        except requests.HTTPError as erro:
            status = erro.response.status_code if erro.response is not None else None
            logger.warning(
                "página do curso indisponível",
                extra={"dados": {"curso": item.url, "status": status}},
            )
            return None


def para_api(url: str) -> str:
    """https://www.utfpr.edu.br/cursos/... -> https://www.utfpr.edu.br/++api++/cursos/..."""
    return url.replace(SITE, API, 1) if "/++api++/" not in url else url


def montar_curso(item: CursoListado, detalhes: DetalhesCurso | None, cidade: str) -> Curso:
    """Junta o que veio da busca e da página "Apresentação" num Curso do nosso modelo.

    Sem a página (detalhes None), o curso entra com o que a busca dá: nome, grau pelo
    título, campus e o link da pasta do curso.
    """
    sem_pagina = detalhes is None
    detalhes = detalhes or DetalhesCurso()
    nome, grau = nome_e_grau(item.nome, detalhes.titulacao)
    turno = _primeira_maiuscula(detalhes.turno)
    duracao = (detalhes.duracao or "").strip() or None
    return Curso(
        # A chave usa o título do site, com o grau ("Licenciatura em Química"), para o
        # bacharelado e a licenciatura do mesmo campus não terem a mesma chave.
        chave=montar_chave_curso("utfpr", item.nome, cidade, turno or ""),
        url_origem=item.url if sem_pagina else item.url + "/apresentacao",
        nome=nome,
        opcoes=[Opcao(grau=grau, turno=turno)] if grau else [],
        modalidade=Modalidade.PRESENCIAL,
        turno=turno,
        sobre=juntar_sobre(detalhes),
        mercado_trabalho=detalhes.mercado_trabalho,
        duracao_texto=duracao,
        duracao_semestres=semestres_de_texto(_so_a_duracao(duracao)),
        cidade=cidade,
        uf=UF,
        # Os codigos_emec vêm da tabela de casamento (spiders/dados/utfpr_codigos.csv).
    )


def nome_e_grau(titulo: str, titulacao: str | None) -> tuple[str, Grau | None]:
    """Nome sem o grau e o grau, pelo título do site ou, se ele não disser, pela titulação.

    "Licenciatura em Matemática" -> ("Matemática", licenciatura)
    "Engenharia Civil" + titulação "Engenheiro(a) Civil" -> ("Engenharia Civil", bacharelado)
    """
    normalizado = _normalizar(titulo)
    for prefixo, grau in _PREFIXOS_GRAU:
        if normalizado.startswith(prefixo):
            return titulo[len(prefixo) :].strip(), grau
    grau = grau_da_titulacao(titulacao)
    if grau is None and normalizado.startswith(("engenharia", "arquitetura")):
        grau = Grau.BACHARELADO  # engenharia e arquitetura só existem como bacharelado
    return titulo.strip(), grau


def grau_da_titulacao(titulacao: str | None) -> Grau | None:
    """'Bacharel em ...'/'Engenheiro ...'/'Arquiteto ...' -> bacharelado,
    'Licenciado ...' -> licenciatura, 'Tecnólogo ...' -> tecnólogo."""
    texto = _normalizar(titulacao)
    if "licenciad" in texto or "licenciatura" in texto:
        return Grau.LICENCIATURA
    # Engenheiro antes de tecnólogo: "Engenheiro de Bioprocessos e Biotecnologia".
    if any(termo in texto for termo in ("bachar", "engenheir", "arquitet")):
        return Grau.BACHARELADO
    if re.search(r"\btecnolog[oa]s?\b", texto):
        return Grau.TECNOLOGICO
    return None


def juntar_sobre(detalhes: DetalhesCurso) -> str | None:
    """Apresentação + "Perfil do egresso" (como na UEM, o perfil fica no sobre)."""
    partes = [detalhes.sobre]
    if detalhes.perfil:
        partes.append(f"Perfil do egresso\n{detalhes.perfil}")
    return "\n\n".join(p for p in partes if p) or None


def _so_a_duracao(texto: str | None) -> str | None:
    """Só o número e a unidade, para converter em semestres; o texto inteiro fica em
    duracao_texto. '4 anos (8 semestres)' -> '4 anos';
    'mínima do curso: 10 semestres' -> '10 semestres'; '8 períodos' -> '8 semestres'."""
    if not texto:
        return None
    encontrado = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(anos?|semestres?|per[ií]odos?)", texto, re.IGNORECASE
    )
    if not encontrado:
        return texto
    unidade = encontrado.group(2).lower()
    return f"{encontrado.group(1)} {'anos' if unidade.startswith('ano') else 'semestres'}"


def _primeira_maiuscula(texto: str | None) -> str | None:
    texto = (texto or "").strip()
    return texto[0].upper() + texto[1:] if texto else None


def _normalizar(texto: str | None) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())
