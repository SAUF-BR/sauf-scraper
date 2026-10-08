"""Lê os microdados do Censo da Educação Superior (INEP) e monta o LoteCenso.

Regras (docs/MAPEAMENTO_CENSO.md): arquivos em Latin-1 com ";", leitura em streaming,
só as instituições informadas, só graduação, e uma oferta por CO_CURSO (cursos EAD
aparecem uma vez por polo).
"""

import csv
import logging
from collections.abc import Iterable, Iterator
from pathlib import Path

from sauf_scraper.censo.modelos import InstituicaoCenso, LoteCenso, OfertaCenso
from sauf_scraper.core.models import Grau, Modalidade

logger = logging.getLogger(__name__)

PRESENCIAL = "1"
EAD_POR_POLO = "2"
EAD_CONSOLIDADO = "3"

_TIPO = {"1": "publica", "2": "privada"}
_CATEGORIA = {
    "1": "publica_federal",
    "2": "publica_estadual",
    "3": "publica_municipal",
    "4": "privada_com_fins_lucrativos",
    "5": "privada_sem_fins_lucrativos",
    "7": "especial",
}
_ORGANIZACAO = {
    "1": "universidade",
    "2": "centro_universitario",
    "3": "faculdade",
    "4": "instituto_federal",
    "5": "cefet",
}
_GRAU = {
    "1": Grau.BACHARELADO,
    "2": Grau.LICENCIATURA,
    "3": Grau.TECNOLOGICO,
    "4": Grau.BACHARELADO_E_LICENCIATURA,
}
_MODALIDADE = {"1": Modalidade.PRESENCIAL, "2": Modalidade.EAD}


def ler_censo(pasta: Path, codigos_ies: Iterable[int]) -> LoteCenso:
    codigos = {str(c) for c in codigos_ies}
    arquivo_ies = arquivo_censo(pasta, "MICRODADOS_ED_SUP_IES_*.CSV")
    arquivo_cursos = arquivo_censo(pasta, "MICRODADOS_CADASTRO_CURSOS_*.CSV")

    instituicoes, ano = ler_instituicoes(arquivo_ies, codigos)
    faltando = codigos - {str(i.codigo_emec) for i in instituicoes}
    if faltando:
        logger.warning(
            "IES não encontradas no Censo", extra={"dados": {"codigos": sorted(faltando)}}
        )

    return LoteCenso(
        ano_censo=ano,
        instituicoes=instituicoes,
        ofertas=ler_ofertas(arquivo_cursos, codigos),
    )


def ler_instituicoes(arquivo: Path, codigos: set[str]) -> tuple[list[InstituicaoCenso], int]:
    instituicoes = []
    ano = 0
    for linha in linhas(arquivo):
        if linha["CO_IES"] not in codigos:
            continue
        ano = int(linha["NU_ANO_CENSO"])
        instituicoes.append(
            InstituicaoCenso(
                codigo_emec=int(linha["CO_IES"]),
                nome=linha["NO_IES"],
                sigla=linha["SG_IES"] or None,
                tipo=_TIPO[linha["TP_REDE"]],
                categoria_administrativa=_CATEGORIA.get(linha["TP_CATEGORIA_ADMINISTRATIVA"]),
                organizacao_academica=_ORGANIZACAO.get(linha["TP_ORGANIZACAO_ACADEMICA"]),
                uf=linha["SG_UF_IES"],
                cidade=linha["NO_MUNICIPIO_IES"],
            )
        )
    return instituicoes, ano


def ler_ofertas(arquivo: Path, codigos: set[str]) -> list[OfertaCenso]:
    escolhidas: dict[str, dict[str, str]] = {}
    for linha in linhas(arquivo):
        if linha["CO_IES"] not in codigos or linha["TP_NIVEL_ACADEMICO"] != "1":
            continue
        codigo = linha["CO_CURSO"]
        atual = escolhidas.get(codigo)
        if atual is None or _prioridade(linha) < _prioridade(atual):
            escolhidas[codigo] = linha

    ofertas = []
    for codigo, linha in escolhidas.items():
        if linha["TP_DIMENSAO"] == EAD_POR_POLO:
            logger.warning("curso EAD sem linha consolidada", extra={"dados": {"coCurso": codigo}})
            linha = {**linha, "NO_MUNICIPIO": "", "SG_UF": ""}
        ofertas.append(_oferta(linha))
    return sorted(ofertas, key=lambda o: o.codigo_emec)


def _oferta(linha: dict[str, str]) -> OfertaCenso:
    return OfertaCenso(
        codigo_emec=int(linha["CO_CURSO"]),
        codigo_emec_instituicao=int(linha["CO_IES"]),
        nome=linha["NO_CURSO"],
        grau=_GRAU.get(linha["TP_GRAU_ACADEMICO"]),
        modalidade=_MODALIDADE.get(linha["TP_MODALIDADE_ENSINO"]),
        cidade=linha["NO_MUNICIPIO"] or None,
        uf=linha["SG_UF"] or None,
        vagas=_inteiro(linha["QT_VG_TOTAL"]),
        gratuito={"1": True, "0": False}.get(linha["IN_GRATUITO"]),
        codigo_cine_rotulo=_sem_aspas(linha["CO_CINE_ROTULO"]),
        nome_cine_rotulo=linha["NO_CINE_ROTULO"],
        codigo_cine_area=_sem_aspas(linha["CO_CINE_AREA_GERAL"]),
    )


def _prioridade(linha: dict[str, str]) -> int:
    """Menor = preferida: presencial, depois EAD consolidado, depois EAD por polo."""
    return {PRESENCIAL: 0, EAD_CONSOLIDADO: 1}.get(linha["TP_DIMENSAO"], 2)


def linhas(arquivo: Path) -> Iterator[dict[str, str]]:
    with arquivo.open(encoding="latin-1", newline="") as f:
        for linha in csv.DictReader(f, delimiter=";"):
            yield {chave: (valor or "").strip() for chave, valor in linha.items()}


def arquivo_censo(pasta: Path, padrao: str) -> Path:
    encontrados = sorted((pasta / "dados").glob(padrao)) or sorted(pasta.glob(padrao))
    if not encontrados:
        raise FileNotFoundError(f"{padrao} não encontrado em {pasta}")
    return encontrados[-1]


def _sem_aspas(valor: str) -> str:
    return valor.strip('"')


def _inteiro(valor: str) -> int | None:
    return int(valor) if valor.isdigit() else None
