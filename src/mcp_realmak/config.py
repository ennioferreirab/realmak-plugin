"""Configuração lida só de variáveis de ambiente. Nada é gravado no repositório."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_CONLICITACAO_URL = "https://consultaonline.conlicitacao.com.br"
DEFAULT_SESSION_FILE = "/data/conlicitacao-sessao.json"
MAX_RESULT_CHARS = 100_000


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int_env(name: str, default: int) -> int:
    raw = _env(name)
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class Settings:
    galeed_api_url: str
    galeed_timeout_s: float
    token_cache_ttl_s: int
    conlicitacao_url: str
    conlicitacao_token: str
    conlicitacao_login: str
    conlicitacao_site_password: str
    conlicitacao_session_file: str
    max_result_chars: int

    @property
    def galeed_configured(self) -> bool:
        return bool(self.galeed_api_url)


def load_settings() -> Settings:
    """Lê o ambiente a cada chamada, o que facilita os testes."""
    return Settings(
        galeed_api_url=_env("GALEED_API_URL").rstrip("/"),
        galeed_timeout_s=_int_env("GALEED_TIMEOUT_MS", 30_000) / 1000,
        token_cache_ttl_s=_int_env("MCP_REALMAK_TOKEN_CACHE_SECONDS", 300),
        conlicitacao_url=(_env("CONLICITACAO_URL") or DEFAULT_CONLICITACAO_URL).rstrip("/"),
        conlicitacao_token=_env("CONLICITACAO_TOKEN"),
        conlicitacao_login=_env("CONLICITACAO_LOGIN"),
        conlicitacao_site_password=_env("CONLICITACAO_SITE_PASSWORD"),
        conlicitacao_session_file=_env("CONLICITACAO_SESSION_FILE") or DEFAULT_SESSION_FILE,
        max_result_chars=_int_env("MCP_REALMAK_MAX_RESULT_CHARS", MAX_RESULT_CHARS),
    )
