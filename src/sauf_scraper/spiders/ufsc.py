"""Spider da UFSC - Universidade Federal de Santa Catarina (código e-MEC 585)."""

import re
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
)
from sauf_scraper.parsers.ufsc import CursoListado, DetalhesCurso, extrair_detalhes, extrair_lista
from sauf_scraper.spiders.base import Spider

URL_LISTA = "https://guiadecursos.ufsc.br/listagem/"
UF = "SC"

# Grau escrito no nome ou no título: "Matemática – Bacharelado",
# "Química (Licenciatura, Bacharelado e Tecnológica)", "Licenciatura Indígena".
_GRAUS = (("bacharelado", Grau.BACHARELADO), ("licenciatura", Grau.LICENCIATURA))
# " – Bacharelado" / " - Licenciatura" no fim do nome, ou "(Licenciatura, ...)".
_SUFIXO_GRAU = re.compile(
    r"\s*(?:[–-]\s*(?:bacharelado|licenciatura)|\((?:[^)]*(?:bacharelado|licenciatura)[^)]*)\))\s*$",
    re.IGNORECASE,
)


class UfscSpider(Spider):
    chave = "ufsc"
    codigo_emec = 585

    def coletar(self) -> LoteIngestao:
        lista = extrair_lista(self.http.get(URL_LISTA).text)

        codigos = codigos_confirmados(self.chave)
        cursos = []
        for item in lista:
            # O HttpEducado já espera o delay entre uma página e outra.
            resposta = self.http.get(item.url)
            # Algumas páginas redirecionam; a URL final é a que vai para o estudante.
            item = CursoListado(
                nome=item.nome, campus=item.campus, url=getattr(resposta, "url", None) or item.url
            )
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
    """Junta a linha da lista e a página do curso num Curso do nosso modelo.

    O guia não informa turno, duração nem mercado de trabalho: ficam null. Grau só quando
    o nome ou o título dizem; sem isso, o grau vem do Censo pelo casamento (aplicar_codigos).
    """
    graus = graus_do_texto(f"{item.nome} {detalhes.titulo or ''}")
    if not graus and _normalizar(item.nome).startswith(("engenharia", "arquitetura")):
        graus = [Grau.BACHARELADO]  # engenharia e arquitetura só existem como bacharelado
    return Curso(
        # A chave usa o nome da lista com o grau ("Química – Bacharelado"), para o
        # bacharelado e a licenciatura do mesmo campus não terem a mesma chave.
        chave=montar_chave_curso("ufsc", item.nome, item.campus),
        url_origem=item.url,
        nome=nome_sem_grau(item.nome),
        opcoes=[Opcao(grau=grau) for grau in graus],
        # Os cursos a distância ficam numa página separada, fora da lista.
        modalidade=Modalidade.PRESENCIAL,
        sobre=detalhes.sobre,
        cidade=item.campus,
        uf=UF,
        # Os codigos_emec vêm da tabela de casamento (spiders/dados/ufsc_codigos.csv).
    )


def graus_do_texto(texto: str) -> list[Grau]:
    normalizado = _normalizar(texto)
    return [grau for termo, grau in _GRAUS if termo in normalizado]


def nome_sem_grau(nome: str) -> str:
    """'Matemática – Licenciatura' -> 'Matemática'. 'Licenciatura Indígena' fica igual."""
    return _SUFIXO_GRAU.sub("", nome).strip() or nome


def _normalizar(texto: str | None) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())
