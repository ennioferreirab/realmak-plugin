"""Mostra as ferramentas de registros só para chaves que o gateway deixa usar.

Na listagem de ferramentas, o servidor pergunta ao gateway (GET /consulta/esquema)
com a chave do usuário. 200 ou 503 (módulo ligado, dataset ainda sem derivação)
mostram as ferramentas; 403 e 404 as escondem. Qualquer outra falha esconde só
nesta listagem e não entra no cache. Respostas definitivas ficam 5 minutos em
cache, indexadas pelo sha256 da chave.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence

import httpx
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware, MiddlewareContext
from mcp import types as mt

from ..auth import token_hash
from ..config import load_settings
from .client import GaleedApiError, GaleedClient
from .tools import REGISTROS_TAG

log = logging.getLogger("mcp_realmak.cerebro")


class RegistrosVisibilityMiddleware(Middleware):
    def __init__(self, ttl_seconds: int = 300, transport: httpx.AsyncBaseTransport | None = None):
        self.ttl = ttl_seconds
        self._transport = transport
        self._cache: dict[str, tuple[float, bool]] = {}

    async def _visivel(self, token: str) -> bool:
        key = token_hash(token)
        hit = self._cache.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        settings = load_settings()
        if not settings.galeed_configured:
            return False
        client = GaleedClient(
            settings.galeed_api_url, token, timeout=settings.galeed_timeout_s, transport=self._transport
        )
        try:
            await client.esquema()
            visivel, definitivo = True, True
        except GaleedApiError as exc:
            if exc.status in (403, 404):
                visivel, definitivo = False, True
            elif exc.status == 503:
                visivel, definitivo = True, False
            else:
                visivel, definitivo = False, False
        if definitivo:
            if len(self._cache) > 2048:
                self._cache.clear()
            self._cache[key] = (time.monotonic() + self.ttl, visivel)
        return visivel

    async def on_list_tools(self, context: MiddlewareContext[mt.ListToolsRequest], call_next):
        tools: Sequence = await call_next(context)
        access = get_access_token()
        mostrar = bool(access and access.token and await self._visivel(access.token))
        if mostrar:
            return tools
        return [t for t in tools if REGISTROS_TAG not in (t.tags or set())]
