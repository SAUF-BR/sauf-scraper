"""Q1: questões do ENEM para os simulados (ADR-SC-010, D-68 do sauf-api).

Duas fontes, lidas de fontes/enem/:

- <ano>.jsonl do dataset maritaca-ai/enem (Apache-2.0): texto das 180 questões do caderno
  acessível (laranja), com as figuras em URL e a descrição de cada uma. Se faltar, o comando
  baixa do Hugging Face.
- ITENS_PROVA_<ano>.csv dos microdados do ENEM (INEP): por caderno e posição, a área, a
  habilidade, os parâmetros TRI, o código do item e o gabarito oficial. Vem dentro do zip
  dos microdados (pasta DADOS/) e é colocado à mão, como as planilhas do IGC e do Sisu.

As figuras ficam no repositório dos autores do dataset (piresramon/gpt-4-enem). Com
SAUF_QUESTOES_IMAGENS_URL definida, o link passa a apontar para essa base (ex.: o bucket público
do Supabase), mantendo o mesmo caminho relativo (`<ano>/...png`); `--baixar-imagens` baixa as
imagens para fontes/enem/imagens/, que é a pasta que vai para o bucket.

Tudo aqui é puro (sem rede), menos `baixar_maritaca` e `baixar_imagens`.
"""

import csv
import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from sauf_scraper.core.models import SaufModel

logger = logging.getLogger(__name__)

ENDPOINT = "/api/v1/ingestao/questoes"
URL_DATASET = "https://huggingface.co/datasets/maritaca-ai/enem"
URL_JSONL = URL_DATASET + "/resolve/main/{ano}.jsonl"
URL_FIGURAS = "https://raw.githubusercontent.com/piresramon/gpt-4-enem/main/data/figures/"
CADERNO = "LARANJA"
CORES_REFERENCIA = ("LARANJA", "LEITOR TELA")  # mesma ordem de questões do caderno acessível
ANULADO_DATASET = "Anulado"
ANULADO_INEP = "X"
ROTULOS = ("A", "B", "C", "D", "E")
QUESTOES_POR_DIA = 90
MINIMO_DE_ACERTO = 0.9  # abaixo disso o ITENS_PROVA não é do mesmo ano/caderno

MARCADOR_FIGURA = "[[placeholder]]"
FORMULA_POR_EXTENSO = re.compile(
    r"numerador|denominador|\bavos\b|elevad[oa] a|raiz quadrada|raiz cúbica|"
    r"abre parêntese|fecha parêntese|ao quadrado|ao cubo|subscrito|sobrescrito",
    re.IGNORECASE,
)
TABELA_COM_LIXO = re.compile(r"Unnamed: \d+|\|\s*nan\s*\|")
SO_FIGURA = re.compile(r"^(!\[[^\]]*\]\([^)]*\)\s*)+$")
FIGURA = re.compile(r"!\[[^\]]*\]\([^)\s]*\)")

AREAS = {"LC": "lc", "CH": "ch", "CN": "cn", "MT": "mt"}
LINGUAS = {"0": "ingles", "1": "espanhol"}


class AlternativaLote(SaufModel):
    rotulo: str
    valor: int | None = None
    texto: str
    correta: bool


class QuestaoLote(SaufModel):
    numero: int = Field(gt=0)
    lingua: str | None = None
    tipo: str = "multipla_escolha"
    area: str
    materia: str | None = None
    assunto: str | None = None
    habilidade: int | None = None
    texto_base: str | None = None
    comando: str = Field(min_length=1)
    gabarito_soma: int | None = None
    dificuldade: float | None = None
    anulada: bool = False
    status: str
    motivo_pendencia: str | None = None
    codigo_origem: int | None = None
    credito: str
    alternativas: list[AlternativaLote]


class ProvaLote(SaufModel):
    banca: str = "enem"
    ano: int
    edicao: str
    caderno: str = CADERNO
    url_origem: str | None = URL_DATASET
    credito: str


class LoteQuestoes(SaufModel):
    """Corpo de POST /api/v1/ingestao/questoes: um caderno de um dia."""

    prova: ProvaLote
    questoes: list[QuestaoLote]


class ProvasEnem(SaufModel):
    """O que o --dry-run grava em output/questoes-enem-<ano>.json: os dois dias."""

    ano: int
    lotes: list[LoteQuestoes]


