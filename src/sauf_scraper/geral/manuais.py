"""Dados cadastrados à mão (D-98 da API, ADR-BE-017): o que nenhuma fonte oficial entrega pronto.

- dados/ies/<sigla>.toml: ano de fundação, "sobre", site, logo e capa de cada universidade;
- dados/areas.toml: uma imagem por área Cine, usada nos cursos da área.

Os arquivos são TOML (lido pelo tomllib da biblioteca padrão, sem pacote novo) e as imagens
ficam ao lado deles, em img/. Este módulo valida tudo antes de enviar: campo faltando,
imagem que não existe, formato errado ou licença sem autor param o comando com uma mensagem
dizendo o arquivo e o campo. Passo a passo para quem vai preencher: dados/README.md.
"""

import base64
import re
import tomllib
from datetime import date
from pathlib import Path
from typing import Annotated

from pydantic import Field, HttpUrl, ValidationError, field_validator

from sauf_scraper.core.config import RAIZ_PROJETO
from sauf_scraper.core.models import SaufModel

DADOS = RAIZ_PROJETO / "dados"
PASTA_IES = DADOS / "ies"
ARQUIVO_AREAS = DADOS / "areas.toml"

ENDPOINT_UNIVERSIDADE = "/api/v1/ingestao/universidades/{codigo_emec}"
ENDPOINT_AREA = "/api/v1/ingestao/areas/{codigo_cine}/imagem"

# Mesmo limite e mesmos formatos que a API confere (TipoImagem, D-81)
TAMANHO_MAXIMO = 2 * 1024 * 1024
ASSINATURAS = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
}
COMMONS = "https://commons.wikimedia.org/wiki/File:"


class DadoManualInvalidoError(Exception):
    """Arquivo de dados manuais com problema. A mensagem diz o arquivo e o que corrigir."""


Paragrafo = Annotated[str, Field(min_length=1, max_length=2000)]


class ImagemManual(SaufModel):
    """Imagem tirada do Wikimedia Commons, com o crédito que a licença pede (D-100)."""

    arquivo: str
    autor: str = Field(min_length=1, max_length=300)
    licenca: str = Field(min_length=1, max_length=100)
    licenca_url: HttpUrl | None = None
    fonte_url: HttpUrl

    @field_validator("fonte_url")
    @classmethod
    def _do_commons(cls, url: HttpUrl) -> HttpUrl:
        if not str(url).startswith(COMMONS):
            raise ValueError(f"use a página do arquivo no Wikimedia Commons ({COMMONS}...)")
        return url


class FontesUniversidade(SaufModel):
    """De onde veio cada dado escrito à mão: quem for conferir abre esses links."""

    ano_fundacao: HttpUrl
    sobre: list[HttpUrl] = Field(min_length=1)


class UniversidadeManual(SaufModel):
    sigla: str = Field(min_length=2, max_length=20)
    codigo_emec: int = Field(gt=0)
    nome: str
    ano_fundacao: int = Field(ge=1500)
    site_url: HttpUrl
    sobre: list[Paragrafo] = Field(min_length=1, max_length=5)
    fontes: FontesUniversidade
    logo: ImagemManual | None = None
    capa: ImagemManual | None = None

    @field_validator("ano_fundacao")
    @classmethod
    def _nao_no_futuro(cls, ano: int) -> int:
        if ano > date.today().year:
            raise ValueError("o ano de fundação não pode estar no futuro")
        return ano

    @field_validator("sobre", mode="before")
    @classmethod
    def _um_paragrafo_por_item(cls, sobre: list[str]) -> list[str]:
        # A quebra de linha dentro de um parágrafo do TOML é só para caber na tela: vira espaço
        if not isinstance(sobre, list):
            return sobre
        paragrafos = []
        for texto in sobre:
            if not isinstance(texto, str):
                return sobre
            if re.search(r"\n\s*\n", texto.strip()):
                raise ValueError("cada parágrafo vai num item separado da lista")
            paragrafos.append(re.sub(r"\s+", " ", texto).strip())
        return paragrafos


class AreaManual(SaufModel):
    codigo_cine: str = Field(pattern=r"^\d{2}$")
    nome: str
    # Sem [area.imagem] a área fica de fora do envio (imagem ainda não escolhida ou baixada)
    imagem: ImagemManual | None = None


class ArquivoAreas(SaufModel):
    area: list[AreaManual] = Field(min_length=1)


# ---------- O que vai para a API (camelCase, como os outros lotes) ----------


class ImagemEnvio(SaufModel):
    conteudo_base64: str
    autor: str
    licenca: str
    licenca_url: HttpUrl | None
    fonte_url: HttpUrl


class DadosUniversidadeEnvio(SaufModel):
    ano_fundacao: int
    sobre: list[str]
    site_url: HttpUrl
    logo: ImagemEnvio | None
    capa: ImagemEnvio | None


# ---------- Leitura e validação ----------


