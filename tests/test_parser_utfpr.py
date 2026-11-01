"""Testes do parser e do spider da UTFPR, usando o JSON real salvo em tests/fixtures/utfpr/.

uv run pytest tests/test_parser_utfpr.py -v
"""

import json
from pathlib import Path

import pytest
import requests

from sauf_scraper.censo import casamento
from sauf_scraper.core.models import Grau, Modalidade, Opcao
from sauf_scraper.parsers.utfpr import (
    CursoListado,
    DetalhesCurso,
    _guardar_dado,
    campi_da_lista,
    elementos_da_pagina,
    extrair_detalhes,
    extrair_lista,
    separar_rotulos,
)
from sauf_scraper.spiders.utfpr import (
    URL_BUSCA,
    UtfprSpider,
    _so_a_duracao,
    grau_da_titulacao,
    juntar_sobre,
    montar_curso,
    nome_e_grau,
    para_api,
)

FIXTURES = Path(__file__).parent / "fixtures" / "utfpr"
BASE = "https://www.utfpr.edu.br/cursos/coordenacoes/graduacao"


def ler(nome: str) -> dict:
    return json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))


# --- Lista de cursos ---------------------------------------------------------------


def test_lista_fica_so_com_as_pastas_de_curso():
    cursos = extrair_lista(ler("busca"))

    assert len(cursos) == 6
    assert (
        CursoListado(
            nome="Bacharelado em Engenharia de Software",
            campus="cornelio-procopio",
            url=f"{BASE}/cornelio-procopio/cp-bacharelado-em-engenharia-de-software",
        )
        in cursos
    )


def test_campi_vem_das_pastas_de_primeiro_nivel():
    assert campi_da_lista(ler("busca")) == {
        "pato-branco": "Pato Branco",
        "cornelio-procopio": "Cornélio Procópio",
        "curitiba": "Curitiba",
    }


# --- Página "Apresentação" ---------------------------------------------------------


def test_pagina_completa_separa_sobre_perfil_atuacao_e_tabela():
    detalhes = extrair_detalhes(ler("completa_eng_software_cornelio"))

    assert detalhes.sobre.startswith("O Curso de Bacharelado em Engenharia de Software")
    assert detalhes.perfil.startswith("O egresso do curso superior de Bacharelado")
    assert detalhes.mercado_trabalho.startswith("Em 2022, a coordenação do curso conduziu")
    assert (detalhes.turno, detalhes.duracao) == ("Noturno", "4 anos")
    assert detalhes.titulacao == "Bacharel em Engenharia de Software"


def test_secoes_fora_do_mapa_ficam_de_fora():
    detalhes = extrair_detalhes(ler("completa_eng_software_cornelio"))
    texto = " ".join(t for t in (detalhes.sobre, detalhes.perfil, detalhes.mercado_trabalho) if t)

    assert "Competência Comum" not in texto  # seção "Formação"
    assert "Portaria MEC" not in texto  # seção "Autorização e Reconhecimento"
    assert "Carga Horária" not in texto  # tabela "Dados Sobre o Curso"


def test_paragrafo_em_negrito_e_titulo():
    titulos = [e.texto for e in elementos_da_pagina(ler("completa_eng_software_cornelio"))]

    assert "Perfil do Egresso" in titulos


def test_texto_sem_titulo_sobre_vai_para_o_sobre():
    detalhes = extrair_detalhes(ler("tecnologia_ads_pato_branco"))

    assert detalhes.sobre.startswith("O curso de Tecnologia em Análise e Desenvolvimento")
    assert detalhes.turno == "Noturno"
    assert detalhes.duracao == "3 anos"


def test_tabela_com_tudo_numa_celula():
    detalhes = extrair_detalhes(ler("tabela_uma_celula_eng_quimica_londrina"))

    assert (detalhes.turno, detalhes.duracao) == ("Integral", "5 anos")
    assert detalhes.mercado_trabalho.startswith("O profissional formado em Engenharia Química")


def test_pagina_em_html_puro():
    detalhes = extrair_detalhes(ler("html_eng_civil_pato_branco"))

    assert detalhes.sobre.startswith("O curso de Engenharia Civil tem como missão")
    assert (detalhes.turno, detalhes.duracao) == ("Manhã e Tarde", "5 anos")
    assert detalhes.titulacao == "Engenheiro(a) Civil"
    assert detalhes.mercado_trabalho is not None


def test_mais_de_um_turno_fica_como_o_site_escreve():
    detalhes = extrair_detalhes(ler("dois_turnos_eng_eletrica_curitiba"))

    assert detalhes.turno == "Manhã e tarde / tarde e noite"


def test_pagina_so_com_listagem_aponta_para_a_filha():
    detalhes = extrair_detalhes(ler("listing_biologia_santa_helena"))

    assert detalhes.sobre is None
    assert detalhes.filhos == [
        f"{BASE}/santa-helena/sh-licenciatura-em-ciencias-biologicas/apresentacao/apresentacao"
    ]


