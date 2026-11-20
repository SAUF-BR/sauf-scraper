"""Calendário de vestibulares (D-104 a D-106 da API): datas oficiais cadastradas à mão.

As datas ficam em dados/calendario.toml, um bloco [[evento]] por evento, sempre com a página
oficial de onde vieram (edital, cronograma ou notícia da instituição). Data que a fonte ainda
não publicou ("a divulgar") não entra: fica como comentário no arquivo até sair. Cada evento vai
para a API por PUT na chave dele, então reenviar o arquivo não duplica nada. Passo a passo:
dados/README.md, seção "Calendário".
"""

from datetime import date
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, HttpUrl, model_validator

from sauf_scraper.core.models import SaufModel
from sauf_scraper.geral.manuais import (
    DADOS,
    PASTA_IES,
    DadoManualInvalidoError,
    ler_toml,
    validar,
)

ARQUIVO_CALENDARIO = DADOS / "calendario.toml"
ENDPOINT_EVENTO = "/api/v1/admin/calendario/eventos/{chave}"

TipoEvento = Literal["inscricao", "prova", "resultado", "feira", "outro"]


class EventoManual(SaufModel):
    # Nome estável: trocar a chave cria outro evento na API (o antigo fica até ser removido)
    chave: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=100)
    titulo: str = Field(min_length=1, max_length=200)
    tipo: TipoEvento
    inicio: date
    fim: date | None = None
    # Sigla de dados/ies/<sigla>.toml; sem sigla = evento nacional (ENEM, ProUni)
    sigla: str | None = None
    descricao: str | None = Field(default=None, max_length=1000)
    fonte_url: HttpUrl
    ano: int = Field(ge=2000, le=2100)

    @model_validator(mode="after")
    def _fim_depois_do_inicio(self) -> Self:
        if self.fim is not None and self.fim < self.inicio:
            raise ValueError("o fim não pode ser antes do início")
        return self


class ArquivoCalendario(SaufModel):
    evento: list[EventoManual] = Field(min_length=1)


class EventoEnvio(SaufModel):
    titulo: str
    tipo: TipoEvento
    inicio: date
    fim: date | None
    codigo_emec_instituicao: int | None
    descricao: str | None
    fonte_url: HttpUrl
    ano_referencia: int


def codigos_emec(pasta: Path | None = None) -> dict[str, int]:
    """Sigla (minúscula) -> código e-MEC, lido dos arquivos das universidades."""
    pasta = pasta or PASTA_IES
    return {
        caminho.stem.lower(): int(ler_toml(caminho)["codigo_emec"])
        for caminho in sorted(pasta.glob("*.toml"))
    }


def ler_eventos(
    caminho: Path | None = None,
    chaves: list[str] | None = None,
    pasta_ies: Path | None = None,
) -> list[tuple[EventoManual, EventoEnvio]]:
    caminho = caminho or ARQUIVO_CALENDARIO
    eventos = validar(ArquivoCalendario, ler_toml(caminho), caminho).evento
    lidas = [e.chave for e in eventos]
    repetidas = {c for c in lidas if lidas.count(c) > 1}
    if repetidas:
        raise DadoManualInvalidoError(f"{caminho}: chave repetida: {', '.join(sorted(repetidas))}")
    codigos = codigos_emec(pasta_ies)
    sem_arquivo = sorted({e.sigla for e in eventos if e.sigla and e.sigla.lower() not in codigos})
    if sem_arquivo:
        raise DadoManualInvalidoError(
            f"{caminho}: sigla sem arquivo em {pasta_ies or PASTA_IES}: {', '.join(sem_arquivo)}"
        )
    if chaves:
        faltando = sorted(set(chaves) - set(lidas))
        if faltando:
            raise DadoManualInvalidoError(f"{caminho}: chave não encontrada: {', '.join(faltando)}")
        eventos = [e for e in eventos if e.chave in chaves]
    return [(e, envio(e, codigos)) for e in eventos]


def envio(evento: EventoManual, codigos: dict[str, int]) -> EventoEnvio:
    return EventoEnvio(
        titulo=evento.titulo,
        tipo=evento.tipo,
        inicio=evento.inicio,
        fim=evento.fim,
        codigo_emec_instituicao=codigos[evento.sigla.lower()] if evento.sigla else None,
        descricao=evento.descricao,
        fonte_url=evento.fonte_url,
        ano_referencia=evento.ano,
    )


def resumo(evento: EventoManual) -> str:
    quando = evento.inicio.strftime("%d/%m/%Y")
    if evento.fim is not None:
        quando += " a " + evento.fim.strftime("%d/%m/%Y")
    return f"{quando:<23} {evento.tipo:<9} {evento.sigla or '-':<6} {evento.titulo}"
