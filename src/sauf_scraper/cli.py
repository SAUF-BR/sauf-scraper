"""Ponto de entrada: `uv run sauf-scraper --help`."""

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

from sauf_scraper.censo.casamento import (
    caminho_tabela,
    codigos_confirmados,
    gerar_tabela,
    gravar_tabela,
)
from sauf_scraper.censo.leitor import ler_censo
from sauf_scraper.client.destinos import ApiRecusouLoteError, ApiSauf, ArquivoJson, Terminal
from sauf_scraper.client.http import HttpEducado
from sauf_scraper.core.config import Settings, resolver_pasta_censo
from sauf_scraper.core.logging import configurar_logging
from sauf_scraper.core.models import LoteIngestao
from sauf_scraper.core.pipeline import executar
from sauf_scraper.geral import calendario, enem, igc, manuais, sisu
from sauf_scraper.geral.base import entregar
from sauf_scraper.spiders import SPIDERS, codigos_emec

logger = logging.getLogger("sauf_scraper")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["censo"]:
        return main_censo(argv[1:])
    if argv[:1] == ["casar"]:
        return main_casar(argv[1:])
    if argv[:1] == ["igc"]:
        return main_igc(argv[1:])
    if argv[:1] == ["sisu"]:
        return main_sisu(argv[1:])
    if argv[:1] == ["questoes"]:
        return main_questoes(argv[1:])
    if argv[:1] == ["ies"]:
        return main_ies(argv[1:])
    if argv[:1] == ["areas"]:
        return main_areas(argv[1:])
    if argv[:1] == ["calendario"]:
        return main_calendario(argv[1:])

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
    parser.add_argument(
        "--pasta",
        type=Path,
        help="pasta dos microdados (padrão: SAUF_CENSO_DIR ou fontes/microdados_censo*)",
    )
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

    lote = ler_censo(resolver_pasta_censo(args.pasta or settings.censo_dir), codigos)
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
    parser.add_argument(
        "--pasta",
        type=Path,
        help="pasta dos microdados (padrão: SAUF_CENSO_DIR ou fontes/microdados_censo*)",
    )
    args = parser.parse_args(argv)

    configurar_logging()
    settings = Settings()
    if args.ies not in SPIDERS:
        parser.error(f"spider inexistente: {args.ies}")
    spider = SPIDERS[args.ies]
    arquivo_lote = args.lote or settings.output_dir / f"emec-{spider.codigo_emec}.json"
    lote = LoteIngestao.model_validate_json(arquivo_lote.read_text(encoding="utf-8"))

    pasta = resolver_pasta_censo(args.pasta or settings.censo_dir)
    tabela = gerar_tabela(lote.cursos, pasta, spider.codigo_emec)
    destino = caminho_tabela(spider.chave)
    gravar_tabela(destino, tabela)

    paginas = Counter(dict({linha.chave: linha.status for linha in tabela}).values())
    print(f"{destino}: páginas por status {dict(paginas)}, {len(tabela)} linha(s)")
    return 0


def main_igc(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sauf-scraper igc",
        description="Lê a planilha do IGC (INEP) e envia a nota MEC das IES do escopo.",
    )
    parser.add_argument("--arquivo", type=Path, required=True, help="ex.: fontes/IGC_2023.xlsx")
    parser.add_argument(
        "--dry-run", action="store_true", help="grava output/igc-<ano>.json em vez de enviar"
    )
    args = parser.parse_args(argv)

    configurar_logging()
    lote, relatorio = igc.ler_igc(args.arquivo, codigos_emec())
    relatorio.registrar()
    resposta = entregar(lote, f"igc-{lote.ano}.json", igc.ENDPOINT, Settings(), args.dry_run)
    if resposta is not None:
        logger.info("igc enviado", extra={"dados": {"resposta": resposta.model_dump()}})
    return 0


def main_sisu(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sauf-scraper sisu",
        description="Lê a planilha de notas de corte do Sisu (ampla concorrência) e envia.",
    )
    parser.add_argument("--arquivo", type=Path, required=True, help="xlsx do Sisu, em fontes/")
    parser.add_argument(
        "--dry-run", action="store_true", help="grava output/sisu-<ano>.json em vez de enviar"
    )
    args = parser.parse_args(argv)

    configurar_logging()
    lote, relatorio = sisu.ler_sisu(args.arquivo, codigos_emec())
    relatorio.registrar()
    sisu.relatar_codigos(lote, codigos_por_ies())
    resposta = entregar(lote, f"sisu-{lote.ano}.json", sisu.ENDPOINT, Settings(), args.dry_run)
    if resposta is not None:
        logger.info("sisu enviado", extra={"dados": {"resposta": resposta.model_dump()}})
    return 0


