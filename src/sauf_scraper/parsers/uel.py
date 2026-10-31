"""Parsers do site de graduação da UEL (https://sites.uel.br/prograd/cursos-de-graduacao-da-uel/).

Funções puras: recebem o HTML (texto) e devolvem dados. Nenhuma faz requisição, por
isso dá para testar tudo com os HTMLs salvos em tests/fixtures/uel/.
"""

from dataclasses import dataclass, field

from bs4 import BeautifulSoup

DOMINIO_CURSOS = "graduacao.uel.br"

# Título da coluna no bloco do curso -> atributo de OpcaoUel.
_ROTULOS = {
    "grau acadêmico": "grau",
    "modalidade": "modalidade",
    "turno": "turno",
    "vagas": "vagas",
    "duração": "duracao",
}


@dataclass
class CursoListado:
    """Um item da página de lista de cursos."""

    nome: str
    url: str


@dataclass
class OpcaoUel:
    """Uma coluna do bloco do curso: um grau num turno, com vagas e duração próprias."""

    grau: str | None = None
    modalidade: str | None = None
    turno: str | None = None
    vagas: str | None = None
    duracao: str | None = None


@dataclass
class DetalhesCurso:
    """Campos da página de um curso. None quando o campo não aparece na página."""

    nome: str | None = None
    centro: str | None = None  # ex.: "Centro de Estudos Sociais Aplicados (CESA)"
    sobre: str | None = None  # frase de chamada abaixo do título
    opcoes: list[OpcaoUel] = field(default_factory=list)


def extrair_lista(html: str) -> list[CursoListado]:
    """Devolve os cursos que têm página no catálogo graduacao.uel.br.

    Ficam de fora os cursos a distância (o link vai para o site do NEAD) e os cursos
    novos ainda sem página (o link vai para o PDF da resolução de criação).
    """
    soup = BeautifulSoup(html, "html.parser")
    artigo = soup.find("article") or soup

    cursos = []
    for link in artigo.find_all("a"):
        url = link.get("href", "")
        if DOMINIO_CURSOS not in url:
            continue
        cursos.append(CursoListado(nome=link.get_text(strip=True), url=url))
    return cursos


def extrair_detalhes(html: str) -> DetalhesCurso:
    """Lê o cabeçalho e o bloco "Grau acadêmico / Modalidade / Turno / Vagas / Duração".

    O bloco aparece duas vezes no HTML (versão de computador e de celular); só a de
    computador (classe "d-lg-block") é lida. Em cada item, a 1ª coluna é a 1ª opção do
    curso, a 2ª coluna é a 2ª opção, e assim por diante.
    Coordenação, corpo docente e contatos ficam em outras páginas, que não são visitadas.
    """
    soup = BeautifulSoup(html, "html.parser")
    detalhes = DetalhesCurso(
        nome=_texto(soup.find(class_="site-title")),
        centro=_texto(soup.find("p", class_="centro-estudos")),
        sobre=_texto(soup.find(class_="site-long-description")),
    )

    bloco = soup.find("div", class_="d-lg-block")
    if bloco is None:
        return detalhes

    colunas: dict[str, list[str]] = {}
    for item in bloco.find_all("div", class_="info-top-curso"):
        titulo = _texto(item.find(class_="curso-info-title"))
        atributo = _ROTULOS.get((titulo or "").lower())
        if atributo:
            colunas[atributo] = [_texto(d) for d in item.find_all(class_="curso-info-desc")]

    total = max((len(valores) for valores in colunas.values()), default=0)
    for i in range(total):
        opcao = OpcaoUel(**{a: v[i] if i < len(v) else None for a, v in colunas.items()})
        if opcao not in detalhes.opcoes:  # mesma coluna repetida = mesma opção
            detalhes.opcoes.append(opcao)
    return detalhes


def _texto(elemento) -> str | None:
    if elemento is None:
        return None
    return " ".join(elemento.get_text(" ", strip=True).split()) or None
