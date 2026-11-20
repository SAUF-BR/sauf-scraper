import json

import pytest
import responses

from sauf_scraper.cli import main
from sauf_scraper.geral import calendario, manuais

EVENTOS = """
[[evento]]
chave = "enem-2026-prova-1"
titulo = "ENEM 2026: 1º dia"
tipo = "prova"
inicio = 2026-11-08
fonte_url = "https://www.gov.br/inep/enem"
ano = 2026

[[evento]]
chave = "uem-verao-2026-inscricao"
titulo = "Inscrições UEM"
tipo = "inscricao"
inicio = 2026-08-17
fim = 2026-09-23
sigla = "uem"
descricao = "Ingresso em 2027."
fonte_url = "https://www.cvu.uem.br/programacao.html"
ano = 2026
"""


@pytest.fixture
def arquivo(tmp_path, monkeypatch):
    pasta_ies = tmp_path / "ies"
    pasta_ies.mkdir()
    (pasta_ies / "uem.toml").write_text('sigla = "UEM"\ncodigo_emec = 57\n', encoding="utf-8")
    monkeypatch.setattr(calendario, "PASTA_IES", pasta_ies)
    caminho = tmp_path / "calendario.toml"
    caminho.write_text(EVENTOS, encoding="utf-8")
    monkeypatch.setattr(calendario, "ARQUIVO_CALENDARIO", caminho)
    return caminho


def test_le_os_eventos_e_troca_a_sigla_pelo_codigo_emec(arquivo):
    eventos = calendario.ler_eventos()

    assert [e.chave for e, _ in eventos] == ["enem-2026-prova-1", "uem-verao-2026-inscricao"]
    enem, uem = (envio for _, envio in eventos)
    assert enem.codigo_emec_instituicao is None and enem.fim is None
    corpo = uem.model_dump(mode="json", by_alias=True)
    assert corpo == {
        "titulo": "Inscrições UEM",
        "tipo": "inscricao",
        "inicio": "2026-08-17",
        "fim": "2026-09-23",
        "codigoEmecInstituicao": 57,
        "descricao": "Ingresso em 2027.",
        "fonteUrl": "https://www.cvu.uem.br/programacao.html",
        "anoReferencia": 2026,
    }


@pytest.mark.parametrize(
    ("antes", "depois", "mensagem"),
    [
        ('tipo = "prova"', 'tipo = "palestra"', "tipo"),
        ("fim = 2026-09-23", "fim = 2026-08-01", "o fim não pode ser antes do início"),
        ('chave = "enem-2026-prova-1"', 'chave = "ENEM 2026"', "chave"),
        ('fonte_url = "https://www.gov.br/inep/enem"\n', "", "fonteUrl"),
        ('sigla = "uem"', 'sigla = "usp"', "sigla sem arquivo"),
        ('chave = "enem-2026-prova-1"', 'chave = "uem-verao-2026-inscricao"', "chave repetida"),
    ],
)
def test_recusa_evento_com_problema(arquivo, antes, depois, mensagem):
    arquivo.write_text(EVENTOS.replace(antes, depois, 1), encoding="utf-8")
    with pytest.raises(manuais.DadoManualInvalidoError, match=mensagem):
        calendario.ler_eventos()


def test_dry_run_so_lista(arquivo, capsys):
    assert main(["calendario", "--dry-run"]) == 0
    saida = capsys.readouterr().out
    assert "17/08/2026 a 23/09/2026" in saida
    assert "2 evento(s) validados, nada enviado" in saida


@responses.activate
def test_envia_por_put_na_chave_com_api_key(arquivo, monkeypatch, capsys):
    monkeypatch.setenv("SAUF_API_BASE_URL", "http://api.teste")
    monkeypatch.setenv("SAUF_API_KEY", "segredo")
    rota = "http://api.teste/api/v1/admin/calendario/eventos/"
    responses.put(rota + "enem-2026-prova-1", json={"criados": 1})
    responses.put(rota + "uem-verao-2026-inscricao", json={"criados": 0, "atualizados": 0})

    assert main(["calendario"]) == 0

    assert [c.request.headers["X-Api-Key"] for c in responses.calls] == ["segredo", "segredo"]
    assert json.loads(responses.calls[1].request.body)["codigoEmecInstituicao"] == 57
    saida = capsys.readouterr().out
    assert "enviado: criado" in saida and "enviado: sem mudanças" in saida


@responses.activate
def test_so_as_chaves_pedidas(arquivo, monkeypatch):
    monkeypatch.setenv("SAUF_API_BASE_URL", "http://api.teste")
    responses.put("http://api.teste/api/v1/admin/calendario/eventos/enem-2026-prova-1", json={})

    assert main(["calendario", "--chave", "enem-2026-prova-1"]) == 0
    assert len(responses.calls) == 1
    assert main(["calendario", "--chave", "nao-existe"]) == 1


@responses.activate
def test_remover_apaga_e_avisa_quando_nao_existe(monkeypatch, capsys):
    monkeypatch.setenv("SAUF_API_BASE_URL", "http://api.teste")
    rota = "http://api.teste/api/v1/admin/calendario/eventos/"
    responses.delete(rota + "velho", status=204)
    responses.delete(rota + "sumido", status=404, json={"message": "não encontrado"})

    assert main(["calendario", "--remover", "velho", "sumido"]) == 0
    saida = capsys.readouterr().out
    assert "velho: removido" in saida and "sumido: não existe na API" in saida


def test_arquivo_real_do_repositorio_e_valido():
    eventos = calendario.ler_eventos()
    assert eventos
    for evento, _ in eventos:
        assert evento.fonte_url.scheme == "https"
