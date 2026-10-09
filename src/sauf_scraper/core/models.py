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
from typing import Annotated

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
    """Valores em minúsculas, iguais ao contrato da API (D-30 em sauf-api/docs/DECISOES.md)."""

    PRESENCIAL = "presencial"
    EAD = "ead"
    SEMIPRESENCIAL = "semipresencial"


class Grau(StrEnum):
    """Grau acadêmico, conforme TP_GRAU_ACADEMICO do Censo da Educação Superior."""

    BACHARELADO = "bacharelado"  # 1
    LICENCIATURA = "licenciatura"  # 2
    TECNOLOGICO = "tecnologo"  # 3
    BACHARELADO_E_LICENCIATURA = "bacharelado_e_licenciatura"  # 4


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


_DURACAO = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(anos?|semestres?)\s*$", re.IGNORECASE)


def semestres_de_texto(texto: str | None) -> int | None:
    """Converte a duração escrita no site em semestres, quando ela é simples.

    "5 anos" -> 10, "3,5 anos" -> 7, "8 semestres" -> 8,
    "Bacharelado: 4 anos / Licenciatura: 5 anos" -> None.
    """
    if not texto:
        return None
    encontrado = _DURACAO.match(texto)
    if not encontrado:
        return None
    numero = float(encontrado.group(1).replace(",", "."))
    semestres = numero * 2 if encontrado.group(2).lower().startswith("ano") else numero
    return int(semestres) if semestres > 0 and semestres.is_integer() else None


class Opcao(SaufModel):
    """Um grau que a página oferece, com o turno que a página dá para ele (se der)."""

    grau: Grau
    turno: str | None = None


class Curso(SaufModel):
    """UM curso como aparece no site da instituição: uma página = um curso (D-34).

    O site da instituição é a fonte principal (D-33): o curso é aceito mesmo que não exista
    no Censo da Educação Superior. Os códigos e-MEC confirmados da página (D-35, uso interno)
    ligam o curso ao Censo, que só completa o que o site não mostra (área, vagas,
    gratuidade). Mapeamento: docs/MAPEAMENTO_CENSO.md.
    """

    chave: str = Field(pattern=rf"^{_PARTE_CHAVE}(?::{_PARTE_CHAVE})*$")
    codigos_emec: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list)
    url_origem: HttpUrl
    nome: str = Field(min_length=1)
    opcoes: list[Opcao] = Field(default_factory=list)
    modalidade: Modalidade | None = None
    turno: str | None = None
    sobre: str | None = None
    mercado_trabalho: str | None = None
    duracao_texto: str | None = None
    duracao_semestres: int | None = Field(default=None, gt=0)
    cidade: str | None = None
    uf: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")


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
