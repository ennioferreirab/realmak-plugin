"""Isolamento entre empresas, falha fechada e autorização MCP com HTTP simulado."""

from __future__ import annotations

import contextlib
import json
from collections import Counter

import httpx
import pytest
import respx
from fastmcp.server.auth import AccessToken

from mcp_realmak.auth import GaleedTokenVerifier, GaleedUnavailableError, token_hash
from mcp_realmak.cerebro import empresas as empresas_mod
from mcp_realmak.cerebro.client import GaleedApiError
from mcp_realmak.cerebro.empresas import Empresas
from mcp_realmak.config import EMPRESAS, load_settings
from mcp_realmak.oauth import OAuthServer
from mcp_realmak.server import build_app

from .helpers import call_tool, parse_body, rpc

URL = "https://galeed.test/v1"
EMAIL = "analista@example.test"
KEYS = {e: f"gld_live_test_{e}" for e in EMPRESAS}
BOT = "gld_live_bot_aforca"


def acesso(empresa, nivel="total", registros=True):
    return {"brain": "Realmak" if empresa == "realmak" else empresa, "nivel": nivel,
            "areas": ["rh", "obras"] if nivel == "parcial" else ["*"], "registros": registros}


def pessoa():
    return AccessToken(token="rmk_person", client_id="person", scopes=[], claims={"email": EMAIL})


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("GALEED_API_URL", URL)
    monkeypatch.setenv("GALEED_SERVICE_KEYS", ",".join(f"{e}={k}" for e, k in KEYS.items()))
    return load_settings()


def test_config_multichave_e_sem_segredos(monkeypatch, caplog):
    monkeypatch.setenv("GALEED_SERVICE_KEY", "gld_live_old_secret")
    assert load_settings().service_keys == {"realmak": "gld_live_old_secret"}
    monkeypatch.setenv("GALEED_SERVICE_KEYS", " realmak=gld_live_new_secret, aforca=, desconhecida=gld_live_bad_secret,, una=gld_live_una_secret")
    settings = load_settings()
    assert settings.galeed_service_keys == {"realmak": "gld_live_new_secret", "una": "gld_live_una_secret"}
    assert "aforca" in caplog.text
    assert "gld_live_" not in caplog.text + repr(settings)
    assert "desconhecida" not in caplog.text


def test_oauth_so_com_multichave(monkeypatch, settings):
    monkeypatch.setenv("MCP_REALMAK_PUBLIC_URL", "https://mcp.test")
    monkeypatch.setenv("MCP_REALMAK_OAUTH_SECRET", "s" * 40)
    monkeypatch.setenv("GALEED_LOGIN_URL", "https://login.test")
    assert load_settings().oauth_configured


async def test_descoberta_paralelo_cache_so_definitivos(settings):
    calls = Counter()

    def handler(req):
        empresa = next(e for e, key in KEYS.items() if req.headers["authorization"] == f"Bearer {key}")
        assert req.headers["x-galeed-act-as"] == EMAIL
        calls[empresa] += 1
        if empresa == "sublime":
            return httpx.Response(500)
        if empresa == "nortfort":
            return httpx.Response(403)
        return httpx.Response(200, json=acesso(empresa, "parcial" if empresa == "una" else "total"))

    directory = Empresas(settings, httpx.MockTransport(handler))
    first = (await directory.descobrir(pessoa())).publico()
    assert [e["empresa"] for e in first["empresas"]] == ["realmak", "aforca", "una"]
    assert first["indisponiveis"] == ["sublime"] and first["padrao"] == "realmak"
    assert first["empresas"][-1]["areas"] == ["rh", "obras"]
    assert "areas" not in first["empresas"][0]
    assert (await directory.descobrir(pessoa())).publico() == first
    assert calls == Counter(realmak=1, aforca=1, nortfort=1, una=1, sublime=2)
    assert list(directory._cache) == [token_hash(EMAIL)]
    assert all(key not in repr(directory._cache) for key in KEYS.values())


