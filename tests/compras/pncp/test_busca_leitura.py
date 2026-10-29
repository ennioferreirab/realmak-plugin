"""Tests for PNCP full-text search, procurement reading tools and the fixes to
the open-proposals search (UF from unidadeOrgao, page size, local filter footer)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from mcp_realmak.compras._shared import http_client
from mcp_realmak.compras.pncp import client, tools
from mcp_realmak.compras.pncp.constants import (
    CONTRATACOES_PROPOSTA_URL,
    ORGAOS_URL,
    SEARCH_URL,
)
from mcp_realmak.compras.pncp.schemas import (
    ArquivoContratacao,
    Contratacao,
    ContratacaoResultado,
    DocumentoPesquisa,
    EventoHistorico,
    ItemContratacao,
    PesquisaResultado,
    ResultadoItem,
)

CLIENT_MODULE = "mcp_realmak.compras.pncp.client"
CNPJ = "00394494000136"
COMPRA = f"{ORGAOS_URL}/{CNPJ}/compras/2026/1203"


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries back off with asyncio.sleep; skip the wait in tests."""
    monkeypatch.setattr(http_client.asyncio, "sleep", AsyncMock())


# ---------------------------------------------------------------------------
# http_client: transport errors and lenient JSON
# ---------------------------------------------------------------------------


