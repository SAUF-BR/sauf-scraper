"""Contrato que todo spider (um por instituição) precisa cumprir.

Divisão de responsabilidades (contexto consolidado, seção 5):
- O spider BAIXA (usa self.http.get) e decide quais páginas visitar.
- O parser (em sauf_scraper/parsers/) CONVERTE HTML/JSON bruto em dicts ou modelos.
- O spider monta o LoteIngestao no final; o Pydantic valida tudo nessa hora.
"""

from abc import ABC, abstractmethod

from sauf_scraper.client.http import HttpEducado
from sauf_scraper.core.models import LoteIngestao


class Spider(ABC):
    #: Apelido curto do spider, ex.: "uel". Usado só no CLI (--ies uel) e nos logs.
    #: Não vai para o backend como identificador da instituição.
    chave: str
    #: Código da instituição no cadastro e-MEC (ex.: 57). É o que liga os cursos à
    #: instituição no backend e define quais IES o import do CSV do e-MEC deve trazer.
    codigo_emec: int

    def __init__(self, http: HttpEducado, execucao_id: str) -> None:
        self.http = http
        self.execucao_id = execucao_id

    @abstractmethod
    def coletar(self) -> LoteIngestao:
        """Baixa, converte e devolve tudo da instituição. Pode lançar exceção à vontade:
        o pipeline isola a falha e segue para a próxima instituição."""
