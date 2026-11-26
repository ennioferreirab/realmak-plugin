import json
from unittest.mock import AsyncMock

import pytest

from mcp_realmak.compras.exceptions import HttpClientError
from mcp_realmak.licitacao import criacao, tools
from mcp_realmak.licitacao.client import OdooApiError


@pytest.mark.asyncio
async def test_id_conlicitacao_ja_importado():
    card = {"id": 7, "chave": "123", "fonte": "conlicitacao"}
    crm = AsyncMock()
    crm.chamar.return_value = {"licitacao": card}
    resposta = await criacao.criar(crm, None, 123, None, {}, None, None, False)
    assert resposta["ja_existia"] and resposta["licitacao"] == card
    crm.chamar.assert_awaited_once_with("importar", {"conlicitacao_id": 123, "somente_conferir": True})


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
        criado = salvo is None
        salvo = card
        return {"chave": chave, "licitacao": salvo, "criado": criado}

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


@pytest.mark.asyncio
@pytest.mark.parametrize("falha_pncp", [False, True])
async def test_portal_com_metadados_atualiza_card_existente(monkeypatch, falha_pncp):
    card = {"id": 7, "chave": "url-0123456789abcdef", "fonte": "portal"}
    crm = AsyncMock()
    crm.chamar.side_effect = [
        {"licitacao": card, "existe": True},
        {"licitacao": {**card, "objeto": "Manutenção"}, "criado": False, "atualizado": True},
    ]
    monkeypatch.setattr(tools, "cliente", lambda: crm)
    monkeypatch.setattr(criacao, "localizar_conlicitacao", AsyncMock(return_value=None))
    pncp = AsyncMock(return_value=None, side_effect=HttpClientError("503") if falha_pncp else None)
    monkeypatch.setattr(criacao, "localizar_pncp", pncp)
    resposta = json.loads(await tools.licitacao_criar(
        link="https://compras.example.org/edital/42", orgao="Órgão", numero_edital="42/2026",
        objeto="Manutenção", prazo="2026-12-01T10:00", valor_estimado=0,
    ))
    assert resposta["chave"] == card["chave"]
    assert resposta["ja_existia"] and resposta["atualizado"] and not resposta["criado"]
    assert any(("indisponível" if falha_pncp else "sem correspondência") in t for t in resposta["tentativas"])
    assert crm.chamar.await_args_list[0].args[1]["somente_conferir"] is True
    assert crm.chamar.await_args.args[1]["dados"] == {
        "orgao": "Órgão", "edital": "42/2026", "objeto": "Manutenção",
        "prazo": "2026-12-01T10:00", "valor_estimado": 0,
    }


@pytest.mark.asyncio
async def test_conlicitacao_importa_depois_de_conferir_sem_usar_outra_fonte(monkeypatch):
    monkeypatch.setattr(criacao, "localizar_conlicitacao", AsyncMock(return_value=123))
    consulta_pncp = AsyncMock()
    monkeypatch.setattr(criacao, "localizar_pncp", consulta_pncp)
    card = {"id": 7, "chave": "123", "fonte": "conlicitacao"}
    crm = AsyncMock()
    crm.chamar.side_effect = [
        {"licitacao": None}, {"licitacao": None},
        {"licitacao": card, "criado": True, "preparacao": {"estado": "pendente"}},
        {"licitacao": card},
    ]
    args = (crm, "https://compras.example.org/edital/42", None, None, {"processo": "A/2026"}, None, None)
    previa = await criacao.criar(*args, True)
    assert previa["licitacao"] is None and previa["chave"] == "123"
    crm.chamar.assert_awaited_once_with("importar", {"conlicitacao_id": 123, "somente_conferir": True})
    resposta = await criacao.criar(*args, False)
    assert resposta["criado"] and resposta["preparacao"] == {"estado": "pendente"}
    crm.chamar.assert_awaited_with("importar", {"conlicitacao_id": 123, "dados": {"processo": "A/2026"}})
    repeticao = await criacao.criar(*args, False)
    assert repeticao["ja_existia"] and repeticao["licitacao"] == card
    consulta_pncp.assert_not_awaited()


