"""Licitações do Odoo (`licitacao_*`) com o servidor completo em memória.

O Odoo e o Galeed são simulados. bia@realmak.com.br tem as licitações liberadas no Odoo e não tem o cérebro;
ana@realmak.com.br tem o cérebro e não tem as licitações.
"""

from __future__ import annotations

import contextlib
import json
from urllib.parse import urlsplit

import httpx
import pytest
import respx

from mcp_realmak.oauth import OAuthServer
from mcp_realmak.server import build_app

from .helpers import parse_body, rpc

GALEED = "https://galeed.test/v1"
ODOO = "http://odoo.test:8069"
API = f"{ODOO}/realmak_mcp/v1"
PUBLIC = "https://mcp.realmak.test"
SEGREDO_OAUTH = "s" * 40
SEGREDO_ODOO = "o" * 48
SERVICO = "gld_live_servico"
ANA = "ana@realmak.com.br"
BIA = "bia@realmak.com.br"


def _galeed_facts(req: httpx.Request) -> httpx.Response:
    auth, act_as = req.headers.get("authorization", ""), req.headers.get("x-galeed-act-as", "")
    if auth == "Bearer gld_live_boa" and not act_as:
        return httpx.Response(200, json={"facts": []})
    if auth == f"Bearer {SERVICO}" and act_as:
        return httpx.Response(200 if act_as == ANA else 403, json={"facts": []})
    return httpx.Response(401, json={"error": "token inválido"})


def _odoo_acesso(req: httpx.Request) -> httpx.Response:
    if req.headers.get("authorization") != f"Bearer {SEGREDO_ODOO}":
        return httpx.Response(401, json={"erro": "Segredo inválido."})
    if req.headers.get("x-realmak-act-as") != BIA:
        return httpx.Response(403, json={"erro": "Pessoa sem as licitações liberadas no Odoo."})
    return httpx.Response(200, json={"resultado": {"usuario": "Bia"}})


@pytest.fixture
def ambiente(monkeypatch, tmp_path):
    segredo = tmp_path / "secret"
    segredo.write_text(SEGREDO_ODOO + "\n", encoding="ascii")
    for k, v in {
        "GALEED_API_URL": GALEED,
        "MCP_REALMAK_PUBLIC_URL": PUBLIC,
        "MCP_REALMAK_OAUTH_SECRET": SEGREDO_OAUTH,
        "GALEED_SERVICE_KEY": SERVICO,
        "GALEED_LOGIN_URL": "https://painel.galeed.test",
        "ODOO_MCP_URL": ODOO,
        "ODOO_MCP_SECRET_FILE": str(segredo),
    }.items():
        monkeypatch.setenv(k, v)


def token_de(email: str) -> str:
    oauth = OAuthServer(PUBLIC, SEGREDO_OAUTH, verify_person=lambda e: True)
    return oauth.issue_tokens(email, "rc_teste")["access_token"]


@contextlib.asynccontextmanager
async def servidor():
    app = build_app()
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GALEED}/facts").mock(side_effect=_galeed_facts)
        mock.get(f"{GALEED}/consulta/esquema").mock(return_value=httpx.Response(200, json={}))
        mock.post(f"{API}/acesso").mock(side_effect=_odoo_acesso)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC) as c:
                c.mock = mock  # type: ignore[attr-defined]
                yield c


async def nomes(c, token: str) -> set[str]:
    r = await rpc(c, "tools/list", token=token)
    assert r.status_code == 200, r.text
    return {t["name"] for t in parse_body(r)["result"]["tools"]}


async def chamar(c, nome: str, args: dict, token: str) -> dict:
    r = await rpc(c, "tools/call", {"name": nome, "arguments": args}, token)
    assert r.status_code == 200, r.text
    return parse_body(r)["result"]


def corpo(resultado: dict) -> dict:
    return json.loads(resultado["content"][0]["text"])


async def test_cada_grupo_so_aparece_para_quem_tem_o_acesso(ambiente):
    async with servidor() as c:
        bia = await nomes(c, token_de(BIA))
        assert {"licitacao_pasta", "licitacao_status", "licitacao_enviar_arquivo"} <= bia
        assert not any(n.startswith("cerebro_") for n in bia)
        ana = await nomes(c, token_de(ANA))
        assert "cerebro_buscar" in ana and not any(n.startswith("licitacao_") for n in ana)
        bot = await nomes(c, "gld_live_boa")
        assert "cerebro_buscar" in bot and not any(n.startswith("licitacao_") for n in bot)
        recusado = await chamar(c, "licitacao_pasta", {"licitacao_id": 7}, "gld_live_boa")
        assert recusado["isError"] and "login de pessoa" in recusado["content"][0]["text"]
        # Sem cérebro nem licitações, a pessoa não entra.
        assert (await rpc(c, "tools/list", token=token_de("ze@realmak.com.br"))).status_code == 401


