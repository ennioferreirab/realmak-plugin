"""Servidor completo em memória (ASGI), com o Galeed simulado por respx."""

from __future__ import annotations

import contextlib
import functools
import inspect

import httpx
import pytest
import respx

from mcp_realmak.server import build_app

from .helpers import call_tool, parse_body, rpc

GALEED = "https://galeed.test/v1"


def com_servidor(fn):
    """Abre o app dentro da própria tarefa do teste (o lifespan do anyio exige isso)."""

    @functools.wraps(fn)
    async def wrapper(*args, monkeypatch, **kwargs):
        monkeypatch.setenv("GALEED_API_URL", GALEED)
        async with abrir_servidor() as servidor:
            return await fn(servidor, *args, **kwargs)

    params = [p for n, p in inspect.signature(fn).parameters.items() if n != "servidor"]
    params.append(inspect.Parameter("monkeypatch", inspect.Parameter.KEYWORD_ONLY))
    wrapper.__signature__ = inspect.Signature(params)  # type: ignore[attr-defined]
    del wrapper.__wrapped__
    return wrapper


@contextlib.asynccontextmanager
async def abrir_servidor():
    app = build_app()
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GALEED}/facts").mock(
            side_effect=lambda r: httpx.Response(
                200 if r.headers["authorization"] in ("Bearer gld_live_boa", "Bearer gld_live_outra") else 401,
                json={"facts": []},
            )
        )
        mock.get(f"{GALEED}/consulta/esquema").mock(return_value=httpx.Response(200, json={"tabelas": []}))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
                c.galeed = mock  # type: ignore[attr-defined]
                yield c


@com_servidor
async def test_healthz_sem_chave(servidor):
    r = await servidor.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


@com_servidor
async def test_sem_token_devolve_401_sem_descoberta_oauth(servidor):
    r = await rpc(servidor, "tools/list", token=None)
    assert r.status_code == 401
    assert "resource_metadata" not in r.headers.get("www-authenticate", "")
    for caminho in ("/.well-known/oauth-protected-resource", "/.well-known/oauth-authorization-server"):
        assert (await servidor.get(caminho)).status_code == 404


@com_servidor
async def test_chave_recusada_pelo_galeed_devolve_401(servidor):
    r = await rpc(servidor, "tools/list", token="gld_live_ruim")
    assert r.status_code == 401


@com_servidor
async def test_galeed_fora_do_ar_devolve_503_claro(servidor):
    servidor.galeed.get(f"{GALEED}/facts").mock(side_effect=httpx.ConnectError("sem rota"))
    r = await rpc(servidor, "tools/list", token="gld_live_nova")
    assert r.status_code == 503
    assert "Galeed não respondeu" in r.json()["message"]


@com_servidor
async def test_header_estatico_funciona_sem_fluxo_oauth(servidor):
    r = await rpc(servidor, "tools/list")
    assert r.status_code == 200
    nomes = {t["name"] for t in parse_body(r)["result"]["tools"]}
    assert {"pncp_buscar_contratacoes", "dadosabertos_buscar_licitacoes"} <= nomes or any(
        n.startswith("dadosabertos_") for n in nomes
    )
    assert any(n.startswith("contratosgovbr_") for n in nomes)
    assert {"conlicitacao_buscar_licitacao", "conlicitacao_ler_boletim", "galeed_retrieve"} <= nomes
    assert "galeed_consulta" in nomes  # esquema respondeu 200


@com_servidor
async def test_ferramentas_de_registros_somem_quando_o_gateway_nega(servidor):
    servidor.galeed.get(f"{GALEED}/consulta/esquema").mock(
        return_value=httpx.Response(403, json={"error": "sem acesso"})
    )
    r = await rpc(servidor, "tools/list", token="gld_live_outra")
    nomes = {t["name"] for t in parse_body(r)["result"]["tools"]}
    assert "galeed_retrieve" in nomes
    assert not {"galeed_esquema", "galeed_consulta", "galeed_provas"} & nomes


@com_servidor
async def test_cada_chamada_usa_a_chave_do_proprio_usuario(servidor):
    rota = servidor.galeed.post(f"{GALEED}/retrieve").mock(
        return_value=httpx.Response(200, json={"hits": [{"trecho": "x"}]})
    )
    await call_tool(servidor, "galeed_retrieve", {"query": "atestado", "os": "windows"}, "gld_live_boa")
    await call_tool(servidor, "galeed_retrieve", {"query": "atestado"}, "gld_live_outra")
    chaves = [c.request.headers["authorization"] for c in rota.calls]
    assert chaves == ["Bearer gld_live_boa", "Bearer gld_live_outra"]
    corpo = rota.calls[0].request.content.decode()
    assert '"os":"windows"' in corpo.replace(" ", "") and '"query":"atestado"' in corpo.replace(" ", "")
    assert '"os"' not in rota.calls[1].request.content.decode()  # os é opcional


@com_servidor
async def test_resultado_enorme_e_cortado_no_teto(servidor):
    grande = {"hits": [{"trecho": "a" * 1000} for _ in range(300)]}
    servidor.galeed.post(f"{GALEED}/retrieve").mock(return_value=httpx.Response(200, json=grande))
    r = await call_tool(servidor, "galeed_retrieve", {"query": "x"})
    texto = r["content"][0]["text"]
    assert len(texto) < 100_000 + 300
    assert "Resultado cortado" in texto


@pytest.mark.parametrize(
    ("status", "trecho"),
    [(403, "não lê o dataset de registros"), (404, "não tem o dataset"), (503, "ainda não está disponível")],
)
@com_servidor
async def test_erros_de_registros_sao_claros(servidor, status, trecho):
    servidor.galeed.post(f"{GALEED}/consulta").mock(
        return_value=httpx.Response(status, json={"error": "detalhe do gateway"})
    )
    r = await call_tool(servidor, "galeed_consulta", {"sql": "select 1"})
    assert r["isError"] is True
    assert trecho in r["content"][0]["text"]


@com_servidor
async def test_consulta_400_aponta_o_esquema(servidor):
    servidor.galeed.post(f"{GALEED}/consulta").mock(
        return_value=httpx.Response(400, json={"error": "coluna x não existe"})
    )
    r = await call_tool(servidor, "galeed_consulta", {"sql": "select x from y"})
    assert "galeed_esquema" in r["content"][0]["text"]
    assert "coluna x não existe" in r["content"][0]["text"]
