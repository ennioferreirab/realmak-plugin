"""Mostra registros quando ao menos uma empresa liberada anuncia o dataset em /acesso.

A descoberta compartilhada guarda apenas respostas definitivas por identidade.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx
from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware, MiddlewareContext
from mcp import types as mt

from ..config import load_settings
from .empresas import get_empresas
from .tools import REGISTROS_TAG


class RegistrosVisibilityMiddleware(Middleware):
    def __init__(self, ttl_seconds: int = 300, transport: httpx.AsyncBaseTransport | None = None):
        self.ttl = ttl_seconds
        self._transport = transport

    async def _visivel(self, access: AccessToken) -> bool:
        settings = load_settings()
        if not settings.galeed_configured:
            return False
        empresas = await get_empresas(settings, self._transport).empresas_liberadas(access)
        return any(e.registros for e in empresas)

    async def on_list_tools(self, context: MiddlewareContext[mt.ListToolsRequest], call_next):
        tools: Sequence = await call_next(context)
        access = get_access_token()
        mostrar = bool(access and access.token and await self._visivel(access))
        if mostrar:
            return tools
        return [t for t in tools if REGISTROS_TAG not in (t.tags or set())]