@dataclass(frozen=True)
class ItemInep:
    """Uma linha do ITENS_PROVA no caderno de referência."""

    posicao: int
    area: str
    codigo_item: int
    gabarito: str
    habilidade: int | None
    dificuldade: float | None
    lingua: str | None


def credito(ano: int) -> str:
    return f"ENEM {ano} (INEP), via maritaca-ai/enem (Apache-2.0)"


def ler_maritaca(arquivo: Path) -> dict[int, dict]:
    """Questões do dataset por número (o id "questao_07" vira 7)."""
    registros = {}
    with arquivo.open(encoding="utf-8") as linhas:
        for linha in linhas:
            if linha.strip():
                registro = json.loads(linha)
                registros[int(registro["id"].rsplit("_", 1)[1])] = registro
    return registros


def ler_itens(arquivo: Path) -> list[dict[str, str]]:
    """ITENS_PROVA_<ano>.csv: separado por ";" e em Latin-1, como os outros microdados."""
    with arquivo.open(encoding="latin-1", newline="") as entrada:
        return list(csv.DictReader(entrada, delimiter=";"))


def caderno_de_referencia(
    itens: list[dict[str, str]], registros: dict[int, dict]
) -> dict[int, ItemInep]:
    """Itens do caderno com a mesma ordem do dataset, por posição (1 a 180).

    O ITENS_PROVA tem uma prova (CO_PROVA) por área e cor. Para cada área, fica a prova
    laranja ou leitor de tela cujo gabarito mais bate com o do dataset; nas questões 1 a 5
    vale a de inglês (TP_LINGUA 0), a única que o dataset traz.
    """
    provas: dict[tuple[str, str], dict[int, dict[str, str]]] = defaultdict(dict)
    for linha in itens:
        if linha["TX_COR"] in CORES_REFERENCIA and linha["TP_LINGUA"] in ("", "0"):
            provas[(linha["SG_AREA"], linha["CO_PROVA"])][int(linha["CO_POSICAO"])] = linha

    escolhidos: dict[int, ItemInep] = {}
    for area in AREAS:
        candidatas = []
        for (area_prova, codigo), linhas in provas.items():
            if area_prova != area:
                continue
            comparaveis = [
                p for p in linhas if p in registros and registros[p]["label"] != ANULADO_DATASET
            ]
            acertos = sum(linhas[p]["TX_GABARITO"] == registros[p]["label"] for p in comparaveis)
            taxa = acertos / len(comparaveis) if comparaveis else 0
            laranja = linhas[next(iter(linhas))]["TX_COR"] == "LARANJA"
            candidatas.append((taxa, laranja, -int(codigo), codigo, linhas))
        if not candidatas:
            continue  # questão sem item é recusada em montar_lotes
        taxa, _, _, codigo, linhas = max(candidatas, key=lambda c: c[:3])
        if taxa < MINIMO_DE_ACERTO:
            raise ValueError(
                f"gabarito da área {area} bate só {taxa:.0%} com o dataset: "
                "o ITENS_PROVA é do mesmo ano?"
            )
        logger.info(
            "caderno de referência",
            extra={"dados": {"area": area, "coProva": codigo, "acerto": taxa}},
        )
        for posicao, linha in linhas.items():
            escolhidos[posicao] = ItemInep(
                posicao=posicao,
                area=AREAS[area],
                codigo_item=int(linha["CO_ITEM"]),
                gabarito=linha["TX_GABARITO"],
                habilidade=_inteiro(linha["CO_HABILIDADE"]),
                dificuldade=_numero(linha["NU_PARAM_B"]),
                lingua=LINGUAS.get(linha["TP_LINGUA"]),
            )
    return escolhidos


