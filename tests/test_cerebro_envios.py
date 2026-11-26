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

    res = await client.envios(limite=5, sha256="abc123", envio_id="env-1")
    assert res["envios"][0]["id"] == "env-1"
    assert dict(get.calls[0].request.url.params) == {"limite": "5", "sha256": "abc123", "id": "env-1"}


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
                r_and = await call_tool(c, "cerebro_envios", {"empresa": "realmak", "limite": 10}, token)
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
    assert "incluir_historico=false" in SERVER_INSTRUCOES
    assert "historico_omitido.aviso" in SERVER_INSTRUCOES
    assert "há versão posterior" in SERVER_INSTRUCOES
    assert "substitui_sha256` e `substitui_caminho` do MESMO documento antigo" in SERVER_INSTRUCOES
    assert "comprovante de inscrição e de situação cadastral" in SERVER_INSTRUCOES
    assert "cerebro_comentar" in SERVER_INSTRUCOES
    assert "nota_revisao" in SERVER_INSTRUCOES


async def test_cerebro_buscar_incluir_historico_e_estado_documento(monkeypatch, tmp_path):
    token = _setup_env(monkeypatch, tmp_path)
    app = build_app(load_settings())
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GALEED}/acesso").mock(
            return_value=httpx.Response(200, json={"brain": "Realmak", "nivel": "total", "areas": ["*"], "registros": True})
        )

        def retrieve_handler(req: httpx.Request) -> httpx.Response:
            body = json.loads(req.content)
            vigente = {
                "slug": "cnpj-novo",
                "original": {"sha256": "sha_novo", "file_path": r"E:\acervo-2.0\realmak\empresa\cadastro\CNPJ_2026.pdf"},
                "estado_documento": {"estado": "vigente", "desde": "2026-11-25T21:35:00Z"},
            }
            antigo = {
                "slug": "cnpj-antigo",
                "original": {"sha256": "sha_antigo", "file_path": r"E:\acervo-2.0\realmak\empresa\cadastro\anteriores\CNPJ_2025.pdf"},
                "estado_documento": {
                    "estado": "substituido",
                    "rotulo": "versão anterior: há versão posterior deste documento",
                    "substituido_por": "sha_novo",
                    "desde": "2026-11-25T21:35:00Z",
                },
            }
            if body.get("incluir_historico") is True:
                return httpx.Response(200, json={"hits": [vigente, antigo]})
            return httpx.Response(
                200,
                json={
                    "hits": [vigente],
                    "historico_omitido": {
                        "total": 1,
                        "substituidos": 1,
                        "vencidos": 0,
                        "aviso": "1 versão anterior não mostrado; use incluir_historico=true para ver.",
                    },
                },
            )

        ret = mock.post(f"{GALEED}/retrieve").mock(side_effect=retrieve_handler)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC) as c:
                r_padrao = await call_tool(c, "cerebro_buscar", {"empresa": "realmak", "query": "cartão CNPJ"}, token)
                assert not r_padrao.get("isError"), r_padrao
                d_padrao = json.loads(r_padrao["content"][0]["text"])
                assert json.loads(ret.calls[0].request.content)["incluir_historico"] is False
                assert len(d_padrao["hits"]) == 1
                assert d_padrao["hits"][0]["estado_documento"]["estado"] == "vigente"
                assert d_padrao["historico_omitido"]["total"] == 1
                assert "versão anterior" in d_padrao["historico_omitido"]["aviso"]

                r_hist = await call_tool(
                    c, "cerebro_buscar", {"empresa": "realmak", "query": "cartão CNPJ", "incluir_historico": True}, token
                )
                assert not r_hist.get("isError"), r_hist
                d_hist = json.loads(r_hist["content"][0]["text"])
                assert json.loads(ret.calls[1].request.content)["incluir_historico"] is True
                assert len(d_hist["hits"]) == 2
                assert "historico_omitido" not in d_hist
                assert d_hist["hits"][1]["estado_documento"]["estado"] == "substituido"
                assert d_hist["hits"][1]["estado_documento"]["substituido_por"] == "sha_novo"


