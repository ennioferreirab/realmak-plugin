"""Autenticação. Dois tipos de token Bearer:

- chave de bot do Galeed (gld_live_...), usada por bots e pelo Claude Code;
- token de pessoa (rmk_...), emitido pelo login OAuth (oauth.py). Ele carrega o e-mail
  verificado; o servidor confere no Galeed, com a chave de serviço e o header
  X-Galeed-Act-As, se esse e-mail ainda tem acesso ao cérebro.

A cada token novo o servidor pergunta ao Galeed (GET /facts?limit=1). 200 vale,
401 e 403 não valem. O resultado fica em cache por 5 minutos, indexado pelo
sha256 do token, e o token nunca é gravado em log nem em disco.

Se o Galeed não responder, o servidor recusa o acesso (falha fechada) com um
erro 503 que diz isso, em vez de liberar sem checar.
"""

from __future__ import annotations

import hashlib
import logging
import time

import httpx
from fastmcp.server.auth import AccessToken, TokenVerifier
from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend
from mcp.server.auth.routes import create_protected_resource_routes
from starlette.authentication import AuthenticationError
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .oauth import ACCESS_PREFIX, OAuthServer
from .sanitize import mask_sensitive

log = logging.getLogger("mcp_realmak.auth")

MAX_CACHE_ENTRIES = 2048


class GaleedUnavailableError(AuthenticationError):
    """O Galeed não respondeu: não dá para conferir a chave."""


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class GaleedTokenVerifier(TokenVerifier):
    """Valida a chave do bot chamando o Galeed, com cache de 5 minutos."""

    def __init__(
        self,
        api_url: str,
        *,
        ttl_seconds: int = 300,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        public_url: str = "",
        service_key: str = "",
    ) -> None:
        # Sem OAuth (padrão): sem base_url, o FastMCP não publica metadados (RFC 9728),
        # o 401 não traz resource_metadata e o cliente usa só o cabeçalho Authorization.
        # Com OAuth (public_url + attach_oauth), os metadados e as rotas de login passam a existir.
        super().__init__(base_url=public_url or None)
        self.oauth: OAuthServer | None = None
        self.service_key = service_key
        self.api_url = api_url.rstrip("/")
        self.ttl = ttl_seconds
        self.timeout = timeout_seconds
        self._transport = transport
        self._cache: dict[str, tuple[float, bool]] = {}

    # --- cache -------------------------------------------------------------

    def _cache_get(self, key: str) -> bool | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        expires, valid = entry
        if expires < time.monotonic():
            self._cache.pop(key, None)
            return None
        return valid

    def _cache_put(self, key: str, valid: bool) -> None:
        if len(self._cache) >= MAX_CACHE_ENTRIES:
            now = time.monotonic()
            for k in [k for k, (exp, _) in self._cache.items() if exp < now]:
                self._cache.pop(k, None)
            while len(self._cache) >= MAX_CACHE_ENTRIES:
                self._cache.pop(next(iter(self._cache)))
        self._cache[key] = (time.monotonic() + self.ttl, valid)

    # --- verificação -------------------------------------------------------

    def attach_oauth(self, oauth: OAuthServer) -> None:
        self.oauth = oauth

    async def check_person(self, email: str) -> bool:
        """O e-mail tem acesso ao cérebro? Pergunta ao Galeed agindo em nome dele (cache de 5 min)."""
        if not self.service_key:
            return False
        key = "pessoa:" + token_hash(email)
        cached = self._cache_get(key)
        if cached is None:
            cached = await self._check_with_galeed(self.service_key, act_as=email)
            self._cache_put(key, cached)
        return cached

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or not self.api_url:
            return None
        if self.oauth is not None and token.startswith(ACCESS_PREFIX):
            lido = self.oauth.read_access_token(token)
            if lido is None:
                return None
            email, expira = lido
            if not await self.check_person(email):
                return None
            return AccessToken(
                token=token, client_id=f"pessoa:{token_hash(email)[:12]}", scopes=[],
                expires_at=expira, claims={"email": email},
            )
        key = token_hash(token)
        cached = self._cache_get(key)
        if cached is None:
            cached = await self._check_with_galeed(token)
            self._cache_put(key, cached)
        if not cached:
            return None
        return AccessToken(token=token, client_id=f"galeed:{key[:12]}", scopes=[])

    async def _check_with_galeed(self, token: str, act_as: str = "") -> bool:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self._transport, follow_redirects=False
            ) as client:
                resp = await client.get(
                    f"{self.api_url}/facts",
                    params={"limit": 1},
                    headers={
                        "Authorization": f"Bearer {token}",
                        **({"X-Galeed-Act-As": act_as} if act_as else {}),
                    },
                )
        except httpx.HTTPError as exc:
            log.warning("Galeed inacessível ao validar chave: %s", type(exc).__name__)
            raise GaleedUnavailableError(
                "Não foi possível conferir a chave porque o cérebro não respondeu. "
                "Tente de novo em instantes."
            ) from None
        if resp.status_code == 200:
            return True
        if act_as and resp.status_code == 401:
            log.error("Galeed recusou a chave de serviço (GALEED_SERVICE_KEY)")
            raise GaleedUnavailableError(
                "O servidor não conseguiu consultar o cérebro (chave de serviço recusada). Avise quem administra."
            )
        if resp.status_code in (401, 403):
            return False
        log.warning("Galeed respondeu HTTP %s ao validar chave", resp.status_code)
        raise GaleedUnavailableError(
            f"O cérebro respondeu HTTP {resp.status_code} ao conferir a chave. "
            "Tente de novo em instantes."
        )

    # --- OAuth (opcional) --------------------------------------------------

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        if self.oauth is None:
            return []
        self.set_mcp_path(mcp_path)
        resource_url = self._get_resource_url(mcp_path)
        resource_routes = create_protected_resource_routes(
            resource_url=resource_url,
            authorization_servers=[self.base_url],
            resource_name="Servidor MCP da Realmak",
        )
        return self.oauth.routes(resource_routes)

    # --- erros HTTP --------------------------------------------------------

    def get_middleware(self) -> list:
        return [
            Middleware(
                AuthenticationMiddleware,
                backend=BearerAuthBackend(self),
                on_error=_on_auth_error,
            ),
            Middleware(AuthContextMiddleware),
        ]


def _on_auth_error(conn: HTTPConnection, exc: Exception) -> Response:
    if isinstance(exc, GaleedUnavailableError):
        return JSONResponse(
            {"error": "cerebro_indisponivel", "message": str(exc)},
            status_code=503,
            headers={"Retry-After": "10"},
        )
    log.warning("Falha de autenticação: %s", mask_sensitive(exc))
    return JSONResponse({"error": "invalid_token", "message": "Chave inválida."}, status_code=401)


