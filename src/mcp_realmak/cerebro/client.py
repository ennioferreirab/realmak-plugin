"""Cliente HTTP fino do gateway público /v1 do Galeed (porte do client.ts).

Rotas:
    POST /retrieve            {query, limit?, include_facts?, os?}
    GET  /facts               ?dim&area&status&as_of&min_confidence&limit&cursor&os
    GET  /consulta/esquema
    POST /consulta            {sql, limite?}
    POST /consulta/provas     {ids, os?}

Regra de segurança: a chave nunca aparece em mensagem de erro, log ou exceção.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

SISTEMAS = ("macos", "linux", "windows")


class GaleedApiError(Exception):
    """Erro do gateway com o status HTTP preservado (0 = falha de rede ou tempo)."""

    def __init__(self, status: int, message: str, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class GaleedClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        act_as: str = "",
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._act_as = act_as
        self._timeout = timeout
        self._transport = transport

    async def retrieve(
        self,
        query: str,
        limit: int | None = None,
        include_facts: bool | None = None,
        os: str | None = None,
    ) -> Any:
        body: dict[str, Any] = {"query": query}
        if limit is not None:
            body["limit"] = limit
        if include_facts is not None:
            body["include_facts"] = include_facts
        if os:
            body["os"] = os
        return await self._request("POST", "/retrieve", json_body=body)

    async def facts(self, **params: Any) -> Any:
        query = {k: v for k, v in params.items() if v is not None and v != ""}
        return await self._request("GET", "/facts", params=query)

    async def esquema(self) -> Any:
        return await self._request("GET", "/consulta/esquema")

    async def consulta(self, sql: str, limite: int | None = None) -> Any:
        body: dict[str, Any] = {"sql": sql}
        if limite is not None:
            body["limite"] = limite
        return await self._request("POST", "/consulta", json_body=body)

    async def provas(self, ids: list[str], os: str | None = None) -> Any:
        body: dict[str, Any] = {"ids": ids}
        if os:
            body["os"] = os
        return await self._request("POST", "/consulta/provas", json_body=body)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport, follow_redirects=False
            ) as client:
                resp = await client.request(
                    method,
                    url,
                    json=json_body,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        **({"X-Galeed-Act-As": self._act_as} if self._act_as else {}),
                    },
                )
        except httpx.TimeoutException:
            raise GaleedApiError(
                0, f"tempo esgotado após {int(self._timeout * 1000)}ms ao chamar {method} {path}"
            ) from None
        except httpx.HTTPError as exc:
            raise GaleedApiError(
                0, f"falha de rede ao chamar {method} {path}: {type(exc).__name__}"
            ) from None

        text = resp.text
        if resp.status_code >= 400:
            server_msg = text
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict) and isinstance(parsed.get("error"), str):
                    server_msg = parsed["error"]
            except ValueError:
                pass
            server_msg = server_msg.replace(self._token, "***")[:500]
            raise GaleedApiError(
                resp.status_code, f"{method} {path} -> HTTP {resp.status_code}: {server_msg}", server_msg
            )
        if not text:
            return None
        try:
            return resp.json()
        except ValueError:
            raise GaleedApiError(resp.status_code, f"{method} {path} -> resposta não é JSON válido") from None
