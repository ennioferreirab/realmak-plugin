"""Quem vê o quê: cada grupo de ferramentas só aparece para quem tem aquele acesso.

- `licitacao_*`: só para pessoa (login OAuth) que o Odoo representa, isto é, com as licitações liberadas.
- `cerebro_*`: para chave de bot válida (já conferida na entrada) ou pessoa com acesso ao cérebro no Galeed.

As respostas definitivas ficam 5 minutos em cache por e-mail. Odoo ou Galeed fora do ar escondem o grupo só nesta
listagem, sem entrar no cache.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Sequence

import httpx
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware, MiddlewareContext
from mcp import types as mt

from ..auth import GaleedUnavailableError, token_hash
from ..config import load_settings
from .client import OdooApiError, OdooClient
from .tools import LICITACAO_TAG

log = logging.getLogger("mcp_realmak.licitacao")

CEREBRO_TAG = "cerebro"


class AcessoOdoo:
    """O Odoo representa este e-mail? (`POST /realmak_mcp/v1/acesso`), com cache de 5 minutos."""

    def __init__(self, ttl_seconds: int = 300, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.ttl = ttl_seconds
        self._transport = transport
        self._cache: dict[str, tuple[float, bool]] = {}

    async def __call__(self, email: str) -> bool:
        settings = load_settings()
        if not settings.licitacao_configured or not email:
            return False
        chave = token_hash(email.lower())
        hit = self._cache.get(chave)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        try:
            await OdooClient(settings, email, self._transport).chamar("acesso")
            liberado = True
        except OdooApiError as exc:
            if exc.status not in (400, 403, 404):
                log.warning("Odoo indisponível ao conferir acesso às licitações: %s", exc.status)
                return False
            liberado = False
        if len(self._cache) > 2048:
            self._cache.clear()
        self._cache[chave] = (time.monotonic() + self.ttl, liberado)
        return liberado


class PessoaVisibilityMiddleware(Middleware):
    def __init__(self, acesso_odoo: AcessoOdoo, acesso_cerebro: Callable[[str], Awaitable[bool]] | None) -> None:
        self.acesso_odoo = acesso_odoo
        self.acesso_cerebro = acesso_cerebro

    async def _cerebro(self, email: str) -> bool:
        if self.acesso_cerebro is None:
            return False
        try:
            return await self.acesso_cerebro(email)
        except GaleedUnavailableError:
            return False

    async def on_list_tools(self, context: MiddlewareContext[mt.ListToolsRequest], call_next):
        tools: Sequence = await call_next(context)
        access = get_access_token()
        email = (access.claims or {}).get("email") if access is not None else None
        esconder = set()
        if not email or not await self.acesso_odoo(email):
            esconder.add(LICITACAO_TAG)
        if email and not await self._cerebro(email):
            esconder.add(CEREBRO_TAG)
        if not esconder:
            return tools
        return [t for t in tools if not (esconder & set(t.tags or ()))]
