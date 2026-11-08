"""Importador de questões do ENEM (geral/enem.py), com fixtures recortadas dos arquivos reais:
6 questões do maritaca-ai/enem 2024 e as linhas delas no ITENS_PROVA_2024 (caderno laranja
e um azul, que não pode ser escolhido).

uv run pytest tests/test_enem.py -v
"""

import json
from pathlib import Path

import pytest

from sauf_scraper.cli import main
from sauf_scraper.geral import enem

FIXTURES = Path(__file__).parent / "fixtures" / "enem"


@pytest.fixture
def registros():
    return enem.ler_maritaca(FIXTURES / "2024.jsonl")


@pytest.fixture
def itens():
    return enem.ler_itens(FIXTURES / "ITENS_PROVA_2024.csv")


@pytest.fixture
def questoes(registros, itens):
    lotes = enem.montar_lotes(2024, registros, itens)
    return {q.numero: q for lote in lotes for q in lote.questoes}


def test_dois_lotes_um_por_dia(registros, itens):
    lotes = enem.montar_lotes(2024, registros, itens)

    assert [(lote.prova.edicao, lote.prova.caderno) for lote in lotes] == [
        ("D1", "LARANJA"),
        ("D2", "LARANJA"),
    ]
    assert [q.numero for q in lotes[0].questoes] == [1, 2]
    assert [q.numero for q in lotes[1].questoes] == [93, 124, 151, 171]
    assert lotes[0].prova.credito == "ENEM 2024 (INEP), via maritaca-ai/enem (Apache-2.0)"


def test_cruzamento_com_o_caderno_laranja(questoes):
    ingles = questoes[1]

    # Laranja (1401), inglês: item 118194; o azul (1353) tem outro gabarito e fica de fora.
    assert ingles.codigo_origem == 118194
    assert ingles.lingua == "ingles"
    assert ingles.area == "lc"
    assert ingles.habilidade == 5
    assert ingles.dificuldade == pytest.approx(0.81082)
    assert questoes[171].area == "mt"
    assert questoes[171].lingua is None


def test_texto_base_comando_e_alternativas(questoes):
    ingles = questoes[1]

    assert ingles.texto_base.startswith("## Holy War")
    assert ingles.comando.startswith("Nessa letra de canção")
    assert [a.rotulo for a in ingles.alternativas] == ["A", "B", "C", "D", "E"]
    assert [a.correta for a in ingles.alternativas] == [True, False, False, False, False]
    assert ingles.status == "disponivel"
    assert ingles.credito == enem.credito(2024)


def test_figura_vira_imagem_markdown_com_a_descricao(questoes):
    texto_base = questoes[2].texto_base

    assert texto_base.startswith("![Descrição da imagem: Reprodução de janela")
    assert (
        "(https://raw.githubusercontent.com/piresramon/gpt-4-enem/main/data/figures/2024/"
        in texto_base
    )
    assert questoes[2].comando.startswith("O texto estabelece uma relação")


def test_figura_depois_do_comando_fica_com_o_comando(questoes):
    heredograma = questoes[93]

    assert heredograma.comando.startswith("Qual heredograma foi recebido pelo casal?\n![")
    assert heredograma.texto_base.endswith("para esse bebê.")
    assert all(a.texto.startswith("![") for a in heredograma.alternativas)
    assert heredograma.status == "pendente_revisao"
    assert heredograma.motivo_pendencia == "alternativa só com figura"


def test_anulada_sem_correta_e_sem_dificuldade(questoes):
    anulada = questoes[124]

    assert anulada.anulada is True
    assert not any(a.correta for a in anulada.alternativas)
    assert anulada.dificuldade is None


@pytest.mark.parametrize(
    ("numero", "motivo"),
    [(171, "fórmula escrita por extenso"), (151, "tabela com sobras da conversão")],
)
def test_pendencias(questoes, numero, motivo):
    assert questoes[numero].status == "pendente_revisao"
    assert motivo in questoes[numero].motivo_pendencia


def test_gabarito_do_inep_prevalece_na_divergencia(registros, itens, monkeypatch):
    # Com só 2 questões de MT na fixture, 1 divergência derrubaria o acerto para 50%.
    monkeypatch.setattr(enem, "MINIMO_DE_ACERTO", 0.5)
    registros[151]["label"] = "B"

    lotes = enem.montar_lotes(2024, registros, itens)
    questao = next(q for q in lotes[1].questoes if q.numero == 151)

    assert [a.rotulo for a in questao.alternativas if a.correta] == ["A"]
    assert "gabarito do dataset (B) diverge do INEP (A)" in questao.motivo_pendencia


def test_itens_de_outro_ano_sao_recusados(registros, itens):
    for linha in itens:
        linha["TX_GABARITO"] = "C" if linha["TX_GABARITO"] != "C" else "D"

    with pytest.raises(ValueError, match="o ITENS_PROVA é do mesmo ano"):
        enem.montar_lotes(2024, registros, itens)


def test_questao_sem_item_e_recusada(registros, itens):
    registros[200] = {**registros[171], "id": "questao_200"}

    with pytest.raises(ValueError, match=r"sem item no ITENS_PROVA: \[200\]"):
        enem.montar_lotes(2024, registros, itens)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Só o comando", (None, "Só o comando")),
        ("Texto\nOutro parágrafo\nComando?", ("Texto\nOutro parágrafo", "Comando?")),
        ("Texto\nComando é\n![fig](u)", ("Texto", "Comando é\n![fig](u)")),
        ("![fig](u)\n| a | b |", (None, "![fig](u)\n| a | b |")),
    ],
)
def test_separar_texto_base(texto, esperado):
    assert enem.separar_texto_base(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("## TEXTO 1![fig](u)", "## TEXTO 1\n![fig](u)"),
        ("![fig](u)A carta", "![fig](u)\nA carta"),
        ("medidas.![fig](u)Qual", "medidas.\n![fig](u)\nQual"),
        ("Texto\n![fig](u)\nComando", "Texto\n![fig](u)\nComando"),
    ],
)
def test_figura_grudada_vira_linha_propria(texto, esperado):
    assert enem.FIGURA.sub(enem._linha_propria, texto) == esperado


