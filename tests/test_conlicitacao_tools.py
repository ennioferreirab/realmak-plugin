"""Ferramentas do ConLicitação: resumo, paginação, sanitização e API por token."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mcp_realmak.conlicitacao.tools import build_conlicitacao_server

BASE = "https://consultaonline.conlicitacao.com.br"
LINK_ASSINADO = "/boletim_web/public/api/download?auth=eyJhbGciOiJIUzI1NiJ9.segredosegredo"


@pytest.fixture
def cfg(monkeypatch, tmp_path):
    monkeypatch.setenv("CONLICITACAO_TOKEN", "token-api-teste")
    monkeypatch.setenv("CONLICITACAO_LOGIN", "usuario-teste")
    monkeypatch.setenv("CONLICITACAO_SITE_PASSWORD", "senha-teste")
    monkeypatch.setenv("CONLICITACAO_SESSION_FILE", str(tmp_path / "sessao.json"))


def login_ok():
    respx.post(f"{BASE}/users/login.json").mock(
        return_value=httpx.Response(
            200, json={"user": {"client_id": 1}}, headers={"Set-Cookie": "_boletim_web_session=s; Path=/"}
        )
    )


async def chamar(nome: str, args: dict) -> str:
    async with Client(build_conlicitacao_server()) as c:
        r = await c.call_tool(nome, args)
        return r.content[0].text


async def test_lista_as_sete_ferramentas_somente_leitura():
    async with Client(build_conlicitacao_server()) as c:
        tools = await c.list_tools()
    assert sorted(t.name for t in tools) == [
        "conlicitacao_buscar_licitacao",
        "conlicitacao_detalhe_licitacao",
        "conlicitacao_ler_boletim",
        "conlicitacao_listar_boletins",
        "conlicitacao_listar_filtros",
        "conlicitacao_mensagens_pregao",
        "conlicitacao_pregoes_monitorados",
    ]
    assert all(t.annotations and t.annotations.read_only_hint for t in tools)


@respx.mock
async def test_buscar_resume_e_nao_devolve_links_assinados(cfg):
    login_ok()
    rota = respx.get(url__regex=rf"{BASE}/biddings\.json.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "total_entries": 1, "total_pages": 1,
                "biddings": [
                    {
                        "id": 123, "objeto": "x" * 2000, "notice_number": "112/2026",
                        "edicts": [{"filename": "edital.zip", "url": LINK_ASSINADO}],
                        "bidding_info": [{"texto": "longo"}],
                    }
                ],
            },
        )
    )
    out = await chamar(
        "conlicitacao_buscar_licitacao",
        {"uasg": "160089", "numero_edital": "112/2026", "uf": "df", "modalidade": "pregao_eletronico"},
    )
    p = rota.calls[0].request.url.params
    assert p["orgao_uasg"] == "160089" and p["notice_number"] == "112/2026"
    assert p["orgao_estado_id[]"] == "7" and p["modalities_ids[]"] == "10"
    data = json.loads(out)
    item = data["licitacoes"][0]
    assert item["link"] == "https://consulteonline.conlicitacao.com.br/biddings/123"
    assert item["arquivos_do_edital"] == ["edital.zip"]
    assert len(item["objeto"]) <= 501
    for proibido in ("segredosegredo", "download?auth", "senha-teste", "_boletim_web_session"):
        assert proibido not in out


async def test_buscar_exige_algum_filtro_e_valida_uf(cfg):
    async with Client(build_conlicitacao_server()) as c:
        with pytest.raises(ToolError, match="pelo menos um filtro"):
            await c.call_tool("conlicitacao_buscar_licitacao", {})
        with pytest.raises(ToolError, match="UF inválida"):
            await c.call_tool("conlicitacao_buscar_licitacao", {"uf": "XX"})


@respx.mock
async def test_detalhe_ordena_bidding_info_por_data_e_remove_urls(cfg):
    login_ok()
    respx.get(f"{BASE}/biddings/55.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 55, "objeto": "Serviços",
                "edital_site": "https://pncp.gov.br/app/editais/x",
                "edicts": [{"filename": "a.pdf", "url": LINK_ASSINADO}],
                "status_bidding_info": [{"status_name": "Aberta", "updated_at": "2026-10-01", "expiration_date": None}],
                "bidding_info": [
                    {"message_date": "2026-10-20", "texto": f"esclarecimento {LINK_ASSINADO}"},
                    {"message_date": "2026-10-05", "texto": "impugnação"},
                    {"sem_data": True},
                ],
                "itens": [{"n": 1}],
            },
        )
    )
    out = await chamar("conlicitacao_detalhe_licitacao", {"id_conlicitacao": 55})
    data = json.loads(out)
    datas = [e.get("message_date") for e in data["bidding_info_em_ordem_de_data"]]
    assert datas == ["2026-10-05", "2026-10-20", None]
    assert data["arquivos_do_edital"] == ["a.pdf"]
    assert data["situacoes"][0]["nome"] == "Aberta"
    assert data["edital_site"].startswith("https://pncp.gov.br")
    assert "segredosegredo" not in out and "edicts" not in data


@respx.mock
async def test_ler_boletim_pagina_e_limita(cfg):
    licitacoes = [
        {
            "id": i, "orgao": {"nome": f"Órgão {i}", "codigo": str(i), "uf": "DF"},
            "objeto": "o" * 1000, "edital": f"PE/{i}/2026", "situacao": "NOVA",
            "documento": [{"filename": f"{i}.zip", "url": LINK_ASSINADO}],
        }
        for i in range(1, 301)
    ]
    rota = respx.get(f"{BASE}/api/boletim/9").mock(
        return_value=httpx.Response(
            200, json={"boletim": {"id": 9, "quantidade_licitacoes": 300}, "licitacoes": licitacoes, "acompanhamentos": []}
        )
    )
    out = await chamar("conlicitacao_ler_boletim", {"boletim_id": 9, "pagina": 2, "por_pagina": 20})
    data = json.loads(out)
    assert rota.calls[0].request.headers["x-auth-token"] == "token-api-teste"
    assert data["total_nesta_secao"] == 300 and data["tem_mais"] is True
    assert [i["id"] for i in data["itens"]] == list(range(21, 41))
    assert len(data["itens"][0]["objeto"]) <= 301
    assert data["itens"][0]["arquivos_do_edital"] == ["21.zip"]
    assert len(out) < 30_000 and "segredosegredo" not in out


@respx.mock
async def test_ler_boletim_com_busca(cfg):
    respx.get(f"{BASE}/api/boletim/9").mock(
        return_value=httpx.Response(
            200,
            json={"boletim": {"id": 9}, "licitacoes": [
                {"id": 1, "objeto": "ar condicionado", "orgao": {"nome": "A"}},
                {"id": 2, "objeto": "pneus", "orgao": {"nome": "B"}},
            ]},
        )
    )
    data = json.loads(await chamar("conlicitacao_ler_boletim", {"boletim_id": 9, "busca": "AR CONDICIONADO"}))
    assert [i["id"] for i in data["itens"]] == [1]


@respx.mock
async def test_filtros_boletins_e_pregoes(cfg):
    respx.get(f"{BASE}/api/filtros").mock(return_value=httpx.Response(200, json={"filtros": [{"id": 1}]}))
    b = respx.get(f"{BASE}/api/filtro/1/boletins").mock(return_value=httpx.Response(200, json={"boletins": []}))
    respx.get(f"{BASE}/api/monitored_biddings").mock(
        return_value=httpx.Response(
            200,
            json={"electronics_trading": [{"bidding_id": 7, "trading_situation": "Aberta",
                                            "bidding": {"edital": "PE/1/2026", "public_body": {"nome": "Órgão"}}}],
                  "total_entries": 1, "total_pages": 1, "page": 1},
        )
    )
    m = respx.get(f"{BASE}/api/monitored_biddings/messages").mock(
        return_value=httpx.Response(
            200,
            json={"trading_messages": [{"message_holder": "Pregoeiro fala:", "message_time": "t", "message_highlight": "olá"}],
                  "pagination": {"page": "1", "total_pages": 1, "total_entries": 1}, "bidding_id": 7},
        )
    )
    assert "filtros" in await chamar("conlicitacao_listar_filtros", {})
    await chamar("conlicitacao_listar_boletins", {"filtro_id": 1, "por_pagina": 5})
    assert dict(b.calls[0].request.url.params) == {"page": "1", "per_page": "5", "order": "desc"}
    pregoes = json.loads(await chamar("conlicitacao_pregoes_monitorados", {}))
    assert pregoes["pregoes"][0]["bidding_id"] == 7 and pregoes["pregoes"][0]["orgao"] == "Órgão"
    msgs = json.loads(await chamar("conlicitacao_mensagens_pregao", {"bidding_id": 7}))
    assert msgs["mensagens"][0]["quem"] == "Pregoeiro fala:" and msgs["total_registros"] == 1
    assert m.calls[0].request.url.params["bidding_id"] == "7"


@respx.mock
async def test_api_401_explica_sem_vazar_token(cfg):
    respx.get(f"{BASE}/api/filtros").mock(return_value=httpx.Response(401))
    async with Client(build_conlicitacao_server()) as c:
        with pytest.raises(ToolError) as exc:
            await c.call_tool("conlicitacao_listar_filtros", {})
    assert "IP de saída" in str(exc.value) and "token-api-teste" not in str(exc.value)


@respx.mock
async def test_api_tenta_de_novo_em_503(cfg, monkeypatch):
    monkeypatch.setattr("mcp_realmak.conlicitacao.api.asyncio.sleep", lambda s: _noop())
    respostas = iter([httpx.Response(503), httpx.Response(200, json={"filtros": []})])
    rota = respx.get(f"{BASE}/api/filtros").mock(side_effect=lambda r: next(respostas))
    await chamar("conlicitacao_listar_filtros", {})
    assert rota.call_count == 2


async def _noop():
    return None


async def test_token_ausente_da_erro_claro(monkeypatch):
    async with Client(build_conlicitacao_server()) as c:
        with pytest.raises(ToolError, match="token da API"):
            await c.call_tool("conlicitacao_listar_filtros", {})
