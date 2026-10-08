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

from sauf_scraper.censo.modelos import LoteCenso
from sauf_scraper.core.config import Settings
from sauf_scraper.core.models import LoteIngestao, RespostaIngestao, SaufModel

logger = logging.getLogger(__name__)

ENDPOINT_LOTES = "/api/v1/ingestao/lotes"
ENDPOINT_CENSO = "/api/v1/ingestao/censo"


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
        return self._post(ENDPOINT_LOTES, lote)

    def enviar_censo(self, lote: LoteCenso) -> RespostaIngestao:
        return self._post(ENDPOINT_CENSO, lote)

    def _post(self, endpoint: str, corpo: SaufModel) -> RespostaIngestao:
        url = self._settings.api_base_url.rstrip("/") + endpoint
        resposta = self._session.post(
            url,
            json=corpo.model_dump(mode="json", by_alias=True),
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
            opcoes = "; ".join(
                f"{o.grau.value} ({o.turno})" if o.turno else o.grau.value for o in curso.opcoes
            )
            campos = {
                "chave": curso.chave,
                "códigos e-MEC": ", ".join(str(c) for c in curso.codigos_emec),
                "opções": opcoes,
                "modalidade": curso.modalidade,
                "turno": curso.turno,
                "sobre": _resumo(curso.sobre),
                "duração": curso.duracao_texto,
                "semestres": curso.duracao_semestres,
                "cidade": f"{curso.cidade}/{curso.uf}" if curso.cidade else None,
                "link": curso.url_origem,
            }
            for rotulo, valor in campos.items():
                print(f"  {rotulo + ':':<14}{valor or '-'}")
        print()
        return None

    def enviar_censo(self, lote: LoteCenso) -> None:
        print()
        print(f"=== Censo {lote.ano_censo}: {len(lote.instituicoes)} instituição(ões)")
        for ies in lote.instituicoes:
            ofertas = [o for o in lote.ofertas if o.codigo_emec_instituicao == ies.codigo_emec]
            print()
            print(f"{ies.nome} ({ies.sigla or '-'}) e-MEC {ies.codigo_emec}, {ies.cidade}/{ies.uf}")
            print(f"  {len(ofertas)} oferta(s)")
            for o in ofertas:
                local = f"{o.cidade}/{o.uf}" if o.cidade else "-"
                print(
                    f"  {o.codigo_emec:>8}  {o.nome:<40.40} {o.grau or '-':<13} "
                    f"{o.modalidade or '-':<11} {local:<22} Cine: {o.nome_cine_rotulo}"
                )
        print()
        return None


def _resumo(texto: str | None, limite: int = 80) -> str | None:
    """Primeira linha do texto, cortada, para caber numa linha do terminal."""
    if not texto:
        return None
    linha = texto.split("\n", 1)[0]
    return linha if len(linha) <= limite else linha[: limite - 3] + "..."


class ArquivoJson:
    """Modo --dry-run: grava o lote em output/emec-<codigo>.json em vez de enviar."""

    def __init__(self, pasta: Path) -> None:
        self._pasta = pasta

    def enviar(self, lote: LoteIngestao) -> None:
        self._pasta.mkdir(parents=True, exist_ok=True)
        self._gravar(self._pasta / f"emec-{lote.codigo_emec_instituicao}.json", lote)
        return None

    def enviar_censo(self, lote: LoteCenso) -> None:
        self._pasta.mkdir(parents=True, exist_ok=True)
        self._gravar(self._pasta / f"censo-{lote.ano_censo}.json", lote)
        return None

    def _gravar(self, caminho: Path, lote: SaufModel) -> None:
        conteudo = lote.model_dump(mode="json", by_alias=True)
        caminho.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("lote gravado", extra={"dados": {"arquivo": str(caminho)}})