@pytest.mark.asyncio
async def test_criar_encaminha_modalidade_preparacao_e_campos_vazios(monkeypatch):
    controle = "46251021000180-1-000443/2026"
    chave = "pncp-46251021000180-1-000443-2026"
    card = {"id": 7010, "chave": chave, "fonte": "pncp", "etapa": "Acervo"}
    crm = AsyncMock()
    crm.chamar.side_effect = [
        {"chave": chave, "licitacao": None, "existe": False},
        {"total": 0, "licitacoes": []},
        {"total": 0, "licitacoes": []},
        {
            "chave": chave,
            "licitacao": card,
            "criado": True,
            "atualizado": False,
            "preparacao": {"estado": "baixando", "motivo": None, "documentos": {"total": 0, "extraindo": 0, "com_texto": 0, "classificados": 0}},
            "campos_vazios": ["visita"],
        },
    ]
    monkeypatch.setattr(tools, "cliente", lambda: crm)
    monkeypatch.setattr(criacao, "localizar_conlicitacao", AsyncMock(return_value=None))
    monkeypatch.setattr(criacao, "consultar_pncp", AsyncMock(return_value={
        "numeroControlePNCP": controle,
        "numeroCompra": "35",
        "anoCompra": 2026,
        "modalidadeNome": "Pregão - Eletrônico",
        "processo": "2026/00035",
        "objetoCompra": "Manutenção preventiva",
        "orgaoEntidade": {"razaoSocial": "TJGO"},
        "unidadeOrgao": {"codigoUnidade": "926415", "municipioNome": "Goiânia", "ufSigla": "GO"},
    }))
    resposta = json.loads(await tools.licitacao_criar(numero_controle_pncp=controle))
    assert resposta["criado"] is True
    assert resposta["preparacao"]["estado"] == "baixando"
    assert resposta["campos_vazios"] == ["visita"]
    enviado = crm.chamar.await_args.args[1]["dados"]
    assert enviado["modalidade"] == "Pregão - Eletrônico"
    assert enviado["orgao"] == "TJGO"
    assert enviado["edital"] == "35/2026"


@pytest.mark.asyncio
async def test_proximos_passos_e_link_card_por_fonte_e_numero_edital_preservado(monkeypatch):
    monkeypatch.setenv("MCP_REALMAK_PUBLIC_URL", "https://app.realmakservicos.com.br")
    controle = "02292266000180-1-000164/2026"
    card_em_analise = {
        "id": 6623, "chave": "pncp-02292266000180-1-000164-2026",
        "fonte": "pncp", "etapa": "Análise IA",
    }
    crm = AsyncMock()
    crm.chamar.return_value = {"chave": card_em_analise["chave"], "licitacao": card_em_analise, "existe": True}
    monkeypatch.setattr(criacao, "localizar_conlicitacao", AsyncMock(return_value=None))
    monkeypatch.setattr(criacao, "consultar_pncp", AsyncMock(return_value={
        "numeroControlePNCP": controle, "numeroCompra": "124137", "anoCompra": 2026,
        "processo": "202600001", "orgaoEntidade": {"razaoSocial": "TJGO"},
        "unidadeOrgao": {"codigoUnidade": "926415"},
    }))

    # Card já em Análise IA: informa a etapa atual sem instrução de mover.
    res_analise = await criacao.criar(
        crm, "https://pncp.gov.br/app/editais/02292266000180/2026/164",
        None, None, {"edital": "47/2026"}, None, None, True,
    )
    assert res_analise["link_card"] == "https://app.realmakservicos.com.br/odoo/licitacoes/6623"
    assert res_analise["proximos_passos"] == ["Card já está na etapa Análise IA."]
    assert all("mover" not in p.casefold() and "mova" not in p.casefold() for p in res_analise["proximos_passos"])
    assert crm.chamar.await_args.args[1]["dados"]["edital"] == "47/2026"

    # Card criado no Acervo (PNCP): download, extração e classificação automáticos na chegada, sem mover etapa.
    card_acervo = {
        "id": 6624, "chave": "pncp-02292266000180-1-000165-2026",
        "fonte": "pncp", "etapa": "Acervo",
    }
    res_acervo = criacao.resultado(card_acervo, True, ["ConLicitação", "PNCP"])
    assert res_acervo["link_card"] == "https://app.realmakservicos.com.br/odoo/licitacoes/6624"
    assert any("Card criado no Acervo." in p and "classificação (Jev)" in p for p in res_acervo["proximos_passos"])
    assert all("mover" not in p.casefold() and "mova" not in p.casefold() for p in res_acervo["proximos_passos"])
    assert all("licitacao_enviar_arquivo" not in p for p in res_acervo["proximos_passos"])

    # Card criado no Acervo (portal): orienta enviar edital/anexos via licitacao_enviar_arquivo(destino='documento').
    card_portal = {"id": 7001, "chave": "url-0123456789abcdef", "fonte": "portal", "etapa": "Acervo"}
    res_portal = criacao.resultado(card_portal, True, ["ConLicitação", "PNCP"])
    assert res_portal["link_card"] == "https://app.realmakservicos.com.br/odoo/licitacoes/7001"
    assert all("mover" not in p.casefold() and "mova" not in p.casefold() for p in res_portal["proximos_passos"])
    assert any("licitacao_enviar_arquivo(destino='documento')" in p for p in res_portal["proximos_passos"])
