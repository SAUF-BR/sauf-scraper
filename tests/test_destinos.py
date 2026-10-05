import json

import pytest
import responses

from sauf_scraper.client.destinos import ApiRecusouLoteError, ApiSauf, ArquivoJson


@responses.activate
def test_api_envia_lote_com_api_key(settings, lote):
    responses.post("http://api.teste/api/v1/ingestao/lotes", json={"criados": 1})

    resposta = ApiSauf(settings).enviar(lote)

    assert resposta.criados == 1
    requisicao = responses.calls[0].request
    assert requisicao.headers["X-Api-Key"] == "segredo"
    assert json.loads(requisicao.body)["codigoEmecInstituicao"] == 57


@responses.activate
def test_api_recusa_lote(settings, lote):
    responses.post("http://api.teste/api/v1/ingestao/lotes", status=400, body="chave inválida")

    with pytest.raises(ApiRecusouLoteError) as erro:
        ApiSauf(settings).enviar(lote)
    assert erro.value.status == 400


def test_dry_run_grava_json(settings, lote):
    ArquivoJson(settings.output_dir).enviar(lote)

    arquivo = settings.output_dir / "emec-57.json"
    assert (
        json.loads(arquivo.read_text(encoding="utf-8"))["cursos"][0]["nome"] == "Engenharia Civil"
    )
