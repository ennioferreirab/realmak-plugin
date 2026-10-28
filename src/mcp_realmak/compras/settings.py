"""Configuração do cliente HTTP das fontes de compras.

Adaptado do mcp-brasil (MIT). Valores podem ser sobrescritos por variáveis de
ambiente. Não carrega arquivos `.env`: o ambiente vem do processo (Docker).
"""

from __future__ import annotations

import os

HTTP_TIMEOUT: float = float(os.environ.get("MCP_REALMAK_HTTP_TIMEOUT", "30.0"))
HTTP_MAX_RETRIES: int = int(os.environ.get("MCP_REALMAK_HTTP_MAX_RETRIES", "3"))
HTTP_BACKOFF_BASE: float = float(os.environ.get("MCP_REALMAK_HTTP_BACKOFF_BASE", "1.0"))
USER_AGENT: str = os.environ.get("MCP_REALMAK_USER_AGENT", "mcp-realmak/0.1.0")
