"""Links de arquivo das licitações: baixar um documento e enviar um arquivo grande, sem o conteúdo passar pela conversa.

O link leva um token assinado com `MCP_REALMAK_OAUTH_SECRET`, que vale 15 minutos e fica preso à pessoa, à licitação e
ao documento (ou ao nome do arquivo enviado). O servidor repassa ao Odoo pela rede interna, como a pessoa; o Odoo
confere a permissão de novo. O link de envio vale uma vez.

    GET       {MCP_REALMAK_PUBLIC_URL}/mcp/arquivos/<token>
    PUT/POST  {MCP_REALMAK_PUBLIC_URL}/mcp/arquivos/envio/<token>   corpo = bytes do arquivo
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any

import httpx
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from ..config import Settings, load_settings
from .client import OdooApiError, OdooClient, interpretar

log = logging.getLogger("mcp_realmak.licitacao")

VALIDADE_S = 15 * 60
_NO_STORE = {"Cache-Control": "no-store"}
_REPASSAR = ("content-type", "content-disposition", "content-length", "x-content-type-options")


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _chave(settings: Settings) -> bytes:
    return hashlib.sha256(b"realmak-arquivos:" + settings.oauth_secret.encode("utf-8")).digest()


def assinar(settings: Settings, dados: dict[str, Any]) -> str:
    corpo = _b64e(json.dumps({**dados, "x": int(time.time()) + VALIDADE_S, "j": secrets.token_urlsafe(9)},
                             separators=(",", ":")).encode())
    return f"{corpo}.{_b64e(hmac.new(_chave(settings), corpo.encode(), hashlib.sha256).digest())}"


def ler_token(settings: Settings, token: str, tipo: str) -> dict[str, Any] | None:
    if len(settings.oauth_secret) < 32 or token.count(".") != 1:
        return None
    corpo, assinatura = token.split(".")
    esperado = _b64e(hmac.new(_chave(settings), corpo.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(esperado, assinatura):
        return None
    try:
        dados = json.loads(_b64d(corpo))
    except ValueError:
        return None
    if not isinstance(dados, dict) or dados.get("t") != tipo or not isinstance(dados.get("x"), int) or dados["x"] < time.time():
        return None
    return dados


def link(settings: Settings, caminho: str, dados: dict[str, Any]) -> dict[str, Any]:
    token = assinar(settings, dados)
    return {
        "url": f"{settings.oauth_public_url}/mcp/arquivos/{caminho}{token}",
        "expira_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + VALIDADE_S)),
    }


def _erro(status: int, mensagem: str) -> JSONResponse:
    return JSONResponse({"erro": mensagem}, status_code=status, headers=_NO_STORE)


def rotas(transport: httpx.AsyncBaseTransport | None = None) -> list[tuple[str, list[str], Any]]:
    usados: dict[str, float] = {}

    def primeiro_uso(jti: str, expira: float) -> bool:
        agora = time.time()
        for antigo in [j for j, exp in usados.items() if exp < agora]:
            usados.pop(antigo, None)
        if jti in usados:
            return False
        usados[jti] = expira
        return True

    async def baixar(request: Request) -> Response:
        settings = load_settings()
        dados = ler_token(settings, request.path_params["token"], "baixar")
        if dados is None or not settings.licitacao_configured:
            return _erro(404, "Link inválido ou expirado. Peça outro com licitacao_link_arquivo.")
        try:
            cliente, pedido = OdooClient(settings, dados["e"], transport).baixar(dados["l"], dados["d"])
        except OdooApiError as exc:
            return _erro(503, f"Licitações indisponíveis: {exc}.")
        try:
            resp = await cliente.send(pedido, stream=True)
        except httpx.HTTPError:
            await cliente.aclose()
            return _erro(502, "O Odoo não respondeu. Tente de novo.")
        if resp.status_code != 200:
            await resp.aread()
            await resp.aclose()
            await cliente.aclose()
            try:
                interpretar(resp)
            except OdooApiError as exc:
                return _erro(resp.status_code, str(exc))
            return _erro(resp.status_code, f"HTTP {resp.status_code}")
        cabecalhos = {k: v for k, v in resp.headers.items() if k.lower() in _REPASSAR}

        async def fechar() -> None:
            await resp.aclose()
            await cliente.aclose()

        return StreamingResponse(resp.aiter_raw(), headers={**cabecalhos, **_NO_STORE},
                                 background=BackgroundTask(fechar))

    async def enviar(request: Request) -> Response:
        settings = load_settings()
        dados = ler_token(settings, request.path_params["token"], "enviar")
        if dados is None or not settings.licitacao_configured:
            return _erro(404, "Link de envio inválido ou expirado. Peça outro com licitacao_enviar_arquivo.")
        tamanho = int(request.headers.get("content-length") or 0)
        if tamanho > settings.arquivo_max_bytes:
            return _erro(413, f"Arquivo acima de {settings.arquivo_max_bytes // (1024 * 1024)} MB.")
        partes, total = [], 0
        async for parte in request.stream():
            total += len(parte)
            if total > settings.arquivo_max_bytes:
                return _erro(413, f"Arquivo acima de {settings.arquivo_max_bytes // (1024 * 1024)} MB.")
            partes.append(parte)
        if not total:
            return _erro(400, "Arquivo vazio: envie os bytes no corpo (curl --upload-file).")
        if not primeiro_uso(dados["j"], dados["x"]):
            return _erro(409, "Este link de envio já foi usado. Peça outro com licitacao_enviar_arquivo.")
        try:
            resultado = await OdooClient(settings, dados["e"], transport).enviar(
                dados["l"], dados["n"], b"".join(partes), dados.get("s"))
        except OdooApiError as exc:
            return _erro(exc.status or 502, str(exc))
        log.info("Arquivo enviado pelo link para a licitação %s", dados["l"])
        return JSONResponse({"resultado": resultado}, headers=_NO_STORE)

    return [
        ("/mcp/arquivos/envio/{token}", ["PUT", "POST"], enviar),
        ("/mcp/arquivos/{token}", ["GET"], baixar),
    ]
