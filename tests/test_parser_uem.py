"""Testes do parser e do spider da UEM, usando o HTML real salvo em tests/fixtures/uem/.

uv run pytest tests/test_parser_uem.py -v
"""

from pathlib import Path

import pytest

from sauf_scraper.core.models import Grau
from sauf_scraper.parsers.uem import CursoListado, extrair_detalhes, extrair_lista
from sauf_scraper.spiders.uem import cidade_do_campus, grau_da_habilitacao, montar_curso

FIXTURES = Path(__file__).parent / "fixtures" / "uem"


def ler(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


# --- Lista de cursos ---------------------------------------------------------------


def test_lista_traz_todos_os_cursos_presenciais():
    assert len(extrair_lista(ler("lista.html"))) == 67


def test_primeiro_curso_da_lista():
    primeiro = extrair_lista(ler("lista.html"))[0]
    assert primeiro.nome == "Administração"
    assert primeiro.campus == "Campus Sede - Maringá/PR"
    assert primeiro.url == (
        "https://www.pen.uem.br/site/public/curso/c6e9c1b9daea38a42b28d6d97f567ce6d551aeb0"
    )


def test_curso_de_outro_campus_sai_com_o_campus_certo():
    cursos = extrair_lista(ler("lista.html"))
    cianorte = [c for c in cursos if c.campus.startswith("Campus Regional de Cianorte")]
    assert [c.nome for c in cianorte] == ["Ciências Contábeis", "Design", "Moda", "Pedagogia"]


def test_link_do_ead_fica_de_fora():
    cursos = extrair_lista(ler("lista.html"))
    assert all("/curso/" in c.url for c in cursos)


# --- Página do curso ---------------------------------------------------------------


def test_detalhes_de_engenharia_de_software():
    detalhes = extrair_detalhes(ler("curso_engenharia_software.html"))
    assert detalhes.turno == "Noturno"
    assert detalhes.habilitacao == "Bacharelado"
    assert detalhes.prazo_minimo == "5 anos"
    assert detalhes.prazo_maximo == "9 anos"


def test_detalhes_com_rotulos_em_b_em_vez_de_strong():
    # Arquitetura e Urbanismo usa <b>Turno:</b> no lugar de <strong>Turno:</strong>.
    detalhes = extrair_detalhes(ler("curso_arquitetura_urbanismo.html"))
    assert detalhes.turno == "integral"
    assert detalhes.habilitacao == "Bacharelado"
    assert detalhes.prazo_minimo == "5 anos"
    assert detalhes.prazo_maximo == "9 anos"


@pytest.mark.parametrize(
    "arquivo", ["curso_engenharia_software.html", "curso_arquitetura_urbanismo.html"]
)
def test_dados_da_coordenacao_nao_sao_coletados(arquivo):
    # LGPD: nome e e-mail de professores não entram no SAUF.
    texto = str(extrair_detalhes(ler(arquivo)))
    assert "Fulano" not in texto
    assert "coordenador@" not in texto


def test_pagina_sem_os_campos_devolve_none():
    detalhes = extrair_detalhes("<html><body><p>Nada aqui</p></body></html>")
    assert detalhes.turno is None
    assert detalhes.habilitacao is None


# --- Montagem do Curso -------------------------------------------------------------


def test_montar_curso_de_engenharia_de_software():
    item = CursoListado(
        nome="Engenharia de Software",
        campus="Campus Sede - Maringá/PR",
        url="https://www.pen.uem.br/site/public/curso/a99a3305e6ffbd5db96ef5506978504214b31397",
    )
    curso = montar_curso(item, extrair_detalhes(ler("curso_engenharia_software.html")))

    assert curso.chave == "uem:engenharia-de-software:maringa:noturno"
    assert str(curso.url_origem) == item.url
    assert curso.grau == Grau.BACHARELADO
    assert curso.duracao == "5 anos"
    assert curso.codigo_emec is None


@pytest.mark.parametrize(
    ("campus", "cidade"),
    [
        ("Campus Sede - Maringá/PR", "Maringá"),
        ("Campus do Arenito - Cidade Gaúcha/PR", "Cidade Gaúcha"),
        ("Câmpus Regional do Vale do Ivaí - Ivaiporã/PR", "Ivaiporã"),
    ],
)
def test_cidade_do_campus(campus, cidade):
    assert cidade_do_campus(campus) == cidade


@pytest.mark.parametrize(
    ("habilitacao", "grau"),
    [
        ("Bacharelado", Grau.BACHARELADO),
        ("Licenciatura", Grau.LICENCIATURA),
        ("Bacharelado e Licenciatura", Grau.BACHARELADO_E_LICENCIATURA),
        ("Tecnologia", Grau.TECNOLOGICO),
        ("", None),
        (None, None),
    ],
)
def test_grau_da_habilitacao(habilitacao, grau):
    assert grau_da_habilitacao(habilitacao) == grau
