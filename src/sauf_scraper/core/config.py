"""Configuração lida de variáveis de ambiente (ou do arquivo .env).

Equivale ao application.properties + @ConfigurationProperties do Spring:
cada campo abaixo vira a variável SAUF_<NOME_DO_CAMPO>, ex.: SAUF_API_BASE_URL.
"""

import logging
import re
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROJETO = Path(__file__).resolve().parents[3]
FONTES = RAIZ_PROJETO / "fontes"
PADRAO_PASTA_CENSO = "microdados_censo*"

logger = logging.getLogger("sauf_scraper")


def resolver_pasta_censo(pasta: Path | None, fontes: Path = FONTES) -> Path:
    """Pasta dos microdados do Censo.

    Com --pasta ou SAUF_CENSO_DIR, usa exatamente esse caminho. Sem eles, procura
    fontes/microdados_censo* e fica com a de maior ano no nome (2025 ganha de 2024).
    """
    if pasta is not None:
        return Path(pasta)
    candidatas = [p for p in fontes.glob(PADRAO_PASTA_CENSO) if p.is_dir()]
    if not candidatas:
        raise FileNotFoundError(
            f"Nenhuma pasta {PADRAO_PASTA_CENSO} em {fontes.resolve()}. "
            "Extraia os microdados do Censo em fontes/ ou indique outra pasta com "
            "--pasta <caminho> ou SAUF_CENSO_DIR no .env."
        )
    escolhida = max(candidatas, key=lambda p: (ano_no_nome(p.name), p.name))
    logger.info("pasta do censo", extra={"dados": {"pasta": str(escolhida)}})
    return escolhida


def ano_no_nome(nome: str) -> int:
    """Último número de 4 dígitos do nome (0 se não houver)."""
    anos = re.findall(r"\d{4}", nome)
    return int(anos[-1]) if anos else 0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAUF_", env_file=".env", extra="ignore")

    api_base_url: str = "http://localhost:8080"
    api_key: SecretStr | None = None
    api_timeout_seconds: float = 30.0

    user_agent: str = "SAUF-BR-Bot/0.1"
    request_delay_seconds: float = 2.0
    request_timeout_seconds: float = 20.0

    output_dir: Path = Path("output")

    # Vazio = procura fontes/microdados_censo* (ver resolver_pasta_censo).
    censo_dir: Path | None = None
