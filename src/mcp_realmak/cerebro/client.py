"""Cliente HTTP fino do gateway público /v1 do Galeed (porte do client.ts).

Rotas:
    POST /retrieve            {query, limit?, include_facts?, os?, incluir_historico?}
    GET  /facts               ?dim&area&status&as_of&min_confidence&limit&cursor&os&incluir_historico
    GET  /consulta/esquema
    POST /consulta            {sql, limite?}
    POST /consulta/provas     {ids, os?, incluir_historico?}
    GET  /original            ?slug   bytes do arquivo original da página (em fluxo)
    POST /envios              corpo = arquivo cru, x-galeed-nome, x-galeed-contexto (201 novo / 200 repetido)
    GET  /envios              ?limite&id&sha256   andamento dos envios
    POST /documentos/comentarios  {sha256|caminho, texto}   anota um documento existente (201)
    GET  /documentos/comentarios  ?sha256|caminho           lista comentários e nota_revisao

Regra de segurança: a chave nunca aparece em mensagem de erro, log ou exceção.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx

SISTEMAS = ("macos", "linux", "windows")
CONTEXTO_ENVIO_MAX_BYTES = 8 * 1024


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
        incluir_historico: bool | None = None,
    ) -> Any:
        body: dict[str, Any] = {"query": query}
        if limit is not None:
            body["limit"] = limit
        if include_facts is not None:
            body["include_facts"] = include_facts
        if os:
            body["os"] = os
        if incluir_historico is not None:
            body["incluir_historico"] = bool(incluir_historico)
        return await self._request("POST", "/retrieve", json_body=body)

    async def facts(self, **params: Any) -> Any:
        query: dict[str, Any] = {}
        for k, v in params.items():
            if v is None or v == "":
                continue
            if k == "incluir_historico":
                if v:
                    query[k] = "true"
                continue
            query[k] = v
        return await self._request("GET", "/facts", params=query)

    async def acesso(self) -> Any:
        return await self._request("GET", "/acesso", expected_status=200)

    async def esquema(self) -> Any:
        return await self._request("GET", "/consulta/esquema")

    async def consulta(self, sql: str, limite: int | None = None) -> Any:
        body: dict[str, Any] = {"sql": sql}
        if limite is not None:
            body["limite"] = limite
        return await self._request("POST", "/consulta", json_body=body)

    async def provas(
        self,
        ids: list[str],
        os: str | None = None,
        incluir_historico: bool | None = None,
    ) -> Any:
        body: dict[str, Any] = {"ids": ids}
        if os:
            body["os"] = os
        if incluir_historico is not None:
            body["incluir_historico"] = bool(incluir_historico)
        return await self._request("POST", "/consulta/provas", json_body=body)

    async def corpos(self, shas: list[str], brain: str | None = None) -> Any:
        body: dict[str, Any] = {"shas": shas}
        if brain:
            body["brain"] = brain
        return await self._request("POST", "/corpos", json_body=body)

    def original(self, slug: str) -> tuple[httpx.AsyncClient, httpx.Request]:
        """Cliente e pedido do original em fluxo; quem chama abre `send(stream=True)` e fecha os dois."""
        cliente = httpx.AsyncClient(timeout=self._timeout, transport=self._transport, follow_redirects=False)
        return cliente, cliente.build_request("GET", f"{self._base}/original", params={"slug": slug},
                                              headers=self._headers())

    async def enviar(
        self,
        nome: str,
        conteudo: bytes,
        *,
        contexto: dict[str, Any] | None = None,
        content_type: str = "application/octet-stream",
    ) -> tuple[int, Any]:
        headers = {
            **self._headers(),
            "Content-Type": content_type or "application/octet-stream",
            "x-galeed-nome": quote(nome, safe=""),
        }
        if contexto:
            codificado = quote(json.dumps(contexto, ensure_ascii=False, separators=(",", ":")), safe="")
            if len(codificado.encode("ascii")) > CONTEXTO_ENVIO_MAX_BYTES:
                raise GaleedApiError(400, "x-galeed-contexto excede o limite de 8 KB", "contexto acima de 8 KB")
            headers["x-galeed-contexto"] = codificado
        url = f"{self._base}/envios"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport, follow_redirects=False
            ) as client:
                resp = await client.post(url, content=conteudo, headers=headers)
        except httpx.TimeoutException:
            raise GaleedApiError(
                0, f"tempo esgotado após {int(self._timeout * 1000)}ms ao chamar POST /envios"
            ) from None
        except httpx.HTTPError as exc:
            raise GaleedApiError(
                0, f"falha de rede ao chamar POST /envios: {type(exc).__name__}"
            ) from None
        return resp.status_code, self._parse_response("POST", "/envios", resp)

    async def envios(
        self,
        *,
        limite: int | None = None,
        sha256: str | None = None,
        envio_id: str | None = None,
    ) -> Any:
        params: dict[str, Any] = {}
        if limite is not None:
            params["limite"] = limite
        if sha256:
            params["sha256"] = sha256
        if envio_id:
            params["id"] = envio_id
        return await self._request("GET", "/envios", params=params or None)

    async def comentar(
        self,
        texto: str,
        *,
        sha256: str | None = None,
        caminho: str | None = None,
    ) -> Any:
        body: dict[str, Any] = {"texto": texto}
        if sha256:
            body["sha256"] = sha256
        if caminho:
            body["caminho"] = caminho
        return await self._request("POST", "/documentos/comentarios", json_body=body)

    async def comentarios(
        self,
        *,
        sha256: str | None = None,
        caminho: str | None = None,
    ) -> Any:
        params: dict[str, Any] = {}
        if sha256:
            params["sha256"] = sha256
        if caminho:
            params["caminho"] = caminho
        return await self._request("GET", "/documentos/comentarios", params=params or None)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", **({"X-Galeed-Act-As": self._act_as} if self._act_as else {})}

    def _parse_response(
        self, method: str, path: str, resp: httpx.Response, expected_status: int | None = None
    ) -> Any:
        text = resp.text
        if resp.status_code >= 300 or (expected_status is not None and resp.status_code != expected_status):
            server_msg = text
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict) and isinstance(parsed.get("error"), str):
                    server_msg = parsed["error"]
            except ValueError:
                pass
            server_msg = server_msg.replace(self._token, "***")[:500]
            raise GaleedApiError(
                resp.status_code if resp.status_code >= 300 else 502,
                f"{method} {path} -> HTTP {resp.status_code}: {server_msg}",
                server_msg,
            )
        if not text:
            return None
        try:
            return resp.json()
        except ValueError:
            raise GaleedApiError(502, f"{method} {path} -> resposta não é JSON válido") from None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
        params: dict[str, Any] | None = None,
        expected_status: int | None = None,
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
                    headers=self._headers(),
                )
        except httpx.TimeoutException:
            raise GaleedApiError(
                0, f"tempo esgotado após {int(self._timeout * 1000)}ms ao chamar {method} {path}"
            ) from None
        except httpx.HTTPError as exc:
            raise GaleedApiError(
                0, f"falha de rede ao chamar {method} {path}: {type(exc).__name__}"
            ) from None
        return self._parse_response(method, path, resp, expected_status)