def montar_questao(
    registro: dict, item: ItemInep, ano: int, base_imagens: str | None = None
) -> QuestaoLote:
    """Uma questão do dataset com os dados do INEP. O gabarito oficial prevalece."""
    numero = int(registro["id"].rsplit("_", 1)[1])
    pendencias: list[str] = []

    figuras = _figuras(registro, base_imagens)
    # Figura grudada no texto ("## TEXTO 1![...]" ou "...png)A carta") vira linha própria.
    texto = FIGURA.sub(_linha_propria, _trocar_figuras(registro["question"], figuras))
    alternativas_texto = [_trocar_figuras(a, figuras) for a in registro["alternatives"]]
    if figuras:
        pendencias.append("figura sem lugar no texto")
    if any(MARCADOR_FIGURA in t for t in [texto, *alternativas_texto]):
        pendencias.append("figura faltando")
    texto_base, comando = separar_texto_base(texto)
    if not any(p.strip() and not _figura_ou_tabela(p) for p in comando.split("\n")):
        pendencias.append("questão sem comando em texto")

    anulada = item.gabarito == ANULADO_INEP
    if (registro["label"] == ANULADO_DATASET) != anulada or (
        not anulada and registro["label"] != item.gabarito
    ):
        pendencias.append(
            f"gabarito do dataset ({registro['label']}) diverge do INEP ({item.gabarito})"
        )
        logger.warning(
            "gabarito divergente",
            extra={
                "dados": {
                    "ano": ano,
                    "numero": numero,
                    "dataset": registro["label"],
                    "inep": item.gabarito,
                }
            },
        )

    conteudo = "\n".join([texto, *alternativas_texto])
    if FORMULA_POR_EXTENSO.search(conteudo):
        pendencias.append("fórmula escrita por extenso")
    if TABELA_COM_LIXO.search(conteudo):
        pendencias.append("tabela com sobras da conversão")
    if any(not a.strip() for a in alternativas_texto):
        pendencias.append("alternativa vazia")
    elif any(SO_FIGURA.match(a.strip()) for a in alternativas_texto):
        pendencias.append("alternativa só com figura")

    return QuestaoLote(
        numero=numero,
        lingua=item.lingua,
        area=item.area,
        habilidade=item.habilidade,
        texto_base=texto_base,
        comando=comando,
        dificuldade=item.dificuldade,
        anulada=anulada,
        status="pendente_revisao" if pendencias else "disponivel",
        motivo_pendencia="; ".join(pendencias) or None,
        codigo_origem=item.codigo_item,
        credito=credito(ano),
        alternativas=[
            AlternativaLote(
                rotulo=rotulo, texto=texto_alt, correta=not anulada and rotulo == item.gabarito
            )
            for rotulo, texto_alt in zip(ROTULOS, alternativas_texto, strict=True)
        ],
    )


def _linha_propria(achado: re.Match[str]) -> str:
    texto, inicio, fim = achado.string, achado.start(), achado.end()
    antes = "\n" if inicio > 0 and not texto[inicio - 1].isspace() else ""
    depois = "\n" if fim < len(texto) and not texto[fim].isspace() else ""
    return f"{antes}{achado.group()}{depois}"


def separar_texto_base(texto: str) -> tuple[str | None, str]:
    """Último parágrafo de texto = comando; o resto = texto-base.

    Figuras e linhas de tabela depois do último parágrafo ficam com o comando ("Qual
    heredograma foi recebido pelo casal?" + a figura). Sem nenhum parágrafo de texto, vai
    tudo como comando.
    """
    paragrafos = texto.strip().split("\n")
    texto_puro = [i for i, p in enumerate(paragrafos) if p.strip() and not _figura_ou_tabela(p)]
    if not texto_puro:
        return None, texto.strip()
    inicio = texto_puro[-1]
    texto_base = "\n".join(paragrafos[:inicio]).strip()
    return texto_base or None, "\n".join(paragrafos[inicio:]).strip()


def montar_lotes(
    ano: int,
    registros: dict[int, dict],
    itens: list[dict[str, str]],
    base_imagens: str | None = None,
) -> list[LoteQuestoes]:
    """Dois lotes: D1 (questões 1 a 90) e D2 (91 a 180)."""
    referencia = caderno_de_referencia(itens, registros)
    faltando = sorted(set(registros) - set(referencia))
    if faltando:
        raise ValueError(f"questões sem item no ITENS_PROVA: {faltando}")
    lotes = []
    for dia, numeros in (("D1", range(1, 91)), ("D2", range(91, 181))):
        questoes = [
            montar_questao(registros[n], referencia[n], ano, base_imagens)
            for n in numeros
            if n in registros
        ]
        if questoes:
            prova = ProvaLote(ano=ano, edicao=dia, credito=credito(ano))
            lotes.append(LoteQuestoes(prova=prova, questoes=questoes))
    return lotes


