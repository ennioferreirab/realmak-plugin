"""Login de pessoa por OAuth (oauth.py) com o servidor completo em memória.

O Galeed, o Google e o SMTP são simulados. A pessoa com acesso é ana@realmak.com.br:
o Galeed só responde 200 para a chave de serviço com X-Galeed-Act-As desse e-mail.
"""

from __future__ import annotations

import base64
import contextlib
import json
import re
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx

from mcp_realmak.oauth import OAuthServer, pkce_s256
from mcp_realmak.server import build_app

from .helpers import call_tool, parse_body, rpc

GALEED = "https://galeed.test/v1"
LOGIN = "https://painel.galeed.test"
PUBLIC = "https://mcp.realmak.test"
SERVICO = "gld_live_servico"
ANA = "ana@realmak.com.br"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
VERIFIER = "v" * 64


def _galeed_facts(req: httpx.Request) -> httpx.Response:
    auth = req.headers.get("authorization", "")
    act_as = req.headers.get("x-galeed-act-as", "")
    if auth == "Bearer gld_live_boa" and not act_as:
        return httpx.Response(200, json={"facts": []})
    if auth == f"Bearer {SERVICO}" and act_as:
        return httpx.Response(200 if act_as == ANA else 403, json={"facts": []})
    return httpx.Response(401, json={"error": "token inválido"})


@pytest.fixture
def ambiente(monkeypatch):
    for k, v in {
        "GALEED_API_URL": GALEED,
        "MCP_REALMAK_PUBLIC_URL": PUBLIC,
        "MCP_REALMAK_OAUTH_SECRET": "s" * 40,
        "GALEED_SERVICE_KEY": SERVICO,
        "GALEED_LOGIN_URL": LOGIN,
        "GOOGLE_CLIENT_ID": "gid.apps.googleusercontent.com",
        "GOOGLE_CLIENT_SECRET": "gsecret",
        "GOOGLE_WORKSPACE_DOMAIN": "realmak.com.br",
        "SMTP_HOST": "smtp.test",
        "SMTP_FROM": "naoresponda@realmak.com.br",
    }.items():
        monkeypatch.setenv(k, v)
    enviados: list[tuple[str, str]] = []

    async def falso_envio(self, to, code):
        enviados.append((to, code))

    monkeypatch.setattr(OAuthServer, "_send_email_smtp", falso_envio)
    return enviados


@contextlib.asynccontextmanager
async def servidor():
    app = build_app()
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GALEED}/facts").mock(side_effect=_galeed_facts)
        mock.get(f"{GALEED}/consulta/esquema").mock(return_value=httpx.Response(200, json={}))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC) as c:
                c.mock = mock  # type: ignore[attr-defined]
                yield c


async def registrar(c, uris=(REDIRECT,)) -> httpx.Response:
    return await c.post("/mcp/oauth/register", json={"client_name": "Claude", "redirect_uris": list(uris)})


async def abrir_login(c) -> tuple[str, str]:
    client_id = (await registrar(c)).json()["client_id"]
    r = await c.get(
        "/mcp/oauth/authorize",
        params={
            "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
            "code_challenge": pkce_s256(VERIFIER), "code_challenge_method": "S256", "state": "xyz",
        },
    )
    assert r.status_code == 200, r.text
    return client_id, re.search(r'name="txn" value="([^"]+)"', r.text).group(1)


def codigo_do_redirect(r: httpx.Response) -> str:
    assert r.status_code == 302, r.text
    destino = urlsplit(r.headers["location"])
    assert f"{destino.scheme}://{destino.netloc}{destino.path}" == REDIRECT
    q = parse_qs(destino.query)
    assert q["state"] == ["xyz"]
    return q["code"][0]


async def trocar(c, client_id: str, code: str, verifier: str = VERIFIER) -> httpx.Response:
    return await c.post("/mcp/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "client_id": client_id,
        "redirect_uri": REDIRECT, "code_verifier": verifier,
    })


async def login_galeed(c, email=ANA) -> tuple[str, httpx.Response]:
    c.mock.post(f"{LOGIN}/auth/login").mock(
        return_value=httpx.Response(200, json={}, headers={"set-cookie": "galeed_sess=abc; HttpOnly"})
    )
    c.mock.post(f"{LOGIN}/auth/logout").mock(return_value=httpx.Response(200, json={"ok": True}))
    client_id, txn = await abrir_login(c)
    r = await c.post("/mcp/oauth/login/galeed", data={"txn": txn, "email": email, "password": "senha"})
    return client_id, r


# --- descoberta ---------------------------------------------------------------


async def test_com_oauth_o_401_aponta_os_metadados(ambiente):
    async with servidor() as c:
        r = await rpc(c, "tools/list", token=None)
        assert r.status_code == 401
        assert "/.well-known/oauth-protected-resource/mcp" in r.headers["www-authenticate"]
        prm = (await c.get("/.well-known/oauth-protected-resource/mcp")).json()
        assert prm["resource"] == f"{PUBLIC}/mcp" and prm["authorization_servers"] == [f"{PUBLIC}/"]
        asm = (await c.get("/.well-known/oauth-authorization-server")).json()
        assert asm["token_endpoint"] == f"{PUBLIC}/mcp/oauth/token"
        assert asm["code_challenge_methods_supported"] == ["S256"]