def test_dry_run_grava_os_dois_dias(tmp_path, monkeypatch):
    monkeypatch.setenv("SAUF_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("SAUF_QUESTOES_IMAGENS_URL", "")  # vazia vence a do .env

    assert main(["questoes", "enem", "--ano", "2024", "--pasta", str(FIXTURES), "--dry-run"]) == 0

    gravado = json.loads((tmp_path / "questoes-enem-2024.json").read_text(encoding="utf-8"))
    assert gravado["ano"] == 2024
    assert [lote["prova"]["edicao"] for lote in gravado["lotes"]] == ["D1", "D2"]
    primeira = gravado["lotes"][0]["questoes"][0]
    assert primeira["textoBase"].startswith("## Holy War")
    assert primeira["codigoOrigem"] == 118194


BUCKET = "https://exemplo.supabase.co/storage/v1/object/public/questoes-enem/"


class HttpFalso:
    """Responde qualquer GET com bytes fixos; as URLs em `falhar` levantam erro."""

    def __init__(self, falhar=()):
        self.falhar = set(falhar)
        self.pedidas = []

    def get(self, url):
        self.pedidas.append(url)
        if url in self.falhar:
            raise ConnectionError("conexão recusada")
        return type("Resposta", (), {"content": b"png"})()


def test_base_das_imagens_troca_so_o_dominio(registros, itens):
    lotes = enem.montar_lotes(2024, registros, itens, BUCKET)
    questoes = {q.numero: q for lote in lotes for q in lote.questoes}

    assert f"({BUCKET}2024/questao_02_fileoutpart5.png)" in questoes[2].texto_base
    assert questoes[2].texto_base.startswith("![Descrição da imagem: Reprodução de janela")
    assert all(a.texto.startswith("![") and BUCKET in a.texto for a in questoes[93].alternativas)
    assert "raw.githubusercontent.com" not in json.dumps([lote.model_dump() for lote in lotes])


def test_baixar_imagens_lista_falhas_e_depois_so_baixa_as_que_faltam(registros, tmp_path):
    urls = enem.imagens_do_dataset(registros)
    http = HttpFalso(falhar=[urls[0]])

    falhas = enem.baixar_imagens(http, registros, tmp_path)

    assert len(urls) == 8
    assert falhas == [f"{urls[0]}: conexão recusada"]
    assert (tmp_path / "2024" / "questao_171_fileoutpart100.png").read_bytes() == b"png"
    assert enem.imagens_faltando(registros, tmp_path) == ["2024/questao_02_fileoutpart5.png"]

    segunda = HttpFalso()
    assert enem.baixar_imagens(segunda, registros, tmp_path) == []
    assert segunda.pedidas == [urls[0]]
    assert enem.imagens_faltando(registros, tmp_path) == []


@pytest.fixture
def pasta_enem(tmp_path, monkeypatch):
    """Cópia das fixtures (para baixar imagens nela) e HttpEducado trocado pelo falso."""
    pasta = tmp_path / "enem"
    pasta.mkdir()
    for arquivo in FIXTURES.iterdir():
        (pasta / arquivo.name).write_bytes(arquivo.read_bytes())
    monkeypatch.setenv("SAUF_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("SAUF_QUESTOES_IMAGENS_URL", "")  # vazia vence a do .env
    return pasta


def test_cli_baixar_imagens_sai_com_erro_se_alguma_falhar(pasta_enem, monkeypatch):
    falha = "https://raw.githubusercontent.com/piresramon/gpt-4-enem/main/data/figures/2024/questao_02_fileoutpart5.png"
    monkeypatch.setattr("sauf_scraper.cli.HttpEducado", lambda _: HttpFalso(falhar=[falha]))
    argv = ["questoes", "enem", "--ano", "2024", "--pasta", str(pasta_enem), "--baixar-imagens"]

    assert main(argv) == 1
    assert len(list((pasta_enem / "imagens" / "2024").iterdir())) == 7

    monkeypatch.setattr("sauf_scraper.cli.HttpEducado", lambda _: HttpFalso())
    assert main(argv) == 0
    assert len(list((pasta_enem / "imagens" / "2024").iterdir())) == 8


def test_cli_com_bucket_exige_as_imagens_baixadas(pasta_enem, monkeypatch, tmp_path):
    monkeypatch.setenv("SAUF_QUESTOES_IMAGENS_URL", BUCKET)
    monkeypatch.setattr("sauf_scraper.cli.HttpEducado", lambda _: HttpFalso())
    argv = ["questoes", "enem", "--ano", "2024", "--pasta", str(pasta_enem), "--dry-run"]

    with pytest.raises(SystemExit):
        main(argv)

    assert main([*argv[:-1], "--baixar-imagens"]) == 0
    assert main(argv) == 0
    gravado = (tmp_path / "output" / "questoes-enem-2024.json").read_text(encoding="utf-8")
    assert f"{BUCKET}2024/questao_02_fileoutpart5.png" in gravado
    assert "raw.githubusercontent.com" not in gravado
