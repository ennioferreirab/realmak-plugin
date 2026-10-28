"""Cliente do gateway: rotas, corpo, limite de consulta e segurança da chave."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from mcp_realmak.cerebro.client import GaleedApiError, GaleedClient
from mcp_realmak.cerebro.tools import explicar_erro

URL = "https://galeed.test/v1"


@respx.mock
async def test_rotas_e_corpos():
    ret = respx.post(f"{URL}/retrieve").mock(return_value=httpx.Response(200, json={"hits": []}))
    fac = respx.get(f"{URL}/facts").mock(return_value=httpx.Response(200, json={"facts": []}))
    esq = respx.get(f"{URL}/consulta/esquema").mock(return_value=httpx.Response(200, json={}))
    con = respx.post(f"{URL}/consulta").mock(return_value=httpx.Response(200, json={"linhas": []}))
    pro = respx.post(f"{URL}/consulta/provas").mock(return_value=httpx.Response(200, json={}))
    c = GaleedClient(URL + "/", "gld_live_k")

    await c.retrieve("q", 5, True, "windows")
    assert json.loads(ret.calls[0].request.content) == {"query": "q", "limit": 5, "include_facts": True, "os": "windows"}
    await c.facts(dim="decisions", limit=10, area=None, cursor="")
    assert dict(fac.calls[0].request.url.params) == {"dim": "decisions", "limit": "10"}
    await c.esquema()
    await c.consulta("select 1", 100)
    assert json.loads(con.calls[0].request.content) == {"sql": "select 1", "limite": 100}
    await c.provas(["a", "b"])
    assert json.loads(pro.calls[0].request.content) == {"ids": ["a", "b"]}
    assert esq.called
    for rota in (ret, fac, esq, con, pro):
        assert rota.calls[0].request.headers["authorization"] == "Bearer gld_live_k"


@respx.mock
async def test_erro_do_gateway_nao_vaza_a_chave():
    respx.get(f"{URL}/facts").mock(
        return_value=httpx.Response(400, json={"error": "chave gld_live_k é ruim"})
    )
    with pytest.raises(GaleedApiError) as exc:
        await GaleedClient(URL, "gld_live_k").facts()
    assert "gld_live_k" not in str(exc.value) and "gld_live_k" not in exc.value.body


@respx.mock
async def test_falha_de_rede_vira_status_zero():
    respx.get(f"{URL}/facts").mock(side_effect=httpx.ConnectError("x"))
    with pytest.raises(GaleedApiError) as exc:
        await GaleedClient(URL, "k").facts()
    assert exc.value.status == 0
    assert "falha de conexão" in explicar_erro(exc.value)


@pytest.mark.parametrize(
    ("status", "trecho"),
    [(401, "chave inválida"), (402, "limite diário"), (429, "Aguarde"), (403, "permissão")],
)
def test_mensagens_acionaveis(status, trecho):
    assert trecho in explicar_erro(GaleedApiError(status, "m", "corpo"))
