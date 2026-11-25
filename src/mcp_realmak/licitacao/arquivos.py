"""Links de arquivo: ver e baixar um documento (da licitação ou original do cérebro) e enviar um arquivo grande, sem o
conteúdo passar pela conversa.

Leitura (cérebro e licitação): cada documento recebe um link curto único (`/a/<codigo>`, válido por 30 minutos e
por vários usos), cujo token assinado fica guardado em SQLite no servidor sem expor e-mail na URL. Abrir no navegador
exibe a visualização (incluindo prévia PDF para Word e Excel quando configurada) com o botão para baixar o original;
`?b=1` entrega o original em `attachment` direto. Os acessos são registrados e links vencidos são limpos.

Compatibilidade: os links assinados legados (`/mcp/arquivos/cerebro/<token>` e `/mcp/arquivos/<token>`) continuam
aceitos normalmente. Envio (15 minutos, uma vez) e base de custos seguem nos caminhos atuais:

    GET       {MCP_REALMAK_PUBLIC_URL}/a/<codigo>                   visualização (?v=1) ou download (?b=1)
    GET       {MCP_REALMAK_PUBLIC_URL}/mcp/arquivos/<token>         documento da licitação (legado)
    GET       {MCP_REALMAK_PUBLIC_URL}/mcp/arquivos/cerebro/<token> original do cérebro (legado)
    PUT/POST  {MCP_REALMAK_PUBLIC_URL}/mcp/arquivos/cerebro-envio/<token>  envio de arquivo ao cérebro
    PUT/POST  {MCP_REALMAK_PUBLIC_URL}/mcp/arquivos/envio/<token>   corpo = bytes do arquivo
    POST      {MCP_REALMAK_PUBLIC_URL}/mcp/arquivos/base-custos/<token>   multipart: base (JSON) ou planilha (xlsx)

O link da base de custos fica preso só à pessoa; o Odoo confere se ela tem a base liberada.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import logging
import secrets
import time
import unicodedata
from collections.abc import Callable
from email.message import Message
from email.utils import collapse_rfc2231_value
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

import httpx
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response, StreamingResponse

from ..cerebro.client import GaleedApiError, GaleedClient
from ..config import NOMES_EMPRESAS, Settings, load_settings
from . import links_curtos, previa
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
    """Links legados de visualizar e de baixar o mesmo arquivo: 30 minutos, vários usos."""
    x = int(time.time()) + VALIDADE_DOWNLOAD_S
    base = f"{settings.oauth_public_url}/mcp/arquivos/{caminho}"
    return {
        "link_visualizar": base + assinar(settings, {**dados, "modo": "v", "x": x}),
        "link_baixar": base + assinar(settings, {**dados, "modo": "b", "x": x}),
        "expira_em": _expira_em(x),
    }


def link_curto(settings: Settings, dados: dict[str, Any], *, nome: str = "") -> dict[str, Any]:
    """Link curto único (/a/<codigo>): 30 minutos, vários usos, abre visualização e oferece Baixar."""
    x = int(time.time()) + VALIDADE_DOWNLOAD_S
    token = assinar(settings, {**dados, "x": x})
    codigo = links_curtos.criar(
        settings,
        tipo=dados["t"],
        token=token,
        email=dados.get("e", ""),
        expira_em=x,
        nome=nome,
    )
    return {
        "link": f"{settings.oauth_public_url}/a/{codigo}",
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


def _ip_cliente(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


def _pagina_visualizacao(codigo: str, nome: str) -> HTMLResponse:
    titulo = html.escape(nome or "Documento")
    baixar_url = html.escape(f"/a/{codigo}?b=1")
    ver_url = html.escape(f"/a/{codigo}?v=1")
    corpo = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titulo}</title>
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; font-family: system-ui, -apple-system, sans-serif; background: #111827; color: #f9fafb; display: flex; flex-direction: column; }}
  header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 16px; background: #1f2937; border-bottom: 1px solid #374151; }}
  .nome {{ font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .acoes {{ display: flex; align-items: center; gap: 12px; flex-shrink: 0; }}
  .validade {{ font-size: 12px; color: #9ca3af; }}
  .btn {{ display: inline-block; padding: 7px 14px; border-radius: 6px; background: #2563eb; color: #fff; text-decoration: none; font-size: 13px; font-weight: 600; }}
  .btn:hover {{ background: #1d4ed8; }}
  iframe {{ flex: 1; width: 100%; border: 0; background: #fff; }}
</style>
</head>
<body>
<header>
  <span class="nome" title="{titulo}">{titulo}</span>
  <div class="acoes">
    <span class="validade">Link válido por 30 min</span>
    <a class="btn" href="{baixar_url}" download>Baixar arquivo</a>
  </div>
</header>
<iframe src="{ver_url}" title="{titulo}"></iframe>
</body>
</html>"""
    return HTMLResponse(
        corpo,
        headers={
            **_NO_STORE,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; frame-src 'self'; "
                "base-uri 'none'; form-action 'none'"
            ),
        },
    )