def test_pagina_vazia_devolve_none():
    detalhes = extrair_detalhes(
        {"blocks": {"a": {"@type": "title"}}, "blocks_layout": {"items": ["a"]}}
    )

    assert detalhes == DetalhesCurso()


def test_frase_que_comeca_com_turno_nao_e_dado():
    pagina = {
        "blocks": {
            "a": {
                "@type": "slate",
                "value": [
                    {
                        "type": "p",
                        "children": [
                            {"text": "Turno da manhã permite estagiar à tarde na cidade."}
                        ],
                    }
                ],
            }
        },
        "blocks_layout": {"items": ["a"]},
    }
    detalhes = extrair_detalhes(pagina)

    assert detalhes.turno is None
    assert detalhes.sobre.startswith("Turno da manhã")


# --- Montagem do Curso -------------------------------------------------------------


def test_montar_curso_de_engenharia_de_software():
    item = CursoListado(
        "Bacharelado em Engenharia de Software",
        "cornelio-procopio",
        f"{BASE}/cornelio-procopio/cp-bacharelado-em-engenharia-de-software",
    )
    curso = montar_curso(
        item, extrair_detalhes(ler("completa_eng_software_cornelio")), "Cornélio Procópio"
    )

    assert curso.chave == "utfpr:bacharelado-em-engenharia-de-software:cornelio-procopio:noturno"
    assert curso.nome == "Engenharia de Software"
    assert curso.opcoes == [Opcao(grau=Grau.BACHARELADO, turno="Noturno")]
    assert (curso.duracao_texto, curso.duracao_semestres) == ("4 anos", 8)
    assert curso.modalidade == Modalidade.PRESENCIAL
    assert (curso.cidade, curso.uf) == ("Cornélio Procópio", "PR")
    assert str(curso.url_origem).endswith("/cp-bacharelado-em-engenharia-de-software/apresentacao")
    assert "\n\nPerfil do egresso\nO egresso do curso superior" in curso.sobre
    assert curso.mercado_trabalho.startswith("Em 2022")


@pytest.mark.parametrize(
    ("titulo", "titulacao", "esperado"),
    [
        ("Licenciatura em Matemática", None, ("Matemática", Grau.LICENCIATURA)),
        ("Tecnologia em Radiologia", None, ("Radiologia", Grau.TECNOLOGICO)),
        ("Bacharelado em Química", None, ("Química", Grau.BACHARELADO)),
        ("Engenharia Civil", "Engenheiro(a) Civil", ("Engenharia Civil", Grau.BACHARELADO)),
        ("Sistemas de Informação", None, ("Sistemas de Informação", None)),
    ],
)
def test_nome_e_grau(titulo, titulacao, esperado):
    assert nome_e_grau(titulo, titulacao) == esperado


@pytest.mark.parametrize(
    ("titulacao", "grau"),
    [
        ("Bacharel em Ciência da Computação", Grau.BACHARELADO),
        ("Engenheiro Eletricista", Grau.BACHARELADO),
        ("Arquiteto(a) e Urbanista", Grau.BACHARELADO),
        ("Licenciado(a) em Matemática", Grau.LICENCIATURA),
        ("Tecnólogo em Radiologia", Grau.TECNOLOGICO),
        (None, None),
    ],
)
def test_grau_da_titulacao(titulacao, grau):
    assert grau_da_titulacao(titulacao) == grau


def test_curso_sem_grau_conhecido_fica_sem_opcoes():
    item = CursoListado(
        "Sistemas de Informação", "curitiba", f"{BASE}/curitiba/ct-sistemas-de-informacao"
    )

    assert montar_curso(item, DetalhesCurso(turno="noturno"), "Curitiba").opcoes == []


def test_sobre_sem_perfil_fica_so_com_a_apresentacao():
    assert juntar_sobre(DetalhesCurso(sobre="Texto.")) == "Texto."
    assert juntar_sobre(DetalhesCurso()) is None


def test_para_api():
    assert para_api(f"{BASE}/curitiba/x") == (
        "https://www.utfpr.edu.br/++api++/cursos/coordenacoes/graduacao/curitiba/x"
    )


# --- Spider inteiro (sem rede) -----------------------------------------------------


def test_curso_sem_pagina_publica_entra_com_o_que_a_busca_da():
    item = CursoListado(
        "Bacharelado em Química Ambiental",
        "curitiba",
        f"{BASE}/curitiba/ct-bacharelado-em-quimica-ambiental",
    )
    curso = montar_curso(item, None, "Curitiba")

    assert curso.nome == "Química Ambiental"
    assert curso.opcoes == [Opcao(grau=Grau.BACHARELADO, turno=None)]
    assert str(curso.url_origem) == f"{BASE}/curitiba/ct-bacharelado-em-quimica-ambiental"
    assert (curso.sobre, curso.turno, curso.duracao_semestres) == (None, None, None)


