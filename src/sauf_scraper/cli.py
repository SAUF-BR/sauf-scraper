"""Ponto de entrada: `uv run sauf-scraper --help`."""

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

from sauf_scraper.censo.casamento import caminho_tabela, gerar_tabela, gravar_tabela
from sauf_scraper.censo.leitor import ler_censo
from sauf_scraper.client.destinos import ApiSauf, ArquivoJson, Terminal
from sauf_scraper.client.http import HttpEducado
from sauf_scraper.core.config import Settings
from sauf_scraper.core.logging import configurar_logging
from sauf_scraper.core.models import LoteIngestao
from sauf_scraper.core.pipeline import executar
from sauf_scraper.spiders import SPIDERS, codigos_emec

logger = logging.getLogger("sauf_scraper")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["censo"]:
        return main_censo(argv[1:])
    if argv[:1] == ["casar"]:
        return main_casar(argv[1:])

    parser = argparse.ArgumentParser(
        prog="sauf-scraper", epilog="Import do Censo: sauf-scraper censo --help"
    )
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
    return 1 if resumo.houve_falha else 0


def main_censo(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sauf-scraper censo",
        description="Lê os microdados do Censo e envia instituições e ofertas das IES com spider.",
    )
    parser.add_argument("--pasta", type=Path, help="pasta dos microdados (padrão: SAUF_CENSO_DIR)")
    parser.add_argument(
        "--dry-run", action="store_true", help="grava output/censo-<ano>.json em vez de enviar"
    )
    parser.add_argument("--mostrar", action="store_true", help="imprime o resultado na tela")
    args = parser.parse_args(argv)

    configurar_logging()
    settings = Settings()
    codigos = codigos_emec()
    if not codigos:
        logger.warning("nenhum spider registrado: nada para importar do Censo")
        return 0

    lote = ler_censo(args.pasta or settings.censo_dir, codigos)
    logger.info(
        "censo lido",
        extra={
            "dados": {
                "ano": lote.ano_censo,
                "instituicoes": len(lote.instituicoes),
                "ofertas": len(lote.ofertas),
            }
        },
    )

    if args.mostrar:
        Terminal().enviar_censo(lote)
    elif args.dry_run:
        ArquivoJson(settings.output_dir).enviar_censo(lote)
    else:
        resposta = ApiSauf(settings).enviar_censo(lote)
        logger.info("censo enviado", extra={"dados": {"resposta": resposta.model_dump()}})
    return 0


def main_casar(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sauf-scraper casar",
        description=(
            "Gera a tabela de casamento curso do site -> código e-MEC "
            "(spiders/dados/<ies>_codigos.csv), preservando as linhas já confirmadas."
        ),
    )
    parser.add_argument("--ies", required=True, metavar="CHAVE", help="spider, ex.: uem")
    parser.add_argument(
        "--lote", type=Path, help="JSON do --dry-run do spider (padrão: output/emec-<codigo>.json)"
    )
    parser.add_argument("--pasta", type=Path, help="pasta dos microdados (padrão: SAUF_CENSO_DIR)")
    args = parser.parse_args(argv)

    configurar_logging()
    settings = Settings()
    if args.ies not in SPIDERS:
        parser.error(f"spider inexistente: {args.ies}")
    spider = SPIDERS[args.ies]
    arquivo_lote = args.lote or settings.output_dir / f"emec-{spider.codigo_emec}.json"
    lote = LoteIngestao.model_validate_json(arquivo_lote.read_text(encoding="utf-8"))

    tabela = gerar_tabela(lote.cursos, args.pasta or settings.censo_dir, spider.codigo_emec)
    destino = caminho_tabela(spider.chave)
    gravar_tabela(destino, tabela)

    paginas = Counter(dict({linha.chave: linha.status for linha in tabela}).values())
    print(f"{destino}: páginas por status {dict(paginas)}, {len(tabela)} linha(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
