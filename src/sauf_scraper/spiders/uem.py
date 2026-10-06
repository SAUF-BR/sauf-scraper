"""Spider da UEM - Universidade Estadual de Maringá (código e-MEC 57)."""

import unicodedata
from collections import Counter

from sauf_scraper.core.models import Curso, Fonte, Grau, LoteIngestao, montar_chave_curso
from sauf_scraper.parsers.uem import CursoListado, DetalhesCurso, extrair_detalhes, extrair_lista
from sauf_scraper.spiders.base import Spider

URL_LISTA = "https://www.pen.uem.br/site/public/cursos"


class UemSpider(Spider):
    chave = "uem"
    codigo_emec = 57

    def coletar(self) -> LoteIngestao:
        lista = extrair_lista(self.http.get(URL_LISTA).text)

        cursos = []
        for item in lista:
            # HttpEducado já espera o delay entre uma página e outra.
            detalhes = extrair_detalhes(self.http.get(item.url).text)
            cursos.append(montar_curso(item, detalhes))

        contagem = Counter(c.chave for c in cursos)
        repetidas = sorted(chave for chave, n in contagem.items() if n > 1)
        if repetidas:
            # Duas páginas com a mesma chave virariam um curso só no backend.
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
        grau=grau_da_habilitacao(detalhes.habilitacao),
        duracao=detalhes.prazo_minimo,
        # codigo_emec fica None até existir a tabela de casamento com o Censo.
    )


def cidade_do_campus(campus: str) -> str:
    """'Campus Sede - Maringá/PR' -> 'Maringá'."""
    return campus.rsplit(" - ", 1)[-1].split("/")[0].strip()


def grau_da_habilitacao(habilitacao: str | None) -> Grau | None:
    """Converte o texto da página ('Bacharelado', 'Licenciatura'...) no enum Grau."""
    if not habilitacao:
        return None
    texto = unicodedata.normalize("NFKD", habilitacao).encode("ascii", "ignore").decode().lower()
    bacharel = "bachar" in texto
    licenciatura = "licenc" in texto
    if bacharel and licenciatura:
        return Grau.BACHARELADO_E_LICENCIATURA
    if bacharel:
        return Grau.BACHARELADO
    if licenciatura:
        return Grau.LICENCIATURA
    if "tecnolog" in texto:
        return Grau.TECNOLOGICO
    return None
