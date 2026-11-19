from unittest.mock import AsyncMock

import pytest

from mcp_realmak.licitacao import criacao
from mcp_realmak.licitacao.client import OdooApiError


@pytest.mark.asyncio
async def test_id_conlicitacao_ja_importado():
    card = {"id": 7, "chave": "123", "fonte": "conlicitacao"}
    crm = AsyncMock()
    crm.chamar.return_value = {"licitacao": card}
    resposta = await criacao.criar(crm, None, 123, None, {}, None, None, False)
    assert resposta["ja_existia"] and resposta["licitacao"] == card
    crm.chamar.assert_awaited_once_with("pasta", {"conlicitacao_id": 123})


@pytest.mark.asyncio
@pytest.mark.parametrize("fonte", ["pncp", "portal"])
async def test_cria_apos_conferir_e_retorna_mesmo_card(monkeypatch, fonte):
    controle = "12345678000100-1-000003/2026"
    chave = "pncp-12345678000100-1-000003-2026" if fonte == "pncp" else "url-0123456789abcdef"
    card = {"id": 7, "chave": chave, "fonte": fonte}
    crm = AsyncMock()
    salvo = None

    async def chamar(rota, params):
        nonlocal salvo
        if rota == "buscar":
            return {"total": 0, "licitacoes": []}
        assert rota == "criar"
        assert params["fonte"] == fonte
        if params.get("somente_conferir"):
            return {"chave": chave, "licitacao": salvo, "existe": bool(salvo)}
        assert salvo is None
        salvo = card
        return {"chave": chave, "licitacao": salvo, "criado": True}

    crm.chamar.side_effect = chamar
    consulta = AsyncMock(return_value={
        "numeroControlePNCP": controle, "numeroCompra": "42", "anoCompra": 2026,
        "processo": "123/2026", "unidadeOrgao": {"codigoUnidade": "123456"},
    })
    con = AsyncMock(return_value=None)
    monkeypatch.setattr(criacao, "consultar_pncp", consulta)
    monkeypatch.setattr(criacao, "localizar_conlicitacao", con)
    args = (
        crm, "https://compras.example.org/edital/42" if fonte == "portal" else None,
        None, controle if fonte == "pncp" else None, {}, None, None,
    )
    previa = await criacao.criar(*args, True)
    assert previa["chave"] == chave and salvo is None
    primeira = await criacao.criar(*args, False)
    segunda = await criacao.criar(*args, False)
    assert primeira["criado"] and segunda["ja_existia"]
    assert primeira["licitacao"] == segunda["licitacao"] == card


@pytest.mark.asyncio
async def test_recusa_criar_quando_crm_nao_pode_conferir():
    crm = AsyncMock()
    crm.chamar.side_effect = OdooApiError(403, "sem acesso")
    with pytest.raises(OdooApiError, match="sem acesso"):
        await criacao.criar(crm, "https://compras.example.org/edital/42", None, None, {}, None, None, False)
    assert crm.chamar.await_args.args[1]["somente_conferir"] is True


@pytest.mark.asyncio
async def test_resolve_duplicado_de_outra_fonte(monkeypatch):
    control = "12345678000100-1-000003/2026"
    card = {"id": 8, "chave": "url-0123456789abcdef", "fonte": "portal", "processo": "A/2026"}
    monkeypatch.setattr(criacao, "localizar_conlicitacao", AsyncMock(return_value=None))
    monkeypatch.setattr(criacao, "consultar_pncp", AsyncMock(return_value={
        "numeroControlePNCP": control, "numeroCompra": "42", "anoCompra": 2026, "processo": "A/2026",
    }))
    crm = AsyncMock()
    crm.chamar.side_effect = [
        {"licitacao": None}, {"total": 1, "licitacoes": [{"id": 8}]}, {"licitacao": card},
        {"total": 0, "licitacoes": []},
    ]
    resposta = await criacao.criar(crm, None, None, control, {}, None, None, False)
    assert resposta["ja_existia"] and resposta["licitacao"] == card
    assert crm.chamar.await_args_list[0].args[1]["somente_conferir"] is True
    assert [chamada.args[0] for chamada in crm.chamar.await_args_list].count("criar") == 1
