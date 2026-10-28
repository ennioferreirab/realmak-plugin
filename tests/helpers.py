"""Ajuda para falar JSON-RPC com o app ASGI do servidor (Streamable HTTP)."""

from __future__ import annotations

import json
from typing import Any

import httpx

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def parse_body(resp: httpx.Response) -> dict[str, Any]:
    ctype = resp.headers.get("content-type", "")
    if ctype.startswith("text/event-stream"):
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        raise AssertionError(f"SSE sem dados: {resp.text!r}")
    return resp.json()


async def rpc(
    client: httpx.AsyncClient, method: str, params: dict | None = None, token: str | None = "gld_live_boa"
) -> httpx.Response:
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return await client.post("/mcp", json=body, headers=headers)


async def call_tool(client: httpx.AsyncClient, name: str, args: dict, token: str = "gld_live_boa") -> dict:
    resp = await rpc(client, "tools/call", {"name": name, "arguments": args}, token)
    assert resp.status_code == 200, resp.text
    return parse_body(resp)["result"]
