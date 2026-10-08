"""Spider da UEM - Universidade Estadual de Maringá (código e-MEC 57)."""

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
from sauf_scraper.parsers.uem import (
    CursoListado,
    DetalhesCurso,
    extrair_detalhes,
    extrair_lista,
    turnos_por_grau,
)
from sauf_scraper.spiders.base import Spider

URL_LISTA = "https://www.pen.uem.br/site/public/cursos"


class UemSpider(Spider):
    chave = "uem"
    codigo_emec = 57

    def coletar(self) -> LoteIngestao:
        lista = extrair_lista(self.http.get(URL_LISTA).text)

        codigos = codigos_confirmados(self.chave)
        cursos = []
        for item in lista:
            # O HttpEducado já espera o delay entre uma página e outra.
            detalhes = extrair_detalhes(self.http.get(item.url).text)
            curso = montar_curso(item, detalhes)
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
    cidade = cidade_do_campus(item.campus)
    return Curso(
        chave=montar_chave_curso("uem", item.nome, cidade, detalhes.turno or ""),
        url_origem=item.url,
        nome=item.nome,
        opcoes=opcoes_da_pagina(detalhes),
        modalidade=Modalidade.PRESENCIAL,
        turno=detalhes.turno,
        sobre=detalhes.sobre,
        duracao_texto=detalhes.prazo_minimo,
        duracao_semestres=semestres_de_texto(detalhes.prazo_minimo),
        cidade=cidade,
        uf=uf_do_campus(item.campus),
        # Os codigos_emec vêm da tabela de casamento (spiders/dados/uem_codigos.csv) em coletar().
    )


def opcoes_da_pagina(detalhes: DetalhesCurso) -> list[Opcao]:
    """Graus da página, cada um com o turno que a página dá para ele.

    Quando a página não separa o turno por grau, todos os graus ficam com o turno da página.
    """
    graus = graus_da_habilitacao(detalhes.habilitacao)
    turnos = turnos_por_grau(detalhes.habilitacao, detalhes.turno)
    return [Opcao(grau=grau, turno=turnos.get(grau.value, detalhes.turno)) for grau in graus]


def cidade_do_campus(campus: str) -> str:
    """'Campus Sede - Maringá/PR' -> 'Maringá'."""
    return campus.rsplit(" - ", 1)[-1].split("/")[0].strip()


def uf_do_campus(campus: str) -> str | None:
    """Exemplo: 'Campus Sede - Maringá/PR' -> 'PR'."""
    partes = campus.rsplit("/", 1)
    uf = partes[-1].strip().upper() if len(partes) == 2 else ""
    return uf if len(uf) == 2 and uf.isalpha() else None


def graus_da_habilitacao(habilitacao: str | None) -> list[Grau]:
    """'Licenciatura ... ou Bacharelado ...' -> [licenciatura, bacharelado], na ordem do texto."""
    if not habilitacao:
        return []
    texto = unicodedata.normalize("NFKD", habilitacao).encode("ascii", "ignore").decode().lower()
    encontrados = [
        (posicao, grau)
        for termo, grau in (
            ("bachar", Grau.BACHARELADO),
            ("licenc", Grau.LICENCIATURA),
            ("tecnolog", Grau.TECNOLOGICO),
        )
        if (posicao := texto.find(termo)) >= 0
    ]
    return [grau for _, grau in sorted(encontrados)]
