"""Parsers do Guia de Cursos da UFSC (https://guiadecursos.ufsc.br/listagem/).

Funções puras: recebem o HTML (texto) e devolvem dados. Nenhuma faz requisição, por
isso dá para testar tudo com os HTMLs salvos em tests/fixtures/ufsc/.
"""

from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

URL_BASE = "https://guiadecursos.ufsc.br/"


@dataclass
class CursoListado:
    """Uma linha da tabela "Por Nome do Curso": nome, campus e link da página."""

    nome: str
    campus: str
    url: str


@dataclass
class DetalhesCurso:
    """Campos da página do curso no guia. None quando não aparecem."""

    titulo: str | None = None  # ex.: "Química (Licenciatura, Bacharelado e Tecnológica)"
    sobre: str | None = None


def extrair_lista(html: str) -> list[CursoListado]:
    """Linhas da tabela de cursos (coluna 1 = nome com o link, coluna 2 = campus).

    Os cursos a distância ficam numa página à parte (graduacao-a-distancia), fora da tabela.
    """
    soup = BeautifulSoup(html, "html.parser")
    cursos = []
    for linha in soup.select("table tr"):
        colunas = linha.find_all("td")
        link = colunas[0].find("a") if colunas else None
        if len(colunas) < 2 or link is None or not link.get("href"):
            continue
        cursos.append(
            CursoListado(
                nome=_limpar(link.get_text()),
                campus=_limpar(colunas[1].get_text()),
                url=urljoin(URL_BASE, link["href"]),
            )
        )
    return cursos


def extrair_detalhes(html: str) -> DetalhesCurso:
    """Título e texto da página do curso.

    O `sobre` é o texto corrido até o primeiro separador (<hr>). Depois dele vêm os
    depoimentos de estudantes, com nome (ficam de fora por LGPD), e o quadro "Visite o
    site do curso". Os subtítulos ("Formação Prática") não entram, só os parágrafos.
    """
    soup = BeautifulSoup(html, "html.parser")
    artigo = soup.find("article")
    if artigo is None:
        return DetalhesCurso()
    titulo = artigo.find("h2")
    conteudo = artigo.find(class_="content") or artigo

    textos = []
    for tag in conteudo.find_all(["p", "li", "hr", "h3"]):
        if tag.name == "hr" or _e_depoimento(tag) or _e_visite_o_site(tag):
            break
        if tag.name == "h3" or (tag.name == "p" and tag.find_parent("li")):
            continue
        texto = _limpar(tag.get_text(" "))
        if texto:
            textos.append(f"- {texto}" if tag.name == "li" else texto)
    return DetalhesCurso(
        titulo=_limpar(titulo.get_text()) if titulo else None,
        sobre=_juntar(textos),
    )


def _e_depoimento(tag) -> bool:
    """Depoimento: parágrafo que abre com a imagem de aspas ("newaspas-in.png")."""
    return any("aspas" in (img.get("src") or "") for img in tag.find_all("img"))


def _e_visite_o_site(tag) -> bool:
    return tag.name == "h3" and "visite o site" in tag.get_text().lower()


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
    """Espaços repetidos viram um só; também corrige o espaço antes de pontuação que
    sobra das tags <strong>/<a> no meio da frase ("Ação Júnior ." -> "Ação Júnior.")."""
    texto = " ".join(texto.replace("\xa0", " ").split())
    for sinal in (".", ",", ";", ":", ")"):
        texto = texto.replace(f" {sinal}", sinal)
    return texto.replace("( ", "(")
