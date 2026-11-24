"""Rota HTTP enxuta `POST /mcp/corpos`: repasse em lote para `POST /v1/corpos` do Brain.

Usada pelo daemon de análises do CRM para ler textos já extraídos (`galeed_registros_corpos`)
sem duplicar `GALEED_SERVICE_KEYS` fora do servidor MCP e sem teto de 40 KB das tools MCP.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from fastmcp.server.dependencies import get_access_token
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..config import EMPRESAS, NOMES_EMPRESAS, Settings
from .client import GaleedApiError
from .empresas import Empresa, get_empresas
from .tools import client_for_access

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_SHAS = 100
_NO_STORE = {"Cache-Control": "private, no-store"}


def _erro(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status, headers=_NO_STORE)


def rota_corpos(settings: Settings, galeed_transport: httpx.AsyncBaseTransport | None = None):
    """Cria o handler Starlette para `POST /mcp/corpos`."""

    async def handler(request: Request) -> JSONResponse:
        access = get_access_token()
        if access is None or not access.token:
            return _erro(401, "invalid_token", "Chave ausente ou inválida.")

        try:
            payload: Any = await request.json()
        except (ValueError, TypeError):
            return _erro(400, "invalid_body", "Corpo JSON inválido.")

        if not isinstance(payload, dict):
            return _erro(400, "invalid_body", "Corpo deve ser um objeto JSON.")

        empresa_bruta = payload.get("empresa")
        if not isinstance(empresa_bruta, str):
            return _erro(400, "invalid_empresa", "Informe empresa válida.")
        empresa_norm = empresa_bruta.strip().lower()
        if empresa_norm not in EMPRESAS:
            return _erro(400, "invalid_empresa", "Empresa inválida.")
        empresa: Empresa = empresa_norm  # type: ignore[assignment]

        shas_brutos = payload.get("shas")
        if not isinstance(shas_brutos, list) or not (1 <= len(shas_brutos) <= _MAX_SHAS):
            return _erro(400, "invalid_shas", f"Informe de 1 a {_MAX_SHAS} shas válidos.")
        shas: list[str] = []
        vistos: set[str] = set()
        for item in shas_brutos:
            if not isinstance(item, str):
                return _erro(400, "invalid_shas", "Cada item de shas deve ser um SHA-256 em hex.")
            sha = item.strip().lower()
            if not _SHA_RE.match(sha):
                return _erro(400, "invalid_shas", "SHA-256 inválido em shas.")
            if sha not in vistos:
                vistos.add(sha)
                shas.append(sha)

        if not settings.galeed_configured or empresa not in settings.service_keys:
            return _erro(400, "empresa_indisponivel", f"Empresa {NOMES_EMPRESAS[empresa]} não configurada neste servidor.")

        descoberta = await get_empresas(settings, galeed_transport).descobrir(access)
        liberada = next((e for e in descoberta.empresas if e.empresa == empresa), None)
        if not liberada:
            if empresa in descoberta.indisponiveis:
                return _erro(503, "cerebro_indisponivel", f"Cérebro da empresa {NOMES_EMPRESAS[empresa]} indisponível.")
            return _erro(403, "forbidden", f"Sem acesso à empresa {NOMES_EMPRESAS[empresa]}.")

        client = client_for_access(access, settings, transport=galeed_transport, empresa=empresa)
        try:
            dados = await client.corpos(shas, brain=empresa)
        except GaleedApiError as exc:
            if exc.status == 0:
                status = 504 if "tempo esgotado" in str(exc).lower() else 502
                return _erro(status, "gateway_error", "Falha ao consultar textos no cérebro.")
            if exc.status in (400, 401, 403, 429):
                return _erro(exc.status, "gateway_rejected", "Cérebro recusou a consulta de corpos.")
            return _erro(502, "gateway_error", f"Cérebro respondeu HTTP {exc.status}.")

        if not isinstance(dados, dict):
            return _erro(502, "gateway_error", "Resposta inválida do cérebro.")
        return JSONResponse(dados, status_code=200, headers=_NO_STORE)

    return handler
