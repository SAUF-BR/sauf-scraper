"""Parsers do site de graduação da UEM (https://www.pen.uem.br/site/public/cursos).

Funções puras: recebem o HTML (texto) e devolvem dados. Nenhuma faz requisição, por
isso dá para testar tudo com os HTMLs salvos em tests/fixtures/uem/.
"""

from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString

# Rótulo na página do curso -> atributo do DetalhesCurso.
_ROTULOS = {
    "Turno": "turno",
    "Habilitação": "habilitacao",
    "Prazo Mínimo de Conclusão": "prazo_minimo",
    "Prazo Máximo de Conclusão": "prazo_maximo",
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
        atributo = _ROTULOS.get(rotulo.get_text(strip=True).rstrip(":").strip())
        if atributo is None:
            continue
        valor = rotulo.next_sibling
        if isinstance(valor, NavigableString) and valor.strip():
            setattr(detalhes, atributo, valor.strip())
    return detalhes