class TestHttpClientRobustez:
    @respx.mock
    async def test_retries_on_connection_reset(self) -> None:
        route = respx.get("https://example.test/x").mock(
            side_effect=[
                httpx.RemoteProtocolError("Server disconnected"),
                httpx.ReadError("Connection reset by peer"),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        assert await http_client.http_get("https://example.test/x") == {"ok": True}
        assert route.call_count == 3

    @respx.mock
    async def test_short_capped_backoff(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sleep = AsyncMock()
        monkeypatch.setattr(http_client.asyncio, "sleep", sleep)
        respx.get("https://example.test/x").mock(
            side_effect=[httpx.ReadError("reset")] * 6 + [httpx.Response(200, json={})]
        )
        await http_client.http_get(
            "https://example.test/x", max_retries=8, backoff_base=0.5, max_wait=3.0
        )
        assert [c.args[0] for c in sleep.await_args_list] == [0.5, 1.0, 2.0, 3.0, 3.0, 3.0]

    @respx.mock
    async def test_parses_json_with_raw_control_characters(self) -> None:
        respx.get("https://example.test/x").mock(
            return_value=httpx.Response(
                200,
                content=b'{"description": "linha 1\nlinha 2"}',
                headers={"Content-Type": "application/json"},
            )
        )
        data = await http_client.http_get("https://example.test/x")
        assert data["description"] == "linha 1\nlinha 2"


# ---------------------------------------------------------------------------
# buscar_contratacoes_abertas: fixes
# ---------------------------------------------------------------------------


ITEM_PROPOSTA = {
    "orgaoEntidade": {
        "cnpj": "01567525000176",
        "razaoSocial": "SERVICO DE LIMPEZA URBANA",
        "esferaId": "D",
        "poderId": "E",
    },
    "unidadeOrgao": {
        "ufSigla": "DF",
        "municipioNome": "Brasília",
        "codigoIbge": "5300108",
        "codigoUnidade": "926254",
        "nomeUnidade": "EDF - SERVICO DE LIMPEZA URBANA DO DF",
    },
    "anoCompra": 2026,
    "sequencialCompra": 22,
    "numeroControlePNCP": "01567525000176-1-000022/2026",
    "objetoCompra": "Manutenção de grupo gerador",
    "dataAberturaProposta": "2026-11-03T08:00:00",
    "dataEncerramentoProposta": "2026-11-19T09:00:00",
    "linkSistemaOrigem": "https://cnetmobile.estaleiro.serpro.gov.br/x",
    "srp": False,
}


class TestContratacoesAbertasCorrecoes:
    @respx.mock
    async def test_uf_municipio_from_unidade_and_new_fields(self) -> None:
        respx.get(CONTRATACOES_PROPOSTA_URL).mock(
            return_value=httpx.Response(200, json={"totalRegistros": 1, "data": [ITEM_PROPOSTA]})
        )
        r = await client.buscar_contratacoes_abertas(data_final="20261130", uf="DF")
        c = r.contratacoes[0]
        assert (c.uf, c.municipio) == ("DF", "Brasília")
        assert c.unidade_nome == "EDF - SERVICO DE LIMPEZA URBANA DO DF"
        assert c.esfera == "Distrital"
        assert c.data_encerramento == "2026-11-19T09:00:00"
        assert c.link_pncp == "https://pncp.gov.br/app/editais/01567525000176/2026/22"
        assert c.link_origem.startswith("https://cnetmobile")

    @respx.mock
    async def test_new_filters_and_page_size(self) -> None:
        route = respx.get(CONTRATACOES_PROPOSTA_URL).mock(
            return_value=httpx.Response(200, json={"totalRegistros": 0, "data": []})
        )
        await client.buscar_contratacoes_abertas(
            data_final="20261130",
            codigo_municipio_ibge="5300108",
            codigo_unidade="926254",
            tamanho=30,
        )
        params = route.calls.last.request.url.params
        assert params["codigoMunicipioIbge"] == "5300108"
        assert params["codigoUnidadeAdministrativa"] == "926254"
        assert params["tamanhoPagina"] == "30"

    @respx.mock
    async def test_text_filter_uses_max_page_and_keeps_api_total(self) -> None:
        outro = {**ITEM_PROPOSTA, "objetoCompra": "Limpeza urbana"}
        route = respx.get(CONTRATACOES_PROPOSTA_URL).mock(
            return_value=httpx.Response(
                200, json={"totalRegistros": 483, "data": [ITEM_PROPOSTA, outro]}
            )
        )
        r = await client.buscar_contratacoes_abertas(data_final="20261130", texto="gerador")
        assert route.calls.last.request.url.params["tamanhoPagina"] == "50"
        assert r.total == 1
        assert r.total_api == 483

    async def test_tool_shows_deadline_and_next_page_when_filtering(self) -> None:
        resultado = ContratacaoResultado(
            total=1,
            total_api=483,
            contratacoes=[
                Contratacao(
                    objeto="Manutenção de grupo gerador",
                    numero_controle_pncp="01567525000176-1-000022/2026",
                    data_abertura="2026-11-03T08:00:00",
                    data_encerramento="2026-11-19T09:00:00",
                    uf="DF",
                    municipio="Brasília",
                )
            ],
        )
        with patch(
            f"{CLIENT_MODULE}.buscar_contratacoes_abertas",
            new_callable=AsyncMock,
            return_value=resultado,
        ):
            out = await tools.buscar_contratacoes_abertas("20261130", _mock_ctx(), texto="gerador")
        assert "até 2026-11-19T09:00:00" in out
        assert "Brasília/DF" in out
        assert "01567525000176-1-000022/2026" in out
        assert "1 nesta página de 483" in out
        assert "pagina=2" in out
        assert "pncp_pesquisar" in out


# ---------------------------------------------------------------------------
# pesquisar (busca textual do portal)
# ---------------------------------------------------------------------------


HIT_EDITAL = {
    "document_type": "edital",
    "title": "Edital nº 123627/2026",
    "description": "Aquisição de Grupo Gerador de Energia",
    "item_url": "/compras/00394494000136/2026/1203",
    "numero_controle_pncp": "00394494000136-1-001203/2026",
    "orgao_cnpj": "00394494000136",
    "orgao_nome": "MINISTERIO DA JUSTICA",
    "unidade_nome": "SENAPPEN",
    "ano": "2026",
    "numero_sequencial": "1203",
    "municipio_nome": "Brasília",
    "uf": "DF",
    "modalidade_licitacao_nome": "Pregão - Eletrônico",
    "situacao_nome": "Divulgada no PNCP",
    "data_inicio_vigencia": "2026-10-23T08:00",
    "data_fim_vigencia": "2026-11-06T09:00",
    "data_inicio_recebimento_propostas": "",
    "data_fim_recebimento_propostas": "",
    "valor_global": None,
    "tem_resultado": False,
}


class TestPesquisarClient:
    @respx.mock
    async def test_builds_portal_params(self) -> None:
        route = respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json={"total": 1, "items": [HIT_EDITAL]})
        )
        r = await client.pesquisar(
            "grupo gerador",
            ufs="df, go",
            modalidades="6,8",
            data_publicacao_inicio="01/10/2026",
            tamanho=200,
        )
        params = route.calls.last.request.url.params
        assert params["q"] == "grupo gerador"
        assert params["tipos_documento"] == "edital"
        assert params["status"] == "recebendo_proposta"
        assert params["ufs"] == "DF|GO"
        assert params["modalidades"] == "6|8"
        assert params["data_publicacao_inicio"] == "2026-10-01"
        assert params["tam_pagina"] == "50"
        d = r.documentos[0]
        assert (d.ano, d.numero_sequencial) == (2026, 1203)
        assert d.data_fim == "2026-11-06T09:00"
        assert d.link_pncp == "https://pncp.gov.br/app/editais/00394494000136/2026/1203"

    @respx.mock
    async def test_survives_many_resets(self) -> None:
        route = respx.get(SEARCH_URL).mock(
            side_effect=[httpx.ReadError("Connection reset by peer")] * 7
            + [httpx.Response(200, json={"total": 1, "items": [HIT_EDITAL]})]
        )
        r = await client.pesquisar("grupo gerador")
        assert r.total == 1
        assert route.call_count == 8

    @respx.mock
    async def test_contract_defaults_to_vigente(self) -> None:
        route = respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json={"total": 0, "items": []})
        )
        await client.pesquisar("manutenção gerador", tipo="contrato")
        assert route.calls.last.request.url.params["status"] == "vigente"

    async def test_rejects_status_of_other_type(self) -> None:
        with pytest.raises(ValueError, match="status inválido para contrato"):
            await client.pesquisar("gerador", tipo="contrato", status="recebendo_proposta")

    async def test_rejects_unknown_type(self) -> None:
        with pytest.raises(ValueError, match="tipo inválido"):
            await client.pesquisar("gerador", tipo="pca")


