import pytest
from pydantic import ValidationError

from sauf_scraper.core.models import Curso, LoteIngestao


def test_json_sai_em_camel_case(lote):
    dados = lote.model_dump(mode="json", by_alias=True)
    assert "execucaoId" in dados
    assert dados["codigoEmecInstituicao"] == 57
    assert "instituicao" not in dados
    assert "areaConhecimento" in dados["cursos"][0]


def test_codigo_emec_precisa_ser_positivo(lote):
    dados = lote.model_dump() | {"codigo_emec_instituicao": 0}
    with pytest.raises(ValidationError):
        LoteIngestao(**dados)


def test_nome_vazio_e_rejeitado():
    with pytest.raises(ValidationError):
        Curso(chave="x:y", nome="   ")


def test_chave_com_maiuscula_ou_espaco_e_rejeitada():
    with pytest.raises(ValidationError):
        Curso(chave="UEL Civil", nome="Engenharia Civil")


def test_campo_desconhecido_e_rejeitado():
    with pytest.raises(ValidationError):
        Curso(chave="x:y", nome="Curso", campo_inventado=1)
