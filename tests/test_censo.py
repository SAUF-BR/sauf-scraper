import json

import pytest
import responses

from sauf_scraper.censo.leitor import ler_censo
from sauf_scraper.cli import main
from sauf_scraper.client.destinos import ApiSauf
from sauf_scraper.core.models import Grau, Modalidade

COLUNAS_IES = [
    "NU_ANO_CENSO", "SG_UF_IES", "NO_MUNICIPIO_IES", "TP_ORGANIZACAO_ACADEMICA", "TP_REDE",
    "TP_CATEGORIA_ADMINISTRATIVA", "CO_IES", "NO_IES", "SG_IES",
]  # fmt: skip
COLUNAS_CURSOS = [
    "NU_ANO_CENSO", "SG_UF", "NO_MUNICIPIO", "TP_DIMENSAO", "CO_IES", "NO_CURSO", "CO_CURSO",
    "NO_CINE_ROTULO", "CO_CINE_ROTULO", "CO_CINE_AREA_GERAL", "TP_GRAU_ACADEMICO", "IN_GRATUITO",
    "TP_MODALIDADE_ENSINO", "TP_NIVEL_ACADEMICO", "QT_VG_TOTAL",
]  # fmt: skip

IES = [
    ["2024", "PR", "Maringá", "1", "1", "2", "57", "UNIVERSIDADE ESTADUAL DE MARINGÁ", "UEM"],
    ["2024", "PR", "Londrina", "1", "1", "2", "9", "UNIVERSIDADE ESTADUAL DE LONDRINA", "UEL"],
]
CURSOS = [
    # Presencial: uma linha.
    ["2024", "PR", "Maringá", "1", "57", "Engenharia Civil", "3402", "Engenharia civil",
     '"""0732E01"""', "07", "1", "1", "1", "1", "80"],
    # EAD: duas linhas de polo + a consolidada (sem cidade).
    ["2024", "PR", "Assaí", "2", "57", "Pedagogia", "5001", "Pedagogia", '"""0113P01"""', "01",
     "2", "1", "2", "1", "0"],
    ["2024", "PR", "Astorga", "2", "57", "Pedagogia", "5001", "Pedagogia", '"""0113P01"""', "01",
     "2", "1", "2", "1", "0"],
    ["2024", "", "", "3", "57", "Pedagogia", "5001", "Pedagogia", '"""0113P01"""', "01", "2",
     "1", "2", "1", "300"],
    # EAD só com linhas de polo.
    ["2024", "PR", "Cianorte", "2", "57", "Gestão Pública", "5002", "Gestão pública",
     '"""0413G01"""', "04", "3", "1", "2", "1", "0"],
    # Sequencial: fica de fora.
    ["2024", "PR", "Maringá", "1", "57", "Curso Sequencial", "5003", "Outro", '"""0000X00"""',
     "00", "", "0", "1", "2", "10"],
    # Outra IES: fica de fora.
    ["2024", "PR", "Londrina", "1", "9", "Medicina", "9001", "Medicina", '"""0912M01"""', "09",
     "1", "1", "1", "1", "60"],
]  # fmt: skip


def escrever_csv(caminho, colunas, linhas):
    texto = "\n".join(";".join(linha) for linha in [colunas, *linhas]) + "\n"
    caminho.write_bytes(texto.encode("latin-1"))


@pytest.fixture
def pasta_censo(tmp_path):
    dados = tmp_path / "censo" / "dados"
    dados.mkdir(parents=True)
    escrever_csv(dados / "MICRODADOS_ED_SUP_IES_2024.CSV", COLUNAS_IES, IES)
    escrever_csv(dados / "MICRODADOS_CADASTRO_CURSOS_2024.CSV", COLUNAS_CURSOS, CURSOS)
    return tmp_path / "censo"


def test_le_so_as_instituicoes_pedidas(pasta_censo):
    lote = ler_censo(pasta_censo, [57])

    assert lote.ano_censo == 2024
    assert len(lote.instituicoes) == 1
    uem = lote.instituicoes[0]
    assert (uem.codigo_emec, uem.sigla, uem.uf, uem.cidade) == (57, "UEM", "PR", "Maringá")
    assert uem.nome == "UNIVERSIDADE ESTADUAL DE MARINGÁ"
    assert uem.tipo == "publica"
    assert uem.categoria_administrativa == "publica_estadual"
    assert uem.organizacao_academica == "universidade"


def test_uma_oferta_por_codigo_e_so_graduacao(pasta_censo):
    ofertas = {o.codigo_emec: o for o in ler_censo(pasta_censo, [57]).ofertas}

    assert sorted(ofertas) == [3402, 5001, 5002]


def test_oferta_presencial(pasta_censo):
    civil = {o.codigo_emec: o for o in ler_censo(pasta_censo, [57]).ofertas}[3402]

    assert civil.grau == Grau.BACHARELADO
    assert civil.modalidade == Modalidade.PRESENCIAL
    assert (civil.cidade, civil.uf, civil.vagas, civil.gratuito) == ("Maringá", "PR", 80, True)
    assert civil.codigo_cine_rotulo == "0732E01"
    assert civil.codigo_cine_area == "07"


def test_ead_usa_a_linha_consolidada(pasta_censo):
    pedagogia = {o.codigo_emec: o for o in ler_censo(pasta_censo, [57]).ofertas}[5001]

    assert pedagogia.modalidade == Modalidade.EAD
    assert pedagogia.vagas == 300
    assert pedagogia.cidade is None


def test_ead_sem_consolidada_usa_um_polo_sem_cidade(pasta_censo):
    gestao = {o.codigo_emec: o for o in ler_censo(pasta_censo, [57]).ofertas}[5002]

    assert gestao.grau == Grau.TECNOLOGICO
    assert gestao.cidade is None
    assert gestao.uf is None


def test_json_sai_em_camel_case(pasta_censo):
    dados = ler_censo(pasta_censo, [57]).model_dump(mode="json", by_alias=True)

    assert dados["anoCenso"] == 2024
    assert dados["instituicoes"][0]["codigoEmec"] == 57
    assert dados["ofertas"][0]["codigoCineRotulo"] == "0732E01"
    assert dados["ofertas"][0]["modalidade"] == "presencial"


def test_pasta_sem_arquivos_da_erro_claro(tmp_path):
    with pytest.raises(FileNotFoundError):
        ler_censo(tmp_path, [57])


@responses.activate
def test_api_recebe_o_censo(settings, pasta_censo):
    responses.post("http://api.teste/api/v1/ingestao/censo", json={"criados": 4})

    resposta = ApiSauf(settings).enviar_censo(ler_censo(pasta_censo, [57]))

    assert resposta.criados == 4
    assert responses.calls[0].request.headers["X-Api-Key"] == "segredo"


def test_comando_censo_dry_run(pasta_censo, tmp_path, monkeypatch):
    monkeypatch.setenv("SAUF_OUTPUT_DIR", str(tmp_path / "saida"))

    assert main(["censo", "--pasta", str(pasta_censo), "--dry-run"]) == 0

    gravado = json.loads((tmp_path / "saida" / "censo-2024.json").read_text(encoding="utf-8"))
    assert [i["sigla"] for i in gravado["instituicoes"]] == ["UEM"]
    assert len(gravado["ofertas"]) == 3
