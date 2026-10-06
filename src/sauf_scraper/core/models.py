"""Modelos Pydantic que definem o formato do lote enviado para a API.

Os campos de Curso seguem o Modelo de Dados (DER) atual. Dados da instituição
vêm do Censo da Educação Superior, não do scraper (ver LoteIngestao).
Campos que dependem de regra de negócio ainda em aberto estão marcados com
TODO e o número da pergunta em /scraper/01-analise-e-proposta.md, seção 5.

O JSON sai em camelCase (padrão do Jackson no Spring), enquanto o código
Python usa snake_case: o alias_generator faz a conversão.
"""

import re
import unicodedata
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
    SEMIPRESENCIAL = "SEMIPRESENCIAL"


class Grau(StrEnum):
    """Grau acadêmico, conforme TP_GRAU_ACADEMICO do Censo da Educação Superior."""

    BACHARELADO = "BACHARELADO"  # 1
    LICENCIATURA = "LICENCIATURA"  # 2
    TECNOLOGICO = "TECNOLOGICO"  # 3
    BACHARELADO_E_LICENCIATURA = "BACHARELADO_E_LICENCIATURA"  # 4


class Fonte(SaufModel):
    url: HttpUrl
    coletado_em: datetime = Field(default_factory=lambda: datetime.now(UTC))
    versao_scraper: str = "0.1.0"


_PARTE_CHAVE = r"[a-z0-9]+(?:-[a-z0-9]+)*"


def montar_chave_curso(*partes: str) -> str:
    """Monta a chave natural de um curso a partir de textos da página.

    Tira acentos, deixa tudo minúsculo, troca o que não for letra/número por "-" e junta
    as partes com ":". Use sempre esta função nos spiders, para a mesma página gerar
    sempre a mesma chave (senão o backend cria cursos duplicados).

    >>> montar_chave_curso("UEM", "Engenharia de Software", "Maringá", "Noturno")
    'uem:engenharia-de-software:maringa:noturno'
    """
    normalizadas = []
    for parte in partes:
        sem_acento = unicodedata.normalize("NFKD", parte).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
        if slug:
            normalizadas.append(slug)
    return ":".join(normalizadas)


class Curso(SaufModel):
    """Dados de UM curso coletados no site da instituição.

    O site da instituição é a fonte principal: o curso é aceito mesmo que não exista no
    Censo da Educação Superior. Quando existe, o código e-MEC liga os dois, e o Censo só
    completa o que o site não mostra (vagas, área Cine, gratuidade). Se site e Censo
    discordarem, vale o site. Mapeamento: docs/MAPEAMENTO_CENSO.md.
    """

    chave: str = Field(pattern=rf"^{_PARTE_CHAVE}(?::{_PARTE_CHAVE})*$")
    codigo_emec: int | None = Field(default=None, gt=0)
    url_origem: HttpUrl
    nome: str = Field(min_length=1)
    grau: Grau | None = None
    area_conhecimento: str | None = None
    modalidade: Modalidade | None = None
    duracao: str | None = None


class LoteIngestao(SaufModel):
    """Tudo que foi coletado de UMA instituição em UMA execução.

    A instituição em si NÃO vem do scraper: os dados dela (nome, tipo, UF etc.) são
    importados do Censo da Educação Superior em um fluxo separado. Aqui vai só o
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