async def test_agente_le_a_pasta_registra_e_deixa_status_como_a_pessoa(ambiente):
    async with servidor() as c:
        pasta = c.mock.post(f"{API}/pasta").mock(return_value=httpx.Response(200, json={"resultado": {
            "versao": 1, "licitacao": {"id": 7}, "documentos": [{"id": 31, "le_como_texto": True}]}}))
        status = c.mock.post(f"{API}/status").mock(return_value=httpx.Response(200, json={"resultado": {"ok": True}}))
        proibido = c.mock.post(f"{API}/registrar").mock(
            return_value=httpx.Response(403, json={"erro": "Você não vê esta licitação."}))
        token = token_de(BIA)

        aberta = await chamar(c, "licitacao_pasta", {"licitacao_id": 7}, token)
        assert corpo(aberta)["documentos"][0]["id"] == 31
        await chamar(c, "licitacao_status", {"licitacao_id": 7, "estado": "trabalhando", "texto": "Lendo o edital"}, token)
        negado = await chamar(c, "licitacao_registrar", {"licitacao_id": 8, "tipo": "pendencia", "texto": "x"}, token)

        for rota in (pasta, status):
            pedido = rota.calls.last.request
            assert pedido.headers["authorization"] == f"Bearer {SEGREDO_ODOO}"
            assert pedido.headers["x-realmak-act-as"] == BIA
        assert json.loads(status.calls.last.request.content) == {
            "licitacao_id": 7, "estado": "trabalhando", "texto": "Lendo o edital"}
        assert proibido.called and negado["isError"]
        texto = negado["content"][0]["text"]
        assert "sem permissão (403)" in texto and SEGREDO_ODOO not in texto


async def test_links_baixam_e_enviam_arquivo_sem_passar_pela_conversa(ambiente):
    async with servidor() as c:
        token = token_de(BIA)
        download = c.mock.get(f"{API}/arquivo/7/31").mock(return_value=httpx.Response(
            200, content=b"%PDF-1.7 edital", headers={"Content-Type": "application/pdf",
                                                      "Content-Disposition": 'attachment; filename="edital.pdf"'}))
        upload = c.mock.post(f"{API}/arquivo/7").mock(return_value=httpx.Response(
            200, json={"resultado": {"documento_id": 90, "pasta": "Saída IA / Agentes MCP"}}))

        link = corpo(await chamar(c, "licitacao_link_arquivo", {"licitacao_id": 7, "documento_id": 31}, token))
        caminho = urlsplit(link["url"]).path
        r = await c.get(caminho)
        assert r.status_code == 200 and r.content == b"%PDF-1.7 edital"
        assert r.headers["content-disposition"] == 'attachment; filename="edital.pdf"'
        assert download.calls.last.request.headers["x-realmak-act-as"] == BIA
        assert (await c.get(caminho[:-3] + "xyz")).status_code == 404  # token adulterado

        envio = corpo(await chamar(c, "licitacao_enviar_arquivo",
                                   {"licitacao_id": 7, "nome": "planilha.xlsx", "descricao": "Preços"}, token))
        caminho = urlsplit(envio["url"]).path
        assert envio["limite_mb"] == 50
        r = await c.put(caminho, content=b"PK\x03\x04 planilha")
        assert r.status_code == 200 and r.json()["resultado"]["documento_id"] == 90
        pedido = upload.calls.last.request
        assert pedido.content == b"PK\x03\x04 planilha" and pedido.headers["x-realmak-act-as"] == BIA
        assert pedido.url.params["nome"] == "planilha.xlsx" and pedido.url.params["descricao"] == "Preços"
        assert (await c.put(caminho, content=b"de novo")).status_code == 409  # o link vale uma vez

        direto = await chamar(c, "licitacao_enviar_arquivo",
                              {"licitacao_id": 7, "nome": "notas.md", "conteudo_texto": "# Achados"}, token)
        assert not direto.get("isError") and upload.calls.last.request.content == b"# Achados"