def main_questoes(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sauf-scraper questoes",
        description=(
            "Monta o banco de questões (ADR-SC-010): dataset maritaca-ai/enem cruzado com o "
            "ITENS_PROVA dos microdados do ENEM. Envia um lote por dia de prova."
        ),
    )
    parser.add_argument("banca", choices=["enem"], help="por enquanto só o ENEM")
    parser.add_argument("--ano", type=int, nargs="+", required=True, help="ex.: 2022 2023 2024")
    parser.add_argument(
        "--pasta",
        type=Path,
        default=Path("fontes/enem"),
        help="onde ficam <ano>.jsonl e ITENS_PROVA_<ano>.csv (padrão: fontes/enem)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="grava output/questoes-enem-<ano>.json em vez de enviar",
    )
    parser.add_argument(
        "--baixar-imagens",
        action="store_true",
        help="só baixa as figuras para <pasta>/imagens/ (a pasta que vai para o bucket) e sai",
    )
    args = parser.parse_args(argv)

    configurar_logging()
    settings = Settings()
    http = HttpEducado(settings)
    if args.baixar_imagens:
        return baixar_imagens_enem(http, args.pasta, args.ano)

    pasta_imagens = args.pasta / "imagens"
    for ano in args.ano:
        itens = args.pasta / f"ITENS_PROVA_{ano}.csv"
        if not itens.exists():
            parser.error(
                f"falta {itens}: extraia DADOS/ITENS_PROVA_{ano}.csv do zip dos microdados "
                f"do ENEM {ano} (INEP) para essa pasta"
            )
        registros = enem.ler_maritaca(enem.baixar_maritaca(http, args.pasta, ano))
        base_imagens = settings.questoes_imagens_url
        if base_imagens and (faltando := enem.imagens_faltando(registros, pasta_imagens)):
            parser.error(
                f"SAUF_QUESTOES_IMAGENS_URL definida, mas {len(faltando)} figura(s) de {ano} "
                f"não estão em {pasta_imagens} (ex.: {faltando[0]}): rode com --baixar-imagens "
                "e suba a pasta para o bucket antes de enviar"
            )
        lotes = enem.montar_lotes(ano, registros, enem.ler_itens(itens), base_imagens)
        logger.info("questões montadas", extra={"dados": {"ano": ano, **enem.resumo(lotes)}})
        if args.dry_run:
            ArquivoJson(settings.output_dir).gravar(
                f"questoes-enem-{ano}.json", enem.ProvasEnem(ano=ano, lotes=lotes)
            )
            continue
        api = ApiSauf(settings)
        for lote in lotes:
            resposta = api.postar(enem.ENDPOINT, lote)
            logger.info(
                "questões enviadas",
                extra={
                    "dados": {
                        "ano": ano,
                        "edicao": lote.prova.edicao,
                        "resposta": resposta.model_dump(),
                    }
                },
            )
    return 0


def main_ies(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sauf-scraper ies",
        description=(
            "Envia os dados manuais das universidades (dados/ies/<sigla>.toml): ano de fundação, "
            "sobre, site, logo e capa. Como preencher: dados/README.md."
        ),
    )
    parser.add_argument("--sigla", nargs="+", metavar="SIGLA", help="só estas (padrão: todas)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="só valida e grava output/ies-<sigla>.json, sem enviar",
    )
    args = parser.parse_args(argv)

    configurar_logging()
    settings = Settings()
    try:
        universidades = manuais.ler_universidades(args.sigla)
    except manuais.DadoManualInvalidoError as erro:
        print(f"ERRO: {erro}")
        return 1
    if not universidades:
        print(f"Nenhum arquivo .toml em {manuais.PASTA_IES}")
        return 1

    api = None if args.dry_run else ApiSauf(settings)
    for universidade, caminho in universidades:
        envio = manuais.envio_universidade(universidade, caminho.parent)
        print(manuais.resumo_universidade(universidade))
        if api is None:
            ArquivoJson(settings.output_dir).gravar(f"ies-{universidade.sigla.lower()}.json", envio)
            continue
        endpoint = manuais.ENDPOINT_UNIVERSIDADE.format(codigo_emec=universidade.codigo_emec)
        resposta = api.substituir(endpoint, envio)
        print(f"  enviado: {'atualizado' if resposta.atualizados else 'sem mudanças'}")
    return 0


