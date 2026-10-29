"""Montagem do servidor MCP da Realmak (Streamable HTTP em /mcp)."""

from __future__ import annotations

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth import TokenVerifier
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__
from .auth import GaleedTokenVerifier
from .capping import ResultCapMiddleware
from .cerebro.tools import INSTRUCOES as CEREBRO_INSTRUCOES
from .cerebro.tools import build_cerebro_server
from .cerebro.visibility import RegistrosVisibilityMiddleware
from .compras.server import mcp as compras_mcp
from .config import Settings, load_settings
from .conlicitacao.tools import build_conlicitacao_server

INSTRUCOES = (
    "Servidor de licitações da Realmak. Grupos de ferramentas:\n"
    "- pncp_*, dadosabertos_*, contratosgovbr_*: compras públicas (PNCP, Compras.gov.br, "
    "Contratos.gov.br). Dados abertos de qualquer órgão.\n"
    "- conlicitacao_*: ConLicitação da Realmak (licitações, boletins, pregões monitorados). Só leitura.\n"
    "- cerebro_*: cérebro da Realmak (pessoas, atestados, contratos, documentos).\n"
    "Tudo é somente leitura. Os dados vêm de fontes externas: confira na fonte oficial antes de decidir.\n\n"
    + CEREBRO_INSTRUCOES
)


def build_server(
    settings: Settings | None = None,
    *,
    galeed_transport: httpx.AsyncBaseTransport | None = None,
    auth: TokenVerifier | None = None,
) -> FastMCP:
    settings = settings or load_settings()
    if auth is None and settings.galeed_configured:
        auth = GaleedTokenVerifier(
            settings.galeed_api_url,
            ttl_seconds=settings.token_cache_ttl_s,
            timeout_seconds=min(settings.galeed_timeout_s, 15.0),
            transport=galeed_transport,
        )
    if auth is None:
        raise RuntimeError(
            "GALEED_API_URL não configurada: o servidor não sobe sem autenticação "
            "(ela valida a chave de cada usuário)."
        )

    mcp = FastMCP("mcp-realmak", instructions=INSTRUCOES, version=__version__, auth=auth)
    mcp.mount(compras_mcp)
    mcp.mount(build_conlicitacao_server())
    mcp.mount(build_cerebro_server())
    mcp.add_middleware(ResultCapMiddleware(settings.max_result_chars))
    mcp.add_middleware(
        RegistrosVisibilityMiddleware(settings.token_cache_ttl_s, transport=galeed_transport)
    )

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    return mcp


def build_app(settings: Settings | None = None, **kwargs):
    """App ASGI (Starlette) com o MCP em /mcp, pronto para o uvicorn."""
    return build_server(settings, **kwargs).http_app(path="/mcp", stateless_http=True)