def _erro_iframe(codigo: str, resp: JSONResponse) -> HTMLResponse:
    try:
        mensagem = json.loads(resp.body).get("erro") or f"HTTP {resp.status_code}"
    except ValueError:
        mensagem = f"HTTP {resp.status_code}"
    msg_html = html.escape(str(mensagem))
    baixar_url = html.escape(f"/a/{codigo}?b=1")
    botao = (
        f'<p><a href="{baixar_url}" download style="display:inline-block;padding:8px 16px;'
        'border-radius:6px;background:#2563eb;color:#fff;text-decoration:none;font-weight:600">'
        "Baixar arquivo</a></p>"
        if resp.status_code in (413, 422, 502, 503, 504)
        else ""
    )
    corpo = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Prévia indisponível</title></head>
<body style="font-family:system-ui,-apple-system,sans-serif;padding:32px;color:#111827;background:#f9fafb">
<p>{msg_html}</p>{botao}
</body></html>"""
    return HTMLResponse(
        corpo,
        status_code=resp.status_code,
        headers={**_NO_STORE, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "SAMEORIGIN"},
    )


async def _transmitir(
    cliente: httpx.AsyncClient, pedido: httpx.Request, modo: str,
    erro: Callable[[httpx.Response], JSONResponse], sem_resposta: str, visualizador_url: str,
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
    async def fechar() -> None:
        await resp.aclose()
        await cliente.aclose()

    nome = nome_do_arquivo(resp.headers.get("content-disposition", ""))
    arquivo = PurePosixPath(nome)
    ext = arquivo.suffix.lower()
    cabecalhos = {**_NO_STORE, "X-Content-Type-Options": "nosniff"}
    if modo == "v" and visualizador_url and ext in previa.EXTENSOES:
        try:
            pdf = await previa.converter(visualizador_url, ext, resp)
        except previa.ErroPrevia as exc:
            return _erro(exc.status, str(exc))
        finally:
            await fechar()
        cabecalhos["Content-Disposition"] = disposicao("v", f"{arquivo.stem}.pdf")
        return Response(pdf, media_type="application/pdf", headers=cabecalhos)

    cabecalhos.update({k: v for k, v in resp.headers.items() if k.lower() in _REPASSAR})
    cabecalhos["Content-Disposition"] = disposicao(modo, nome)
    return StreamingResponse(resp.aiter_raw(), headers=cabecalhos, background=BackgroundTask(fechar))


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

    async def _servir_lic(settings: Settings, dados: dict[str, Any], modo: str) -> Response:
        if not settings.licitacao_configured:
            return _erro(404, "Link inválido ou expirado (vale 30 minutos). Peça outro com licitacao_link_arquivo.")
        try:
            cliente, pedido = OdooClient(settings, dados["e"], transport).baixar(dados["l"], dados["d"])
        except OdooApiError as exc:
            return _erro(503, f"Licitações indisponíveis: {exc}.")
        return await _transmitir(cliente, pedido, modo, _erro_odoo, "O Odoo não respondeu. Tente de novo.", settings.visualizador_url)

    async def _servir_cerebro(settings: Settings, dados: dict[str, Any], modo: str) -> Response:
        if not settings.galeed_configured:
            return _erro(404, "Link inválido ou expirado (vale 30 minutos). Busque o arquivo de novo no cérebro.")
        chave = settings.service_keys.get(dados["m"], "")
        if not chave:
            return _erro(503, f"O cérebro da empresa {NOMES_EMPRESAS.get(dados['m'], dados['m'])} não está configurado neste servidor.")
        cliente, pedido = GaleedClient(settings.galeed_api_url, chave, timeout=settings.galeed_timeout_s,
                                       transport=galeed_transport, act_as=dados["e"]).original(dados["s"])
        return await _transmitir(cliente, pedido, modo, _erro_cerebro(chave),
                                 "O cérebro não respondeu. Tente de novo.", settings.visualizador_url)

    async def curto(request: Request) -> Response:
        settings = load_settings()
        codigo = request.path_params["codigo"]
        registro = links_curtos.buscar(settings, codigo)
        if registro is None:
            return _erro(404, "Link inválido ou expirado (vale 30 minutos). Busque o arquivo de novo.")
        dados = ler_token(settings, registro.token, registro.tipo)
        if dados is None:
            return _erro(404, "Link inválido ou expirado (vale 30 minutos). Busque o arquivo de novo.")
        qp = request.query_params
        if qp.get("b") in ("1", "true", "sim") or qp.get("download") in ("1", "true") or qp.get("modo") == "b":
            modo = "b"
        elif qp.get("v") in ("1", "true", "sim") or qp.get("modo") == "v":
            modo = "v"
        elif "text/html" in request.headers.get("accept", "").lower():
            return _pagina_visualizacao(codigo, registro.nome)
        else:
            modo = "v"

        resp = (
            await _servir_cerebro(settings, dados, modo)
            if registro.tipo == "cerebro"
            else await _servir_lic(settings, dados, modo)
        )
        links_curtos.registrar_acesso(
            settings,
            codigo=codigo,
            tipo=registro.tipo,
            email=str(dados.get("e", "")),
            modo=modo,
            ip=_ip_cliente(request),
            user_agent=request.headers.get("user-agent", ""),
            status=resp.status_code,
        )
        if (
            isinstance(resp, JSONResponse)
            and resp.status_code >= 400
            and request.headers.get("sec-fetch-dest", "").lower() == "iframe"
        ):
            return _erro_iframe(codigo, resp)
        return resp

    async def baixar(request: Request) -> Response:
        settings = load_settings()
        dados = ler_token(settings, request.path_params["token"], "baixar")
        if dados is None or dados.get("modo") not in MODOS:
            return _erro(404, "Link inválido ou expirado (vale 30 minutos). Peça outro com licitacao_link_arquivo.")
        return await _servir_lic(settings, dados, dados["modo"])

    async def baixar_cerebro(request: Request) -> Response:
        settings = load_settings()
        dados = ler_token(settings, request.path_params["token"], "cerebro")
        if dados is None or dados.get("modo") not in MODOS:
            return _erro(404, "Link inválido ou expirado (vale 30 minutos). Busque o arquivo de novo no cérebro.")
        return await _servir_cerebro(settings, dados, dados["modo"])

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

    async def enviar_cerebro(request: Request) -> Response:
        settings = load_settings()
        dados = ler_token(settings, request.path_params["token"], "cerebro_enviar")
        if dados is None or not settings.galeed_configured:
            return _erro(404, "Link de envio inválido ou expirado. Peça outro com cerebro_enviar.")
        empresa = str(dados.get("m", ""))
        chave = settings.service_keys.get(empresa, "")
        if not chave:
            return _erro(503, f"O cérebro da empresa {NOMES_EMPRESAS.get(empresa, empresa)} não está configurado neste servidor.")
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
            return _erro(409, "Este link de envio já foi usado. Peça outro com cerebro_enviar.")
        client = GaleedClient(
            settings.galeed_api_url,
            chave,
            timeout=max(settings.galeed_timeout_s, 120.0),
            transport=galeed_transport,
            act_as=str(dados.get("e", "")),
        )
        try:
            status, resultado = await client.enviar(
                str(dados["n"]),
                b"".join(partes),
                contexto=dados.get("c") if isinstance(dados.get("c"), dict) else None,
                content_type=request.headers.get("content-type", "application/octet-stream"),
            )
        except GaleedApiError as exc:
            return _erro(exc.status or 502, f"Cérebro: {exc.body or exc}")
        log.info("Arquivo enviado pelo link para o cérebro %s", empresa)
        corpo = (
            {"empresa": empresa, "http_status": status, "repetido": status == 200, **resultado}
            if isinstance(resultado, dict)
            else {"empresa": empresa, "http_status": status, "repetido": status == 200, "resultado": resultado}
        )
        return JSONResponse(corpo, status_code=status, headers=_NO_STORE)

    return [
        ("/a/{codigo}", ["GET"], curto),
        ("/mcp/arquivos/cerebro-envio/{token}", ["PUT", "POST"], enviar_cerebro),
        ("/mcp/arquivos/cerebro/{token}", ["GET"], baixar_cerebro),
        ("/mcp/arquivos/envio/{token}", ["PUT", "POST"], enviar),
        ("/mcp/arquivos/base-custos/{token}", ["POST"], enviar_base_custos),
        ("/mcp/arquivos/{token}", ["GET"], baixar),
    ]
