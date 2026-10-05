"""Cliente HTTP "educado" usado pelos spiders para baixar páginas das universidades.

Faz três coisas por você, para nenhum spider esquecer:
1. Identifica o bot com um User-Agent próprio.
2. Respeita o robots.txt de cada site (cacheado por domínio).
3. Espera `request_delay_seconds` entre requisições ao mesmo domínio.
"""

import logging
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

from sauf_scraper.core.config import Settings

logger = logging.getLogger(__name__)


class BloqueadoPorRobotsError(Exception):
    """O robots.txt do site não permite acessar essa URL."""


class HttpEducado:
    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self._settings = settings
        self._session = session or requests.Session()
        self._session.headers["User-Agent"] = settings.user_agent
        self._robots: dict[str, RobotFileParser] = {}
        self._ultima_requisicao: dict[str, float] = {}

    def get(self, url: str, **kwargs) -> requests.Response:
        dominio = self._dominio(url)
        if not self._permitido(url, dominio):
            raise BloqueadoPorRobotsError(url)
        self._esperar_vez(dominio)

        kwargs.setdefault("timeout", self._settings.request_timeout_seconds)
        resposta = self._session.get(url, **kwargs)
        self._ultima_requisicao[dominio] = time.monotonic()
        logger.info("GET", extra={"dados": {"url": url, "status": resposta.status_code}})
        resposta.raise_for_status()
        return resposta

    @staticmethod
    def _dominio(url: str) -> str:
        partes = urlsplit(url)
        return f"{partes.scheme}://{partes.netloc}"

    def _permitido(self, url: str, dominio: str) -> bool:
        if dominio not in self._robots:
            parser = RobotFileParser()
            try:
                r = self._session.get(
                    f"{dominio}/robots.txt", timeout=self._settings.request_timeout_seconds
                )
                # Sem robots.txt (404) = tudo liberado; robots.txt protegido (401/403) = nada.
                if r.status_code in (401, 403):
                    parser.disallow_all = True
                elif r.ok:
                    parser.parse(r.text.splitlines())
                else:
                    parser.allow_all = True
            except requests.RequestException:
                logger.warning("robots.txt inacessível", extra={"dados": {"dominio": dominio}})
                parser.allow_all = True
            self._robots[dominio] = parser
        return self._robots[dominio].can_fetch(self._settings.user_agent, url)

    def _esperar_vez(self, dominio: str) -> None:
        ultima = self._ultima_requisicao.get(dominio)
        if ultima is None:
            return
        restante = self._settings.request_delay_seconds - (time.monotonic() - ultima)
        if restante > 0:
            time.sleep(restante)