class TestPesquisarTool:
    async def test_formats_contracts(self) -> None:
        resultado = PesquisaResultado(
            total=41,
            documentos=[
                DocumentoPesquisa(
                    tipo="contrato",
                    titulo="Empenho nº 2026NE000143",
                    descricao="MANUTENÇÃO GRUPO GERADOR",
                    numero_controle_pncp="32901688000177-2-000033/2026",
                    orgao_nome="ÓRGÃO X",
                    uf="DF",
                    municipio="Brasília",
                    data_inicio="2026-05-13",
                    data_fim="2026-12-31",
                    valor_global=10833.8,
                    fornecedor_nome="GENFORCE ENGENHARIA",
                    fornecedor_ni="07210733000108",
                    link_pncp="https://pncp.gov.br/app/contratos/32901688000177/2026/33",
                )
            ],
        )
        with patch(f"{CLIENT_MODULE}.pesquisar", new_callable=AsyncMock, return_value=resultado):
            out = await tools.pesquisar("manutenção gerador", _mock_ctx(), tipo="contrato", ufs="DF")
        assert "41 contratos (Vigentes)" in out
        assert "GENFORCE ENGENHARIA (07210733000108)" in out
        assert "**Vigência:** 2026-05-13 até 2026-12-31" in out
        assert "pagina=2" in out

    async def test_validation_error_is_message(self) -> None:
        out = await tools.pesquisar("gerador", _mock_ctx(), tipo="edital", status="vigente")
        assert out.startswith("Erro de validação")


