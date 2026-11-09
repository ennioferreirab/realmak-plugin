"""Regressões das rotas que respondiam 404/301 e das respostas vazias."""

import httpx
import pytest
import respx

from mcp_realmak.compras._shared.http_client import http_get
from mcp_realmak.compras.pncp import client
from mcp_realmak.compras.pncp.constants import CONTRATACAO_DETALHE_URL, PCA_URL


def test_pca_usa_a_barra_final_que_o_pncp_exige() -> None:
    # /v1/pca responde 404; só /v1/pca/ existe no OpenAPI.
    assert PCA_URL.endswith("/pca/")


@pytest.mark.asyncio
@respx.mock
async def test_detalhe_da_contratacao_usa_a_rota_de_consulta() -> None:
    # /api/pncp/v1/orgaos/.../compras/... responde 301 sem destino utilizável.
    rota = respx.get(f"{CONTRATACAO_DETALHE_URL}/00394460000141/compras/2026/1").mock(
        return_value=httpx.Response(200, json={"numeroControlePNCP": "x"})
    )
    await client.consultar_contratacao_detalhe("00394460000141", 2026, 1)
    assert rota.called
    assert "/api/consulta/v1/" in str(rota.calls[0].request.url)


@pytest.mark.asyncio
@respx.mock
async def test_corpo_vazio_vira_resposta_vazia_em_vez_de_json_decode_error() -> None:
    respx.get("https://exemplo.gov.br/vazio").mock(return_value=httpx.Response(200, content=b""))
    assert await http_get("https://exemplo.gov.br/vazio") == {}
