"""Fixtures globais: ambiente limpo e sem rede real."""

from __future__ import annotations

import pytest

VARS = [
    "GALEED_API_URL", "GALEED_TIMEOUT_MS", "CONLICITACAO_URL", "CONLICITACAO_TOKEN",
    "CONLICITACAO_LOGIN", "CONLICITACAO_SITE_PASSWORD", "CONLICITACAO_SESSION_FILE",
    "MCP_REALMAK_TOKEN_CACHE_SECONDS", "MCP_REALMAK_MAX_RESULT_CHARS",
    "MCP_REALMAK_PUBLIC_URL", "MCP_REALMAK_OAUTH_SECRET", "MCP_REALMAK_OAUTH_REDIRECT_HOSTS",
    "GALEED_SERVICE_KEY", "GALEED_LOGIN_URL", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    "GOOGLE_WORKSPACE_DOMAIN", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM",
]


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch: pytest.MonkeyPatch):
    for name in VARS:
        monkeypatch.delenv(name, raising=False)
    # Zera os clientes únicos entre testes.
    from mcp_realmak.conlicitacao import tools as clt

    clt._site = None
    clt._site_key = None
    yield
