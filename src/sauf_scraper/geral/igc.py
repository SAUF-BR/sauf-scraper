"""G2: IGC (Índice Geral de Cursos) do INEP, a "nota MEC" da instituição (D-49).

Planilha: IGC_<ano>.xlsx, aba "IGC". Colunas usadas: "Ano", "Código da IES" (= CO_IES do
e-MEC e do Censo), "IGC (Contínuo)" e "IGC (Faixa)". A faixa vem como texto, '1' a '5',
ou 'SC' (sem conceito), que vira null.
"""

from pathlib import Path

from pydantic import Field

from sauf_scraper.core.models import SaufModel
from sauf_scraper.geral.base import Relatorio, do_escopo, inteiro, ler_planilha

ABA = "IGC"
ENDPOINT = "/api/v1/ingestao/igc"


class IgcInstituicao(SaufModel):
    codigo_emec: int = Field(gt=0)
    igc_continuo: float | None = Field(default=None, ge=0, le=5)
    igc_faixa: int | None = Field(default=None, ge=1, le=5)


class LoteIgc(SaufModel):
    ano: int
    instituicoes: list[IgcInstituicao]


def ler_igc(arquivo: Path, escopo: list[int]) -> tuple[LoteIgc, Relatorio]:
    relatorio = Relatorio(fonte=arquivo.name, escopo=sorted(escopo))
    anos: set[int] = set()
    instituicoes = []
    for linha in do_escopo(ler_planilha(arquivo, ABA), "Código da IES", relatorio):
        anos.add(int(linha["Ano"]))
        instituicoes.append(
            IgcInstituicao(
                codigo_emec=inteiro(linha["Código da IES"]),
                igc_continuo=_numero(linha.get("IGC (Contínuo)")),
                igc_faixa=faixa(linha.get("IGC (Faixa)")),
            )
        )
    if len(anos) > 1:
        raise ValueError(f"planilha com mais de um ano: {sorted(anos)}")
    if not anos:
        raise ValueError("nenhuma IES do escopo encontrada na planilha")
    return LoteIgc(ano=anos.pop(), instituicoes=instituicoes), relatorio


def faixa(valor) -> int | None:
    """'1'..'5' → 1..5; 'SC' (sem conceito) ou vazio → None."""
    numero = inteiro(valor)
    return numero if numero is not None and 1 <= numero <= 5 else None


def _numero(valor) -> float | None:
    if valor is None or isinstance(valor, str) and not valor.strip():
        return None
    try:
        return float(str(valor).replace(",", "."))
    except ValueError:
        return None
