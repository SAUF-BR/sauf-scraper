"""Testes do parser e do spider da UFSC, usando o HTML real salvo em tests/fixtures/ufsc/
(depoimentos com nomes trocados por fictícios).

uv run pytest tests/test_parser_ufsc.py -v
"""

from pathlib import Path

import pytest

from sauf_scraper.censo import casamento
from sauf_scraper.core.models import Grau, Modalidade, Opcao
from sauf_scraper.parsers.ufsc import CursoListado, DetalhesCurso, extrair_detalhes, extrair_lista
from sauf_scraper.spiders.ufsc import URL_LISTA, UfscSpider, montar_curso, nome_sem_grau

FIXTURES = Path(__file__).parent / "fixtures" / "ufsc"


def ler(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


# --- Lista de cursos ---------------------------------------------------------------


def test_lista_traz_nome_campus_e_link():
    cursos = extrair_lista(ler("listagem.html"))

    assert len(cursos) == 92
    assert cursos[0] == CursoListado(
        nome="Administração",
        campus="Florianópolis",
        url="https://guiadecursos.ufsc.br/administracao/",
    )
    medicinas = [c.campus for c in cursos if c.nome == "Medicina"]
    assert sorted(medicinas) == ["Araranguá", "Curitibanos", "Florianópolis"]


# --- Página do curso ---------------------------------------------------------------


def test_sobre_vai_ate_o_depoimento_e_sem_subtitulos():
    detalhes = extrair_detalhes(ler("administracao.html"))

    assert detalhes.titulo == "Administração"
    assert detalhes.sobre.startswith("O curso de Administração da UFSC prepara")
    assert "Ação Júnior (com mais de 30 anos de atuação)" in detalhes.sobre
    assert "Formação Prática" not in detalhes.sobre
    assert "Visite o site" not in detalhes.sobre
    assert "\n\n" in detalhes.sobre


@pytest.mark.parametrize("arquivo", ["administracao.html", "quimica.html"])
def test_depoimento_com_nome_de_estudante_fica_de_fora(arquivo):
    sobre = extrair_detalhes(ler(arquivo)).sobre

    assert "Fulano de Tal" not in sobre
    assert "Beltrana de Tal" not in sobre


def test_titulo_com_os_graus():
    detalhes = extrair_detalhes(ler("quimica.html"))

    assert detalhes.titulo == "Química (Licenciatura, Bacharelado e Tecnológica)"
    assert "Química Tecnológica" in detalhes.sobre


def test_pagina_sem_artigo():
    assert extrair_detalhes("<html><body><p>nada</p></body></html>") == DetalhesCurso()


# --- Montagem do Curso -------------------------------------------------------------


def test_montar_curso_sem_turno_duracao_nem_mercado():
    item = CursoListado(
        "Administração", "Florianópolis", "https://guiadecursos.ufsc.br/administracao/"
    )

    curso = montar_curso(item, extrair_detalhes(ler("administracao.html")))

    assert curso.chave == "ufsc:administracao:florianopolis"
    assert curso.nome == "Administração"
    assert curso.opcoes == []  # o grau vem do Censo, pelo casamento
    assert curso.modalidade == Modalidade.PRESENCIAL
    assert (curso.cidade, curso.uf) == ("Florianópolis", "SC")
    assert curso.turno is None
    assert curso.duracao_texto is None
    assert curso.duracao_semestres is None
    assert curso.mercado_trabalho is None


def test_graus_pelo_titulo_da_pagina():
    item = CursoListado("Química", "Florianópolis", "https://guiadecursos.ufsc.br/quimica/")

    curso = montar_curso(item, extrair_detalhes(ler("quimica.html")))

    assert curso.opcoes == [Opcao(grau=Grau.BACHARELADO), Opcao(grau=Grau.LICENCIATURA)]


def test_grau_no_nome_sai_do_nome_mas_fica_na_chave():
    item = CursoListado("Matemática – Licenciatura", "Blumenau", "https://guiadecursos.ufsc.br/x/")

    curso = montar_curso(item, DetalhesCurso())

    assert curso.nome == "Matemática"
    assert curso.chave == "ufsc:matematica-licenciatura:blumenau"
    assert curso.opcoes == [Opcao(grau=Grau.LICENCIATURA)]


def test_engenharia_sem_grau_escrito_e_bacharelado():
    item = CursoListado("Engenharia Naval", "Joinville", "https://guiadecursos.ufsc.br/x/")

    assert montar_curso(item, DetalhesCurso()).opcoes == [Opcao(grau=Grau.BACHARELADO)]


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("Química – Bacharelado", "Química"),
        ("Letras - Libras", "Letras - Libras"),
        ("Licenciatura Indígena", "Licenciatura Indígena"),
        ("Química (Licenciatura, Bacharelado e Tecnológica)", "Química"),
    ],
)
def test_nome_sem_grau(nome, esperado):
    assert nome_sem_grau(nome) == esperado


# --- Spider -----------------------------------------------------------------------


class HttpDeFixtures:
    """Simula o HttpEducado: a lista vem da fixture e toda página de curso devolve a de
    Administração, com redirect para a URL com "/curso" no fim."""

    def get(self, url):
        if url == URL_LISTA:
            return type("Resposta", (), {"text": ler("listagem.html"), "url": url})
        return type("Resposta", (), {"text": ler("administracao.html"), "url": url + "curso"})


def test_spider_usa_a_url_final_e_os_codigos_confirmados(tmp_path, monkeypatch):
    monkeypatch.setattr(casamento, "PASTA_TABELAS", tmp_path)
    (tmp_path / "ufsc_codigos.csv").write_text(
        "chave;nome_site;cidade;turno_site;grau_site;status;codigo_emec;nome_censo;grau_censo;"
        "vagas_diurno;vagas_noturno;sugestao;confirmado\n"
        "ufsc:administracao:florianopolis;;;;;direto;1234;;bacharelado;40;80;;sim\n",
        encoding="utf-8",
    )

    lote = UfscSpider(HttpDeFixtures(), "t").coletar()
    administracao = lote.cursos[0]

    assert lote.codigo_emec_instituicao == 585
    assert len(lote.cursos) == 92
    assert str(administracao.url_origem) == "https://guiadecursos.ufsc.br/administracao/curso"
    assert administracao.codigos_emec == [1234]
    assert administracao.opcoes == [Opcao(grau=Grau.BACHARELADO)]
