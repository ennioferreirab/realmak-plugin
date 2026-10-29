"""Verificador de token: chave do Galeed, cache de 5 minutos e falha fechada."""

from __future__ import annotations

import logging

import httpx
import pytest

from mcp_realmak import auth as auth_mod
from mcp_realmak.auth import GaleedTokenVerifier, GaleedUnavailableError, token_hash

URL = "https://galeed.test/v1"


def verificador(handler, ttl: int = 300) -> tuple[GaleedTokenVerifier, list[httpx.Request]]:
    chamadas: list[httpx.Request] = []

    def wrapper(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return handler(request)

    return GaleedTokenVerifier(URL, ttl_seconds=ttl, transport=httpx.MockTransport(wrapper)), chamadas


async def test_chave_valida_devolve_access_token_com_a_propria_chave():
    v, chamadas = verificador(lambda r: httpx.Response(200, json={"facts": []}))
    acesso = await v.verify_token("gld_live_abc")
    assert acesso is not None
    assert acesso.token == "gld_live_abc"
    assert "gld_live_abc" not in acesso.client_id  # o id público não carrega a chave
    req = chamadas[0]
    assert req.method == "GET" and req.url.path == "/v1/facts"
    assert req.url.params["limit"] == "1"
    assert req.headers["authorization"] == "Bearer gld_live_abc"


@pytest.mark.parametrize("status", [401, 403])
async def test_chave_recusada_devolve_none(status):
    v, _ = verificador(lambda r: httpx.Response(status, json={"error": "não"}))
    assert await v.verify_token("gld_live_ruim") is None


async def test_cache_vale_para_chave_valida_e_invalida():
    v, chamadas = verificador(
        lambda r: httpx.Response(200 if r.headers["authorization"].endswith("boa") else 401)
    )
    for _ in range(3):
        assert await v.verify_token("boa") is not None
        assert await v.verify_token("ruim") is None
    assert len(chamadas) == 2  # uma por chave, mesmo com seis verificações


async def test_cache_expira_depois_do_ttl(monkeypatch):
    agora = [1000.0]
    monkeypatch.setattr(auth_mod.time, "monotonic", lambda: agora[0])
    v, chamadas = verificador(lambda r: httpx.Response(200), ttl=300)
    await v.verify_token("k")
    agora[0] += 299
    await v.verify_token("k")
    assert len(chamadas) == 1
    agora[0] += 2  # passou de 300 s
    await v.verify_token("k")
    assert len(chamadas) == 2


async def test_cache_indexado_por_sha256_e_sem_a_chave():
    v, _ = verificador(lambda r: httpx.Response(200))
    await v.verify_token("gld_live_segredo")
    assert list(v._cache) == [token_hash("gld_live_segredo")]
    assert "segredo" not in repr(v._cache)


async def test_galeed_fora_do_ar_falha_fechada():
    def cai(request):
        raise httpx.ConnectError("sem rota")

    v, _ = verificador(cai)
    with pytest.raises(GaleedUnavailableError) as exc:
        await v.verify_token("gld_live_x")
    assert "cérebro não respondeu" in str(exc.value)


async def test_erro_5xx_nao_libera_e_nao_entra_no_cache():
    respostas = iter([500, 200])
    v, chamadas = verificador(lambda r: httpx.Response(next(respostas)))
    with pytest.raises(GaleedUnavailableError):
        await v.verify_token("k")
    assert await v.verify_token("k") is not None  # tentou de novo: falha não ficou em cache
    assert len(chamadas) == 2


async def test_chave_nunca_aparece_no_log(caplog):
    caplog.set_level(logging.DEBUG)

    def cai(request):
        raise httpx.ConnectError("falha com gld_live_segredo123")

    v, _ = verificador(cai)
    with pytest.raises(GaleedUnavailableError):
        await v.verify_token("gld_live_segredo123")
    assert "segredo123" not in caplog.text


async def test_token_vazio_ou_sem_url_e_recusado():
    v, chamadas = verificador(lambda r: httpx.Response(200))
    assert await v.verify_token("") is None
    assert chamadas == []
