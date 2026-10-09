"""Parsers do site de graduação da UEM (https://www.pen.uem.br/site/public/cursos).

Funções puras: recebem o HTML (texto) e devolvem dados. Nenhuma faz requisição, por
isso dá para testar tudo com os HTMLs salvos em tests/fixtures/uem/.
"""

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString

_ROTULOS = {
    "turno": "turno",
    "turnos": "turno",
    "habilitação": "habilitacao",
    "habilitações": "habilitacao",
    "prazo mínimo de conclusão": "prazo_minimo",
    "prazo máximo de conclusão": "prazo_maximo",
}


@dataclass
class CursoListado:
    """Um item da página de lista de cursos."""

    nome: str
    campus: str
    url: str


@dataclass
class DetalhesCurso:
    """Campos da página de um curso. None quando o campo não aparece na página."""

    turno: str | None = None
    habilitacao: str | None = None  # Bacharelado, etc...
    prazo_minimo: str | None = None
    prazo_maximo: str | None = None
    sobre: str | None = None  # texto da seção "Sobre o Curso"
    mercado_trabalho: str | None = None  # texto da seção "Mercado de Trabalho"


def extrair_lista(html: str) -> list[CursoListado]:
    """Devolve todos os cursos presenciais da página de lista.

    Cada campus é um <p class="text-xl"> seguido de um <ul> com os links dos cursos.
    O bloco "Modalidade de Educação a Distância" aponta para outro site (sem "/curso/"
    no link) e fica de fora.
    """
    soup = BeautifulSoup(html, "html.parser")

    cursos = []
    for cabecalho in soup.find_all("p", class_="text-xl"):
        campus = cabecalho.get_text(strip=True)
        lista = cabecalho.find_next_sibling("ul")
        if lista is None:
            continue
        for link in lista.find_all("a"):
            url = link.get("href", "")
            if "/curso/" not in url:
                continue
            cursos.append(CursoListado(nome=link.get_text(strip=True), campus=campus, url=url))
    return cursos


_GRAU_E_TURNO = re.compile(r"(licenciatura|bacharelado)[^()]*?\(([^)]+)\)", re.IGNORECASE)
_TURNO_E_GRAU = re.compile(r"^\s*(.+?)\s*\((licenciatura|bacharelado)\)\s*$", re.IGNORECASE)


def turnos_por_grau(habilitacao: str | None, turno: str | None) -> dict[str, str]:
    """Turno de cada grau quando a página especifica, ex.:

    "Licenciatura (Integral ou Noturno) ou Bacharelado (Integral)"
        -> {"licenciatura": "Integral ou Noturno", "bacharelado": "Integral"}
    "Noturno (Licenciatura) ou Vespertino/Noturno (Bacharelado)"  (no campo Turno)
        -> {"licenciatura": "Noturno", "bacharelado": "Vespertino/Noturno"}
    """
    turnos: dict[str, str] = {}
    for grau, texto in _GRAU_E_TURNO.findall(habilitacao or ""):
        turnos[grau.lower()] = _formatar_turno(texto)
    for parte in re.split(r"\s+ou\s+", turno or "", flags=re.IGNORECASE):
        encontrado = _TURNO_E_GRAU.match(parte)
        if encontrado:
            turnos.setdefault(encontrado.group(2).lower(), _formatar_turno(encontrado.group(1)))
    return turnos


def _formatar_turno(texto: str) -> str:
    """'vespertino / noturno' -> 'Vespertino/Noturno' ("ou" e "e" ficam em minúsculas)."""
    texto = re.sub(r"\s*/\s*", "/", " ".join(texto.split()))
    return re.sub(
        r"[^\W\d_]+", lambda p: p[0] if p[0].lower() in ("ou", "e") else p[0].capitalize(), texto
    )


def extrair_detalhes(html: str) -> DetalhesCurso:
    """Lê os campos rotulados da página de um curso.

    Os campos vêm como <strong>Turno:</strong> Noturno<br/>: o valor é o texto logo
    depois do rótulo. Algumas páginas usam <b> no lugar de <strong>, e algumas não têm
    todos os campos (ex.: Letras não informa o turno).
    Dados da coordenação (nome e e-mail) não são coletados (LGPD).
    """
    soup = BeautifulSoup(html, "html.parser")

    detalhes = DetalhesCurso()
    for rotulo in soup.find_all(["strong", "b"]):
        atributo = _ROTULOS.get(_nome_rotulo(rotulo))
        if atributo is None:
            continue
        valor = rotulo.next_sibling
        if not isinstance(valor, NavigableString):
            continue
        texto = valor.strip().lstrip(":").strip()
        if texto:
            setattr(detalhes, atributo, texto)

    detalhes.sobre = extrair_secao(soup, "sobre o curso")
    detalhes.mercado_trabalho = extrair_secao(soup, "mercado de trabalho")
    if detalhes.mercado_trabalho is None and detalhes.sobre:
        detalhes.sobre, detalhes.mercado_trabalho = separar_mercado(detalhes.sobre)
    return detalhes


_TITULO_MERCADO = re.compile(r"^mercado de trabalho:?$", re.IGNORECASE | re.MULTILINE)


def separar_mercado(sobre: str) -> tuple[str | None, str | None]:
    """Separa o "Mercado de trabalho" escrito sem negrito, como linha solta dentro do "Sobre".

    Na maioria das páginas da UEM o título é texto puro no começo de um parágrafo, então
    `extrair_secao` não o reconhece como rótulo e ele fica dentro do `sobre`.
    """
    titulo = _TITULO_MERCADO.search(sobre)
    if titulo is None:
        return sobre, None
    return sobre[: titulo.start()].strip() or None, sobre[titulo.end() :].strip() or None


_SECOES = {"sobre o curso", "mercado de trabalho", "mais informações", "coordenação"}


def extrair_secao(soup: BeautifulSoup, titulo: str) -> str | None:
    """Texto puro de uma seção da página, ex.: "Sobre o Curso", sem HTML.

    A seção começa depois do rótulo (<strong> ou <b>) e vai até o próximo rótulo de
    seção (`_SECOES`) ou até o fim do bloco de conteúdo. <br> vira quebra de linha e cada
    parágrafo novo vira linha em branco.
    """
    rotulo = next((r for r in soup.find_all(["strong", "b"]) if _nome_rotulo(r) == titulo), None)
    if rotulo is None:
        return None
    bloco = rotulo.find_parent("div") or soup
    dentro_do_bloco = {id(elemento) for elemento in bloco.descendants}

    partes: list[str] = []
    for elemento in rotulo.next_elements:
        if id(elemento) not in dentro_do_bloco:
            break
        if isinstance(elemento, NavigableString):
            if not any(p is rotulo for p in elemento.parents):
                partes.append(re.sub(r"\s+", " ", str(elemento)))
        elif elemento.name in ("strong", "b") and _nome_rotulo(elemento) in _SECOES:
            break
        elif elemento.name == "br":
            partes.append("\n")
        elif elemento.name in ("p", "div", "li"):
            partes.append("\n\n")
    return _limpar_texto("".join(partes))


def _nome_rotulo(rotulo) -> str:
    return " ".join(rotulo.get_text(" ", strip=True).rstrip(":").split()).lower()


def _limpar_texto(texto: str) -> str | None:
    paragrafos = []
    for bloco in re.split(r"\n\s*\n", texto):
        linhas = [" ".join(linha.split()) for linha in bloco.split("\n")]
        linhas = [linha for linha in linhas if linha and linha != ":"]
        if linhas:
            paragrafos.append("\n".join(linhas))
    return "\n\n".join(paragrafos) or None
