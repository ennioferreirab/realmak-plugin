"""Cliente do site do ConLicitação com HTTP simulado: login, cookie, re-login e lock."""

from __future__ import annotations

import asyncio
import json
import os
import stat

import httpx
import pytest
import respx

from mcp_realmak.conlicitacao.errors import ConlicitacaoError
from mcp_realmak.conlicitacao.site import ConlicitacaoSiteClient

BASE = "https://consultaonline.conlicitacao.com.br"


def novo(tmp_path, **kw) -> ConlicitacaoSiteClient:
    return ConlicitacaoSiteClient(
        BASE, "usuario-teste", "senha-teste", str(tmp_path / "sessao.json"), **kw
    )


def rota_login(mock, empresa=4242, contador=None):
    def resp(request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.content)
        assert corpo == {"login": "usuario-teste", "senha": "senha-teste", "refresh": False}
        assert request.headers["frontend"] == "true"
        n = len(mock.routes["login"].calls) + 1
        return httpx.Response(
            200,
            json={"user": {"client_id": empresa}},
            headers={"Set-Cookie": f"_boletim_web_session=sessao{n}; Path=/; HttpOnly"},
        )

    return mock.post(f"{BASE}/users/login.json", name="login").mock(side_effect=resp)


@respx.mock
async def test_login_cookie_e_consulta(tmp_path):
    login = rota_login(respx)
    rota = respx.get(f"{BASE}/biddings/77.json").mock(
        return_value=httpx.Response(200, json={"id": 77, "objeto": "x", "edicts": []})
    )
    c = novo(tmp_path)
    data = await c.obter_licitacao(77)
    assert data["id"] == 77
    assert login.call_count == 1
    assert "_boletim_web_session=sessao1" in rota.calls[0].request.headers["cookie"]
    await c.obter_licitacao(77)
    assert login.call_count == 1  # reaproveitou a sessão


@respx.mock
async def test_sessao_gravada_com_modo_0600_e_reutilizada_por_outra_instancia(tmp_path):
    login = rota_login(respx)
    respx.get(f"{BASE}/biddings/77.json").mock(return_value=httpx.Response(200, json={"id": 77, "edicts": []}))
    await novo(tmp_path).obter_licitacao(77)
    arquivo = tmp_path / "sessao.json"
    assert stat.S_IMODE(os.stat(arquivo).st_mode) == 0o600
    outro = novo(tmp_path)  # simula reinício do servidor
    await outro.obter_licitacao(77)
    assert login.call_count == 1
    assert outro.empresa_id == 4242


@respx.mock
async def test_relogin_quando_a_sessao_vence(tmp_path):
    login = rota_login(respx)
    respostas = iter([httpx.Response(423), httpx.Response(200, json={"id": 5, "edicts": []})])
    rota = respx.get(f"{BASE}/biddings/5.json").mock(side_effect=lambda r: next(respostas))
    c = novo(tmp_path)
    data = await c.obter_licitacao(5)
    assert data["id"] == 5
    assert login.call_count == 2 and rota.call_count == 2
    assert "sessao2" in rota.calls[1].request.headers["cookie"]


@pytest.mark.parametrize("status", [401, 403])
@respx.mock
async def test_relogin_tambem_em_401_e_403(tmp_path, status):
    login = rota_login(respx)
    respostas = iter([httpx.Response(status), httpx.Response(200, json={"id": 5, "edicts": []})])
    respx.get(f"{BASE}/biddings/5.json").mock(side_effect=lambda r: next(respostas))
    await novo(tmp_path).obter_licitacao(5)
    assert login.call_count == 2


@respx.mock
async def test_nao_entra_em_loop_se_o_site_continua_recusando(tmp_path):
    login = rota_login(respx)
    respx.get(f"{BASE}/biddings/5.json").mock(return_value=httpx.Response(423))
    with pytest.raises(ConlicitacaoError):
        await novo(tmp_path).obter_licitacao(5)
    assert login.call_count == 2  # login inicial + uma renovação, nada além


