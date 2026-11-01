"""Parsers do site da UTFPR (https://www.utfpr.edu.br/cursos/graduacao).

O site é Plone 6 com Volto: o HTML chega vazio e o conteúdo vem de uma API JSON pública,
que responde em /++api++/<caminho da página>. Estas funções recebem esse JSON (já como
dict) e devolvem dados. Nenhuma faz requisição, então dá para testar tudo com os arquivos
salvos em tests/fixtures/utfpr/.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

CAMINHO_CURSOS = "/cursos/coordenacoes/graduacao/"

# Título de seção (sem acento, minúsculo) -> onde o texto vai.
_SECOES_SOBRE = {"sobre o curso", "o curso", "sobre", "apresentacao", "objetivos do curso"}
_SECOES_PERFIL = {"perfil do egresso", "perfil profissional", "perfil do profissional"}
_SECOES_MERCADO = {
    "atuacao",
    "atuacao profissional",
    "campo de atuacao",
    "areas de atuacao",
    "mercado de trabalho",
    "onde trabalhar",
}

# Rótulo da tabela "Dados Sobre o Curso" -> atributo de DetalhesCurso. O valor vem depois do
# rótulo, com ou sem dois-pontos ("Turno: Noturno" ou "Turno Noturno").
_ROTULOS = {
    "turno": re.compile(r"^\W*turnos?\s*:?\s*(.+)$", re.IGNORECASE),
    "duracao": re.compile(r"^\W*dura[cç][aã]o\s*:?\s*(.+)$", re.IGNORECASE),
    "titulacao": re.compile(r"^\W*titula[cç][aã]o\s*:?\s*(.+)$", re.IGNORECASE),
}


@dataclass
class CursoListado:
    """Um curso da busca da API: a pasta do curso dentro da pasta do campus."""

    nome: str
    campus: str  # pasta do campus, ex.: "cornelio-procopio"
    url: str  # URL pública da pasta do curso (sem /++api++/)


@dataclass
class Elemento:
    """Um pedaço de texto da página, na ordem em que aparece."""

    tipo: str  # "titulo", "texto" ou "linha" (linha de tabela, ex.: "Turno: Noturno")
    texto: str


@dataclass
class DetalhesCurso:
    """Campos da página "Apresentação" do curso. None quando não aparecem."""

    sobre: str | None = None
    perfil: str | None = None
    mercado_trabalho: str | None = None
    turno: str | None = None
    duracao: str | None = None
    titulacao: str | None = None  # ex.: "Bacharel em Engenharia de Software"
    filhos: list[str] = field(default_factory=list)  # páginas filhas (@id), se a página só lista


def extrair_lista(busca: dict) -> list[CursoListado]:
    """Cursos da busca /@search?path.depth=2 na pasta de graduação.

    O resultado traz as pastas dos campi (1 nível) e as pastas dos cursos (2 níveis);
    só as de 2 níveis são cursos.
    """
    cursos = []
    for item in busca.get("items", []):
        caminho = item["@id"].split(CAMINHO_CURSOS, 1)[-1].strip("/").split("/")
        if len(caminho) != 2:
            continue
        cursos.append(CursoListado(nome=item["title"].strip(), campus=caminho[0], url=item["@id"]))
    return cursos


def campi_da_lista(busca: dict) -> dict[str, str]:
    """Pasta do campus -> nome da cidade, ex.: "cornelio-procopio" -> "Cornélio Procópio"."""
    campi = {}
    for item in busca.get("items", []):
        caminho = item["@id"].split(CAMINHO_CURSOS, 1)[-1].strip("/").split("/")
        if len(caminho) == 1:
            campi[caminho[0]] = item["title"].strip()
    return campi


def extrair_detalhes(pagina: dict) -> DetalhesCurso:
    """Lê os blocos da página na ordem e separa as seções pelo título.

    - texto antes do primeiro título, ou sob "Sobre o Curso"/"O Curso" -> sobre;
    - "Perfil do Egresso" -> perfil;
    - "Atuação", "Campo de atuação", "Mercado de trabalho"... -> mercado de trabalho;
    - linhas "Turno", "Duração" e "Titulação" da tabela "Dados Sobre o Curso";
    - outras seções ("Formação", "Autorização e Reconhecimento"...) ficam de fora.
    """
    detalhes = DetalhesCurso(filhos=[i["@id"] for i in pagina.get("items", []) if "@id" in i])
    partes: dict[str, list[str]] = {"sobre": [], "perfil": [], "mercado": []}
    destino: str | None = "sobre"  # o texto antes do primeiro título é a apresentação

    for elemento in elementos_da_pagina(pagina):
        if elemento.tipo == "linha" or _eh_dado(elemento.texto):
            _guardar_dado(detalhes, elemento.texto)
            continue
        if elemento.tipo == "titulo":
            destino = _destino_do_titulo(elemento.texto)
            continue
        if destino:
            partes[destino].append(elemento.texto)

    detalhes.sobre = _juntar(partes["sobre"])
    detalhes.perfil = _juntar(partes["perfil"])
    detalhes.mercado_trabalho = _juntar(partes["mercado"])
    return detalhes


def elementos_da_pagina(pagina: dict) -> list[Elemento]:
    """Transforma os blocos do Volto (slate, tabela, html) numa lista de títulos e textos."""
    elementos: list[Elemento] = []
    blocos = pagina.get("blocks", {})
    for chave in pagina.get("blocks_layout", {}).get("items", []):
        bloco = blocos.get(chave, {})
        tipo = bloco.get("@type")
        if tipo == "slate":
            elementos += _elementos_slate(bloco.get("value", []))
        elif tipo == "slateTable":
            for linha in bloco.get("table", {}).get("rows", []):
                celulas = [_texto_slate(c.get("value", [])) for c in linha.get("cells", [])]
                celulas = [c for c in celulas if c]
                if len(celulas) == 2 and "\n" not in "".join(celulas):
                    # Tabela de duas colunas: rótulo | valor.
                    elementos.append(Elemento("linha", ": ".join(celulas)))
                else:
                    # Uma célula só, com uma linha por dado ("Turno: Integral" / "Duração: 5 anos").
                    for celula in celulas:
                        elementos += [Elemento("linha", t) for t in celula.split("\n")]
        elif tipo == "html":
            elementos += _elementos_html(bloco.get("html", ""))
    return elementos


def _elementos_slate(valor: list) -> list[Elemento]:
    elementos = []
    for no in valor:
        tipo = no.get("type", "p")
        if tipo in ("ul", "ol"):
            for item in no.get("children", []):
                texto = _texto_slate([item])
                if texto:
                    elementos.append(Elemento("texto", f"- {texto}"))
            continue
        texto = _texto_slate([no])
        if texto:
            titulo = tipo in ("h1", "h2", "h3", "h4") or _paragrafo_em_negrito(no, texto)
            elementos.append(Elemento("titulo" if titulo else "texto", texto))
    return elementos


def _paragrafo_em_negrito(no: dict, texto: str) -> bool:
    """Parágrafo curto todo em negrito também é título, ex.: "Perfil do Egresso"."""
    filhos = [f for f in no.get("children", []) if f.get("text", "x").strip()]
    return (
        len(texto) < 60
        and "\n" not in texto
        and bool(filhos)
        and all(f.get("type") == "strong" for f in filhos)
    )


def _elementos_html(html: str) -> list[Elemento]:
    soup = BeautifulSoup(html, "html.parser")
    elementos = []
    # Fichas em HTML puro trazem o rótulo e o valor em elementos separados
    # ("🕒 Turno" e, logo depois, "Manhã e Tarde"): vira a linha "Turno: Manhã e Tarde".
    textos = [_limpar(t) for t in soup.stripped_strings]
    for i, texto in enumerate(textos[:-1]):
        if _normalizar(texto) in ("turno", "duracao", "titulacao"):
            elementos.append(Elemento("linha", f"{_normalizar(texto)}: {textos[i + 1]}"))
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "tr"]):
        if tag.name in ("p", "li") and tag.find_parent(["li", "tr"]):
            continue
        partes = [c.get_text(" ", strip=True) for c in tag.find_all(["td", "th"])] or [
            tag.get_text(" ", strip=True)
        ]
        texto = _limpar(": ".join(p for p in partes if p))
        if not texto:
            continue
        if tag.name.startswith("h"):
            elementos.append(Elemento("titulo", texto))
        elif tag.name == "tr":
            elementos.append(Elemento("linha", texto))
        else:
            elementos.append(Elemento("texto", f"- {texto}" if tag.name == "li" else texto))
    return elementos


def _texto_slate(nos: list) -> str:
    """Texto puro de nós slate (folhas têm "text"; os demais, "children")."""
    pedacos = []

    def visitar(no):
        if "text" in no:
            pedacos.append(no["text"])
        for filho in no.get("children", []):
            visitar(filho)

    for no in nos:
        visitar(no)
    linhas = [_limpar(linha) for linha in "".join(pedacos).split("\n")]
    return "\n".join(linha for linha in linhas if linha)


def _destino_do_titulo(titulo: str) -> str | None:
    nome = _normalizar(titulo)
    if nome in _SECOES_SOBRE:
        return "sobre"
    if nome in _SECOES_PERFIL:
        return "perfil"
    if nome in _SECOES_MERCADO:
        return "mercado"
    return None


def _eh_dado(texto: str) -> bool:
    """Parágrafo solto com um dado ("Turno: Noturno"). Exige dois-pontos ou texto curto,
    para não confundir com frases como "Turno da manhã permite estagiar à tarde..."."""
    for padrao in _ROTULOS.values():
        if padrao.match(texto) and (":" in texto[:20] or len(texto) < 40):
            return True
    return False


# Onde começa o próximo dado quando a ficha vem toda numa linha só
# ("Integral Duração: 4 anos Carga Horária Total…" ou até "NoturnoDuração: 4 anos").
_PROXIMO_ROTULO = re.compile(
    r"(?=dura[cç][aã]o\b|carga hor|est[aá]gio|vagas\b|titula[cç][aã]o|in[ií]cio d|"
    r"atividades? compl|abertura d)",
    re.IGNORECASE,
)


def separar_rotulos(linha: str) -> list[str]:
    """'Integral Duração: 4 anos Vagas: 44' -> ['Integral', 'Duração: 4 anos', 'Vagas: 44']."""
    pedacos = [p.strip() for p in _PROXIMO_ROTULO.split(linha)]
    return [p for p in pedacos if p]


def _guardar_dado(detalhes: DetalhesCurso, texto: str) -> None:
    """'Turno: Noturno' / 'Turno Noturno' -> detalhes.turno = 'Noturno' (só o primeiro)."""
    pedacos = separar_rotulos(texto)
    for pedaco in pedacos:
        for atributo, padrao in _ROTULOS.items():
            encontrado = padrao.match(pedaco)
            if encontrado and getattr(detalhes, atributo) is None:
                setattr(detalhes, atributo, encontrado.group(1).strip(" :"))


def _juntar(textos: list[str]) -> str | None:
    """Um parágrafo por texto; itens de lista seguidos ficam em linhas seguidas."""
    resultado = ""
    for texto in textos:
        if resultado:
            junta_lista = texto.startswith("- ") and resultado.split("\n")[-1].startswith("- ")
            resultado += "\n" if junta_lista else "\n\n"
        resultado += texto
    return resultado or None


def _limpar(texto: str) -> str:
    return " ".join(texto.replace("\xa0", " ").split())


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def _normalizar(texto: str) -> str:
    """Minúsculas, sem acento, sem emoji e sem pontuação: "🎓 O Curso" -> "o curso"."""
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", _sem_acento(texto).lower()).split())