async def test_sem_chave_de_servico_o_oauth_fica_desligado(ambiente, monkeypatch):
    monkeypatch.delenv("GALEED_SERVICE_KEY")
    async with servidor() as c:
        assert (await c.get("/.well-known/oauth-authorization-server")).status_code == 404
        assert "resource_metadata" not in (await rpc(c, "tools/list", token=None)).headers["www-authenticate"]


async def test_bot_com_chave_continua_funcionando(ambiente):
    async with servidor() as c:
        assert (await rpc(c, "tools/list")).status_code == 200


async def test_registro_recusa_redirect_fora_da_lista(ambiente):
    async with servidor() as c:
        assert (await registrar(c, ["https://evil.example/cb"])).status_code == 400
        assert (await registrar(c, ["http://claude.ai/cb"])).status_code == 400
        assert (await registrar(c, ["http://127.0.0.1:33418/callback"])).status_code == 201


async def test_authorize_recusa_redirect_diferente_do_cadastro(ambiente):
    async with servidor() as c:
        client_id = (await registrar(c)).json()["client_id"]
        r = await c.get("/mcp/oauth/authorize", params={
            "response_type": "code", "client_id": client_id, "redirect_uri": "https://claude.ai/outro",
            "code_challenge": "x", "code_challenge_method": "S256",
        })
        assert r.status_code == 400


async def test_pagina_mostra_as_tres_formas(ambiente, monkeypatch):
    async with servidor() as c:
        client_id = (await registrar(c)).json()["client_id"]
        params = {
            "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
            "code_challenge": "x", "code_challenge_method": "S256",
        }
        pagina = (await c.get("/mcp/oauth/authorize", params=params)).text
        assert all(m in pagina for m in ('href="/mcp/oauth/login/google?', 'action="/mcp/oauth/login/galeed"', 'action="/mcp/oauth/login/email"'))
        assert (await c.get("/mcp/oauth/authorize", params={})).status_code == 400
    monkeypatch.delenv("SMTP_HOST")
    monkeypatch.delenv("GOOGLE_CLIENT_ID")
    async with servidor() as c:
        params["client_id"] = (await registrar(c)).json()["client_id"]
        pagina = (await c.get("/mcp/oauth/authorize", params=params)).text
        assert 'action="/mcp/oauth/login/galeed"' in pagina
        assert "/mcp/oauth/login/google" not in pagina and 'action="/mcp/oauth/login/email"' not in pagina


# --- login pela conta do Galeed -----------------------------------------------


async def test_login_galeed_ponta_a_ponta_e_consulta_em_nome_da_pessoa(ambiente):
    async with servidor() as c:
        client_id, r = await login_galeed(c)
        tokens = (await trocar(c, client_id, codigo_do_redirect(r))).json()
        assert tokens["access_token"].startswith("rmk_") and tokens["refresh_token"].startswith("rmkr_")
        assert c.mock.calls  # o login conferiu a senha no Galeed
        rota = c.mock.post(f"{GALEED}/retrieve").mock(return_value=httpx.Response(200, json={"hits": []}))
        await call_tool(c, "cerebro_buscar", {"query": "atestado"}, tokens["access_token"])
        req = rota.calls.last.request
        assert req.headers["authorization"] == f"Bearer {SERVICO}"
        assert req.headers["x-galeed-act-as"] == ANA


async def test_login_galeed_senha_errada(ambiente):
    async with servidor() as c:
        c.mock.post(f"{LOGIN}/auth/login").mock(return_value=httpx.Response(401, json={}))
        _, txn = await abrir_login(c)
        r = await c.post("/mcp/oauth/login/galeed", data={"txn": txn, "email": ANA, "password": "x"})
        assert r.status_code == 401 and "inválidos" in r.text


async def test_pessoa_sem_acesso_ao_cerebro_nao_recebe_codigo(ambiente):
    async with servidor() as c:
        _, r = await login_galeed(c, "fulano@realmak.com.br")
        assert r.status_code == 403 and "não tem acesso" in r.text


async def test_codigo_vale_uma_vez_e_exige_pkce(ambiente):
    async with servidor() as c:
        client_id, r = await login_galeed(c)
        code = codigo_do_redirect(r)
        assert (await trocar(c, client_id, code, verifier="w" * 64)).json()["error"] == "invalid_grant"
        assert (await trocar(c, client_id, code)).json()["error"] == "invalid_grant"  # já usado acima


