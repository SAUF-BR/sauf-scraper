"""Testes do parser e do spider da UEL, usando o HTML real salvo em tests/fixtures/uel/.

uv run pytest tests/test_parser_uel.py -v
"""

from pathlib import Path

import pytest

from sauf_scraper.censo import casamento
from sauf_scraper.core.models import Grau, Modalidade, Opcao
from sauf_scraper.parsers.uel import (
    CursoListado,
    DetalhesCurso,
    OpcaoUel,
    extrair_detalhes,
    extrair_lista,
)
from sauf_scraper.spiders.uel import (
    URL_LISTA,
    UelSpider,
    duracao_da_pagina,
    graus_do_texto,
    montar_curso,
    opcoes_da_pagina,
    turno_da_pagina,
)

FIXTURES = Path(__file__).parent / "fixtures" / "uel"


def ler(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


# --- Lista de cursos ---------------------------------------------------------------


def test_lista_traz_os_cursos_com_pagina_no_catalogo():
    cursos = extrair_lista(ler("lista.html"))

    assert len(cursos) == 46
    assert cursos[0] == CursoListado(
        nome="Administração", url="http://graduacao.uel.br/administracao"
    )
    assert all("graduacao.uel.br" in c.url for c in cursos)


def test_ead_e_cursos_novos_sem_pagina_ficam_de_fora():
    nomes = [c.nome for c in extrair_lista(ler("lista.html"))]

    assert "Computação – Licenciatura (EAD)" not in nomes
    assert "Tecnologia em Gestão Pública (EAD)" not in nomes
    assert "Estatística e Ciências de Dados" not in nomes  # (novo curso): link para PDF


# --- Página do curso ---------------------------------------------------------------


def test_cabecalho_do_curso():
    detalhes = extrair_detalhes(ler("curso_administracao.html"))

    assert detalhes.nome == "Administração"
    assert detalhes.centro == "Centro de Estudos Sociais Aplicados (CESA)"
    assert detalhes.sobre.startswith("Prepare-se para liderar com inovação e estratégia")


def test_um_bloco_por_opcao_sem_repetir_a_versao_de_celular():
    detalhes = extrair_detalhes(ler("curso_administracao.html"))

    assert detalhes.opcoes == [
        OpcaoUel("BACHARELADO", "PRESENCIAL", "MATUTINO", "40 Vagas", "4.5 ANOS"),
        OpcaoUel("BACHARELADO", "PRESENCIAL", "NOTURNO", "80 Vagas", "4.5 ANOS"),
    ]


def test_bacharelado_e_licenciatura_na_mesma_pagina():
    detalhes = extrair_detalhes(ler("curso_matematica.html"))

    assert [(o.grau, o.turno) for o in detalhes.opcoes] == [
        ("BACHARELADO", "MATUTINO"),
        ("LICENCIATURA", "NOTURNO"),
    ]


def test_pagina_sem_o_bloco_devolve_so_o_cabecalho():
    detalhes = extrair_detalhes("<html><body><h1 class='site-title'>Teste</h1></body></html>")

    assert detalhes.nome == "Teste"
    assert detalhes.opcoes == []


@pytest.mark.parametrize(
    "arquivo", ["curso_administracao.html", "curso_matematica.html", "curso_letras_ingles.html"]
)
def test_nao_coleta_e_mail_nem_nome_de_pessoa(arquivo):
    detalhes = extrair_detalhes(ler(arquivo))
    texto = " ".join(str(v) for v in vars(detalhes).values())

    assert "@" not in texto


# --- Montagem do Curso -------------------------------------------------------------


def test_montar_curso_de_administracao():
    item = CursoListado(nome="Administração", url="https://graduacao.uel.br/administracao/")
    curso = montar_curso(item, extrair_detalhes(ler("curso_administracao.html")))

    assert curso.chave == "uel:administracao:londrina:matutino-ou-noturno"
    assert str(curso.url_origem) == "https://graduacao.uel.br/administracao/"
    assert curso.opcoes == [
        Opcao(grau=Grau.BACHARELADO, turno="Matutino"),
        Opcao(grau=Grau.BACHARELADO, turno="Noturno"),
    ]
    assert curso.turno == "Matutino ou Noturno"
    assert (curso.duracao_texto, curso.duracao_semestres) == ("4.5 anos", 9)
    assert curso.modalidade == Modalidade.PRESENCIAL
    assert (curso.cidade, curso.uf) == ("Londrina", "PR")
    assert curso.mercado_trabalho is None
    assert curso.sobre.startswith("Prepare-se")


def test_montar_curso_de_matematica_vira_duas_opcoes():
    item = CursoListado(nome="Matemática", url="https://graduacao.uel.br/matematica/")
    curso = montar_curso(item, extrair_detalhes(ler("curso_matematica.html")))

    assert curso.opcoes == [
        Opcao(grau=Grau.BACHARELADO, turno="Matutino"),
        Opcao(grau=Grau.LICENCIATURA, turno="Noturno"),
    ]
    assert curso.duracao_semestres == 8


def test_duracoes_diferentes_por_opcao_ficam_no_texto_sem_semestres():
    detalhes = DetalhesCurso(
        opcoes=[
            OpcaoUel("BACHARELADO", "PRESENCIAL", "MATUTINO", "30 Vagas", "4 ANOS"),
            OpcaoUel("LICENCIATURA", "PRESENCIAL", "NOTURNO", "40 Vagas", "5 ANOS"),
        ]
    )

    esperado = "Bacharelado Matutino: 4 anos; Licenciatura Noturno: 5 anos"
    assert duracao_da_pagina(detalhes) == esperado
    assert turno_da_pagina(detalhes) == "Matutino ou Noturno"


def test_opcao_repetida_aparece_uma_vez():
    detalhes = DetalhesCurso(
        opcoes=[
            OpcaoUel("LICENCIATURA", "PRESENCIAL", "NOTURNO", "20 Vagas", "4 ANOS"),
            OpcaoUel("LICENCIATURA", "PRESENCIAL", "NOTURNO", "20 Vagas", "4 ANOS"),
        ]
    )

    assert opcoes_da_pagina(detalhes) == [Opcao(grau=Grau.LICENCIATURA, turno="Noturno")]


@pytest.mark.parametrize(
    ("texto", "graus"),
    [
        ("BACHARELADO", [Grau.BACHARELADO]),
        ("LICENCIATURA", [Grau.LICENCIATURA]),
        ("TECNOLÓGICO", [Grau.TECNOLOGICO]),
        ("BACHARELADO E LICENCIATURA", [Grau.BACHARELADO, Grau.LICENCIATURA]),
        (None, []),
        ("SEQUENCIAL", []),
    ],
)
def test_graus_do_texto(texto, graus):
    assert graus_do_texto(texto) == graus


def test_bacharelado_e_licenciatura_vira_duas_opcoes_no_mesmo_turno():
    detalhes = DetalhesCurso(
        opcoes=[OpcaoUel("BACHARELADO E LICENCIATURA", "PRESENCIAL", "MATUTINO", "40", "4 ANOS")]
    )

    assert opcoes_da_pagina(detalhes) == [
        Opcao(grau=Grau.BACHARELADO, turno="Matutino"),
        Opcao(grau=Grau.LICENCIATURA, turno="Matutino"),
    ]


# --- Spider inteiro (sem rede) -----------------------------------------------------


class HttpDeFixtures:
    """Responde a lista e, para qualquer curso, a página de Administração, simulando o
    redirect de http://.../administracao para https://.../administracao/."""

    def get(self, url):
        if url == URL_LISTA:
            return type("Resposta", (), {"text": ler("lista.html"), "url": url})
        final = url.replace("http://", "https://").rstrip("/") + "/"
        return type("Resposta", (), {"text": ler("curso_administracao.html"), "url": final})


def test_spider_usa_a_url_final_e_os_codigos_confirmados(tmp_path, monkeypatch):
    monkeypatch.setattr(casamento, "PASTA_TABELAS", tmp_path)
    (tmp_path / "uel_codigos.csv").write_text(
        "chave;nome_site;cidade;turno_site;grau_site;status;codigo_emec;nome_censo;grau_censo;"
        "vagas_diurno;vagas_noturno;sugestao;confirmado\n"
        "uel:administracao:londrina:matutino-ou-noturno;;;;;direto;1234;;bacharelado;40;80;;sim\n",
        encoding="utf-8",
    )

    lote = UelSpider(HttpDeFixtures(), "t").coletar()
    administracao = next(c for c in lote.cursos if c.nome == "Administração")

    assert lote.codigo_emec_instituicao == 9
    assert len(lote.cursos) == 46
    assert str(administracao.url_origem) == "https://graduacao.uel.br/administracao/"
    assert administracao.codigos_emec == [1234]