def ler_toml(caminho: Path) -> dict:
    try:
        with caminho.open("rb") as arquivo:
            return tomllib.load(arquivo)
    except FileNotFoundError:
        raise DadoManualInvalidoError(f"{caminho}: arquivo não encontrado") from None
    except tomllib.TOMLDecodeError as erro:
        raise DadoManualInvalidoError(f"{caminho}: TOML inválido ({erro})") from None


def validar(modelo: type[SaufModel], dados: dict, caminho: Path):
    try:
        return modelo.model_validate(dados)
    except ValidationError as erro:
        problemas = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or '(arquivo)'}: {e['msg']}"
            for e in erro.errors()
        )
        raise DadoManualInvalidoError(f"{caminho}: {problemas}") from None


def ler_universidade(caminho: Path) -> UniversidadeManual:
    universidade = validar(UniversidadeManual, ler_toml(caminho), caminho)
    if universidade.sigla.lower() != caminho.stem.lower():
        raise DadoManualInvalidoError(
            f"{caminho}: a sigla '{universidade.sigla}' não bate com o nome do arquivo"
        )
    for campo in ("logo", "capa"):
        imagem = getattr(universidade, campo)
        if imagem is not None:
            ler_imagem(caminho.parent / imagem.arquivo, f"{caminho}: {campo}")
    return universidade


def ler_universidades(siglas: list[str] | None = None, pasta: Path | None = None) -> list:
    pasta = pasta or PASTA_IES
    arquivos = sorted(pasta.glob("*.toml"))
    if siglas:
        pedidas = {s.lower() for s in siglas}
        faltando = pedidas - {a.stem.lower() for a in arquivos}
        if faltando:
            raise DadoManualInvalidoError(
                f"sem arquivo em {pasta} para: {', '.join(sorted(faltando))}"
            )
        arquivos = [a for a in arquivos if a.stem.lower() in pedidas]
    return [(ler_universidade(a), a) for a in arquivos]


def ler_areas(
    caminho: Path | None = None, codigos: list[str] | None = None
) -> list[AreaManual]:
    caminho = caminho or ARQUIVO_AREAS
    areas = validar(ArquivoAreas, ler_toml(caminho), caminho).area
    codigos_lidos = [a.codigo_cine for a in areas]
    repetidas = {c for c in codigos_lidos if codigos_lidos.count(c) > 1}
    if repetidas:
        raise DadoManualInvalidoError(f"{caminho}: área repetida: {', '.join(sorted(repetidas))}")
    for area in areas:
        if area.imagem is not None:
            ler_imagem(caminho.parent / area.imagem.arquivo, f"{caminho}: área {area.codigo_cine}")
    if codigos:
        areas = [a for a in areas if a.codigo_cine in codigos]
    return areas


def ler_imagem(caminho: Path, onde: str) -> bytes:
    """Bytes da imagem, conferindo que existe, cabe em 2 MB e é JPG, PNG ou WebP."""
    if not caminho.is_file():
        raise DadoManualInvalidoError(f"{onde}: imagem não encontrada em {caminho}")
    conteudo = caminho.read_bytes()
    if len(conteudo) > TAMANHO_MAXIMO:
        raise DadoManualInvalidoError(
            f"{onde}: {caminho.name} tem {len(conteudo) // 1024} KB; o limite é 2 MB "
            "(baixe um tamanho menor no Commons)"
        )
    if tipo_imagem(conteudo) is None:
        raise DadoManualInvalidoError(
            f"{onde}: {caminho.name} não é JPG, PNG nem WebP (SVG não serve: baixe o PNG)"
        )
    return conteudo


def tipo_imagem(conteudo: bytes) -> str | None:
    for assinatura, tipo in ASSINATURAS.items():
        if conteudo.startswith(assinatura):
            return tipo
    if conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP":
        return "image/webp"
    return None


# ---------- Montagem do envio ----------


def imagem_envio(imagem: ImagemManual | None, pasta: Path) -> ImagemEnvio | None:
    if imagem is None:
        return None
    conteudo = (pasta / imagem.arquivo).read_bytes()
    return ImagemEnvio(
        conteudo_base64=base64.b64encode(conteudo).decode("ascii"),
        autor=imagem.autor,
        licenca=imagem.licenca,
        licenca_url=imagem.licenca_url,
        fonte_url=imagem.fonte_url,
    )


def envio_universidade(universidade: UniversidadeManual, pasta: Path) -> DadosUniversidadeEnvio:
    return DadosUniversidadeEnvio(
        ano_fundacao=universidade.ano_fundacao,
        sobre=universidade.sobre,
        site_url=universidade.site_url,
        logo=imagem_envio(universidade.logo, pasta),
        capa=imagem_envio(universidade.capa, pasta),
    )


def resumo_universidade(universidade: UniversidadeManual) -> str:
    imagens = ", ".join(
        f"{campo} {getattr(universidade, campo).licenca}"
        for campo in ("logo", "capa")
        if getattr(universidade, campo) is not None
    )
    return (
        f"{universidade.sigla} (e-MEC {universidade.codigo_emec}): fundada em "
        f"{universidade.ano_fundacao}, {len(universidade.sobre)} parágrafo(s), "
        f"{imagens or 'sem imagens'}"
    )
