from pathlib import Path

import pytest

from sauf_scraper.censo import casamento
from sauf_scraper.censo.casamento import (
    AMBIGUO,
    DIRETO,
    SEM_PAR,
    SUGESTAO_HABILITACAO,
    SUGESTAO_VARIOS,
    CodigoConfirmado,
    aplicar_codigos,
    gerar_tabela,
    gravar_tabela,
    ler_tabela,
)
from sauf_scraper.core.models import Curso, Grau, Opcao
from sauf_scraper.spiders.uem import URL_LISTA, UemSpider

COLUNAS = [
    "TP_DIMENSAO", "CO_IES", "NO_CURSO", "CO_CURSO", "NO_MUNICIPIO", "TP_GRAU_ACADEMICO",
    "TP_NIVEL_ACADEMICO", "QT_VG_TOTAL_DIURNO", "QT_VG_TOTAL_NOTURNO",
]  # fmt: skip
CENSO = [
    ["1", "57", "Engenharia Civil", "3402", "Maringá", "1", "1", "80", "0"],
    ["1", "57", "Engenharia Civil", "150159", "Umuarama", "1", "1", "40", "0"],
    ["1", "57", "Química", "3406", "Maringá", "1", "1", "100", "0"],
    ["1", "57", "Química", "99368", "Maringá", "2", "1", "0", "156"],
    ["1", "57", "Ciências Econômicas", "3392", "Maringá", "1", "1", "0", "112"],
    ["1", "57", "Ciências Econômicas", "1153285", "Maringá", "1", "1", "82", "0"],
    ["1", "57", "Música", "92099", "Maringá", "1", "1", "17", "0"],
    ["1", "57", "Música", "92107", "Maringá", "1", "1", "5", "0"],
    ["1", "9", "Engenharia Civil", "9001", "Maringá", "1", "1", "50", "0"],
]  # fmt: skip


@pytest.fixture
def pasta_censo(tmp_path):
    dados = tmp_path / "censo" / "dados"
    dados.mkdir(parents=True)
    texto = "\n".join(";".join(linha) for linha in [COLUNAS, *CENSO]) + "\n"
    (dados / "MICRODADOS_CADASTRO_CURSOS_2024.CSV").write_bytes(texto.encode("latin-1"))
    return tmp_path / "censo"


def curso(chave, nome, cidade, turno=None, grau=None):
    return Curso(
        chave=chave,
        url_origem="https://exemplo.br/" + chave.replace(":", "/"),
        nome=nome,
        cidade=cidade,
        uf="PR",
        turno=turno,
        opcoes=[Opcao(grau=grau, turno=turno)] if grau else [],
    )


def casar(pasta_censo, *cursos):
    return gerar_tabela(list(cursos), pasta_censo, 57)


def test_nome_e_cidade_unicos_viram_direto_e_confirmado(pasta_censo):
    [linha] = casar(pasta_censo, curso("uem:civil:umuarama", "Engenharia Civil", "Umuarama"))

    assert (linha.status, linha.codigo_emec, linha.confirmado) == (DIRETO, "150159", "sim")


def test_grau_do_site_desempata(pasta_censo):
    [linha] = casar(pasta_censo, curso("uem:q", "Química", "Maringá", grau=Grau.LICENCIATURA))

    assert (linha.status, linha.codigo_emec) == (DIRETO, "99368")


def test_turno_unico_desempata_pelas_vagas(pasta_censo):
    [linha] = casar(pasta_censo, curso("uem:e", "Ciências Econômicas", "Maringá", turno="Noturno"))

    assert (linha.status, linha.codigo_emec) == (DIRETO, "3392")


def test_varios_candidatos_viram_uma_linha_por_codigo_com_sugestao(pasta_censo):
    linhas = casar(
        pasta_censo, curso("uem:e", "Ciências Econômicas", "Maringá", turno="Integral ou Noturno")
    )

    assert sorted(linha.codigo_emec for linha in linhas) == ["1153285", "3392"]
    assert {(linha.status, linha.confirmado, linha.sugestao) for linha in linhas} == {
        (AMBIGUO, "nao", SUGESTAO_VARIOS)
    }


def test_mesmo_grau_e_turno_sugere_habilitacoes(pasta_censo):
    linhas = casar(pasta_censo, curso("uem:m", "Música", "Maringá", turno="Integral"))

    assert {linha.sugestao for linha in linhas} == {SUGESTAO_HABILITACAO}


