import base64
import json

import pytest
import responses

from sauf_scraper.cli import main
from sauf_scraper.geral import manuais

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

UEM = """
sigla = "UEM"
codigo_emec = 57
nome = "Universidade Estadual de Maringá"
ano_fundacao = 1969
site_url = "https://www.uem.br"
sobre = [
  \"\"\"Primeiro parágrafo,
  quebrado em duas linhas.\"\"\",
  "Segundo parágrafo.",
]

[fontes]
ano_fundacao = "https://www.uem.br/a-uem/historico"
sobre = ["https://www.uem.br/a-uem/historico"]

[logo]
arquivo = "img/uem-logo.png"
autor = "Fulano"
licenca = "CC BY-SA 4.0"
licenca_url = "https://creativecommons.org/licenses/by-sa/4.0"
fonte_url = "https://commons.wikimedia.org/wiki/File:Logo_UEM.svg"
"""

AREAS = """
[[area]]
codigo_cine = "07"
nome = "Engenharia, produção e construção"

[area.imagem]
arquivo = "areas/img/07.png"
autor = "Fulana"
licenca = "CC0"
fonte_url = "https://commons.wikimedia.org/wiki/File:Obra.jpg"
"""


@pytest.fixture
def pasta_ies(tmp_path, monkeypatch):
    pasta = tmp_path / "ies"
    (pasta / "img").mkdir(parents=True)
    (pasta / "img" / "uem-logo.png").write_bytes(PNG)
    (pasta / "uem.toml").write_text(UEM, encoding="utf-8")
    monkeypatch.setattr(manuais, "PASTA_IES", pasta)
    return pasta


@pytest.fixture
def arquivo_areas(tmp_path, monkeypatch):
    (tmp_path / "areas" / "img").mkdir(parents=True)
    (tmp_path / "areas" / "img" / "07.png").write_bytes(PNG)
    arquivo = tmp_path / "areas.toml"
    arquivo.write_text(AREAS, encoding="utf-8")
    monkeypatch.setattr(manuais, "ARQUIVO_AREAS", arquivo)
    return arquivo


def trocar(pasta, antes, depois):
    arquivo = pasta / "uem.toml"
    arquivo.write_text(arquivo.read_text(encoding="utf-8").replace(antes, depois), encoding="utf-8")


def test_le_a_universidade_e_junta_as_linhas_do_paragrafo(pasta_ies):
    [(uem, caminho)] = manuais.ler_universidades()

    assert uem.ano_fundacao == 1969
    assert uem.sobre == ["Primeiro parágrafo, quebrado em duas linhas.", "Segundo parágrafo."]
    assert uem.capa is None
    envio = manuais.envio_universidade(uem, caminho.parent).model_dump(mode="json", by_alias=True)
    assert envio["anoFundacao"] == 1969
    assert envio["siteUrl"] == "https://www.uem.br/"
    assert base64.b64decode(envio["logo"]["conteudoBase64"]) == PNG
    assert envio["logo"]["fonteUrl"] == "https://commons.wikimedia.org/wiki/File:Logo_UEM.svg"
    assert envio["capa"] is None


@pytest.mark.parametrize(
    ("antes", "depois", "mensagem"),
    [
        ("ano_fundacao = 1969", "ano_fundacao = 3000", "futuro"),
        ('autor = "Fulano"', 'autor = ""', "logo.autor"),
        ("https://commons.wikimedia.org/wiki/File:Logo_UEM.svg", "https://www.uem.br/logo.png",
         "Wikimedia Commons"),
        ('sigla = "UEM"', 'sigla = "UEL"', "não bate com o nome do arquivo"),
        ('"Segundo parágrafo."', '"Um.\\n\\nDois."', "item separado"),
        ("img/uem-logo.png", "img/nao-existe.png", "imagem não encontrada"),
        ('nome = "Universidade', 'apelido = "x"\nnome = "Universidade', "apelido"),
    ],
)
def test_recusa_arquivo_com_problema(pasta_ies, antes, depois, mensagem):
    trocar(pasta_ies, antes, depois)

    with pytest.raises(manuais.DadoManualInvalidoError, match=mensagem):
        manuais.ler_universidades()


