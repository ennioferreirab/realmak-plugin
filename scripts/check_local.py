"""Verificação local ponta a ponta, sem rede externa.

Sobe um Galeed falso e o mcp-realmak em 127.0.0.1 (portas livres), e confere:
  1. /healthz responde ok sem chave;
  2. POST /mcp sem Authorization devolve 401;
  3. chave que o Galeed falso recusa devolve 401;
  4. tools/list com chave válida, pelo cliente MCP (Streamable HTTP), traz as ferramentas;
  5. uma chamada de cerebro_buscar chega ao Galeed falso com a chave do próprio usuário.

Uso: uv run python scripts/check_local.py
"""

from __future__ import annotations

import asyncio
import os
import socket
import sys
import threading
import time

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

CHAVE_VALIDA = "gld_live_chave_de_teste_valida"
CHAVE_INVALIDA = "gld_live_chave_de_teste_recusada"
recebidas: list[tuple[str, str]] = []  # (caminho, chave)


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _resposta(request: Request) -> JSONResponse:
    chave = request.headers.get("authorization", "").removeprefix("Bearer ")
    recebidas.append((request.url.path, chave))
    if chave != CHAVE_VALIDA:
        return JSONResponse({"error": "chave inválida"}, status_code=401)
    if request.url.path.endswith("/consulta/esquema"):
        return JSONResponse({"tabelas": []})
    if request.url.path.endswith("/retrieve"):
        return JSONResponse({"hits": [{"trecho": "exemplo"}]})
    return JSONResponse({"facts": []})


def servir(app, porta: int) -> uvicorn.Server:
    servidor = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning", lifespan="on")
    )
    threading.Thread(target=servidor.run, daemon=True).start()
    for _ in range(100):
        if servidor.started:
            return servidor
        time.sleep(0.1)
    raise RuntimeError("servidor não subiu")


def conferir(ok: bool, mensagem: str) -> None:
    print(("OK    " if ok else "FALHA ") + mensagem)
    if not ok:
        sys.exit(1)


async def principal() -> None:
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    porta_galeed, porta_mcp = porta_livre(), porta_livre()
    galeed = Starlette(
        routes=[
            Route("/v1/{rest:path}", _resposta, methods=["GET", "POST"]),
        ]
    )
    servir(galeed, porta_galeed)
    os.environ["GALEED_API_URL"] = f"http://127.0.0.1:{porta_galeed}/v1"

    from mcp_realmak.server import build_app

    servir(build_app(), porta_mcp)
    base = f"http://127.0.0.1:{porta_mcp}"

    async with httpx.AsyncClient() as http:
        r = await http.get(f"{base}/healthz")
        conferir(r.status_code == 200 and r.json() == {"status": "ok"}, "/healthz responde ok sem chave")

        corpo = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        cab = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        r = await http.post(f"{base}/mcp", json=corpo, headers=cab)
        conferir(r.status_code == 401, f"POST /mcp sem token devolve 401 (veio {r.status_code})")
        r = await http.post(
            f"{base}/mcp", json=corpo, headers={**cab, "Authorization": f"Bearer {CHAVE_INVALIDA}"}
        )
        conferir(r.status_code == 401, f"POST /mcp com chave recusada devolve 401 (veio {r.status_code})")

    transporte = StreamableHttpTransport(
        f"{base}/mcp", headers={"Authorization": f"Bearer {CHAVE_VALIDA}"}
    )
    async with Client(transporte) as cliente:
        ferramentas = await cliente.list_tools()
        nomes = sorted(t.name for t in ferramentas)
        grupos: dict[str, int] = {}
        for n in nomes:
            grupos[n.split("_")[0]] = grupos.get(n.split("_")[0], 0) + 1
        print(f"tools/list: {len(nomes)} ferramentas, por grupo: {grupos}")
        conferir(len(nomes) >= 40, "tools/list com chave válida trouxe as ferramentas")
        conferir("cerebro_consulta" in nomes, "ferramentas de registros listadas (esquema respondeu 200)")
        resultado = await cliente.call_tool("cerebro_buscar", {"query": "teste", "os": "windows"})
        conferir("exemplo" in str(resultado.content), "cerebro_buscar devolveu o trecho do Galeed falso")

    chaves = {c for p, c in recebidas if p.endswith("/retrieve")}
    conferir(chaves == {CHAVE_VALIDA}, "o Galeed recebeu a chave do próprio usuário na chamada")
    print("Verificação local concluída sem falhas.")


if __name__ == "__main__":
    asyncio.run(principal())
