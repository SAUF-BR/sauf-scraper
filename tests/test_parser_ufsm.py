"""Testes do parser e do spider da UFSM, usando o HTML real salvo em tests/fixtures/ufsm/
(só o bloco "Apresentação", com os nomes de coordenação e secretaria trocados por fictícios).

uv run pytest tests/test_parser_ufsm.py -v
"""

from pathlib import Path

import pytest
import requests

from sauf_scraper.censo import casamento
from sauf_scraper.core.models import Grau, Modalidade, Opcao
from sauf_scraper.parsers.ufsm import (
    CursoListado,
    DetalhesCurso,
    Habilitacao,
    SobreCurso,
    extrair_detalhes,
    extrair_lista,
    extrair_sobre,
)
from sauf_scraper.spiders.ufsm import (
    URL_ROBOTS,
    UfsmSpider,
    duracao_do_curso,
    montar_curso,
    nome_sem_grau,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ufsm"
URL_ADM = "https://www.ufsm.br/cursos/graduacao/santa-maria/administracao/"


def ler(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


# --- Lista de cursos (robots.txt) -------------------------------------------------


def test_lista_vem_dos_sitemaps_dos_cursos_sem_ead_nem_tecnico():
    cursos = extrair_lista(ler("robots.txt"))

    assert [c.pasta for c in cursos] == [
        "administracao",
        "ciencias-biologicas",
        "danca-bacharelado",
    ]
    assert cursos[0] == CursoListado(campus="santa-maria", pasta="administracao", url=URL_ADM)


# --- Página principal: bloco "Apresentação" ----------------------------------------


def test_uma_habilitacao_por_turno():
    detalhes = extrair_detalhes(ler("administracao.html"))

    assert detalhes.titulo == "Administração"
    assert detalhes.habilitacoes == [
        Habilitacao("Administração", "Bacharelado", "Presencial", "Diurno", "Semestral", 8),
        Habilitacao("Administração", "Bacharelado", "Presencial", "Noturno", "Semestral", 10),
    ]


def test_bloco_repetido_aparece_uma_vez():
    detalhes = extrair_detalhes(ler("danca-bacharelado.html"))

    assert detalhes.titulo == "Dança – Bacharelado"
    assert len(detalhes.habilitacoes) == 1


def test_nucleo_comum_abi_fica_de_fora():
    detalhes = extrair_detalhes(ler("ciencias-biologicas.html"))

    assert [(h.grau, h.turno) for h in detalhes.habilitacoes] == [
        ("Bacharelado", "Diurno"),
        ("Licenciatura", "Integral"),
    ]


@pytest.mark.parametrize("arquivo", ["administracao.html", "ciencias-biologicas.html"])
def test_nao_coleta_nome_da_coordenacao(arquivo):
    detalhes = extrair_detalhes(ler(arquivo))

    assert "FULANO" not in repr(detalhes)


# --- Página "Sobre o curso" --------------------------------------------------------


def test_sobre_com_subtitulos_e_lista():
    sobre = extrair_sobre(ler("administracao-sobre-o-curso.html"))

    assert sobre.sobre.startswith("O curso de Bacharelado em Administração")
    assert "\n\nO perfil do formando\n\n- Conhecimento especializado" in sobre.sobre
    assert "- Raciocínio lógico;\n- Empatia" in sobre.sobre
    assert sobre.mercado_trabalho is None


def test_secao_areas_de_atuacao_vira_mercado():
    html = """<div class="entry-content">
        <p>O curso forma profissionais.</p>
        <h3>Áreas de atuação</h3><p>Indústria e pesquisa.</p><ul><li>Laboratórios</li></ul>
        <h3>Estrutura</h3><p>Laboratórios próprios.</p></div>"""

    sobre = extrair_sobre(html)

    assert sobre.mercado_trabalho == "Indústria e pesquisa.\n\n- Laboratórios"
    assert sobre.sobre == "O curso forma profissionais.\n\nEstrutura\n\nLaboratórios próprios."


def test_pagina_sem_conteudo():
    assert extrair_sobre("<html><body></body></html>") == SobreCurso()


# --- Montagem do Curso -------------------------------------------------------------


def test_montar_curso_de_administracao():
    item = CursoListado("santa-maria", "administracao", URL_ADM)
    sobre = SobreCurso(sobre="Texto.", mercado_trabalho=None)

    curso = montar_curso(item, extrair_detalhes(ler("administracao.html")), sobre)

    assert curso.chave == "ufsm:administracao:santa-maria"
    assert curso.nome == "Administração"
    assert curso.opcoes == [Opcao(grau=Grau.BACHARELADO, turno="Diurno ou Noturno")]
    assert curso.turno == "Diurno ou Noturno"
    assert curso.modalidade == Modalidade.PRESENCIAL
    assert (curso.cidade, curso.uf) == ("Santa Maria", "RS")
    # 8 semestres de dia, 10 à noite: o texto lista os dois e os semestres ficam vazios.
    assert (
        curso.duracao_texto == "Bacharelado Diurno: 8 semestres; Bacharelado Noturno: 10 semestres"
    )
    assert curso.duracao_semestres is None
    assert curso.sobre == "Texto."


def test_grau_no_titulo_sai_do_nome_mas_fica_na_chave():
    item = CursoListado("santa-maria", "danca-bacharelado", URL_ADM)

    curso = montar_curso(item, extrair_detalhes(ler("danca-bacharelado.html")), SobreCurso())

    assert curso.nome == "Dança"
    assert curso.chave == "ufsm:danca-bacharelado:santa-maria"
    assert curso.duracao_texto == "8 semestres"
    assert curso.duracao_semestres == 8


def test_regime_anual_vira_anos():
    habilitacao = Habilitacao("Medicina", "Bacharelado", "Presencial", "Integral", "Anual", 6)

    assert duracao_do_curso([habilitacao]) == "6 anos"


def test_pagina_sem_o_bloco():
    item = CursoListado("palmeira-das-missoes", "zootecnia", URL_ADM)

    curso = montar_curso(item, DetalhesCurso(), SobreCurso())

    assert curso.nome == "Zootecnia"
    assert curso.opcoes == []
    assert curso.cidade == "Palmeira das Missões"
    assert curso.modalidade is None


# --- Spider -----------------------------------------------------------------------


class HttpDeFixtures:
    """Simula o HttpEducado: robots.txt e páginas da fixture; "sobre-o-curso" só existe
    na Administração (as outras respondem 404, como no site)."""

    def get(self, url):
        if url == URL_ROBOTS:
            texto = ler("robots.txt")
        elif url.endswith("sobre-o-curso/"):
            if "administracao" not in url:
                resposta = requests.Response()
                resposta.status_code = 404
                raise requests.HTTPError(response=resposta)
            texto = ler("administracao-sobre-o-curso.html")
        else:
            pasta = url.rstrip("/").rsplit("/", 1)[-1]
            arquivo = FIXTURES / f"{pasta}.html"
            texto = arquivo.read_text(encoding="utf-8") if arquivo.exists() else "<html></html>"
        return type("Resposta", (), {"text": texto, "url": url})


def test_spider_junta_as_paginas_e_os_codigos_confirmados(tmp_path, monkeypatch):
    monkeypatch.setattr(casamento, "PASTA_TABELAS", tmp_path)
    (tmp_path / "ufsm_codigos.csv").write_text(
        "chave;nome_site;cidade;turno_site;grau_site;status;codigo_emec;nome_censo;grau_censo;"
        "vagas_diurno;vagas_noturno;sugestao;confirmado\n"
        "ufsm:administracao:santa-maria;;;;;direto;1234;;bacharelado;40;80;;sim\n",
        encoding="utf-8",
    )

    lote = UfsmSpider(HttpDeFixtures(), "t").coletar()
    cursos = {c.chave: c for c in lote.cursos}

    assert lote.codigo_emec_instituicao == 582
    assert len(lote.cursos) == 3
    assert cursos["ufsm:administracao:santa-maria"].codigos_emec == [1234]
    assert cursos["ufsm:administracao:santa-maria"].sobre.startswith("O curso de Bacharelado")
    assert cursos["ufsm:danca-bacharelado:santa-maria"].sobre is None


@pytest.mark.parametrize(
    ("titulo", "esperado"),
    [
        ("Dança – Bacharelado", "Dança"),
        ("Jornalismo Bacharelado", "Jornalismo"),
        ("Química Licenciatura", "Química"),
        ("Licenciatura em Teatro", "Teatro"),
        ("Tecnologia em Alimentos", "Alimentos"),
        ("Licenciatura Intercultural Indígena", "Licenciatura Intercultural Indígena"),
        ("Engenharia Civil", "Engenharia Civil"),
    ],
)
def test_nome_sem_grau(titulo, esperado):
    assert nome_sem_grau(titulo) == esperado


def test_titulo_com_cursos_no_plural():
    html = "<title>Matemática – Cursos de Graduação – Campus Santa Maria</title>"

    assert extrair_detalhes(html).titulo == "Matemática"
