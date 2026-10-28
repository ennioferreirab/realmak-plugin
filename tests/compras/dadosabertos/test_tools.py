"""Tests for the Dados Abertos tool functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_realmak.compras.dadosabertos import tools
from mcp_realmak.compras.dadosabertos.schemas import (
    ContratoDA,
    ContratoDAResultado,
    FornecedorDA,
    FornecedorDAResultado,
    ItemMaterial,
    ItemMaterialResultado,
    ItemServico,
    ItemServicoResultado,
    Licitacao,
    LicitacaoResultado,
    PdmMaterial,
    PrecoPraticado,
    PrecoResultado,
    Uasg,
    UasgResultado,
)

CLIENT_MODULE = "mcp_realmak.compras.dadosabertos.client"


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# buscar_licitacoes
# ---------------------------------------------------------------------------


class TestBuscarLicitacoes:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = LicitacaoResultado(
            total=1,
            licitacoes=[
                Licitacao(
                    uasg=154047,
                    nome_modalidade="PREGÃO",
                    objeto="Aquisição de computadores",
                    situacao_aviso="Publicado",
                    valor_estimado_total=50000.0,
                    valor_homologado_total=45000.0,
                    data_publicacao="2020-01-02",
                    numero_itens=10,
                ),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_licitacoes("2020-01-01", "2020-01-31", ctx)
        assert "Aquisição de computadores" in result
        assert "PREGÃO" in result
        assert "154047" in result
        assert "R$ 50.000,00" in result
        assert "R$ 45.000,00" in result
        assert "1 licitações" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        mock_data = LicitacaoResultado(total=0, licitacoes=[])
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_licitacoes("2020-01-01", "2020-01-31", ctx)
        assert "Nenhuma licitação encontrada" in result


# ---------------------------------------------------------------------------
# buscar_pregoes
# ---------------------------------------------------------------------------


class TestBuscarPregoes:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = LicitacaoResultado(
            total=1,
            licitacoes=[
                Licitacao(
                    uasg=200000,
                    tipo_pregao="eletronico",
                    objeto="Serviço de limpeza",
                    situacao_aviso="Homologado",
                    valor_estimado_total=50000.0,
                ),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_pregoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_pregoes("2020-01-01", "2020-06-30", ctx)
        assert "Serviço de limpeza" in result
        assert "eletronico" in result


# ---------------------------------------------------------------------------
# buscar_dispensas
# ---------------------------------------------------------------------------


class TestBuscarDispensas:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = LicitacaoResultado(
            total=1,
            licitacoes=[
                Licitacao(
                    uasg=300000,
                    nome_modalidade="DISPENSA",
                    objeto="Aquisição emergencial",
                    valor_estimado_total=8000.0,
                ),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_dispensas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_dispensas(2020, ctx)
        assert "Aquisição emergencial" in result
        assert "DISPENSA" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        mock_data = LicitacaoResultado(total=0, licitacoes=[])
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_dispensas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_dispensas(2020, ctx)
        assert "Nenhuma dispensa encontrada" in result


# ---------------------------------------------------------------------------
# buscar_contratos
# ---------------------------------------------------------------------------


class TestBuscarContratos:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = ContratoDAResultado(
            total=1,
            contratos=[
                ContratoDA(
                    nome_orgao="IFNMG",
                    nome_fornecedor="KM JUNIOR LTDA",
                    ni_fornecedor="13225851000184",
                    numero_contrato="12024/2024",
                    nome_modalidade_compra="Pregão",
                    nome_tipo="Contrato",
                    objeto="AQUISIÇÃO DE ESTUFA",
                    valor_global=118800.0,
                    data_vigencia_inicial="2024-01-08",
                    data_vigencia_final="2025-01-08",
                ),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_contratos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_contratos("2024-01-01", "2024-01-31", ctx)
        assert "AQUISIÇÃO DE ESTUFA" in result
        assert "IFNMG" in result
        assert "KM JUNIOR LTDA" in result
        assert "R$ 118.800,00" in result
        assert "1 contratos" in result


# ---------------------------------------------------------------------------
# consultar_fornecedor
# ---------------------------------------------------------------------------


class TestConsultarFornecedor:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = FornecedorDAResultado(
            total=1,
            fornecedores=[
                FornecedorDA(
                    cnpj="33000167000101",
                    nome_razao_social="PETROBRAS",
                    uf_sigla="RJ",
                    nome_municipio="Rio de Janeiro",
                    porte_empresa_nome="DEMAIS",
                    nome_cnae="EXTRAÇÃO DE PETRÓLEO",
                    ativo=True,
                    habilitado_licitar=True,
                ),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_fornecedor",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_fornecedor(ctx, cnpj="33000167000101")
        assert "PETROBRAS" in result
        assert "33000167000101" in result
        assert "RJ" in result
        assert "EXTRAÇÃO DE PETRÓLEO" in result

    @pytest.mark.asyncio
    async def test_missing_filter(self) -> None:
        ctx = _mock_ctx()
        result = await tools.consultar_fornecedor(ctx)
        assert "Informe pelo menos um filtro" in result


# ---------------------------------------------------------------------------
# buscar_material_catmat
# ---------------------------------------------------------------------------


class TestBuscarMaterialCatmat:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = ItemMaterialResultado(
            total=1,
            itens=[
                ItemMaterial(
                    codigo_item=123456,
                    descricao_item="Computador desktop Intel i7",
                    codigo_grupo=70,
                    codigo_classe=7010,
                    codigo_pdm=1234,
                    status_item=True,
                ),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_material",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_material_catmat(ctx, descricao="computador")
        assert "Computador desktop Intel i7" in result
        assert "123456" in result
        assert "70" in result

    @pytest.mark.asyncio
    async def test_missing_filter(self) -> None:
        ctx = _mock_ctx()
        result = await tools.buscar_material_catmat(ctx)
        assert "Informe pelo menos um filtro" in result


# ---------------------------------------------------------------------------
# buscar_servico_catser
# ---------------------------------------------------------------------------


class TestBuscarServicoCatser:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = ItemServicoResultado(
            total=1,
            itens=[
                ItemServico(
                    codigo_servico=5380,
                    nome_servico="SERVIÇO DE LIMPEZA",
                    codigo_grupo=74,
                    codigo_classe=7462,
                    status_servico=True,
                ),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_servico",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_servico_catser(ctx, codigo_grupo=74)
        assert "SERVIÇO DE LIMPEZA" in result
        assert "5380" in result

    @pytest.mark.asyncio
    async def test_missing_filter(self) -> None:
        ctx = _mock_ctx()
        result = await tools.buscar_servico_catser(ctx)
        assert "Informe pelo menos um filtro" in result


# ---------------------------------------------------------------------------
# buscar_uasg
# ---------------------------------------------------------------------------


class TestBuscarUasg:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = UasgResultado(
            total=1,
            uasgs=[
                Uasg(
                    codigo_uasg="154047",
                    nome_uasg="UNIVERSIDADE FEDERAL DE PELOTAS",
                    cnpj_cpf_orgao="92242080000182",
                    sigla_uf="RS",
                    nome_municipio="PELOTAS",
                    uso_sisg=True,
                ),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_uasg",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_uasg(ctx, sigla_uf="RS")
        assert "UNIVERSIDADE FEDERAL DE PELOTAS" in result
        assert "154047" in result
        assert "RS" in result

    @pytest.mark.asyncio
    async def test_missing_filter(self) -> None:
        ctx = _mock_ctx()
        result = await tools.buscar_uasg(ctx)
        assert "Informe pelo menos um filtro" in result


# ---------------------------------------------------------------------------
# pesquisar_preco_material / pesquisar_preco_servico
# ---------------------------------------------------------------------------


def _precos(*valores: float) -> PrecoResultado:
    return PrecoResultado(
        total=len(valores),
        precos=[
            PrecoPraticado(
                data_compra="2026-10-01",
                preco_unitario=v,
                quantidade=2.0,
                unidade="UN",
                nome_fornecedor="FORNECEDOR X",
                nome_orgao="ORGAO Y",
                uf="SP",
            )
            for v in valores
        ],
    )


class TestPesquisarPrecoMaterial:
    @pytest.mark.asyncio
    async def test_computes_statistics(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.pesquisar_preco_material",
            new_callable=AsyncMock,
            return_value=_precos(100.0, 200.0, 600.0),
        ):
            result = await tools.pesquisar_preco_material(_mock_ctx(), "362342")
        assert "R$ 100,00" in result  # mínimo
        assert "R$ 200,00" in result  # mediana
        assert "R$ 300,00" in result  # média
        assert "R$ 600,00" in result  # máximo
        assert "FORNECEDOR X" in result

    @pytest.mark.asyncio
    async def test_invalid_tipo_does_not_call_api(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.pesquisar_preco_material", new_callable=AsyncMock
        ) as mock_client:
            result = await tools.pesquisar_preco_material(_mock_ctx(), "1", tipo="xpto")
        assert "tipo inválido" in result
        mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_pdm_warns_about_mixed_specs(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.pesquisar_preco_material",
            new_callable=AsyncMock,
            return_value=_precos(10.0),
        ):
            result = await tools.pesquisar_preco_material(_mock_ctx(), "313", tipo="codigoPdm")
        assert "PDM agrupa itens" in result

    @pytest.mark.asyncio
    async def test_notes_partial_page(self) -> None:
        parcial = _precos(10.0, 20.0)
        parcial.total = 500
        with patch(
            f"{CLIENT_MODULE}.pesquisar_preco_material",
            new_callable=AsyncMock,
            return_value=parcial,
        ):
            result = await tools.pesquisar_preco_material(_mock_ctx(), "1")
        assert "só sobre os 2 registros desta página" in result

    @pytest.mark.asyncio
    async def test_caps_page_size(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.pesquisar_preco_material",
            new_callable=AsyncMock,
            return_value=_precos(10.0),
        ) as mock_client:
            await tools.pesquisar_preco_material(_mock_ctx(), "1", tamanho=5000)
        assert mock_client.call_args.kwargs["tamanho"] == 500

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.pesquisar_preco_material",
            new_callable=AsyncMock,
            return_value=PrecoResultado(),
        ):
            result = await tools.pesquisar_preco_material(_mock_ctx(), "1")
        assert "Nenhum preço encontrado" in result


class TestPesquisarPrecoServico:
    @pytest.mark.asyncio
    async def test_computes_statistics(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.pesquisar_preco_servico",
            new_callable=AsyncMock,
            return_value=_precos(1.0, 3.0),
        ):
            result = await tools.pesquisar_preco_servico(_mock_ctx(), 26115)
        assert "serviço 26115" in result
        assert "R$ 2,00" in result  # mediana e média

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.pesquisar_preco_servico",
            new_callable=AsyncMock,
            return_value=PrecoResultado(),
        ):
            result = await tools.pesquisar_preco_servico(_mock_ctx(), 1)
        assert "Nenhum preço encontrado" in result


# ---------------------------------------------------------------------------
# pesquisa de preço por texto (descricao)
# ---------------------------------------------------------------------------

_PDMS = [
    PdmMaterial(codigo_pdm=313, nome_pdm="CADEIRA ESCRITÓRIO", nome_classe="MOBILIÁRIO"),
    PdmMaterial(codigo_pdm=999, nome_pdm="CADEIRA ESCRITÓRIO GIRATÓRIA", nome_classe="MOBILIÁRIO"),
    PdmMaterial(codigo_pdm=2754, nome_pdm="APARELHO DETECTOR DE ARMA POR RAIO X"),
]


class TestPesquisarPrecoMaterialPorTexto:
    @pytest.mark.asyncio
    async def test_exact_match_runs_price_search_on_pdm(self) -> None:
        with (
            patch(f"{CLIENT_MODULE}.carregar_pdms", new_callable=AsyncMock, return_value=_PDMS),
            patch(
                f"{CLIENT_MODULE}.pesquisar_preco_material",
                new_callable=AsyncMock,
                return_value=_precos(100.0),
            ) as mock_preco,
        ):
            result = await tools.pesquisar_preco_material(
                _mock_ctx(), descricao="cadeira escritório"
            )
        assert mock_preco.call_args.kwargs["codigo"] == "313"
        assert mock_preco.call_args.kwargs["tipo"] == "codigoPdm"
        assert "PDM 313" in result
        assert "R$ 100,00" in result

    @pytest.mark.asyncio
    async def test_ambiguous_lists_candidates_without_price_search(self) -> None:
        with (
            patch(f"{CLIENT_MODULE}.carregar_pdms", new_callable=AsyncMock, return_value=_PDMS),
            patch(
                f"{CLIENT_MODULE}.pesquisar_preco_material", new_callable=AsyncMock
            ) as mock_preco,
        ):
            result = await tools.pesquisar_preco_material(_mock_ctx(), descricao="cadeira")
        mock_preco.assert_not_called()
        assert "Mais de um código" in result
        assert "313" in result and "999" in result
        assert "tipo='codigoPdm'" in result

    @pytest.mark.asyncio
    async def test_partial_match_lists_closest_without_price_search(self) -> None:
        with (
            patch(f"{CLIENT_MODULE}.carregar_pdms", new_callable=AsyncMock, return_value=_PDMS),
            patch(
                f"{CLIENT_MODULE}.pesquisar_preco_material", new_callable=AsyncMock
            ) as mock_preco,
        ):
            result = await tools.pesquisar_preco_material(_mock_ctx(), descricao="scanner raio x")
        mock_preco.assert_not_called()
        assert "Nenhum código contém todos os termos" in result
        assert "2754" in result

    @pytest.mark.asyncio
    async def test_no_match(self) -> None:
        with patch(f"{CLIENT_MODULE}.carregar_pdms", new_callable=AsyncMock, return_value=_PDMS):
            result = await tools.pesquisar_preco_material(_mock_ctx(), descricao="xyzzy")
        assert "Nenhum PDM do CATMAT corresponde" in result

    @pytest.mark.asyncio
    async def test_requires_codigo_or_descricao(self) -> None:
        result = await tools.pesquisar_preco_material(_mock_ctx())
        assert "Informe codigo" in result

    @pytest.mark.asyncio
    async def test_codigo_takes_priority_over_descricao(self) -> None:
        with (
            patch(f"{CLIENT_MODULE}.carregar_pdms", new_callable=AsyncMock) as mock_catalogo,
            patch(
                f"{CLIENT_MODULE}.pesquisar_preco_material",
                new_callable=AsyncMock,
                return_value=_precos(10.0),
            ),
        ):
            await tools.pesquisar_preco_material(_mock_ctx(), "362342", descricao="cadeira")
        mock_catalogo.assert_not_called()


_SERVICOS = [
    ItemServico(codigo_servico=26115, nome_servico="CHAMADAS LOCAIS FIXO-FIXO STFC-LOCAL-FF"),
    ItemServico(codigo_servico=26123, nome_servico="CHAMADAS LOCAIS FIXO-MOVEL STFC-LOCAL-FM"),
]


class TestPesquisarPrecoServicoPorTexto:
    @pytest.mark.asyncio
    async def test_unique_complete_match_runs_price_search(self) -> None:
        with (
            patch(
                f"{CLIENT_MODULE}.carregar_servicos",
                new_callable=AsyncMock,
                return_value=_SERVICOS,
            ),
            patch(
                f"{CLIENT_MODULE}.pesquisar_preco_servico",
                new_callable=AsyncMock,
                return_value=_precos(0.1),
            ) as mock_preco,
        ):
            result = await tools.pesquisar_preco_servico(
                _mock_ctx(), descricao="chamadas locais fixo-movel"
            )
        assert mock_preco.call_args.kwargs["codigo_item_catalogo"] == 26123
        assert "serviço 26123" in result

    @pytest.mark.asyncio
    async def test_ambiguous_lists_candidates(self) -> None:
        with (
            patch(
                f"{CLIENT_MODULE}.carregar_servicos",
                new_callable=AsyncMock,
                return_value=_SERVICOS,
            ),
            patch(
                f"{CLIENT_MODULE}.pesquisar_preco_servico", new_callable=AsyncMock
            ) as mock_preco,
        ):
            result = await tools.pesquisar_preco_servico(_mock_ctx(), descricao="chamadas locais")
        mock_preco.assert_not_called()
        assert "26115" in result and "26123" in result

    @pytest.mark.asyncio
    async def test_requires_codigo_or_descricao(self) -> None:
        result = await tools.pesquisar_preco_servico(_mock_ctx())
        assert "Informe codigo_item_catalogo" in result