def test_curso_sem_par_no_censo(pasta_censo):
    [linha] = casar(pasta_censo, curso("uem:sw", "Engenharia de Software", "Maringá"))

    assert (linha.status, linha.codigo_emec) == (SEM_PAR, "")


def test_mesmo_codigo_para_duas_paginas_vira_ambiguo(pasta_censo):
    linhas = casar(
        pasta_censo,
        curso("uem:civil:a", "Engenharia Civil", "Maringá"),
        curso("uem:civil:b", "Engenharia Civil", "Maringá"),
    )

    assert {linha.status for linha in linhas} == {AMBIGUO}


def test_regravar_preserva_a_revisao_manual(pasta_censo, tmp_path):
    destino = tmp_path / "uem_codigos.csv"
    economia = curso("uem:e", "Ciências Econômicas", "Maringá", turno="Integral ou Noturno")
    gravar_tabela(destino, casar(pasta_censo, economia))

    revisadas = ler_tabela(destino)
    for linha in revisadas:
        linha.confirmado = "sim"
    gravar_tabela(destino, revisadas)
    gravar_tabela(destino, casar(pasta_censo, economia))

    assert {linha.confirmado for linha in ler_tabela(destino)} == {"sim"}


def test_codigos_vao_numa_lista_interna_sem_dividir_o_curso():
    base = curso("uem:fisica:maringa", "Física", "Maringá")
    base = base.model_copy(
        update={
            "opcoes": [
                Opcao(grau=Grau.LICENCIATURA, turno="Noturno"),
                Opcao(grau=Grau.BACHARELADO, turno="Vespertino/Noturno"),
            ]
        }
    )
    codigos = [
        CodigoConfirmado(303405, "bacharelado", 30, 15),
        CodigoConfirmado(3405, "licenciatura", 0, 53),
    ]

    ligado = aplicar_codigos(base, codigos)

    assert ligado.chave == base.chave
    assert ligado.codigos_emec == [3405, 303405]
    assert ligado.opcoes == base.opcoes


def test_sem_codigos_o_curso_nao_muda():
    base = curso("uem:sw", "Engenharia de Software", "Maringá", grau=Grau.BACHARELADO)
    assert aplicar_codigos(base, []) == base


def test_pagina_sem_grau_recebe_os_graus_do_censo():
    base = curso("uem:q", "Química", "Maringá")
    codigos = [
        CodigoConfirmado(3406, "bacharelado", 100, 0),
        CodigoConfirmado(99368, "licenciatura", 0, 156),
        CodigoConfirmado(1, "bacharelado_e_licenciatura", 0, 0),
    ]

    ligado = aplicar_codigos(base, codigos)

    assert [o.grau for o in ligado.opcoes] == [Grau.BACHARELADO, Grau.LICENCIATURA]
    assert all(o.turno is None for o in ligado.opcoes)


class HttpDeFixtures:
    def __init__(self):
        self.pasta = Path(__file__).parent / "fixtures" / "uem"

    def get(self, url):
        arquivo = "lista.html" if url == URL_LISTA else "curso_engenharia_software.html"
        return type("Resposta", (), {"text": (self.pasta / arquivo).read_text(encoding="utf-8")})


def test_spider_usa_so_os_codigos_confirmados(tmp_path, monkeypatch):
    monkeypatch.setattr(casamento, "PASTA_TABELAS", tmp_path)
    cabecalho = (
        "chave;nome_site;cidade;turno_site;grau_site;status;codigo_emec;nome_censo;grau_censo;"
        "vagas_diurno;vagas_noturno;sugestao;confirmado\n"
    )
    (tmp_path / "uem_codigos.csv").write_text(
        cabecalho
        + "uem:administracao:maringa:noturno;;;;;direto;3393;;bacharelado;0;100;;sim\n"
        + "uem:agronomia:maringa:noturno;;;;;ambiguo;3413;;bacharelado;80;0;;nao\n"
        + "uem:fisica:maringa:noturno;;;;;ambiguo;3405;;licenciatura;0;53;;sim\n"
        + "uem:fisica:maringa:noturno;;;;;ambiguo;303405;;bacharelado;30;15;;sim\n",
        encoding="utf-8",
    )

    lote = UemSpider(HttpDeFixtures(), "t").coletar()
    por_chave = {c.chave: c for c in lote.cursos}

    assert len(lote.cursos) == 67
    assert por_chave["uem:administracao:maringa:noturno"].codigos_emec == [3393]
    assert por_chave["uem:agronomia:maringa:noturno"].codigos_emec == []
    assert por_chave["uem:fisica:maringa:noturno"].codigos_emec == [3405, 303405]
