import pytest
from pydantic import ValidationError

from sauf_scraper.core.models import Curso, LoteIngestao, montar_chave_curso

URL = "https://www.exemplo.br/curso/abc123"


def test_json_sai_em_camel_case(lote):
    dados = lote.model_dump(mode="json", by_alias=True)
    assert "execucaoId" in dados
    assert dados["codigoEmecInstituicao"] == 57
    assert "instituicao" not in dados
    curso = dados["cursos"][0]
    assert "areaConhecimento" in curso
    assert curso["codigoEmec"] == 3402
    assert curso["urlOrigem"] == URL
    assert curso["grau"] == "BACHARELADO"


def test_curso_sem_codigo_emec_e_aceito(lote):
    novo = lote.model_dump(mode="json", by_alias=True)["cursos"][1]
    assert novo["codigoEmec"] is None
    assert novo["chave"] == "uem:engenharia-de-software:maringa:noturno"


def test_codigo_emec_da_instituicao_precisa_ser_positivo(lote):
    dados = lote.model_dump() | {"codigo_emec_instituicao": 0}
    with pytest.raises(ValidationError):
        LoteIngestao(**dados)


@pytest.mark.parametrize("codigo", [0, -5, "abc"])
def test_codigo_emec_do_curso_invalido_e_rejeitado(codigo):
    with pytest.raises(ValidationError):
        Curso(chave="x", codigo_emec=codigo, url_origem=URL, nome="Curso")


@pytest.mark.parametrize("chave", ["", "UEM Civil", "uem::civil", "uem:civil:", "engenharia_civil"])
def test_chave_fora_do_padrao_e_rejeitada(chave):
    with pytest.raises(ValidationError):
        Curso(chave=chave, url_origem=URL, nome="Engenharia Civil")


def test_url_origem_e_obrigatoria():
    with pytest.raises(ValidationError):
        Curso(chave="uem:civil", nome="Engenharia Civil")


def test_nome_vazio_e_rejeitado():
    with pytest.raises(ValidationError):
        Curso(chave="x", url_origem=URL, nome="   ")


def test_grau_desconhecido_e_rejeitado():
    with pytest.raises(ValidationError):
        Curso(chave="x", url_origem=URL, nome="Curso", grau="MESTRADO")


def test_campo_desconhecido_e_rejeitado():
    with pytest.raises(ValidationError):
        Curso(chave="x", url_origem=URL, nome="Curso", campo_inventado=1)


def test_montar_chave_curso_normaliza_texto_da_pagina():
    chave = montar_chave_curso("UEM", " Engenharia de Controle e Automação - IA ", "Maringá/PR")
    assert chave == "uem:engenharia-de-controle-e-automacao-ia:maringa-pr"
    # A chave gerada sempre passa na validação do modelo.
    Curso(chave=chave, url_origem=URL, nome="Curso")


def test_montar_chave_curso_ignora_partes_vazias():
    assert montar_chave_curso("UEM", "", "Física") == "uem:fisica"
