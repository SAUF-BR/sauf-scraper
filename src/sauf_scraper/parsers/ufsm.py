"""Parsers do site de cursos da UFSM (https://www.ufsm.br/cursos/graduacao/<campus>/<curso>/).

Funções puras: recebem o texto (robots.txt ou HTML) e devolvem dados. Nenhuma faz
requisição, por isso dá para testar tudo com os arquivos salvos em tests/fixtures/ufsm/.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

# Linha "Sitemap:" do robots.txt de um curso, ex.:
# Sitemap: https://www.ufsm.br/cursos/graduacao/santa-maria/administracao/wp-sitemap.xml
_SITEMAP_CURSO = re.compile(
    r"^Sitemap:\s*(https://www\.ufsm\.br/cursos/graduacao/([a-z0-9-]+)/([a-z0-9-]+)/)wp-sitemap\.xml",
    re.IGNORECASE | re.MULTILINE,
)
CAMPUS_EAD = "educacao-a-distancia"

# Frases do bloco "Apresentação" (o mesmo texto-modelo em todos os cursos):
# "O curso de Dança está localizado em Campus Camobi – UFSM na modalidade Bacharelado –
# Presencial , sendo Diurno o seu turno de funcionamento."
_LOCALIZACAO = re.compile(
    r"O curso de (?P<nome>.+?) está localizado em .+? na modalidade (?P<grau>[^–-]+?)\s*[–-]\s*"
    r"(?P<modalidade>[^,]+?)\s*,\s*sendo (?P<turno>.+?) o seu turno",
    re.IGNORECASE,
)
# "O curso é ofertado em período Semestral , sendo 8 o número de períodos indicados..."
_PERIODOS = re.compile(
    r"ofertado em período (?P<regime>\w+)\s*,\s*sendo (?P<quantidade>\d+) o número de períodos",
    re.IGNORECASE,
)

# Título de seção (sem acento, minúsculo) da página "Sobre o curso" que vira mercado de trabalho.
_SECOES_MERCADO = {
    "areas de atuacao",
    "area de atuacao",
    "atuacao profissional",
    "campo de atuacao",
    "campo de atuacao profissional",
    "mercado de trabalho",
}


@dataclass
class CursoListado:
    """Um curso achado no robots.txt: pasta do campus e pasta do curso."""

    campus: str  # ex.: "santa-maria"
    pasta: str  # ex.: "administracao"
    url: str  # página principal do curso, com barra no fim


@dataclass
class Habilitacao:
    """Um bloco do texto-modelo "Apresentação" (uma habilitação num turno)."""

    nome: str  # nome do curso no bloco, ex.: "Ciências Biológicas"
    grau: str  # ex.: "Bacharelado", "Licenciatura"
    modalidade: str  # ex.: "Presencial"
    turno: str  # ex.: "Diurno", "Noturno", "Integral"
    regime: str | None = None  # "Semestral" ou "Anual"
    periodos: int | None = None


@dataclass
class DetalhesCurso:
    """Campos da página principal do curso. None quando não aparecem."""

    titulo: str | None = None  # ex.: "Dança – Bacharelado"
    habilitacoes: list[Habilitacao] = field(default_factory=list)


@dataclass
class SobreCurso:
    """Campos da página "Sobre o curso"."""

    sobre: str | None = None
    mercado_trabalho: str | None = None


def extrair_lista(robots: str) -> list[CursoListado]:
    """Cursos pelas linhas Sitemap do robots.txt (o site não tem uma página com a lista).

    Os cursos a distância (pasta "educacao-a-distancia") ficam de fora.
    """
    cursos: list[CursoListado] = []
    for encontrado in _SITEMAP_CURSO.finditer(robots):
        url, campus, pasta = encontrado.groups()
        curso = CursoListado(campus=campus.lower(), pasta=pasta.lower(), url=url)
        if curso.campus != CAMPUS_EAD and curso not in cursos:
            cursos.append(curso)
    return cursos


def extrair_detalhes(html: str) -> DetalhesCurso:
    """Título e habilitações do bloco "Apresentação" da página principal do curso.

    Só as frases do texto-modelo são lidas (grau, modalidade, turno e períodos). A mesma
    frase cita coordenação e secretaria pelo nome: essa parte fica de fora (LGPD). O bloco
    "Núcleo Comum" (ABI, entrada antes de escolher a habilitação) também fica de fora.
    """
    soup = BeautifulSoup(html, "html.parser")
    habilitacoes: list[Habilitacao] = []
    for paragrafo in soup.find_all("p"):
        texto = _limpar(paragrafo.get_text(" "))
        localizacao = _LOCALIZACAO.search(texto)
        # O bloco às vezes vem repetido dentro de outro <p>: só vale o mais interno.
        if not localizacao or paragrafo.find("p"):
            continue
        if _normalizar(localizacao["nome"]).startswith("abi"):
            continue
        periodos = paragrafo.find_next(lambda t: t.name == "p" and "número de períodos" in t.text)
        periodos = _PERIODOS.search(_limpar(periodos.get_text(" "))) if periodos else None
        habilitacao = Habilitacao(
            nome=localizacao["nome"].strip(),
            grau=localizacao["grau"].strip(),
            modalidade=localizacao["modalidade"].strip(),
            turno=localizacao["turno"].strip(),
            regime=periodos["regime"] if periodos else None,
            periodos=int(periodos["quantidade"]) if periodos else None,
        )
        if habilitacao not in habilitacoes:
            habilitacoes.append(habilitacao)
    return DetalhesCurso(titulo=_titulo(soup), habilitacoes=habilitacoes)


def extrair_sobre(html: str) -> SobreCurso:
    """Texto da página "Sobre o curso"; a seção "Áreas de atuação" (e variações) vai para
    o mercado de trabalho, o resto para o sobre (com os subtítulos, como "O perfil do
    formando", em linha própria)."""
    soup = BeautifulSoup(html, "html.parser")
    conteudo = soup.find(class_="entry-content")
    if conteudo is None:
        return SobreCurso()

    sobre: list[str] = []
    mercado: list[str] = []
    destino = sobre
    for tag in conteudo.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        # Um texto entra uma vez só: <p> dentro de <li> fica com o item; bloco que tem
        # <p> dentro fica com os parágrafos.
        if (tag.name == "p" and tag.find_parent("li")) or (tag.name != "li" and tag.find("p")):
            continue
        texto = _limpar(tag.get_text(" "))
        if not texto:
            continue
        if _e_titulo(tag, texto):
            destino = mercado if _normalizar(texto.rstrip(":")) in _SECOES_MERCADO else sobre
            if destino is sobre:
                sobre.append(texto)
            continue
        destino.append(f"- {texto}" if tag.name == "li" else texto)
    return SobreCurso(sobre=_juntar(sobre), mercado_trabalho=_juntar(mercado))


def _titulo(soup: BeautifulSoup) -> str | None:
    """'Dança – Bacharelado – Curso de Graduação – Campus Santa Maria' -> 'Dança – Bacharelado'
    (alguns títulos dizem "Cursos de Graduação")."""
    if soup.title is None:
        return None
    titulo = _limpar(soup.title.get_text())
    return re.split(r"\s+[–-]\s+Cursos? de Graduação", titulo)[0].strip() or None


def _e_titulo(tag, texto: str) -> bool:
    """Subtítulo: tag de título, ou parágrafo curto sem ponto final ("O perfil do formando")."""
    if tag.name.startswith("h"):
        return True
    return tag.name == "p" and len(texto) <= 60 and not texto.endswith((".", ";", "!", "?"))


def _juntar(textos: list[str]) -> str | None:
    """Um parágrafo por texto; itens de lista seguidos ficam em linhas seguidas (D-37)."""
    resultado = ""
    for texto in textos:
        if resultado:
            junta_lista = texto.startswith("- ") and resultado.split("\n")[-1].startswith("- ")
            resultado += "\n" if junta_lista else "\n\n"
        resultado += texto
    return resultado or None


def _limpar(texto: str) -> str:
    """Espaços repetidos viram um só, sem o espaço antes de vírgula e ponto ("Presencial ,")."""
    texto = " ".join(texto.replace("\xa0", " ").split())
    for sinal in (".", ",", ";", ":"):
        texto = texto.replace(f" {sinal}", sinal)
    return texto


def _normalizar(texto: str | None) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())
