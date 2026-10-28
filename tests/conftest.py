"""Fixtures globais: ambiente limpo e sem rede real."""

from __future__ import annotations

import pytest

VARS = [
    "GALEED_API_URL", "GALEED_TIMEOUT_MS", "CONLICITACAO_URL", "CONLICITACAO_TOKEN",
    "CONLICITACAO_LOGIN", "CONLICITACAO_SITE_PASSWORD", "CONLICITACAO_SESSION_FILE",
    "MCP_REALMAK_TOKEN_CACHE_SECONDS", "MCP_REALMAK_MAX_RESULT_CHARS",
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