async def test_cache_nao_renova_ttl_e_revogacao_falha_fechada(settings, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(empresas_mod.time, "monotonic", lambda: now[0])
    calls = []

    def handler(req):
        calls.append(req)
        empresa = next(e for e, key in KEYS.items() if req.headers["authorization"] == f"Bearer {key}")
        return httpx.Response(200, json=acesso(empresa)) if now[0] < 1300 else httpx.Response(403)

    directory = Empresas(settings, httpx.MockTransport(handler))
    assert len((await directory.descobrir(pessoa())).empresas) == 5
    now[0] = 1299
    assert len((await directory.descobrir(pessoa())).empresas) == 5
    assert len(calls) == 5
    now[0] = 1301
    assert not (await directory.descobrir(pessoa())).empresas
    assert len(calls) == 10


@pytest.mark.parametrize(("allowed", "padrao"), [(["una", "aforca"], None), (["una"], "una"), ([], None)])
async def test_padrao_sem_realmak(settings, allowed, padrao):
    def handler(req):
        e = next(e for e, key in KEYS.items() if req.headers["authorization"] == f"Bearer {key}")
        return httpx.Response(200, json=acesso(e)) if e in allowed else httpx.Response(403)
    result = await Empresas(settings, httpx.MockTransport(handler)).descobrir(pessoa())
    assert result.publico()["padrao"] == padrao


async def test_brain_servico_cache_permanente_e_chave_bot_isolada(settings):
    calls = Counter()
    def handler(req):
        key = req.headers["authorization"].removeprefix("Bearer ")
        calls[key] += 1
        assert "x-galeed-act-as" not in req.headers
        e = "aforca" if key == BOT else next(e for e, k in KEYS.items() if k == key)
        return httpx.Response(200, json=acesso(e))
    directory = Empresas(settings, httpx.MockTransport(handler))
    bot = AccessToken(token=BOT, client_id="bot", scopes=[])
    assert [e.empresa for e in (await directory.descobrir(bot)).empresas] == ["aforca"]
    await directory.descobrir(bot)
    assert calls[BOT] == 1
    await directory.brain_da_empresa("aforca")
    assert calls[KEYS["aforca"]] == 1
    assert list(directory._cache) == [token_hash(BOT)]


@pytest.mark.parametrize("data", [{}, {"brain": "una", "nivel": "total", "areas": ["*"], "registros": True}, {"brain": "Realmak", "nivel": "total", "areas": "*", "registros": True}])
async def test_resposta_invalida_ou_brain_trocado_falha_fechada(settings, data):
    directory = Empresas(settings, httpx.MockTransport(lambda r: httpx.Response(200, json=data)))
    result = await directory.descobrir(pessoa())
    assert not any(e.empresa == "realmak" for e in result.empresas)
    assert "realmak" in result.indisponiveis
    assert "realmak" not in directory._cache.get(token_hash(EMAIL), {})


async def test_auth_pessoa_aceita_uma_e_falha_fechada(settings):
    status = [200]
    def handler(req):
        e = next(e for e, k in KEYS.items() if req.headers["authorization"] == f"Bearer {k}")
        return httpx.Response(status[0] if e == "una" else 403, json=acesso(e))
    verifier = GaleedTokenVerifier(URL, service_keys=KEYS, transport=httpx.MockTransport(handler))
    assert await verifier.check_cerebro_person(EMAIL)
    empresas_mod._instances.clear()
    status[0] = 500
    with pytest.raises(GaleedUnavailableError):
        await verifier.check_cerebro_person(EMAIL)
    empresas_mod._instances.clear()
    status[0] = 401
    with pytest.raises(GaleedUnavailableError, match="chave de serviço recusada"):
        await verifier.check_cerebro_person(EMAIL)


@contextlib.asynccontextmanager
async def servidor(monkeypatch, allowed=None, partial=(), registros=(), failed=()):
    monkeypatch.setenv("GALEED_API_URL", URL)
    monkeypatch.setenv("GALEED_SERVICE_KEYS", ",".join(f"{e}={k}" for e, k in KEYS.items()))
    monkeypatch.setenv("MCP_REALMAK_PUBLIC_URL", "https://mcp.test")
    monkeypatch.setenv("MCP_REALMAK_OAUTH_SECRET", "s" * 40)
    monkeypatch.setenv("GALEED_LOGIN_URL", "https://login.test")
    allowed = set(EMPRESAS if allowed is None else allowed)
    state = {"allowed": allowed, "partial": set(partial), "registros": set(registros), "failed": set(failed)}
    app = build_app()
    oauth = OAuthServer("https://mcp.test", "s" * 40, verify_person=lambda e: True)
    token = oauth.issue_tokens(EMAIL, "rc_test")["access_token"]
    def handler(req):
        key = req.headers["authorization"].removeprefix("Bearer ")
        e = "aforca" if key == BOT else next(e for e, k in KEYS.items() if k == key)
        if req.headers.get("x-galeed-act-as"):
            if e in state["failed"]:
                return httpx.Response(500)
            if e not in state["allowed"]:
                return httpx.Response(403)
        return httpx.Response(200, json=acesso(e, "parcial" if e in state["partial"] else "total", e in state["registros"]))
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{URL}/facts").mock(return_value=httpx.Response(200, json={"facts": []}))
        mock.get(f"{URL}/acesso").mock(side_effect=handler)
        mock.post(f"{URL}/retrieve").mock(return_value=httpx.Response(200, json={"hits": []}))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://mcp.test") as client:
                yield client, mock, token, state


def result_data(result):
    assert not result.get("isError"), result
    return json.loads(result["content"][0]["text"])


async def test_mcp_empresas_e_roteamento_parcial(monkeypatch):
    async with servidor(monkeypatch, partial=["nortfort"], registros=["realmak"]) as (c, mock, token, state):
        data = result_data(await call_tool(c, "cerebro_empresas", {}, token))
        assert len(data["empresas"]) == 5 and data["padrao"] == "realmak"
        data = result_data(await call_tool(c, "cerebro_buscar", {"query": "obra", "empresa": "nortfort"}, token))
        assert data["empresa"] == "nortfort" and data["acesso"] == {"nivel": "parcial", "areas": ["rh", "obras"]}
        req = mock.calls.last.request
        assert req.url.path == "/v1/retrieve"
        assert req.headers["authorization"] == f"Bearer {KEYS['nortfort']}"
        assert req.headers["x-galeed-act-as"] == EMAIL
        default = result_data(await call_tool(c, "cerebro_buscar", {"query": "obra"}, token))
        assert default["empresa"] == "realmak"


@pytest.mark.parametrize("partial", [[], ["una"]])
async def test_resultado_cortado_preserva_empresa_e_escopo(monkeypatch, partial):
    async with servidor(monkeypatch, partial=partial) as (c, mock, token, state):
        mock.post(f"{URL}/retrieve").mock(return_value=httpx.Response(200, json={
            "hits": [{"trecho": "x" * 200_000}],
            "empresa": "aforca", "acesso": {"nivel": "total"},
        }))
        result = await call_tool(c, "cerebro_buscar", {"query": "obra", "empresa": "una"}, token)
        text = result["content"][0]["text"]
        assert not result.get("isError") and "Resultado cortado" in text
        assert text.startswith('{\n  "empresa": "una"')
        if partial:
            assert '"nivel": "parcial"' in text[:200]
            assert '"rh"' in text[:200] and '"obras"' in text[:200]
        else:
            assert '"acesso"' not in text


async def test_mcp_bot_nao_consulta_empresa_alheia(monkeypatch):
    async with servidor(monkeypatch) as (c, mock, token, state):
        data = result_data(await call_tool(c, "cerebro_empresas", {}, BOT))
        assert [e["empresa"] for e in data["empresas"]] == ["aforca"]
        result = await call_tool(c, "cerebro_buscar", {"query": "obra", "empresa": "una"}, BOT)
        assert result["isError"] and "só lê a empresa AForça" in result["content"][0]["text"]
        assert not any(req.request.url.path == "/v1/retrieve" for req in mock.calls)
        data = result_data(await call_tool(c, "cerebro_buscar", {"query": "obra", "empresa": "aforca"}, BOT))
        assert data["empresa"] == "aforca"
        assert mock.calls.last.request.headers["authorization"] == f"Bearer {BOT}"


async def test_mcp_sem_acesso_lista_empresas_e_configuracao(monkeypatch):
    async with servidor(monkeypatch, allowed=["realmak", "aforca"]) as (c, mock, token, state):
        result = await call_tool(c, "cerebro_buscar", {"query": "obra", "empresa": "una"}, token)
        assert result["isError"]
        assert "Empresas liberadas: Realmak, AForça" in result["content"][0]["text"]
        monkeypatch.setenv("GALEED_SERVICE_KEYS", f"realmak={KEYS['realmak']}")
        result = await call_tool(c, "cerebro_buscar", {"query": "obra", "empresa": "una"}, token)
        assert "não está configurada" in result["content"][0]["text"]


@pytest.mark.parametrize(("records", "visible"), [([], False), (["una"], True)])
async def test_mcp_visibilidade_por_empresa(monkeypatch, records, visible):
    async with servidor(monkeypatch, allowed=["una"], registros=records) as (c, mock, token, state):
        resp = await rpc(c, "tools/list", token=token)
        names = {t["name"] for t in parse_body(resp)["result"]["tools"]}
        assert "cerebro_empresas" in names
        assert ("cerebro_consulta" in names) == visible
        schema = next(t for t in parse_body(resp)["result"]["tools"] if t["name"] == "cerebro_buscar")["inputSchema"]
        assert schema["properties"]["empresa"]["default"] == "realmak"
        assert schema["properties"]["empresa"]["enum"] == list(EMPRESAS)
        assert not any(req.request.url.path == "/v1/consulta/esquema" for req in mock.calls)


@pytest.mark.parametrize("tool,args", [("cerebro_buscar", {"query": "obra"}), ("cerebro_consulta", {"sql": "select 1"})])
async def test_revogacao_403_invalida_cache_e_lista_empresas(monkeypatch, tool, args):
    async with servidor(monkeypatch, registros=["realmak"]) as (c, mock, token, state):
        await call_tool(c, "cerebro_empresas", {}, token)
        state["allowed"].remove("realmak")
        path = "retrieve" if tool == "cerebro_buscar" else "consulta"
        mock.post(f"{URL}/{path}").mock(return_value=httpx.Response(403))
        result = await call_tool(c, tool, args, token)
        text = result["content"][0]["text"]
        assert result["isError"] and "Você não tem acesso à empresa Realmak" in text
        assert "Empresas liberadas: AForça, Nortfort, UNA, Sublime" in text
        after = result_data(await call_tool(c, "cerebro_empresas", {}, token))
        assert "realmak" not in [e["empresa"] for e in after["empresas"]]


async def test_chaves_nao_vazam_em_erro_ou_retorno(monkeypatch, caplog):
    async with servidor(monkeypatch) as (c, mock, token, state):
        mock.post(f"{URL}/retrieve").mock(return_value=httpx.Response(500, json={"error": f"recusou {KEYS['realmak']}"}))
        result = await call_tool(c, "cerebro_buscar", {"query": "obra"}, token)
        assert result["isError"]
        for key in KEYS.values():
            assert key not in json.dumps(result) + caplog.text


@pytest.mark.parametrize("response", [httpx.Response(200, text="não é JSON"), httpx.Response(302, json=acesso("realmak")), httpx.Response(204)])
async def test_acesso_aceita_so_200_json_valido_sem_cache(settings, response):
    calls = []
    def handler(req):
        calls.append(req)
        return response
    directory = Empresas(settings, httpx.MockTransport(handler))
    for _ in range(2):
        result = await directory.descobrir(pessoa())
        assert result.empresas == [] and result.indisponiveis == list(EMPRESAS)
        assert not directory._cache
    assert len(calls) == 10


@pytest.mark.parametrize(("name", "args", "method", "path"), [
    ("cerebro_fatos", {}, "GET", "facts"),
    ("cerebro_esquema", {}, "GET", "consulta/esquema"),
    ("cerebro_consulta", {"sql": "select 1"}, "POST", "consulta"),
    ("cerebro_provas", {"ids": ["id_de_outro_brain"]}, "POST", "consulta/provas"),
])
async def test_todas_ferramentas_rotulam_e_usam_so_brain_escolhido(monkeypatch, name, args, method, path):
    async with servidor(monkeypatch, partial=["una"]) as (c, mock, token, state):
        route = mock.request(method, f"{URL}/{path}").mock(return_value=httpx.Response(200, json={"items": []}))
        result = result_data(await call_tool(c, name, {**args, "empresa": "una"}, token))
        assert result["empresa"] == "una" and result["acesso"]["areas"] == ["rh", "obras"]
        assert route.calls.last.request.headers["authorization"] == f"Bearer {KEYS['una']}"
        assert route.calls.last.request.headers["x-galeed-act-as"] == EMAIL


async def test_erro_dataset_nomeia_empresa_sem_confundir_revogacao(monkeypatch):
    async with servidor(monkeypatch) as (c, mock, token, state):
        mock.post(f"{URL}/consulta").mock(return_value=httpx.Response(403))
        result = await call_tool(c, "cerebro_consulta", {"sql": "select 1", "empresa": "una"}, token)
        assert result["isError"]
        assert "não lê o dataset de registros da empresa UNA" in result["content"][0]["text"]


async def test_brain_realmak_minusculo_e_outro_brain_falha_fechada(settings):
    directory = Empresas(settings, httpx.MockTransport(lambda req: httpx.Response(200, json={**acesso("realmak"), "brain": "realmak"})))
    result = await directory.descobrir(pessoa())
    assert not result.empresas and result.indisponiveis == list(EMPRESAS)
    with pytest.raises(GaleedApiError, match="Resposta de acesso inválida"):
        await directory.brain_da_empresa("realmak")


async def test_bot_sem_empresa_configurada_nao_ve_ferramentas_cerebro(monkeypatch):
    async with servidor(monkeypatch) as (c, mock, token, state):
        monkeypatch.setenv("GALEED_SERVICE_KEYS", f"realmak={KEYS['realmak']}")
        resp = await rpc(c, "tools/list", token=BOT)
        assert resp.status_code == 200
        names = {t["name"] for t in parse_body(resp)["result"]["tools"]}
        assert not any(name.startswith("cerebro_") for name in names)


def test_config_nova_invalida_nao_retorna_chave_legada(monkeypatch):
    monkeypatch.setenv("GALEED_SERVICE_KEY", "gld_live_old")
    monkeypatch.setenv("GALEED_SERVICE_KEYS", "una=,desconhecida=gld_live_other")
    assert load_settings().service_keys == {}
