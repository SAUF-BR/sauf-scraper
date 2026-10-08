import pytest

from sauf_scraper.core.config import Settings
from sauf_scraper.core.models import Curso, Fonte, Grau, LoteIngestao, Modalidade, Opcao


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
        cursos=[
            # Curso que existe no Censo: tem código e-MEC.
            Curso(
                chave="uem:engenharia-civil:maringa:integral",
                codigos_emec=[3402],
                url_origem="https://www.exemplo.br/curso/abc123",
                nome="Engenharia Civil",
                opcoes=[Opcao(grau=Grau.BACHARELADO, turno="Integral")],
                modalidade=Modalidade.PRESENCIAL,
                turno="Integral",
                duracao_texto="5 anos",
                duracao_semestres=10,
                cidade="Maringá",
                uf="PR",
            ),
            # Curso novo, ainda fora do Censo: sem código e-MEC, mas aceito.
            Curso(
                chave="uem:engenharia-de-software:maringa:noturno",
                url_origem="https://www.exemplo.br/curso/def456",
                nome="Engenharia de Software",
            ),
        ],
    )
