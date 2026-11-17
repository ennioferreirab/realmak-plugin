"""Links de arquivo: ver e baixar um documento (da licitação ou original do cérebro) e enviar um arquivo grande, sem o
conteúdo passar pela conversa.

O link leva um token assinado com `MCP_REALMAK_OAUTH_SECRET`, preso à pessoa e ao arquivo; não pede login. O servidor
repassa ao Odoo (ou ao gateway do cérebro) pela rede interna, como a pessoa, e quem guarda o arquivo confere a permissão
de novo.

- Download: cada arquivo tem dois links, que valem 30 minutos e podem ser usados várias vezes. O de visualizar responde
  `Content-Disposition: inline` (o navegador mostra o que sabe exibir e baixa o resto); o de baixar, `attachment`.
- Envio: vale 15 minutos e uma vez.

    GET       {MCP_REALMAK_PUBLIC_URL}/mcp/arquivos/<token>            documento da licitação
    GET       {MCP_REALMAK_PUBLIC_URL}/mcp/arquivos/cerebro/<token>    original do cérebro
    PUT/POST  {MCP_REALMAK_PUBLIC_URL}/mcp/arquivos/envio/<token>   corpo = bytes do arquivo
    POST      {MCP_REALMAK_PUBLIC_URL}/mcp/arquivos/base-custos/<token>   multipart: base (JSON) ou planilha (xlsx)

O link da base de custos fica preso só à pessoa; o Odoo confere se ela tem a base liberada.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import unicodedata
from collections.abc import Callable
from email.message import Message
from email.utils import collapse_rfc2231_value
from typing import Any
from urllib.parse import quote

import httpx
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from ..cerebro.client import GaleedClient
from ..config import NOMES_EMPRESAS, Settings, load_settings
from .client import OdooApiError, OdooClient, interpretar

log = logging.getLogger("mcp_realmak.licitacao")

VALIDADE_ENVIO_S = 15 * 60
VALIDADE_DOWNLOAD_S = 30 * 60
BASE_CUSTOS_MAX_BYTES = 20 * 1024 * 1024
_NO_STORE = {"Cache-Control": "no-store"}
_REPASSAR = ("content-type", "content-length")
MODOS = {"v": "inline", "b": "attachment"}


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _chave(settings: Settings) -> bytes:
    return hashlib.sha256(b"realmak-arquivos:" + settings.oauth_secret.encode("utf-8")).digest()


def assinar(settings: Settings, dados: dict[str, Any]) -> str:
    """Assina `dados` como vierem; quem chama põe a validade (`x`) e, no link de uso único, o `j`."""
    corpo = _b64e(json.dumps(dados, separators=(",", ":")).encode())
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


def _expira_em(x: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(x))


def link(settings: Settings, caminho: str, dados: dict[str, Any]) -> dict[str, Any]:
    """Link de envio: 15 minutos, uma vez."""
    x = int(time.time()) + VALIDADE_ENVIO_S
    token = assinar(settings, {**dados, "x": x, "j": secrets.token_urlsafe(9)})
    return {"url": f"{settings.oauth_public_url}/mcp/arquivos/{caminho}{token}", "expira_em": _expira_em(x)}


def links_disponiveis(settings: Settings) -> bool:
    return bool(settings.oauth_public_url) and len(settings.oauth_secret) >= 32


def links_download(settings: Settings, caminho: str, dados: dict[str, Any]) -> dict[str, Any]:
    """Links de visualizar e de baixar o mesmo arquivo: 30 minutos, vários usos."""
    x = int(time.time()) + VALIDADE_DOWNLOAD_S
    base = f"{settings.oauth_public_url}/mcp/arquivos/{caminho}"
    return {
        "link_visualizar": base + assinar(settings, {**dados, "modo": "v", "x": x}),
        "link_baixar": base + assinar(settings, {**dados, "modo": "b", "x": x}),
        "expira_em": _expira_em(x),
    }


def nome_do_arquivo(content_disposition: str) -> str:
    """Nome do arquivo no `Content-Disposition` de origem (`filename*` tem prioridade), sem pasta."""
    if not content_disposition:
        return ""
    msg = Message()
    msg["content-disposition"] = content_disposition
    try:
        valores = [v for k, v in msg.get_params(header="content-disposition") or [] if k.lower() == "filename"]
        estendido = next((v for v in valores if isinstance(v, tuple)), None)
        nome = collapse_rfc2231_value(estendido) if estendido else next((v for v in valores if isinstance(v, str)), "")
    except (ValueError, LookupError):
        return ""
    return nome.replace("\\", "/").rsplit("/", 1)[-1].strip()


def disposicao(modo: str, nome: str) -> str:
    """`inline` ou `attachment`, com `filename` ASCII e, se o nome tiver acento, `filename*` em UTF-8."""
    tipo = MODOS[modo]
    nome = "".join(c for c in nome if c.isprintable())
    if not nome:
        return tipo
    ascii_ = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    ascii_ = "".join(c for c in ascii_ if c not in '"\\;').strip() or "arquivo"
    valor = f'{tipo}; filename="{ascii_}"'
    if ascii_ != nome:
        valor += f"; filename*=UTF-8''{quote(nome, safe='')}"
    return valor


def _erro(status: int, mensagem: str) -> JSONResponse:
    return JSONResponse({"erro": mensagem}, status_code=status, headers=_NO_STORE)


async def _transmitir(
    cliente: httpx.AsyncClient, pedido: httpx.Request, modo: str,
    erro: Callable[[httpx.Response], JSONResponse], sem_resposta: str,
) -> Response:
    """Repassa o arquivo em fluxo, com o `Content-Disposition` do modo do link; erro da origem vira `erro(resp)`."""
    pedido.headers["Accept-Encoding"] = "identity"  # os bytes passam crus: sem compressão no caminho
    try:
        resp = await cliente.send(pedido, stream=True)
    except httpx.HTTPError:
        await cliente.aclose()
        return _erro(502, sem_resposta)
    if resp.status_code != 200:
        await resp.aread()
        await resp.aclose()
        await cliente.aclose()
        return erro(resp) if resp.status_code >= 400 else _erro(502, f"Resposta inesperada da origem (HTTP {resp.status_code}).")
    cabecalhos = {k: v for k, v in resp.headers.items() if k.lower() in _REPASSAR}
    cabecalhos["Content-Disposition"] = disposicao(modo, nome_do_arquivo(resp.headers.get("content-disposition", "")))
    cabecalhos["X-Content-Type-Options"] = "nosniff"

    async def fechar() -> None:
        await resp.aclose()
        await cliente.aclose()

    return StreamingResponse(resp.aiter_raw(), headers={**cabecalhos, **_NO_STORE}, background=BackgroundTask(fechar))


def _erro_odoo(resp: httpx.Response) -> JSONResponse:
    try:
        interpretar(resp)
    except OdooApiError as exc:
        return _erro(resp.status_code, str(exc))
    return _erro(resp.status_code, f"HTTP {resp.status_code}")


def _erro_cerebro(chave: str) -> Callable[[httpx.Response], JSONResponse]:
    def erro(resp: httpx.Response) -> JSONResponse:
        mensagem = ""
        try:
            corpo = resp.json()
            if isinstance(corpo, dict) and isinstance(corpo.get("error"), str):
                mensagem = corpo["error"]
        except ValueError:
            pass
        mensagem = (mensagem or f"HTTP {resp.status_code}")[:500]
        if chave:
            mensagem = mensagem.replace(chave, "***")
        return _erro(resp.status_code, f"Cérebro: {mensagem}")
    return erro


def rotas(
    transport: httpx.AsyncBaseTransport | None = None,
    galeed_transport: httpx.AsyncBaseTransport | None = None,
) -> list[tuple[str, list[str], Any]]:
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
        if dados is None or dados.get("modo") not in MODOS or not settings.licitacao_configured:
            return _erro(404, "Link inválido ou expirado (vale 30 minutos). Peça outro com licitacao_link_arquivo.")
        try:
            cliente, pedido = OdooClient(settings, dados["e"], transport).baixar(dados["l"], dados["d"])
        except OdooApiError as exc:
            return _erro(503, f"Licitações indisponíveis: {exc}.")
        return await _transmitir(cliente, pedido, dados["modo"], _erro_odoo, "O Odoo não respondeu. Tente de novo.")

    async def baixar_cerebro(request: Request) -> Response:
        settings = load_settings()
        dados = ler_token(settings, request.path_params["token"], "cerebro")
        if dados is None or dados.get("modo") not in MODOS or not settings.galeed_configured:
            return _erro(404, "Link inválido ou expirado (vale 30 minutos). Busque o arquivo de novo no cérebro.")
        chave = settings.service_keys.get(dados["m"], "")
        if not chave:
            return _erro(503, f"O cérebro da empresa {NOMES_EMPRESAS.get(dados['m'], dados['m'])} não está configurado neste servidor.")
        cliente, pedido = GaleedClient(settings.galeed_api_url, chave, timeout=settings.galeed_timeout_s,
                                       transport=galeed_transport, act_as=dados["e"]).original(dados["s"])
        return await _transmitir(cliente, pedido, dados["modo"], _erro_cerebro(chave),
                                 "O cérebro não respondeu. Tente de novo.")

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

    async def enviar_base_custos(request: Request) -> Response:
        settings = load_settings()
        dados = ler_token(settings, request.path_params["token"], "base_custos")
        if dados is None or not settings.licitacao_configured:
            return _erro(404, "Link de envio inválido ou expirado. Peça outro com precificacao_enviar_base_custos.")
        tipo = request.headers.get("content-type", "")
        if not tipo.startswith("multipart/form-data"):
            return _erro(400, "Envie como formulário: curl -F base=@base-custos.json ou -F planilha=@<planilha>.xlsx.")
        limite = f"Envio acima de {BASE_CUSTOS_MAX_BYTES // (1024 * 1024)} MB."
        if int(request.headers.get("content-length") or 0) > BASE_CUSTOS_MAX_BYTES:
            return _erro(413, limite)
        partes, total = [], 0
        async for parte in request.stream():
            total += len(parte)
            if total > BASE_CUSTOS_MAX_BYTES:
                return _erro(413, limite)
            partes.append(parte)
        if not total:
            return _erro(400, "Envio vazio.")
        if not primeiro_uso(dados["j"], dados["x"]):
            return _erro(409, "Este link de envio já foi usado. Peça outro com precificacao_enviar_base_custos.")
        try:
            resultado = await OdooClient(settings, dados["e"], transport).enviar_base_custos(b"".join(partes), tipo)
        except OdooApiError as exc:
            return _erro(exc.status or 502, str(exc))
        log.info("Base de custos enviada pelo link: competência %s", resultado.get("competencia"))
        return JSONResponse({"resultado": resultado}, headers=_NO_STORE)

    return [
        ("/mcp/arquivos/cerebro/{token}", ["GET"], baixar_cerebro),
        ("/mcp/arquivos/envio/{token}", ["PUT", "POST"], enviar),
        ("/mcp/arquivos/base-custos/{token}", ["POST"], enviar_base_custos),
        ("/mcp/arquivos/{token}", ["GET"], baixar),
    ]
