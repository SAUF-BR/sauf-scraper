import json

import pytest
import responses
from openpyxl import Workbook

from sauf_scraper.cli import main
from sauf_scraper.geral.base import entregar
from sauf_scraper.geral.igc import ENDPOINT, faixa, ler_igc

# Mesmo layout da planilha do INEP: cabeçalhos com espaço no começo e faixa como texto.
CABECALHO = ["Ano", " Código da IES", " Nome da IES", " IGC (Contínuo)", " IGC (Faixa)"]
LINHAS = [
    [2023, 57, "UNIVERSIDADE DE TESTE A", 3.946, "5"],
    [2023, 9, "UNIVERSIDADE DE TESTE B", 2.81, "3"],
    [2023, 777, "FACULDADE FORA DO ESCOPO", 4.1, "5"],
    [2023, 139, "FACULDADE SEM CONCEITO", None, "SC"],
]


@pytest.fixture
def planilha(tmp_path):
    pasta = Workbook()
    aba = pasta.active
    aba.title = "IGC"
    aba.append(CABECALHO)
    for linha in LINHAS:
        aba.append(linha)
    pasta.create_sheet("Atualizações").append(["outra aba, ignorada"])
    caminho = tmp_path / "IGC_2023.xlsx"
    pasta.save(caminho)
    return caminho


def test_le_so_as_ies_do_escopo(planilha):
    lote, relatorio = ler_igc(planilha, [57, 9])

    assert lote.ano == 2023
    assert [(i.codigo_emec, i.igc_faixa, i.igc_continuo) for i in lote.instituicoes] == [
        (57, 5, 3.946),
        (9, 3, 2.81),
    ]
    assert relatorio.ausentes == []


def test_sem_conceito_vira_null(planilha):
    lote, _ = ler_igc(planilha, [139])

    assert lote.instituicoes[0].igc_faixa is None
    assert lote.instituicoes[0].igc_continuo is None


def test_relatorio_lista_ies_do_escopo_que_nao_casaram(planilha):
    _, relatorio = ler_igc(planilha, [57, 4242])

    assert relatorio.encontradas == {57}
    assert relatorio.ausentes == [4242]


def test_nenhuma_ies_do_escopo_na_planilha_e_erro(planilha):
    with pytest.raises(ValueError, match="nenhuma IES do escopo"):
        ler_igc(planilha, [4242])


@pytest.mark.parametrize(
    ("valor", "esperado"), [("5", 5), ("1", 1), (4, 4), ("SC", None), (None, None), ("0", None)]
)
def test_faixa(valor, esperado):
    assert faixa(valor) == esperado


def test_dry_run_grava_json_em_camel_case(planilha, settings):
    lote, _ = ler_igc(planilha, [57])

    assert entregar(lote, "igc-2023.json", ENDPOINT, settings, dry_run=True) is None

    conteudo = json.loads((settings.output_dir / "igc-2023.json").read_text(encoding="utf-8"))
    assert conteudo == {
        "ano": 2023,
        "instituicoes": [{"codigoEmec": 57, "igcContinuo": 3.946, "igcFaixa": 5}],
    }


@responses.activate
def test_envio_para_a_api_com_api_key(planilha, settings):
    responses.post(
        "http://api.teste/api/v1/ingestao/igc",
        json={"criados": 1, "atualizados": 0, "inativados": 0, "rejeitados": []},
    )
    lote, _ = ler_igc(planilha, [57])

    resposta = entregar(lote, "igc-2023.json", ENDPOINT, settings, dry_run=False)

    assert resposta.criados == 1
    enviado = responses.calls[0].request
    assert enviado.headers["X-Api-Key"] == "segredo"
    assert json.loads(enviado.body)["instituicoes"][0]["igcFaixa"] == 5


def test_comando_igc_dry_run(planilha, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sauf_scraper.cli.codigos_emec", lambda: [57])

    assert main(["igc", "--arquivo", str(planilha), "--dry-run"]) == 0
    assert (tmp_path / "output" / "igc-2023.json").exists()
