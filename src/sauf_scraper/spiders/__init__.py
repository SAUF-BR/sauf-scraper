"""Registro dos spiders disponíveis.

Para adicionar uma instituição: crie spiders/<chave>.py com uma classe que herda
de Spider e registre aqui, ex.:

    from sauf_scraper.spiders.uel import UelSpider
    SPIDERS = {UelSpider.chave: UelSpider}
"""

from sauf_scraper.spiders.base import Spider
from sauf_scraper.spiders.uel import UelSpider
from sauf_scraper.spiders.uem import UemSpider
from sauf_scraper.spiders.utfpr import UtfprSpider

SPIDERS: dict[str, type[Spider]] = {
    UemSpider.chave: UemSpider,
    UelSpider.chave: UelSpider,
    UtfprSpider.chave: UtfprSpider,
}


def codigos_emec() -> list[int]:
    """Códigos e-MEC das instituições com spider. O import do CSV do e-MEC filtra por eles."""
    return sorted(s.codigo_emec for s in SPIDERS.values())
