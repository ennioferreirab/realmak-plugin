"""Testes de envio de arquivos/pastas ao Cérebro (`cerebro_enviar`, `cerebro_envios` e rota de upload)."""

from __future__ import annotations

import base64
import json
from urllib.parse import unquote

import httpx
import pytest
import respx

from mcp_realmak.cerebro.client import GaleedApiError, GaleedClient
from mcp_realmak.cerebro.tools import explicar_erro
from mcp_realmak.config import load_settings
from mcp_realmak.oauth import OAuthServer
from mcp_realmak.server import INSTRUCOES as SERVER_INSTRUCOES
from mcp_realmak.server import build_app

from .helpers import call_tool, parse_body, rpc

GALEED = "https://galeed.test/v1"
PUBLIC = "https://mcp.realmak.test"
SECRET = "s" * 40
EMAIL = "analista@realmak.com.br"
KEY_REALMAK = "gld_live_srv_realmak"
KEY_AFORCA = "gld_live_srv_aforca"


def _setup_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> str:
    monkeypatch.setenv("GALEED_API_URL", GALEED)
    monkeypatch.setenv("GALEED_SERVICE_KEYS", f"realmak={KEY_REALMAK},aforca={KEY_AFORCA}")
    monkeypatch.setenv("MCP_REALMAK_PUBLIC_URL", PUBLIC)
    monkeypatch.setenv("MCP_REALMAK_OAUTH_SECRET", SECRET)
    monkeypatch.setenv("GALEED_LOGIN_URL", "https://login.realmak.test")
    monkeypatch.setenv("MCP_REALMAK_LINKS_DB", str(tmp_path / "links.db"))
    return OAuthServer(PUBLIC, SECRET, verify_person=lambda e: True).issue_tokens(EMAIL, "rc_test")["access_token"]


@respx.mock
async def test_client_enviar_e_envios():
    post = respx.post(f"{GALEED}/envios").mock(
        side_effect=[
            httpx.Response(201, json={"id": "env-1", "estado": "pendente", "sha256": "abc123"}),
            httpx.Response(200, json={"id": "env-1", "estado": "publicado", "sha256": "abc123"}),
        ]
    )
    get = respx.get(f"{GALEED}/envios").mock(
        return_value=httpx.Response(200, json={"envios": [{"id": "env-1", "estado": "publicado", "destino": "habilitacao/certidoes/vigentes/doc.pdf"}]})
    )
    client = GaleedClient(GALEED, KEY_REALMAK, act_as=EMAIL)

    ctx = {"origem": "mcp", "acao": "substituir", "comentario": "Cartão CNPJ atualizado", "quem": EMAIL, "substitui": {"sha256": "oldsha"}}
    status1, body1 = await client.enviar("Cartão CNPJ 2026.pdf", b"%PDF-1.4 novo", contexto=ctx)
    assert status1 == 201 and body1["id"] == "env-1"
    req1 = post.calls[0].request
    assert req1.headers["authorization"] == f"Bearer {KEY_REALMAK}"
    assert req1.headers["x-galeed-act-as"] == EMAIL
    assert unquote(req1.headers["x-galeed-nome"]) == "Cartão CNPJ 2026.pdf"
    assert json.loads(unquote(req1.headers["x-galeed-contexto"])) == ctx
    assert req1.content == b"%PDF-1.4 novo"

    status2, body2 = await client.enviar("Cartão CNPJ 2026.pdf", b"%PDF-1.4 novo", contexto=ctx)
    assert status2 == 200 and body2["estado"] == "publicado"

    res = await client.envios(limit=5, estado="publicado", sha256="abc123", envio_id="env-1")
    assert res["envios"][0]["id"] == "env-1"
    assert dict(get.calls[0].request.url.params) == {"limit": "5", "estado": "publicado", "sha256": "abc123", "id": "env-1"}


@respx.mock
async def test_client_enviar_erros_sem_vazar_chave():
    for status, expected in ((415, "tipo de arquivo"), (413, "acima do limite"), (403, "permissão")):
        respx.post(f"{GALEED}/envios").mock(return_value=httpx.Response(status, json={"error": f"recusado {KEY_REALMAK}"}))
        with pytest.raises(GaleedApiError) as exc:
            await GaleedClient(GALEED, KEY_REALMAK).enviar("a.exe", b"x")
        assert exc.value.status == status
        assert KEY_REALMAK not in str(exc.value)
        assert expected in explicar_erro(exc.value)


