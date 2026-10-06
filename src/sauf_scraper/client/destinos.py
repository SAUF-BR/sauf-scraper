"""Para onde vai cada lote coletado: API do SAUF (produção), arquivo JSON (dry-run)
ou a tela do terminal (--mostrar).

As classes têm o mesmo método `enviar(lote)`. O pipeline não sabe qual está
usando, igual a injetar uma interface no Spring e trocar a implementação.
"""

import json
import logging
from pathlib import Path
from typing import Protocol

import requests

from sauf_scraper.core.config import Settings
from sauf_scraper.core.models import LoteIngestao, RespostaIngestao

logger = logging.getLogger(__name__)

ENDPOINT_LOTES = "/api/v1/ingestao/lotes"


class Destino(Protocol):
    def enviar(self, lote: LoteIngestao) -> RespostaIngestao | None: ...


class ApiRecusouLoteError(Exception):
    def __init__(self, status: int, corpo: str) -> None:
        super().__init__(f"API respondeu {status}: {corpo[:500]}")
        self.status = status
        self.corpo = corpo


class ApiSauf:
    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self._settings = settings
        self._session = session or requests.Session()
        if settings.api_key is not None:
            self._session.headers["X-Api-Key"] = settings.api_key.get_secret_value()

    def enviar(self, lote: LoteIngestao) -> RespostaIngestao:
        url = self._settings.api_base_url.rstrip("/") + ENDPOINT_LOTES
        resposta = self._session.post(
            url,
            json=lote.model_dump(mode="json", by_alias=True),
            timeout=self._settings.api_timeout_seconds,
        )
        if not resposta.ok:
            raise ApiRecusouLoteError(resposta.status_code, resposta.text)
        return RespostaIngestao.model_validate(resposta.json())


class Terminal:
    """Modo --mostrar: imprime os cursos coletados de forma legível, sem gravar nem enviar."""

    def enviar(self, lote: LoteIngestao) -> None:
        print()
        print(f"=== Instituição e-MEC {lote.codigo_emec_instituicao}: {len(lote.cursos)} curso(s)")
        for curso in lote.cursos:
            print()
            print(curso.nome)
            campos = {
                "chave": curso.chave,
                "código e-MEC": curso.codigo_emec,
                "grau": curso.grau,
                "duração": curso.duracao,
                "link": curso.url_origem,
            }
            for rotulo, valor in campos.items():
                print(f"  {rotulo + ':':<14}{valor or '-'}")
        print()
        return None


class ArquivoJson:
    """Modo --dry-run: grava o lote em output/emec-<codigo>.json em vez de enviar."""

    def __init__(self, pasta: Path) -> None:
        self._pasta = pasta

    def enviar(self, lote: LoteIngestao) -> None:
        self._pasta.mkdir(parents=True, exist_ok=True)
        caminho = self._pasta / f"emec-{lote.codigo_emec_instituicao}.json"
        conteudo = lote.model_dump(mode="json", by_alias=True)
        caminho.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("lote gravado", extra={"dados": {"arquivo": str(caminho)}})
        return None
