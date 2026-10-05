"""Configuração lida de variáveis de ambiente (ou do arquivo .env).

Equivale ao application.properties + @ConfigurationProperties do Spring:
cada campo abaixo vira a variável SAUF_<NOME_DO_CAMPO>, ex.: SAUF_API_BASE_URL.
"""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAUF_", env_file=".env", extra="ignore")

    # API do backend Java que recebe os lotes
    api_base_url: str = "http://localhost:8080"
    api_key: SecretStr | None = None
    api_timeout_seconds: float = 30.0

    # Comportamento "educado" com os sites das universidades
    user_agent: str = "SAUF-BR-Bot/0.1 (+https://saufbr.com.br)"
    request_delay_seconds: float = 2.0
    request_timeout_seconds: float = 20.0

    # Onde o modo --dry-run grava os lotes em JSON
    output_dir: Path = Path("output")