# ---------------------------------------------------------------------------
# Leitura de uma contratação
# ---------------------------------------------------------------------------


class TestResolverCompra:
    def test_from_control_number(self) -> None:
        assert client.resolver_compra(numero_controle_pncp="00394494000136-1-001203/2026") == (
            CNPJ,
            2026,
            1203,
        )

    def test_from_keys_strips_cnpj(self) -> None:
        assert client.resolver_compra(cnpj="00.394.494/0001-36", ano=2026, sequencial=1203) == (
            CNPJ,
            2026,
            1203,
        )

    def test_contract_number_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="numero_controle_pncp inválido"):
            client.resolver_compra(numero_controle_pncp="32901688000177-2-000033/2026")

    def test_missing_keys(self) -> None:
        with pytest.raises(ValueError, match="Informe numero_controle_pncp"):
            client.resolver_compra(cnpj=CNPJ)


class TestLeituraClient:
    @respx.mock
    async def test_itens(self) -> None:
        respx.get(f"{COMPRA}/itens").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "numeroItem": 1,
                        "descricao": "Grupo Diesel Gerador potência: 180",
                        "materialOuServicoNome": "Material",
                        "quantidade": 1.0,
                        "unidadeMedida": "Unidade",
                        "valorUnitarioEstimado": 154066.67,
                        "valorTotal": 154066.67,
                        "situacaoCompraItemNome": "Em andamento",
                        "temResultado": False,
                    }
                ],
            )
        )
        itens = await client.listar_itens_contratacao(CNPJ, 2026, 1203)
        assert itens[0].valor_unitario_estimado == 154066.67
        assert itens[0].situacao == "Em andamento"

    @respx.mock
    async def test_resultados(self) -> None:
        respx.get(f"{COMPRA}/itens/1/resultados").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "niFornecedor": "29846409000105",
                        "nomeRazaoSocialFornecedor": "INSTITUTO SOCIAL SE LIGA",
                        "porteFornecedorNome": "Demais",
                        "quantidadeHomologada": 30.0,
                        "valorUnitarioHomologado": 37999.05,
                        "valorTotalHomologado": 1139971.45,
                        "situacaoCompraItemResultadoNome": "Informado",
                        "dataResultado": "2025-10-08",
                    }
                ],
            )
        )
        r = await client.listar_resultados_item(CNPJ, 2026, 1203, 1)
        assert r[0].fornecedor_nome == "INSTITUTO SOCIAL SE LIGA"
        assert r[0].valor_unitario_homologado == 37999.05

    @respx.mock
    async def test_arquivos_rewrites_internal_host_and_skips_inactive(self) -> None:
        respx.get(f"{COMPRA}/arquivos").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "sequencialDocumento": 1,
                        "tipoDocumentoNome": "Edital",
                        "titulo": "PE535.26.zip",
                        "statusAtivo": True,
                        "url": "https://pncp.gov.br:41217/pncp-api/v1/orgaos/00394494000136/compras/2026/1203/arquivos/1",
                    },
                    {"sequencialDocumento": 2, "titulo": "antigo", "statusAtivo": False},
                ],
            )
        )
        arquivos = await client.listar_arquivos_contratacao(CNPJ, 2026, 1203)
        assert len(arquivos) == 1
        assert arquivos[0].url == f"{COMPRA}/arquivos/1"

    @respx.mock
    async def test_historico_newest_first(self) -> None:
        respx.get(f"{COMPRA}/historico").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"logManutencaoDataInclusao": "2026-10-23T04:00:00", "tipoLogManutencaoNome": "Inclusão"},
                    {"logManutencaoDataInclusao": "2026-10-23T04:01:00", "tipoLogManutencaoNome": "Retificação"},
                ],
            )
        )
        eventos = await client.listar_historico_contratacao(CNPJ, 2026, 1203)
        assert [e.tipo for e in eventos] == ["Retificação", "Inclusão"]


