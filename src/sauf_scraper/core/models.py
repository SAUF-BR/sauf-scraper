"""Modelos Pydantic que definem o formato do lote enviado para a API.

Os campos de Curso seguem o Modelo de Dados (DER) atual. Dados da instituição
vêm do e-MEC, não do scraper (ver LoteIngestao).
Campos que dependem de regra de negócio ainda em aberto estão marcados com
TODO e o número da pergunta em /scraper/01-analise-e-proposta.md, seção 5.

O JSON sai em camelCase (padrão do Jackson no Spring), enquanto o código
Python usa snake_case: o alias_generator faz a conversão.
"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from pydantic.alias_generators import to_camel


class SaufModel(BaseModel):
    """Base comum: camelCase no JSON e erro se aparecer campo desconhecido."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class Modalidade(StrEnum):
    PRESENCIAL = "PRESENCIAL"
    EAD = "EAD"
    HIBRIDO = "HIBRIDO"


class Fonte(SaufModel):
    url: HttpUrl
    coletado_em: datetime = Field(default_factory=lambda: datetime.now(UTC))
    versao_scraper: str = "0.1.0"


class Curso(SaufModel):
    # Chave natural do curso (ex.: "uel:engenharia-civil"). Formato final depende
    # de como o negócio diferencia cursos iguais em campus/turnos diferentes.
    chave: str = Field(pattern=r"^[a-z0-9:-]+$")
    nome: str = Field(min_length=1)
    area_conhecimento: str | None = None
    modalidade: Modalidade | None = None
    duracao: str | None = None
    # TODO(pergunta 2): formas de ingresso, cidade/campus, turno, vagas etc.
    # TODO: definir com o time quais campos são obrigatórios para o curso ser publicado.


class LoteIngestao(SaufModel):
    """Tudo que foi coletado de UMA instituição em UMA execução.

    A instituição em si NÃO vem do scraper: os dados dela (nome, tipo, UF etc.) são
    importados do cadastro e-MEC (dados abertos) em um fluxo separado. Aqui vai só o
    código e-MEC, e o backend recusa o lote se a instituição ainda não estiver cadastrada.
    """

    execucao_id: str
    fonte: Fonte
    codigo_emec_instituicao: int = Field(gt=0)
    cursos: list[Curso]


class RespostaIngestao(SaufModel):
    """Resposta esperada da API (rascunho do contrato v0)."""

    model_config = ConfigDict(extra="ignore")

    criados: int = 0
    atualizados: int = 0
    inalterados: int = 0
    inativados: int = 0
    rejeitados: list[str] = Field(default_factory=list)