async def test_cerebro_enviar_direto_substituir_link_pasta_e_andamento(monkeypatch, tmp_path):
    token = _setup_env(monkeypatch, tmp_path)
    app = build_app(load_settings())
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GALEED}/acesso").mock(
            side_effect=lambda r: httpx.Response(
                200,
                json={
                    "brain": "Realmak" if r.headers["authorization"] == f"Bearer {KEY_REALMAK}" else "aforca",
                    "nivel": "total",
                    "areas": ["*"],
                    "registros": True,
                },
            )
        )
        post_envios = mock.post(f"{GALEED}/envios").mock(
            side_effect=lambda r: httpx.Response(
                201,
                json={
                    "id": f"env-{len(post_envios.calls)}",
                    "estado": "pendente",
                    "nome": unquote(r.headers["x-galeed-nome"]),
                    "tamanho": len(r.content),
                    "contexto": json.loads(unquote(r.headers["x-galeed-contexto"])),
                },
            )
        )
        get_envios = mock.get(f"{GALEED}/envios").mock(
            return_value=httpx.Response(
                200,
                json={"envios": [{"id": "env-1", "estado": "publicado", "destino": "habilitacao/certidoes/vigentes/novo.pdf", "motivo_revisao": None}]},
            )
        )

        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC) as c:
                # 1. Envio direto <= 1 MB com base64 e acao=substituir
                r_direto = await call_tool(
                    c,
                    "cerebro_enviar",
                    {
                        "empresa": "realmak",
                        "nome": "Realmak-Sublime_03496338000174_2026-11-25.pdf",
                        "conteudo_base64": base64.b64encode(b"%PDF-1.4 cartao").decode(),
                        "comentario": "Cartão CNPJ atualizado, emitido em 25/11/2026",
                        "acao": "substituir",
                        "substitui_sha256": "sha_antigo_123",
                    },
                    token,
                )
                assert not r_direto.get("isError"), r_direto
                d_direto = json.loads(r_direto["content"][0]["text"])
                assert d_direto["empresa"] == "realmak"
                assert d_direto["http_status"] == 201 and d_direto["repetido"] is False
                assert d_direto["contexto"]["origem"] == "mcp"
                assert d_direto["contexto"]["acao"] == "substituir"
                assert d_direto["contexto"]["quem"] == EMAIL
                assert d_direto["contexto"]["substitui"] == {"sha256": "sha_antigo_123"}

                # 2. Erro ao pedir substituir sem sha256 nem caminho
                r_err = await call_tool(
                    c,
                    "cerebro_enviar",
                    {"empresa": "realmak", "nome": "a.pdf", "conteudo_texto": "ok", "acao": "substituir"},
                    token,
                )
                assert r_err.get("isError") is True
                assert "substitui_sha256" in r_err["content"][0]["text"]

                # 3. Envio > 1 MB por link assinado (arquivo único sem conteúdo)
                r_link = await call_tool(
                    c,
                    "cerebro_enviar",
                    {"empresa": "aforca", "nome": "grande.pdf", "comentario": "Manual técnico grande"},
                    token,
                )
                assert not r_link.get("isError"), r_link
                d_link = json.loads(r_link["content"][0]["text"])
                assert d_link["empresa"] == "aforca"
                assert "/mcp/arquivos/cerebro-envio/" in d_link["url"]
                assert "curl -fsS --upload-file" in d_link["comando"]

                path_upload = d_link["url"].removeprefix(PUBLIC)
                payload_grande = b"0" * (1_100_000)
                up = await c.put(path_upload, content=payload_grande)
                assert up.status_code == 201
                up_body = up.json()
                assert up_body["empresa"] == "aforca" and up_body["tamanho"] == len(payload_grande)
                assert up_body["contexto"]["comentario"] == "Manual técnico grande"
                # Reuso do mesmo link deve devolver 409
                assert (await c.put(path_upload, content=b"x")).status_code == 409

                # 4. Pasta com 2 arquivos numa chamada (devolve 2 links + 1 comando único)
                r_pasta = await call_tool(
                    c,
                    "cerebro_enviar",
                    {
                        "empresa": "realmak",
                        "nomes": ["pasta/doc 1.pdf", "pasta/doc 2.pdf"],
                        "comentario": "Lote de teste da pasta",
                    },
                    token,
                )
                assert not r_pasta.get("isError"), r_pasta
                d_pasta = json.loads(r_pasta["content"][0]["text"])
                assert d_pasta["total"] == 2 and len(d_pasta["envios"]) == 2
                assert " && " in d_pasta["comando"]
                for item in d_pasta["envios"]:
                    resp_item = await c.put(item["url"].removeprefix(PUBLIC), content=b"conteudo-pasta")
                    assert resp_item.status_code == 201
                    assert resp_item.json()["nome"] == item["nome"]

                # 5. Consulta de andamento via cerebro_envios
                r_and = await call_tool(c, "cerebro_envios", {"empresa": "realmak", "limit": 10}, token)
                assert not r_and.get("isError"), r_and
                d_and = json.loads(r_and["content"][0]["text"])
                assert d_and["empresa"] == "realmak"
                assert d_and["envios"][0]["estado"] == "publicado"
                assert get_envios.called

                # 6. Conferir ferramentas listadas no MCP
                r_list = await rpc(c, "tools/list", token=token)
                nomes_tools = {t["name"] for t in parse_body(r_list)["result"]["tools"]}
                assert {"cerebro_enviar", "cerebro_envios"} <= nomes_tools


def test_instrucoes_servidor_refletem_cerebro_enviar():
    assert "Compras, ConLicitação e cérebro são só leitura" not in SERVER_INSTRUCOES
    assert "cerebro_enviar" in SERVER_INSTRUCOES
    assert "cerebro_envios" in SERVER_INSTRUCOES
    assert "nunca copie arquivos à mão" in SERVER_INSTRUCOES.casefold()
