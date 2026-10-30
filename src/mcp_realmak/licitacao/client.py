"""Cliente das rotas internas do Odoo (módulo `realmak_mcp` do realmak-crm).

Rotas, todas com `Authorization: Bearer <segredo>` e `X-Realmak-Act-As: <e-mail da pessoa>`:
    POST {ODOO_MCP_URL}/realmak_mcp/v1/<ferramenta>          corpo JSON; resposta {"resultado": ...} ou {"erro": ...}
    POST {ODOO_MCP_URL}/realmak_mcp/v1/arquivo/<licitacao>   bytes do arquivo; ?nome=&descricao=
    GET  {ODOO_MCP_URL}/realmak_mcp/v1/arquivo/<licitacao>/<documento>

O Odoo roda cada chamada como a pessoa: valem as permissões dela. O segredo nunca aparece em erro ou log.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import Settings

PREFIXO = "/realmak_mcp/v1"


class OdooApiError(Exception):
    """Erro do Odoo com o status HTTP preservado (0 = falha de rede ou tempo)."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class OdooClient:
    def __init__(
        self,
        settings: Settings,
        email: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base = settings.odoo_mcp_url.rstrip("/") + PREFIXO
        self._segredo = settings.odoo_secret()
        self._email = email
        self._timeout = settings.odoo_timeout_s
        self._transport = transport
        if not self._segredo:
            raise OdooApiError(503, "o servidor ainda não tem o segredo das licitações (o Odoo cria na primeira subida)")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._segredo}", "X-Realmak-Act-As": self._email}

    def _cliente(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport, follow_redirects=False)

    async def chamar(self, ferramenta: str, params: dict[str, Any] | None = None) -> Any:
        corpo = {k: v for k, v in (params or {}).items() if v is not None}
        return await self._pedir("POST", f"/{ferramenta}", json=corpo)

    async def enviar(self, licitacao_id: int, nome: str, conteudo: bytes, descricao: str | None = None) -> Any:
        query = {"nome": nome, **({"descricao": descricao} if descricao else {})}
        return await self._pedir(
            "POST", f"/arquivo/{licitacao_id}", params=query, content=conteudo,
            headers={"Content-Type": "application/octet-stream"},
        )

    def baixar(self, licitacao_id: int, documento_id: int) -> tuple[httpx.AsyncClient, httpx.Request]:
        """Cliente e pedido para o download em fluxo; quem chama abre `send(stream=True)` e fecha os dois."""
        cliente = self._cliente()
        return cliente, cliente.build_request("GET", f"{self._base}/arquivo/{licitacao_id}/{documento_id}",
                                              headers=self._headers())

    async def _pedir(self, metodo: str, caminho: str, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        try:
            async with self._cliente() as cliente:
                resp = await cliente.request(metodo, self._base + caminho, headers={**self._headers(), **(headers or {})},
                                             **kwargs)
        except httpx.TimeoutException:
            raise OdooApiError(0, f"o Odoo não respondeu em {int(self._timeout)} s") from None
        except httpx.HTTPError as exc:
            raise OdooApiError(0, f"falha de rede ao chamar o Odoo: {type(exc).__name__}") from None
        return interpretar(resp, self._segredo)


def interpretar(resp: httpx.Response, segredo: str = "") -> Any:
    try:
        corpo = resp.json()
    except ValueError:
        corpo = None
    if resp.status_code >= 400 or not isinstance(corpo, dict) or "resultado" not in corpo:
        mensagem = corpo.get("erro") if isinstance(corpo, dict) and isinstance(corpo.get("erro"), str) else ""
        mensagem = (mensagem or f"HTTP {resp.status_code}")[:500]
        if segredo:
            mensagem = mensagem.replace(segredo, "***")
        raise OdooApiError(resp.status_code, mensagem)
    return corpo["resultado"]
