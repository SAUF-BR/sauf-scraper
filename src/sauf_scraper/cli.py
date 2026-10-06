"""Ponto de entrada: `uv run sauf-scraper --help`."""

import argparse
import logging
import sys

from sauf_scraper.client.destinos import ApiSauf, ArquivoJson, Terminal
from sauf_scraper.client.http import HttpEducado
from sauf_scraper.core.config import Settings
from sauf_scraper.core.logging import configurar_logging
from sauf_scraper.core.pipeline import executar
from sauf_scraper.spiders import SPIDERS

logger = logging.getLogger("sauf_scraper")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sauf-scraper")
    parser.add_argument(
        "--ies", nargs="+", metavar="CHAVE", help="roda só estas instituições (padrão: todas)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="grava os lotes em JSON em vez de enviar para a API"
    )
    parser.add_argument(
        "--mostrar",
        action="store_true",
        help="imprime os cursos coletados na tela em vez de gravar ou enviar",
    )
    parser.add_argument("--listar", action="store_true", help="lista os spiders e sai")
    args = parser.parse_args(argv)

    configurar_logging()
    settings = Settings()

    if args.listar:
        for chave in sorted(SPIDERS):
            print(f"{chave}\te-MEC {SPIDERS[chave].codigo_emec}")
        return 0

    chaves = args.ies or sorted(SPIDERS)
    desconhecidas = [c for c in chaves if c not in SPIDERS]
    if desconhecidas:
        parser.error(f"spider(s) inexistente(s): {', '.join(desconhecidas)}")
    if not chaves:
        logger.warning("nenhum spider registrado em sauf_scraper/spiders/__init__.py")
        return 0

    if args.mostrar:
        destino = Terminal()
    elif args.dry_run:
        destino = ArquivoJson(settings.output_dir)
    else:
        destino = ApiSauf(settings)
    resumo = executar([SPIDERS[c] for c in chaves], HttpEducado(settings), destino)

    logger.info(
        "execução finalizada",
        extra={
            "dados": {
                "execucaoId": resumo.execucao_id,
                "resultados": [r.__dict__ for r in resumo.resultados],
            }
        },
    )
    # Código de saída != 0 faz o Jenkins/cron marcar a execução como falha.
    return 1 if resumo.houve_falha else 0


if __name__ == "__main__":
    sys.exit(main())
