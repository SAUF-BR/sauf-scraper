"""Formato do lote do Censo enviado para POST /api/v1/ingestao/censo.

Mapeamento coluna a coluna em docs/MAPEAMENTO_CENSO.md.
"""

from pydantic import Field

from sauf_scraper.core.models import Grau, Modalidade, SaufModel


class InstituicaoCenso(SaufModel):
    codigo_emec: int = Field(gt=0)
    nome: str = Field(min_length=1)
    sigla: str | None = None
    tipo: str = Field(pattern=r"^(publica|privada)$")
    categoria_administrativa: str | None = None
    organizacao_academica: str | None = None
    uf: str = Field(pattern=r"^[A-Z]{2}$")
    cidade: str = Field(min_length=1)


class OfertaCenso(SaufModel):
    codigo_emec: int = Field(gt=0)
    codigo_emec_instituicao: int = Field(gt=0)
    nome: str = Field(min_length=1)
    grau: Grau | None = None
    modalidade: Modalidade | None = None
    cidade: str | None = None
    uf: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    vagas: int | None = Field(default=None, ge=0)
    gratuito: bool | None = None
    codigo_cine_rotulo: str = Field(min_length=1)
    nome_cine_rotulo: str = Field(min_length=1)
    codigo_cine_area: str = Field(pattern=r"^\d{2}$")


class LoteCenso(SaufModel):
    ano_censo: int
    instituicoes: list[InstituicaoCenso]
    ofertas: list[OfertaCenso]
