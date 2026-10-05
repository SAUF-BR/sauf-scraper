import pytest

from sauf_scraper.core.config import Settings
from sauf_scraper.core.models import Curso, Fonte, LoteIngestao


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        api_base_url="http://api.teste",
        api_key="segredo",
        request_delay_seconds=0,
        output_dir=tmp_path / "output",
    )


@pytest.fixture
def lote() -> LoteIngestao:
    return LoteIngestao(
        execucao_id="teste",
        fonte=Fonte(url="https://www.exemplo.br/cursos"),
        codigo_emec_instituicao=57,
        cursos=[Curso(chave="exemplo:engenharia-civil", nome="Engenharia Civil")],
    )