def test_recusa_svg_e_imagem_grande(pasta_ies):
    logo = pasta_ies / "img" / "uem-logo.png"
    logo.write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'/>")
    with pytest.raises(manuais.DadoManualInvalidoError, match="SVG não serve"):
        manuais.ler_universidades()

    logo.write_bytes(PNG + b"0" * manuais.TAMANHO_MAXIMO)
    with pytest.raises(manuais.DadoManualInvalidoError, match="limite é 2 MB"):
        manuais.ler_universidades()


def test_sigla_sem_arquivo(pasta_ies):
    with pytest.raises(manuais.DadoManualInvalidoError, match="ufpr"):
        manuais.ler_universidades(["UFPR"])


def test_dry_run_grava_json_sem_enviar(pasta_ies, settings, monkeypatch, capsys):
    monkeypatch.setenv("SAUF_OUTPUT_DIR", str(settings.output_dir))

    assert main(["ies", "--dry-run"]) == 0

    gravado = json.loads((settings.output_dir / "ies-uem.json").read_text(encoding="utf-8"))
    assert gravado["anoFundacao"] == 1969
    saida = capsys.readouterr().out
    assert "UEM (e-MEC 57): fundada em 1969, 2 parágrafo(s), logo CC BY-SA 4.0" in saida


@responses.activate
def test_envia_por_put_com_api_key(pasta_ies, monkeypatch):
    monkeypatch.setenv("SAUF_API_BASE_URL", "http://api.teste")
    monkeypatch.setenv("SAUF_API_KEY", "segredo")
    responses.put("http://api.teste/api/v1/ingestao/universidades/57", json={"atualizados": 1})

    assert main(["ies", "--sigla", "uem"]) == 0

    requisicao = responses.calls[0].request
    assert requisicao.headers["X-Api-Key"] == "segredo"
    assert json.loads(requisicao.body)["sobre"][1] == "Segundo parágrafo."


def test_arquivo_invalido_sai_com_erro_e_mensagem(pasta_ies, capsys):
    trocar(pasta_ies, "ano_fundacao = 1969", "ano_fundacao = \"mil\"")

    assert main(["ies", "--dry-run"]) == 1
    assert "ERRO:" in capsys.readouterr().out


@responses.activate
def test_areas_envia_a_imagem_de_cada_area(arquivo_areas, monkeypatch):
    monkeypatch.setenv("SAUF_API_BASE_URL", "http://api.teste")
    monkeypatch.setenv("SAUF_API_KEY", "segredo")
    responses.put("http://api.teste/api/v1/ingestao/areas/07/imagem", json={"atualizados": 0})

    assert main(["areas"]) == 0

    corpo = json.loads(responses.calls[0].request.body)
    assert corpo["licenca"] == "CC0"
    assert base64.b64decode(corpo["conteudoBase64"]) == PNG


@responses.activate
def test_area_sem_imagem_fica_de_fora_do_envio(arquivo_areas, monkeypatch, capsys):
    monkeypatch.setenv("SAUF_API_BASE_URL", "http://api.teste")
    monkeypatch.setenv("SAUF_API_KEY", "segredo")
    texto = arquivo_areas.read_text(encoding="utf-8")
    sem_imagem = """
[[area]]
codigo_cine = "09"
nome = "Saúde e bem-estar"
"""
    arquivo_areas.write_text(texto + sem_imagem, encoding="utf-8")
    responses.put("http://api.teste/api/v1/ingestao/areas/07/imagem", json={"atualizados": 1})

    assert main(["areas"]) == 0

    assert len(responses.calls) == 1
    assert "09 Saúde e bem-estar: sem imagem, não enviada" in capsys.readouterr().out


def test_areas_recusa_codigo_repetido_ou_invalido(arquivo_areas):
    texto = arquivo_areas.read_text(encoding="utf-8")
    arquivo_areas.write_text(texto + texto, encoding="utf-8")
    with pytest.raises(manuais.DadoManualInvalidoError, match="repetida: 07"):
        manuais.ler_areas(arquivo_areas)

    arquivo_areas.write_text(texto.replace('"07"', '"7"'), encoding="utf-8")
    with pytest.raises(manuais.DadoManualInvalidoError, match="codigo_cine"):
        manuais.ler_areas(arquivo_areas)


def test_arquivos_reais_do_repositorio_sao_validos():
    """Os .toml de dados/ que vão para a API precisam passar na validação."""
    universidades = manuais.ler_universidades()
    assert {u.sigla for u, _ in universidades} == {"UEM", "UEL", "UTFPR", "UFSC", "UFSM"}
    assert len(manuais.ler_areas()) == 11