def resumo(lotes: list[LoteQuestoes]) -> dict:
    """Números do log: total, por área, por status e os motivos de pendência."""
    questoes = [q for lote in lotes for q in lote.questoes]
    motivos = Counter(
        m for q in questoes if q.motivo_pendencia for m in q.motivo_pendencia.split("; ")
    )
    return {
        "total": len(questoes),
        "porArea": dict(Counter(q.area for q in questoes)),
        "porStatus": dict(Counter(q.status for q in questoes)),
        "anuladas": sum(q.anulada for q in questoes),
        "motivos": dict(motivos),
    }


def baixar_maritaca(http, pasta: Path, ano: int) -> Path:
    """fontes/enem/<ano>.jsonl; baixa do Hugging Face (pelo HttpEducado) se ainda não existir."""
    arquivo = pasta / f"{ano}.jsonl"
    if not arquivo.exists():
        pasta.mkdir(parents=True, exist_ok=True)
        resposta = http.get(URL_JSONL.format(ano=ano))
        arquivo.write_bytes(resposta.content)
        logger.info("dataset baixado", extra={"dados": {"arquivo": str(arquivo)}})
    return arquivo


def caminho_da_imagem(url: str) -> str | None:
    """Caminho relativo da figura (`2023/day_2/fileoutpart44.png`); None se for de outro lugar."""
    return url.removeprefix(URL_FIGURAS) if url.startswith(URL_FIGURAS) else None


def imagens_do_dataset(registros: dict[int, dict]) -> list[str]:
    """URLs de todas as figuras, sem repetir, na ordem das questões."""
    return list(
        dict.fromkeys(u for _, r in sorted(registros.items()) for u in r.get("figures") or [])
    )


def imagens_faltando(registros: dict[int, dict], pasta_imagens: Path) -> list[str]:
    """Caminhos das figuras que ainda não foram baixadas para a pasta."""
    caminhos = (caminho_da_imagem(u) for u in imagens_do_dataset(registros))
    return [c for c in caminhos if c and not (pasta_imagens / c).exists()]


def baixar_imagens(http, registros: dict[int, dict], pasta_imagens: Path) -> list[str]:
    """Baixa as figuras que faltam (pelo HttpEducado), no mesmo caminho do repositório.

    Devolve as falhas ("url: erro"); uma falha não interrompe as outras.
    """
    falhas = []
    for url in imagens_do_dataset(registros):
        caminho = caminho_da_imagem(url)
        if caminho is None:
            falhas.append(f"{url}: fora de {URL_FIGURAS}")
            continue
        destino = pasta_imagens / caminho
        if destino.exists():
            continue
        try:
            conteudo = http.get(url).content
        except Exception as erro:  # noqa: BLE001 - lista a falha e segue com as outras
            falhas.append(f"{url}: {erro}")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
    return falhas


def _figuras(registro: dict, base_imagens: str | None = None) -> list[str]:
    """Imagens em Markdown, na ordem: o texto alternativo é a descrição do caderno ledor."""
    descricoes = registro.get("description") or []
    figuras = []
    for i, url in enumerate(registro.get("figures") or []):
        caminho = caminho_da_imagem(url)
        if base_imagens and caminho:
            url = f"{base_imagens.rstrip('/')}/{caminho}"
        descricao = descricoes[i] if i < len(descricoes) else "Figura"
        descricao = " ".join(descricao.replace("[", "(").replace("]", ")").split())
        figuras.append(f"![{descricao}]({url})")
    return figuras


def _trocar_figuras(texto: str, figuras: list[str]) -> str:
    """Troca cada marcador pela próxima figura (consome a lista: texto, depois alternativas)."""
    while MARCADOR_FIGURA in texto and figuras:
        texto = texto.replace(MARCADOR_FIGURA, figuras.pop(0), 1)
    return texto


def _figura_ou_tabela(paragrafo: str) -> bool:
    return paragrafo.strip().startswith(("![", "|", MARCADOR_FIGURA))


def _inteiro(valor: str) -> int | None:
    valor = (valor or "").strip()
    return int(float(valor)) if valor else None


def _numero(valor: str) -> float | None:
    valor = (valor or "").strip().replace(",", ".")
    return float(valor) if valor else None