async def test_refresh_renova_e_para_quando_o_acesso_e_retirado(ambiente, monkeypatch):
    monkeypatch.setenv("MCP_REALMAK_TOKEN_CACHE_SECONDS", "1")
    async with servidor() as c:
        client_id, r = await login_galeed(c)
        tokens = (await trocar(c, client_id, codigo_do_redirect(r))).json()
        novo = await c.post("/mcp/oauth/token", data={
            "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": client_id,
        })
        assert novo.status_code == 200 and novo.json()["access_token"].startswith("rmk_")
        c.mock.get(f"{GALEED}/facts").mock(return_value=httpx.Response(403, json={}))
        time.sleep(1.1)
        negado = await c.post("/mcp/oauth/token", data={
            "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": client_id,
        })
        assert negado.json()["error"] == "invalid_grant"
        assert (await rpc(c, "tools/list", token=tokens["access_token"])).status_code == 401


async def test_token_de_pessoa_adulterado_e_recusado(ambiente):
    async with servidor() as c:
        assert (await rpc(c, "tools/list", token="rmk_lixo")).status_code == 401


# --- código por e-mail --------------------------------------------------------


async def test_codigo_por_email(ambiente):
    async with servidor() as c:
        client_id, txn = await abrir_login(c)
        r = await c.post("/mcp/oauth/login/email", data={"txn": txn, "email": ANA})
        assert r.status_code == 200
        (para, code), = ambiente
        assert para == ANA
        etxn = re.search(r'name="etxn" value="([^"]+)"', r.text).group(1)
        errado = await c.post("/mcp/oauth/login/email/verify", data={"etxn": etxn, "code": "000000" if code != "000000" else "111111"})
        assert errado.status_code == 401
        ok = await c.post("/mcp/oauth/login/email/verify", data={"etxn": etxn, "code": code})
        assert (await trocar(c, client_id, codigo_do_redirect(ok))).status_code == 200


async def test_codigo_por_email_nao_revela_quem_tem_acesso(ambiente):
    async with servidor() as c:
        _, txn = await abrir_login(c)
        r = await c.post("/mcp/oauth/login/email", data={"txn": txn, "email": "fulano@realmak.com.br"})
        assert r.status_code == 200 and "Se fulano@realmak.com.br tiver acesso" in r.text
        assert ambiente == []  # nada enviado
        etxn = re.search(r'name="etxn" value="([^"]+)"', r.text).group(1)
        assert (await c.post("/mcp/oauth/login/email/verify", data={"etxn": etxn, "code": "123456"})).status_code == 401


async def test_codigo_por_email_limita_tentativas(ambiente):
    async with servidor() as c:
        _, txn = await abrir_login(c)
        r = await c.post("/mcp/oauth/login/email", data={"txn": txn, "email": ANA})
        etxn = re.search(r'name="etxn" value="([^"]+)"', r.text).group(1)
        code = ambiente[0][1]
        errado = "000000" if code != "000000" else "111111"
        for _ in range(5):
            await c.post("/mcp/oauth/login/email/verify", data={"etxn": etxn, "code": errado})
        assert (await c.post("/mcp/oauth/login/email/verify", data={"etxn": etxn, "code": code})).status_code == 429


# --- Google ---------------------------------------------------------------------


def id_token(**claims) -> str:
    base = {
        "iss": "https://accounts.google.com", "aud": "gid.apps.googleusercontent.com",
        "exp": time.time() + 300, "email": ANA, "email_verified": True, "hd": "realmak.com.br",
    }
    corpo = base64.urlsafe_b64encode(json.dumps({**base, **claims}).encode()).decode().rstrip("=")
    return f"e30.{corpo}.assinatura"


async def login_google(c, token: str) -> tuple[str, httpx.Response]:
    client_id, txn = await abrir_login(c)
    ida = await c.get("/mcp/oauth/login/google", params={"txn": txn})
    assert ida.status_code == 302
    google = urlsplit(ida.headers["location"])
    q = parse_qs(google.query)
    assert google.netloc == "accounts.google.com" and q["hd"] == ["realmak.com.br"]
    c.mock.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(200, json={"id_token": token})
    )
    volta = await c.get("/mcp/oauth/login/google/callback", params={"state": q["state"][0], "code": "gcode"})
    return client_id, volta


async def test_login_google_do_workspace(ambiente):
    async with servidor() as c:
        client_id, r = await login_google(c, id_token())
        assert (await trocar(c, client_id, codigo_do_redirect(r))).status_code == 200


async def test_login_google_de_outro_dominio_e_recusado(ambiente):
    async with servidor() as c:
        _, r = await login_google(c, id_token(email="ana@gmail.com", hd=None))
        assert r.status_code == 200 and "realmak.com.br" in r.text


async def test_login_google_sem_o_cookie_do_navegador_e_recusado(ambiente):
    async with servidor() as c:
        _, txn = await abrir_login(c)
        ida = await c.get("/mcp/oauth/login/google", params={"txn": txn})
        state = parse_qs(urlsplit(ida.headers["location"]).query)["state"][0]
        c.cookies.clear()
        r = await c.get("/mcp/oauth/login/google/callback", params={"state": state, "code": "gcode"})
        assert r.status_code == 400


async def test_header_de_bot_ainda_lista_registros(ambiente):
    async with servidor() as c:
        nomes = {t["name"] for t in parse_body(await rpc(c, "tools/list"))["result"]["tools"]}
        assert "cerebro_consulta" in nomes