@respx.mock
async def test_chamadas_concorrentes_fazem_um_unico_login(tmp_path):
    login = rota_login(respx)
    respx.get(url__regex=rf"{BASE}/biddings\.json.*").mock(
        return_value=httpx.Response(200, json={"biddings": [], "total_entries": 0})
    )
    c = novo(tmp_path)
    await asyncio.gather(*(c.buscar([("processo", "1")], 1) for _ in range(8)))
    assert login.call_count == 1


@respx.mock
async def test_renovacao_concorrente_nao_duplica_o_login(tmp_path):
    login = rota_login(respx)

    def consulta(request: httpx.Request) -> httpx.Response:
        if "sessao1" in request.headers.get("cookie", ""):
            return httpx.Response(423)  # a primeira sessão venceu
        return httpx.Response(200, json={"id": 9, "edicts": []})

    respx.get(f"{BASE}/biddings/9.json").mock(side_effect=consulta)
    c = novo(tmp_path)
    await c._ensure_session()  # login 1
    resultados = await asyncio.gather(*(c.obter_licitacao(9) for _ in range(6)))
    assert all(r["id"] == 9 for r in resultados)
    assert login.call_count == 2  # uma renovação só, apesar de seis consultas vencidas ao mesmo tempo


@respx.mock
async def test_login_recusado_da_erro_seguro_sem_credenciais(tmp_path):
    respx.post(f"{BASE}/users/login.json").mock(return_value=httpx.Response(401, json={"error": "x"}))
    with pytest.raises(ConlicitacaoError) as exc:
        await novo(tmp_path).obter_licitacao(5)
    msg = str(exc.value)
    assert "senha-teste" not in msg and "usuario-teste" not in msg


async def test_sem_credenciais_configuradas(tmp_path):
    c = ConlicitacaoSiteClient(BASE, "", "", str(tmp_path / "s.json"))
    with pytest.raises(ConlicitacaoError, match="não estão configuradas"):
        await c.obter_licitacao(5)


@respx.mock
async def test_redirecionamento_para_outra_origem_e_bloqueado(tmp_path):
    rota_login(respx)
    respx.get(f"{BASE}/biddings/5.json").mock(
        return_value=httpx.Response(302, headers={"Location": "https://evil.example/x"})
    )
    with pytest.raises(ConlicitacaoError, match="Redirecionamento bloqueado"):
        await novo(tmp_path).obter_licitacao(5)


async def test_http_so_em_localhost():
    with pytest.raises(ConlicitacaoError, match="HTTPS"):
        ConlicitacaoSiteClient("http://exemplo.test", "a", "b")


@respx.mock
async def test_id_de_outra_licitacao_na_resposta_e_recusado(tmp_path):
    rota_login(respx)
    respx.get(f"{BASE}/biddings/5.json").mock(return_value=httpx.Response(200, json={"id": 6, "edicts": []}))
    with pytest.raises(ConlicitacaoError, match="não é da licitação pedida"):
        await novo(tmp_path).obter_licitacao(5)


@respx.mock
async def test_resumo_vazio_204(tmp_path):
    rota_login(respx)
    respx.get(url__regex=rf"{BASE}/chatbots/bidding_chat/bidding_summary.*").mock(
        return_value=httpx.Response(204)
    )
    assert await novo(tmp_path).obter_resumo(5) is None


@respx.mock
async def test_busca_monta_company_id_filtros_e_pagina(tmp_path):
    rota_login(respx, empresa=999)
    rota = respx.get(url__regex=rf"{BASE}/biddings\.json.*").mock(
        return_value=httpx.Response(200, json={"biddings": []})
    )
    await novo(tmp_path).buscar([("orgao_uasg", "160089"), ("notice_number", "112/2026")], 3)
    p = rota.calls[0].request.url.params
    assert p["companyId"] == "999" and p["orgao_uasg"] == "160089"
    assert p["notice_number"] == "112/2026" and p["page"] == "3"