class TestLeituraTools:
    async def test_itens_table_and_link(self) -> None:
        itens = [
            ItemContratacao(
                numero_item=1,
                descricao="Grupo Diesel | Gerador",
                quantidade=1.0,
                unidade_medida="Unidade",
                valor_unitario_estimado=154066.67,
                valor_total=154066.67,
                situacao="Em andamento",
                tem_resultado=False,
            )
        ]
        with patch(
            f"{CLIENT_MODULE}.listar_itens_contratacao", new_callable=AsyncMock, return_value=itens
        ):
            out = await tools.itens_contratacao(
                _mock_ctx(), numero_controle_pncp="00394494000136-1-001203/2026"
            )
        assert "| 1 | Grupo Diesel / Gerador |" in out
        assert "https://pncp.gov.br/app/editais/00394494000136/2026/1203" in out

    async def test_resultados_empty(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_resultados_item", new_callable=AsyncMock, return_value=[]
        ):
            out = await tools.resultados_item(
                1, _mock_ctx(), cnpj=CNPJ, ano=2026, sequencial=1203
            )
        assert "ainda não tem resultado" in out

    async def test_resultados_formats_winner(self) -> None:
        r = [
            ResultadoItem(
                fornecedor_nome="INSTITUTO SOCIAL SE LIGA",
                fornecedor_ni="29846409000105",
                valor_unitario_homologado=37999.05,
            )
        ]
        with patch(f"{CLIENT_MODULE}.listar_resultados_item", new_callable=AsyncMock, return_value=r):
            out = await tools.resultados_item(1, _mock_ctx(), cnpj=CNPJ, ano=2026, sequencial=1203)
        assert "INSTITUTO SOCIAL SE LIGA (29846409000105)" in out

    async def test_arquivos_and_historico(self) -> None:
        arquivos = [ArquivoContratacao(tipo="Edital", titulo="PE535.26.zip", url=f"{COMPRA}/arquivos/1")]
        eventos = [
            EventoHistorico(
                data="2026-10-23T04:01:00",
                tipo="Retificação",
                categoria="Item de Contratação",
                item_numero=1,
                justificativa="mudança de situação",
            )
        ]
        with (
            patch(
                f"{CLIENT_MODULE}.listar_arquivos_contratacao",
                new_callable=AsyncMock,
                return_value=arquivos,
            ),
            patch(
                f"{CLIENT_MODULE}.listar_historico_contratacao",
                new_callable=AsyncMock,
                return_value=eventos,
            ),
        ):
            arq = await tools.arquivos_contratacao(_mock_ctx(), cnpj=CNPJ, ano=2026, sequencial=1203)
            hist = await tools.historico_contratacao(_mock_ctx(), cnpj=CNPJ, ano=2026, sequencial=1203)
        assert f"[baixar]({COMPRA}/arquivos/1)" in arq
        assert "2026-10-23 04:01 — **Retificação** de Item de Contratação 1: mudança de situação" in hist

    async def test_invalid_keys_message(self) -> None:
        out = await tools.historico_contratacao(_mock_ctx(), numero_controle_pncp="abc")
        assert out.startswith("Erro de validação")

    async def test_long_descriptions_are_cut(self) -> None:
        resultado = PesquisaResultado(
            total=1, documentos=[DocumentoPesquisa(tipo="edital", descricao="manutenção " * 100)]
        )
        with patch(f"{CLIENT_MODULE}.pesquisar", new_callable=AsyncMock, return_value=resultado):
            out = await tools.pesquisar("manutenção", _mock_ctx())
        titulo = next(linha for linha in out.splitlines() if linha.startswith("### 1."))
        assert len(titulo) < 320 and titulo.endswith("…")

    def test_docstrings_have_shared_args(self) -> None:
        assert "numero_controle_pncp:" in (tools.itens_contratacao.__doc__ or "")
        assert "{args}" not in (tools.arquivos_contratacao.__doc__ or "")
