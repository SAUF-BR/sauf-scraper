"""Spider da UEL - Universidade Estadual de Londrina (código e-MEC 9)."""

import unicodedata
from collections import Counter

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
from sauf_scraper.parsers.uel import CursoListado, DetalhesCurso, extrair_detalhes, extrair_lista
from sauf_scraper.spiders.base import Spider

URL_LISTA = "https://sites.uel.br/prograd/cursos-de-graduacao-da-uel/"
CIDADE = "Londrina"  # a UEL tem um campus só
UF = "PR"

_MODALIDADES = {
    "presencial": Modalidade.PRESENCIAL,
    "semipresencial": Modalidade.SEMIPRESENCIAL,
    "ead": Modalidade.EAD,
    "a distancia": Modalidade.EAD,
}


class UelSpider(Spider):
    chave = "uel"
    codigo_emec = 9

    def coletar(self) -> LoteIngestao:
        lista = extrair_lista(self.http.get(URL_LISTA).text)

        codigos = codigos_confirmados(self.chave)
        cursos = []
        for item in lista:
            # O HttpEducado já espera o delay entre uma página e outra.
            resposta = self.http.get(item.url)
            # A lista usa "http://graduacao.uel.br/<curso>"; o site redireciona para https e
            # barra final. A URL final é a que vai para o estudante.
            item = CursoListado(nome=item.nome, url=getattr(resposta, "url", None) or item.url)
            curso = montar_curso(item, extrair_detalhes(resposta.text))
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


def montar_curso(item: CursoListado, detalhes: DetalhesCurso) -> Curso:
    """Junta o que veio da lista e da página do curso em um Curso do nosso modelo."""
    turno = turno_da_pagina(detalhes)
    duracao = duracao_da_pagina(detalhes)
    return Curso(
        chave=montar_chave_curso("uel", item.nome, CIDADE, turno or ""),
        url_origem=item.url,
        nome=item.nome,
        opcoes=opcoes_da_pagina(detalhes),
        modalidade=modalidade_da_pagina(detalhes),
        turno=turno,
        sobre=detalhes.sobre,
        mercado_trabalho=None,  # o site da UEL não tem essa seção
        duracao_texto=duracao,
        duracao_semestres=semestres_de_texto(duracao),
        cidade=CIDADE,
        uf=UF,
        # Os codigos_emec vêm da tabela de casamento (spiders/dados/uel_codigos.csv) em coletar().
    )


def opcoes_da_pagina(detalhes: DetalhesCurso) -> list[Opcao]:
    """Uma Opcao por coluna do bloco (grau + turno), sem repetir o mesmo par.

    "Bacharelado e Licenciatura" vira duas opções no mesmo turno, como nas outras IES
    (sauf-api/docs/DECISOES.md, seção 6, item 5).
    """
    opcoes: list[Opcao] = []
    for coluna in detalhes.opcoes:
        for grau in graus_do_texto(coluna.grau):
            opcao = Opcao(grau=grau, turno=_capitalizar(coluna.turno))
            if opcao not in opcoes:
                opcoes.append(opcao)
    return opcoes


def turno_da_pagina(detalhes: DetalhesCurso) -> str | None:
    """Turnos das colunas, sem repetir, ex.: "Matutino ou Noturno" (mesmo formato da UEM)."""
    turnos = _distintos(_capitalizar(c.turno) for c in detalhes.opcoes)
    return " ou ".join(turnos) or None


def duracao_da_pagina(detalhes: DetalhesCurso) -> str | None:
    """'4.5 ANOS' -> '4.5 anos'. Se as colunas tiverem durações diferentes, o texto lista
    cada uma ("Bacharelado Matutino: 4 anos; ...") e os semestres ficam sem valor."""
    duracoes = _distintos((c.duracao or "").lower() for c in detalhes.opcoes)
    if len(duracoes) <= 1:
        return duracoes[0] if duracoes else None
    return "; ".join(
        f"{_capitalizar(c.grau)} {_capitalizar(c.turno)}: {c.duracao.lower()}"
        for c in detalhes.opcoes
        if c.duracao
    )


def modalidade_da_pagina(detalhes: DetalhesCurso) -> Modalidade | None:
    modalidades = _distintos(_MODALIDADES.get(_normalizar(c.modalidade)) for c in detalhes.opcoes)
    return modalidades[0] if len(modalidades) == 1 else None


def graus_do_texto(texto: str | None) -> list[Grau]:
    """'BACHARELADO' -> [bacharelado]; 'BACHARELADO E LICENCIATURA' -> [bacharelado,
    licenciatura]; 'TECNOLÓGICO' -> [tecnólogo]. Texto desconhecido -> []."""
    normalizado = _normalizar(texto)
    return [
        grau
        for termo, grau in (
            ("bachar", Grau.BACHARELADO),
            ("licenc", Grau.LICENCIATURA),
            ("tecnolog", Grau.TECNOLOGICO),
        )
        if termo in normalizado
    ]


def _capitalizar(texto: str | None) -> str | None:
    return texto.strip().capitalize() if texto and texto.strip() else None


def _distintos(valores) -> list:
    resultado = []
    for valor in valores:
        if valor and valor not in resultado:
            resultado.append(valor)
    return resultado


def _normalizar(texto: str | None) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())