async def test_cerebro_fatos_e_provas_incluir_historico(monkeypatch, tmp_path):
    token = _setup_env(monkeypatch, tmp_path)
    app = build_app(load_settings())
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GALEED}/acesso").mock(
            return_value=httpx.Response(200, json={"brain": "Realmak", "nivel": "total", "areas": ["*"], "registros": True})
        )

        def facts_handler(req: httpx.Request) -> httpx.Response:
            vigente = {"id": "f1", "texto": "fato vigente", "estado_documento": {"estado": "vigente"}}
            antigo = {"id": "f2", "texto": "fato antigo", "estado_documento": {"estado": "substituido", "rotulo": "versão anterior: há versão posterior deste documento"}}
            if req.url.params.get("incluir_historico") == "true":
                return httpx.Response(200, json={"facts": [vigente, antigo]})
            return httpx.Response(
                200,
                json={"facts": [vigente], "historico_omitido": {"total": 1, "substituidos": 1, "vencidos": 0, "aviso": "1 fato de versão anterior não mostrado; use incluir_historico=true para ver."}},
            )

        def provas_handler(req: httpx.Request) -> httpx.Response:
            body = json.loads(req.content)
            vigente = {"id": "p1", "estado_documento": {"estado": "vigente"}}
            antigo = {"id": "p2", "estado_documento": {"estado": "substituido", "rotulo": "versão anterior: há versão posterior deste documento"}}
            if body.get("incluir_historico") is True:
                return httpx.Response(200, json={"provas": [vigente, antigo]})
            return httpx.Response(
                200,
                json={"provas": [vigente], "historico_omitido": {"total": 1, "substituidos": 1, "vencidos": 0, "aviso": "1 prova de versão anterior não mostrada; use incluir_historico=true para ver."}},
            )

        fac = mock.get(f"{GALEED}/facts").mock(side_effect=facts_handler)
        pro = mock.post(f"{GALEED}/consulta/provas").mock(side_effect=provas_handler)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC) as c:
                rf_pad = json.loads((await call_tool(c, "cerebro_fatos", {"empresa": "realmak", "dim": "facts"}, token))["content"][0]["text"])
                assert "incluir_historico" not in fac.calls[0].request.url.params
                assert len(rf_pad["facts"]) == 1 and rf_pad["historico_omitido"]["total"] == 1

                rf_hist = json.loads((await call_tool(c, "cerebro_fatos", {"empresa": "realmak", "dim": "facts", "incluir_historico": True}, token))["content"][0]["text"])
                assert fac.calls[1].request.url.params.get("incluir_historico") == "true"
                assert len(rf_hist["facts"]) == 2 and rf_hist["facts"][1]["estado_documento"]["estado"] == "substituido"

                rp_pad = json.loads((await call_tool(c, "cerebro_provas", {"empresa": "realmak", "ids": ["p1", "p2"]}, token))["content"][0]["text"])
                assert json.loads(pro.calls[0].request.content)["incluir_historico"] is False
                assert len(rp_pad["provas"]) == 1 and rp_pad["historico_omitido"]["total"] == 1

                rp_hist = json.loads((await call_tool(c, "cerebro_provas", {"empresa": "realmak", "ids": ["p1", "p2"], "incluir_historico": True}, token))["content"][0]["text"])
                assert json.loads(pro.calls[1].request.content)["incluir_historico"] is True
                assert len(rp_hist["provas"]) == 2 and rp_hist["provas"][1]["estado_documento"]["estado"] == "substituido"


async def test_cerebro_comentar_e_comentarios(monkeypatch, tmp_path):
    token = _setup_env(monkeypatch, tmp_path)
    app = build_app(load_settings())
    sha_doc = "7f930ceba066461cdcecbdb2bb55f96fd8bb0c388e7769ce028098ba41f62053"
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GALEED}/acesso").mock(
            return_value=httpx.Response(200, json={"brain": "Realmak", "nivel": "total", "areas": ["*"], "registros": True})
        )
        post_com = mock.post(f"{GALEED}/documentos/comentarios").mock(
            side_effect=[
                httpx.Response(
                    201,
                    json={
                        "id": "com-1",
                        "texto": "Razão social antiga EIRELI.",
                        "quem": EMAIL,
                        "origem": "mcp",
                        "criado_em": "2026-11-26T16:20:00Z",
                        "sha256": sha_doc,
                        "caminho": "realmak\\habilitacao\\certidoes\\vigentes\\doc.pdf",
                    },
                ),
                httpx.Response(409, json={"error": "nome ambíguo"}),
            ]
        )
        get_com = mock.get(f"{GALEED}/documentos/comentarios").mock(
            return_value=httpx.Response(
                200,
                json={
                    "sha256": sha_doc,
                    "caminho": "realmak\\habilitacao\\certidoes\\vigentes\\doc.pdf",
                    "comentarios": [{"id": "com-1", "texto": "Razão social antiga EIRELI.", "quem": EMAIL, "origem": "mcp", "criado_em": "2026-11-26T16:20:00Z"}],
                    "nota_revisao": "Conferido por Ennio",
                },
            )
        )
        mock.post(f"{GALEED}/retrieve").mock(
            return_value=httpx.Response(
                200,
                json={
                    "hits": [
                        {
                            "slug": "doc",
                            "original": {"sha256": sha_doc, "file_path": r"E:\acervo-2.0\realmak\doc.pdf"},
                            "comentarios": {"total": 1, "ultimos": [{"texto": "Razão social antiga EIRELI.", "quem": EMAIL, "origem": "mcp", "criado_em": "2026-11-26T16:20:00Z"}]},
                            "nota_revisao": "Conferido por Ennio",
                        }
                    ]
                },
            )
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC) as c:
                r1 = await call_tool(c, "cerebro_comentar", {"empresa": "realmak", "sha256": sha_doc, "texto": "Razão social antiga EIRELI."}, token)
                assert not r1.get("isError"), r1
                d1 = json.loads(r1["content"][0]["text"])
                assert d1["id"] == "com-1" and d1["sha256"] == sha_doc
                assert post_com.calls[0].request.headers["x-galeed-act-as"] == EMAIL

                r_amb = await call_tool(c, "cerebro_comentar", {"empresa": "realmak", "caminho": "duplicado.pdf", "texto": "oi"}, token)
                assert r_amb.get("isError") is True and "409" in r_amb["content"][0]["text"]

                r_sem_doc = await call_tool(c, "cerebro_comentar", {"empresa": "realmak", "texto": "sem doc"}, token)
                assert r_sem_doc.get("isError") is True

                r_list = await call_tool(c, "cerebro_comentarios", {"empresa": "realmak", "sha256": sha_doc}, token)
                assert not r_list.get("isError"), r_list
                d_list = json.loads(r_list["content"][0]["text"])
                assert d_list["nota_revisao"] == "Conferido por Ennio" and len(d_list["comentarios"]) == 1
                assert get_com.called

                r_busc = json.loads((await call_tool(c, "cerebro_buscar", {"empresa": "realmak", "query": "doc"}, token))["content"][0]["text"])
                assert r_busc["hits"][0]["comentarios"]["total"] == 1
                assert r_busc["hits"][0]["nota_revisao"] == "Conferido por Ennio"



