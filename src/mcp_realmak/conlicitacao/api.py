"""Cliente da API oficial do ConLicitação (cabeçalho x-auth-token).

O IP de saída do servidor precisa estar cadastrado no ConLicitação. Rotas de
leitura: /filtros, /filtro/{id}/boletins, /boletim/{id}, /monitored_biddings
e /monitored_biddings/messages. As rotas de escrita não estão aqui.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from .errors import ConlicitacaoError

log = logging.getLogger("mcp_realmak.conlicitacao.api")

RETRY_STATUS = {429, 500, 502, 503, 504}


class ConlicitacaoApiClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 30.0,
        retries: int = 2,
        backoff: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base = base_url.rstrip("/") + "/api"
        self._token = token
        self._timeout = timeout
        self._retries = retries
        self._backoff = backoff
        self._transport = transport

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        if not self._token:
            raise ConlicitacaoError("O token da API do ConLicitação não está configurado no servidor.")
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        resp: httpx.Response | None = None
        for attempt in range(self._retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout, transport=self._transport, follow_redirects=False
                ) as client:
                    resp = await client.get(
                        f"{self._base}{path}",
                        params=clean,
                        # A API responde 406 a Accept: application/json; o curl manda */*.
                        headers={"x-auth-token": self._token, "Accept": "*/*"},
                    )
            except httpx.HTTPError as exc:
                log.warning("Falha de rede na API do ConLicitação: %s", type(exc).__name__)
                if attempt < self._retries:
                    await asyncio.sleep(self._backoff * (2**attempt))
                    continue
                raise ConlicitacaoError("Falha de conexão com a API do ConLicitação.") from None
            if resp.status_code in RETRY_STATUS and attempt < self._retries:
                await asyncio.sleep(self._backoff * (2**attempt))
                continue
            break
        assert resp is not None
        if resp.status_code == 401:
            raise ConlicitacaoError(
                "A API do ConLicitação recusou o token (401). Pode ser token trocado ou IP de saída "
                "do servidor não cadastrado. Avise quem administra o servidor."
            )
        if resp.status_code != 200:
            raise ConlicitacaoError(f"A API do ConLicitação respondeu HTTP {resp.status_code}.")
        try:
            data = resp.json()
        except ValueError:
            raise ConlicitacaoError("Resposta da API do ConLicitação não é JSON válido.") from None
        if not isinstance(data, dict):
            raise ConlicitacaoError("Resposta da API do ConLicitação com estrutura inesperada.")
        return data

    async def filtros(self) -> dict:
        return await self.get("/filtros")

    async def boletins(self, filtro_id: int, page: int, per_page: int, order: str) -> dict:
        return await self.get(
            f"/filtro/{int(filtro_id)}/boletins", {"page": page, "per_page": per_page, "order": order}
        )

    async def boletim(self, boletim_id: int) -> dict:
        return await self.get(f"/boletim/{int(boletim_id)}")

    async def monitoradas(self, page: int, per_page: int) -> dict:
        return await self.get("/monitored_biddings", {"page": page, "per_page": per_page})

    async def mensagens(self, bidding_id: int, page: int, per_page: int) -> dict:
        return await self.get(
            "/monitored_biddings/messages",
            {"bidding_id": int(bidding_id), "page": page, "per_page": per_page},
        )
