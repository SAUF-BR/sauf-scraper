"""Tabela de casamento: curso do site da instituição -> código(s) e-MEC do curso (CO_CURSO).

O spider não tem como saber o código e-MEC de uma página do site. Esta tabela, gerada a
partir do lote do spider e do Censo e revisada à mão, faz essa ligação. Sem ela, o backend
cria uma oferta do site separada da oferta do Censo para o mesmo curso.

Uma página pode valer por vários códigos: ex.: bacharelado e licenciatura de Física na
mesma página. Por isso a tabela tem **uma linha por par página × código**, e o spider usa
só as linhas com confirmado = "sim". A página continua sendo um curso só (D-34); os códigos
vão numa lista interna (D-35) que o backend usa para puxar área e vagas do Censo.

Arquivo: src/sauf_scraper/spiders/dados/<chave-do-spider>_codigos.csv (UTF-8, ";").
"""

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from sauf_scraper.censo.leitor import PRESENCIAL, arquivo_censo, linhas
from sauf_scraper.core.models import Curso, Grau, Opcao

PASTA_TABELAS = Path(__file__).resolve().parent.parent / "spiders" / "dados"

DIRETO = "direto"
AMBIGUO = "ambiguo"
SEM_PAR = "sem_par"

SUGESTAO_VARIOS = "uma página, vários: confirmar os códigos que esta página cobre"
SUGESTAO_HABILITACAO = "mesmo grau e turno: habilitações diferentes? decidir"

_GRAU_CENSO = {
    "1": "bacharelado",
    "2": "licenciatura",
    "3": "tecnologo",
    "4": "bacharelado_e_licenciatura",
}
_TURNOS_DIURNOS = {"integral", "matutino", "vespertino"}


@dataclass
class LinhaCasamento:
    chave: str
    nome_site: str
    cidade: str
    turno_site: str
    grau_site: str
    status: str
    codigo_emec: str
    nome_censo: str
    grau_censo: str
    vagas_diurno: str
    vagas_noturno: str
    sugestao: str
    confirmado: str


@dataclass(frozen=True)
class CodigoConfirmado:
    codigo_emec: int
    grau_censo: str
    vagas_diurno: int
    vagas_noturno: int


def caminho_tabela(chave_spider: str) -> Path:
    return PASTA_TABELAS / f"{chave_spider}_codigos.csv"


def ler_tabela(caminho: Path) -> list[LinhaCasamento]:
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8", newline="") as f:
        return [LinhaCasamento(**linha) for linha in csv.DictReader(f, delimiter=";")]


def codigos_confirmados(chave_spider: str) -> dict[str, list[CodigoConfirmado]]:
    resultado: dict[str, list[CodigoConfirmado]] = defaultdict(list)
    for linha in ler_tabela(caminho_tabela(chave_spider)):
        if linha.confirmado == "sim" and linha.codigo_emec.isdigit():
            resultado[linha.chave].append(
                CodigoConfirmado(
                    codigo_emec=int(linha.codigo_emec),
                    grau_censo=linha.grau_censo,
                    vagas_diurno=_vagas(linha.vagas_diurno),
                    vagas_noturno=_vagas(linha.vagas_noturno),
                )
            )
    return dict(resultado)


def gerar_tabela(cursos: list[Curso], pasta_censo: Path, codigo_ies: int) -> list[LinhaCasamento]:
    censo = [
        linha
        for linha in linhas(arquivo_censo(pasta_censo, "MICRODADOS_CADASTRO_CURSOS_*.CSV"))
        if linha["CO_IES"] == str(codigo_ies)
        and linha["TP_DIMENSAO"] == PRESENCIAL
        and linha["TP_NIVEL_ACADEMICO"] == "1"
    ]
    resultado = [linha for curso in cursos for linha in _casar(curso, censo)]

    paginas_por_codigo = Counter(linha.codigo_emec for linha in resultado if linha.status == DIRETO)
    for linha in resultado:
        if linha.status == DIRETO and paginas_por_codigo[linha.codigo_emec] > 1:
            linha.status, linha.confirmado = AMBIGUO, "nao"
            linha.sugestao = "código usado por outra página: decidir"
    return resultado


def gravar_tabela(caminho: Path, novas: list[LinhaCasamento]) -> None:
    """Grava a tabela preservando as páginas que já têm alguma linha confirmada à mão."""
    revisadas: dict[str, list[LinhaCasamento]] = defaultdict(list)
    for linha in ler_tabela(caminho):
        revisadas[linha.chave].append(linha)
    revisadas = {
        chave: grupo
        for chave, grupo in revisadas.items()
        if any(linha.confirmado == "sim" and linha.status != DIRETO for linha in grupo)
    }

    finais = [linha for linha in novas if linha.chave not in revisadas]
    chaves_novas = {linha.chave for linha in novas}
    finais += [
        linha for chave, grupo in revisadas.items() if chave in chaves_novas for linha in grupo
    ]

    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as f:
        nomes = [campo.name for campo in fields(LinhaCasamento)]
        escritor = csv.DictWriter(f, fieldnames=nomes, delimiter=";")
        escritor.writeheader()
        ordem = {DIRETO: 0, AMBIGUO: 1, SEM_PAR: 2}
        for linha in sorted(
            finais, key=lambda item: (ordem[item.status], item.chave, item.codigo_emec)
        ):
            escritor.writerow(asdict(linha))