def main_areas(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sauf-scraper areas",
        description=(
            "Envia a imagem de cada área Cine (dados/areas.toml), usada nos cards dos cursos "
            "da área. Como preencher: dados/README.md."
        ),
    )
    parser.add_argument("--codigo", nargs="+", metavar="CINE", help="só estas áreas, ex.: 07")
    parser.add_argument(
        "--dry-run", action="store_true", help="só valida e lista as áreas, sem enviar"
    )
    args = parser.parse_args(argv)

    configurar_logging()
    try:
        areas = manuais.ler_areas(codigos=args.codigo)
    except manuais.DadoManualInvalidoError as erro:
        print(f"ERRO: {erro}")
        return 1

    api = None if args.dry_run else ApiSauf(Settings())
    for area in areas:
        if area.imagem is None:
            print(f"{area.codigo_cine} {area.nome}: sem imagem, não enviada")
            continue
        print(f"{area.codigo_cine} {area.nome}: {area.imagem.arquivo} ({area.imagem.licenca})")
        if api is None:
            continue
        imagem = manuais.imagem_envio(area.imagem, manuais.ARQUIVO_AREAS.parent)
        endpoint = manuais.ENDPOINT_AREA.format(codigo_cine=area.codigo_cine)
        resposta = api.substituir(endpoint, imagem)
        print(f"  enviado: {'atualizado' if resposta.atualizados else 'sem mudanças'}")
    return 0


def main_calendario(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sauf-scraper calendario",
        description=(
            "Envia as datas de dados/calendario.toml (ENEM, vestibulares, ProUni) para o "
            "calendário da API. Reenviar não duplica. Como preencher: dados/README.md."
        ),
    )
    parser.add_argument("--chave", nargs="+", metavar="CHAVE", help="só estes eventos")
    parser.add_argument(
        "--remover",
        nargs="+",
        metavar="CHAVE",
        help="apaga estes eventos da API (chave errada ou evento cancelado) e sai",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="só valida e lista os eventos, sem enviar"
    )
    args = parser.parse_args(argv)

    configurar_logging()
    if args.remover:
        if args.dry_run:
            print("--remover não tem --dry-run: confira as chaves e rode sem ele")
            return 1
        api = ApiSauf(Settings())
        for chave in args.remover:
            try:
                api.remover(calendario.ENDPOINT_EVENTO.format(chave=chave))
                print(f"{chave}: removido")
            except ApiRecusouLoteError as erro:
                if erro.status != 404:
                    raise
                print(f"{chave}: não existe na API")
        return 0

    try:
        eventos = calendario.ler_eventos(chaves=args.chave)
    except manuais.DadoManualInvalidoError as erro:
        print(f"ERRO: {erro}")
        return 1

    api = None if args.dry_run else ApiSauf(Settings())
    for evento, envio in eventos:
        print(calendario.resumo(evento))
        if api is None:
            continue
        resposta = api.substituir(calendario.ENDPOINT_EVENTO.format(chave=evento.chave), envio)
        if resposta.criados:
            print("  enviado: criado")
        else:
            print(f"  enviado: {'atualizado' if resposta.atualizados else 'sem mudanças'}")
    print(f"{len(eventos)} evento(s){' validados, nada enviado' if api is None else ''}")
    return 0


def baixar_imagens_enem(http: HttpEducado, pasta: Path, anos: list[int]) -> int:
    """Baixa as figuras dos anos para <pasta>/imagens/; lista as falhas e sai com erro."""
    falhas = []
    for ano in anos:
        registros = enem.ler_maritaca(enem.baixar_maritaca(http, pasta, ano))
        total = len(enem.imagens_do_dataset(registros))
        falhas_do_ano = enem.baixar_imagens(http, registros, pasta / "imagens")
        falhas += falhas_do_ano
        logger.info(
            "imagens baixadas",
            extra={"dados": {"ano": ano, "total": total, "falhas": len(falhas_do_ano)}},
        )
    for falha in falhas:
        logger.error("imagem não baixada", extra={"dados": {"falha": falha}})
    if falhas:
        print(f"{len(falhas)} imagem(ns) não baixada(s); rode de novo para tentar só as que faltam")
        return 1
    print(f"Imagens em {pasta / 'imagens'}: arraste as pastas de ano para o bucket")
    return 0


def codigos_por_ies() -> dict[int, set[int]]:
    """Códigos de curso confirmados na tabela de casamento de cada spider."""
    return {
        spider.codigo_emec: {
            codigo.codigo_emec
            for codigos in codigos_confirmados(spider.chave).values()
            for codigo in codigos
        }
        for spider in SPIDERS.values()
    }


if __name__ == "__main__":
    sys.exit(main())