class HttpDeFixtures:
    """Responde a busca e as páginas com os JSONs salvos, como faria a API do Plone."""

    PAGINAS = {
        "cp-bacharelado-em-engenharia-de-software": "completa_eng_software_cornelio",
        "pb-tecnologia-em-analise-e-desenvolvimento-de-sistemas": "tecnologia_ads_pato_branco",
        "pb-licenciatura-em-matematica": "html_matematica_pato_branco",
        "ct-engenharia-eletrica": "dois_turnos_eng_eletrica_curitiba",
    }

    def __init__(self):
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        if "ct-licenciatura-em-quimica" in url:
            resposta = type("R", (), {"status_code": 401})()
            raise requests.HTTPError("401 Client Error: Unauthorized", response=resposta)
        if url == URL_BUSCA:
            dados = ler("busca")
        else:
            pasta = url.split("/graduacao/")[1].split("/")[1]
            dados = ler(self.PAGINAS.get(pasta, "listing_biologia_santa_helena"))
            if url.endswith("/apresentacao/apresentacao"):
                dados = ler("listing_filha_biologia_santa_helena")
        return type("Resposta", (), {"json": lambda self, d=dados: d})()


def test_spider_le_a_api_e_segue_a_pagina_filha(tmp_path, monkeypatch):
    monkeypatch.setattr(casamento, "PASTA_TABELAS", tmp_path)
    (tmp_path / "utfpr_codigos.csv").write_text(
        "chave;nome_site;cidade;turno_site;grau_site;status;codigo_emec;nome_censo;grau_censo;"
        "vagas_diurno;vagas_noturno;sugestao;confirmado\n"
        "utfpr:bacharelado-em-engenharia-de-software:cornelio-procopio:noturno;;;;;direto;"
        "1234;;bacharelado;0;40;;sim\n",
        encoding="utf-8",
    )
    http = HttpDeFixtures()

    lote = UtfprSpider(http, "t").coletar()
    por_nome = {c.nome: c for c in lote.cursos}

    assert lote.codigo_emec_instituicao == 588
    assert len(lote.cursos) == 6
    assert por_nome["Engenharia de Software"].codigos_emec == [1234]
    assert por_nome["Engenharia de Software"].cidade == "Cornélio Procópio"
    assert all("/++api++/" in u for u in http.urls)
    assert all("/++api++/" not in str(c.url_origem) for c in lote.cursos)
    # O bacharelado em Química de Curitiba (sem página na fixture) cai na página filha.
    assert any(u.endswith("/apresentacao/apresentacao") for u in http.urls)
    # A licenciatura em Química responde 401: entra sem os dados da página.
    quimica_lic = next(
        c for c in lote.cursos if c.chave.startswith("utfpr:licenciatura-em-quimica")
    )
    assert quimica_lic.sobre is None
    assert quimica_lic.opcoes == [Opcao(grau=Grau.LICENCIATURA, turno=None)]


# --- Fichas mal formatadas no site -------------------------------------------------


@pytest.mark.parametrize(
    ("linha", "turno", "duracao"),
    [
        ("Turno: Integral Duração: 4 anos Carga Horária: 3375 horas", "Integral", "4 anos"),
        ("Turno: NoturnoDuração: 4 anos Vagas por semestre: 22", "Noturno", "4 anos"),
        ("Turno Manhã e tarde", "Manhã e tarde", None),
    ],
)
def test_ficha_numa_linha_so_separa_os_dados(linha, turno, duracao):
    detalhes = DetalhesCurso()
    _guardar_dado(detalhes, linha)

    assert (detalhes.turno, detalhes.duracao) == (turno, duracao)


def test_separar_rotulos():
    assert separar_rotulos("Integral Duração: 5 anos Vagas por semestre: 44") == [
        "Integral",
        "Duração: 5 anos",
        "Vagas por semestre: 44",
    ]


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("4 anos", "4 anos"),
        ("4 anos (8 semestres)", "4 anos"),
        ("mínima do curso: 10 semestres", "10 semestres"),
        ("8 períodos", "8 semestres"),
        ("4,5 anos", "4,5 anos"),
        (None, None),
    ],
)
def test_so_a_duracao(texto, esperado):
    assert _so_a_duracao(texto) == esperado


def test_engenharia_sem_titulacao_e_bacharelado():
    assert nome_e_grau("Engenharia Mecatrônica", None) == (
        "Engenharia Mecatrônica",
        Grau.BACHARELADO,
    )


def test_biotecnologia_na_titulacao_nao_vira_tecnologo():
    titulacao = "Engenheiro de Bioprocessos e Biotecnologia"

    assert grau_da_titulacao(titulacao) == Grau.BACHARELADO