def _casar(curso: Curso, censo: list[dict[str, str]]) -> list[LinhaCasamento]:
    cidade = _normalizar(curso.cidade or "")
    candidatos = [
        linha
        for linha in censo
        if _normalizar(linha["NO_CURSO"]) == _normalizar(curso.nome)
        and _normalizar(linha["NO_MUNICIPIO"]) == cidade
    ]
    grau = _grau_unico(curso)
    if len(candidatos) > 1 and grau in ("bacharelado", "licenciatura", "tecnologo"):
        candidatos = [
            c for c in candidatos if _GRAU_CENSO.get(c["TP_GRAU_ACADEMICO"]) == grau
        ] or candidatos
    if len(candidatos) > 1 and curso.turno:
        candidatos = _filtrar_turno(candidatos, _normalizar(curso.turno)) or candidatos

    if not candidatos:
        return [_linha(curso, SEM_PAR, None, "", "nao")]
    if len(candidatos) == 1:
        return [_linha(curso, DIRETO, candidatos[0], "", "sim")]
    perfis = {
        (
            c["TP_GRAU_ACADEMICO"],
            _vagas(c["QT_VG_TOTAL_DIURNO"]) > 0,
            _vagas(c["QT_VG_TOTAL_NOTURNO"]) > 0,
        )
        for c in candidatos
    }
    sugestao = SUGESTAO_HABILITACAO if len(perfis) == 1 else SUGESTAO_VARIOS
    return [_linha(curso, AMBIGUO, c, sugestao, "nao") for c in candidatos]


def _grau_unico(curso: Curso) -> str:
    graus = {opcao.grau.value for opcao in curso.opcoes}
    return graus.pop() if len(graus) == 1 else ""


def _linha(
    curso: Curso, status: str, censo: dict[str, str] | None, sugestao: str, confirmado: str
) -> LinhaCasamento:
    censo = censo or {}
    return LinhaCasamento(
        chave=curso.chave,
        nome_site=curso.nome,
        cidade=curso.cidade or "",
        turno_site=curso.turno or "",
        grau_site=", ".join(opcao.grau.value for opcao in curso.opcoes),
        status=status,
        codigo_emec=censo.get("CO_CURSO", ""),
        nome_censo=censo.get("NO_CURSO", ""),
        grau_censo=_GRAU_CENSO.get(censo.get("TP_GRAU_ACADEMICO", ""), ""),
        vagas_diurno=censo.get("QT_VG_TOTAL_DIURNO", ""),
        vagas_noturno=censo.get("QT_VG_TOTAL_NOTURNO", ""),
        sugestao=sugestao,
        confirmado=confirmado,
    )


def _filtrar_turno(candidatos: list[dict[str, str]], turno: str) -> list[dict[str, str]]:
    # Como o Censo não tem turno, só vagas diurnas e noturnas aqui ele só filtra quando o site traz um turno só!
    if " ou " in f" {turno} " or " e " in f" {turno} ":
        return []
    if turno == "noturno":
        return [c for c in candidatos if _vagas(c["QT_VG_TOTAL_NOTURNO"]) > 0]
    if turno in _TURNOS_DIURNOS:
        return [c for c in candidatos if _vagas(c["QT_VG_TOTAL_DIURNO"]) > 0]
    return []


def aplicar_codigos(curso: Curso, codigos: list[CodigoConfirmado]) -> Curso:
    """Liga o curso do site aos códigos e-MEC confirmados da página (D-34, D-35).

    Uma página continua sendo um curso só; os códigos vão em `codigos_emec` (uso interno do
    backend). O site manda (D-33): os graus do Censo só entram quando a página não informa.
    """
    if not codigos:
        return curso
    atualizacao: dict = {"codigos_emec": sorted({c.codigo_emec for c in codigos})}
    if not curso.opcoes:
        graus = []
        for codigo in codigos:
            for grau in _graus_do_censo(codigo.grau_censo):
                if grau not in graus:
                    graus.append(grau)
        atualizacao["opcoes"] = [Opcao(grau=grau) for grau in graus]
    return curso.model_copy(update=atualizacao)


def _graus_do_censo(valor: str) -> list[Grau]:
    if valor == Grau.BACHARELADO_E_LICENCIATURA.value:
        return [Grau.BACHARELADO, Grau.LICENCIATURA]
    return [Grau(valor)] if valor in {g.value for g in Grau} else []


def _vagas(valor: str) -> int:
    return int(valor) if valor.isdigit() else 0


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()
