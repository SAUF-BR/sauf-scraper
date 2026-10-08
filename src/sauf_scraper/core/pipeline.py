"""Orquestra a execução: roda cada spider isolado e envia o lote para o destino.

Regra principal (contexto consolidado, seção 5): a falha de uma instituição
nunca derruba as outras. Cada falha vira um registro no resumo e no log.
"""

import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import ValidationError

from sauf_scraper.client.destinos import Destino
from sauf_scraper.client.http import HttpEducado
from sauf_scraper.spiders.base import Spider

logger = logging.getLogger(__name__)


@dataclass
class ResultadoSpider:
    chave: str
    sucesso: bool
    cursos: int = 0
    erro: str | None = None
    segundos: float = 0.0


@dataclass
class ResumoExecucao:
    execucao_id: str
    resultados: list[ResultadoSpider] = field(default_factory=list)

    @property
    def houve_falha(self) -> bool:
        return any(not r.sucesso for r in self.resultados)


def novo_execucao_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def executar(
    spiders: Iterable[type[Spider]],
    http: HttpEducado,
    destino: Destino,
    execucao_id: str | None = None,
) -> ResumoExecucao:
    resumo = ResumoExecucao(execucao_id=execucao_id or novo_execucao_id())

    for classe in spiders:
        inicio = time.monotonic()
        try:
            lote = classe(http, resumo.execucao_id).coletar()
            resposta = destino.enviar(lote)
            resultado = ResultadoSpider(classe.chave, sucesso=True, cursos=len(lote.cursos))
            logger.info(
                "spider ok",
                extra={
                    "dados": {
                        "spider": classe.chave,
                        "cursos": len(lote.cursos),
                        "resposta": resposta.model_dump() if resposta else None,
                    }
                },
            )
        except ValidationError as e:
            # Dado incompleto/errado: o site provavelmente mudou de layout.
            resultado = ResultadoSpider(
                classe.chave, sucesso=False, erro=f"validação: {e.error_count()} erro(s)"
            )
            logger.error(
                "spider gerou dado inválido",
                exc_info=True,
                extra={"dados": {"spider": classe.chave}},
            )
        except Exception as e:  # isolamento de falhas é intencional!!!
            resultado = ResultadoSpider(
                classe.chave, sucesso=False, erro=f"{type(e).__name__}: {e}"
            )
            logger.error("spider falhou", exc_info=True, extra={"dados": {"spider": classe.chave}})
        resultado.segundos = round(time.monotonic() - inicio, 2)
        resumo.resultados.append(resultado)

    return resumo
