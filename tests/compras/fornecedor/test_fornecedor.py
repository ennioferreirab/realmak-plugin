"""Testes da busca de contratos vigentes por CNPJ (PNCP + Compras.gov.br)."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from mcp_realmak.compras.dadosabertos import client as dados_abertos
from mcp_realmak.compras.dadosabertos.constants import (
    CONTRATOS_FIM_VIGENCIA_URL,
    FORNECEDOR_URL,
    ORGAO_URL,
)
from mcp_realmak.compras.fornecedor import client, tools
from mcp_realmak.compras.contratosgovbr.constants import CONTRATO_POR_UG_URL
from mcp_realmak.compras.pncp.constants import SEARCH_URL

CNPJ = "03496338000174"  # Realmak
FIM = (date.today() + timedelta(days=400)).isoformat()


@pytest.fixture(autouse=True)
def _estado_limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    client._VARREDURAS.clear()
    client._UG_CACHE.clear()
    dados_abertos.listar_orgaos.cache.clear()  # type: ignore[attr-defined]


def _orgaos() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "totalPaginas": 1,
            "resultado": [
                {"codigoOrgao": 52111, "nomeOrgao": "COMANDO DA AERONAUTICA", "esfera": "F", "nomeTipoAdministracao": "ADMINISTRACAO DIRETA"},
                {"codigoOrgao": 26270, "nomeOrgao": "FUNDACAO UNIVERSIDADE DO AMAZONAS", "esfera": "F", "nomeTipoAdministracao": "FUNDACAO"},
                {"codigoOrgao": 99999, "nomeOrgao": "PREFEITURA X", "esfera": "M", "nomeTipoAdministracao": "ADMINISTRACAO DIRETA MUNICIPAL"},
            ],
        },
    )


def _contrato_compras(**extra: object) -> dict[str, object]:
    return {
        "codigoOrgao": "52111",
        "nomeOrgao": "COMANDO DA AERONAUTICA",
        "numeroContrato": "00116/2024",
        "objeto": "MANUTENÇÃO DE CLIMATIZAÇÃO",
        "dataVigenciaInicial": "2024-09-03T00:00:00",
        "dataVigenciaFinal": f"{FIM}T00:00:00",
        "valorGlobal": 803963.54,
        "numeroControlePncpContrato": "00394429000100-2-000503/2024",
        "niFornecedor": CNPJ,
        "contratoExcluido": False,
        **extra,
    }


def _doc_pncp(controle: str, titulo: str, valor: float) -> dict[str, object]:
    return {
        "document_type": "contrato",
        "title": titulo,
        "description": "OBJETO",
        "numero_controle_pncp": controle,
        "orgao_nome": "COMANDO DA AERONAUTICA",
        "orgao_cnpj": "00394429000100",
        "item_url": "/contratos/00394429000100/2024/503",
        "data_fim_vigencia": FIM,
        "valor_global": valor,
        "fornecedor_ni": CNPJ,
    }


class TestCnpj:
    def test_valido(self) -> None:
        assert client.cnpj_valido(CNPJ)

    @pytest.mark.parametrize("cnpj", ["03496338000175", "00000000000000", "123", ""])
    def test_invalido(self, cnpj: str) -> None:
        assert not client.cnpj_valido(cnpj)

    def test_apenas_digitos(self) -> None:
        assert client.apenas_digitos("03.496.338/0001-74") == CNPJ


class TestUnir:
    def test_mesmo_controle_vira_um_contrato_com_duas_fontes(self) -> None:
        compras = [client._contrato_compras(_contrato_compras())]
        pncp = [
            client.ContratoVigente(
                fontes={"PNCP"},
                controle_pncp="00394429000100-2-000503/2024",
                valor_pncp=500.0,
                link_pncp="https://pncp.gov.br/app/contratos/x",
            ),
            client.ContratoVigente(fontes={"PNCP"}, controle_pncp="outro", data_fim="2027-01-01"),
        ]
        unidos = client.unir(compras, pncp)
        assert len(unidos) == 2
        junto = next(c for c in unidos if c.numero == "00116/2024")
        assert junto.fontes == {"Compras.gov.br", "PNCP"}
        assert junto.valor_global == 803963.54  # vale o do Compras.gov.br (tem os aditivos)
        assert junto.valor_pncp == 500.0


class TestContratosVigentes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_cruza_fontes_e_varre_so_orgaos_federais(self) -> None:
        respx.get(FORNECEDOR_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "totalRegistros": 1,
                    "resultado": [{"cnpj": CNPJ, "nomeRazaoSocialFornecedor": "REALMAK SERVICOS E COMERCIO LTDA", "habilitadoLicitar": True, "ativo": True}],
                },
            )
        )
        respx.get(ORGAO_URL).mock(return_value=_orgaos())
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "total": 2,
                    "items": [
                        _doc_pncp("00394429000100-2-000503/2024", "Contrato nº 00116/2024", 1.0),
                        _doc_pncp("sem-par", "Contrato nº 9/2026", 2.0),
                        {**_doc_pncp("de-outro", "Contrato nº 1/2020", 3.0), "fornecedor_ni": "11111111000191"},
                    ],
                },
            )
        )
        chamadas: list[str] = []

        def por_orgao(request: httpx.Request) -> httpx.Response:
            codigo = request.url.params["codigoOrgao"]
            chamadas.append(codigo)
            assert request.url.params["niFornecedor"] == CNPJ
            itens = [_contrato_compras()] if codigo == "52111" else []
            return httpx.Response(200, json={"resultado": itens, "totalRegistros": len(itens)})

        respx.get(CONTRATOS_FIM_VIGENCIA_URL).mock(side_effect=por_orgao)

        res = await client.contratos_vigentes(CNPJ, aguardar_s=20)

        assert sorted(chamadas) == ["26270", "52111"]  # municipal fica de fora
        assert res.razao_social == "REALMAK SERVICOS E COMERCIO LTDA"
        assert res.varredura.concluida and res.varredura.feitos == 2 and not res.varredura.falhas
        assert res.pncp_ok
        assert len(res.contratos) == 2  # o do PNCP de outro fornecedor não entra
        assert {tuple(sorted(c.fontes)) for c in res.contratos} == {
            ("Compras.gov.br", "PNCP"),
            ("PNCP",),
        }
        texto = tools.formatar(res)
        assert "00116/2024" in texto and "9/2026" in texto
        assert "2 de 2 órgãos federais consultados" in texto

    @pytest.mark.asyncio
    @respx.mock
    async def test_429_espera_e_tenta_de_novo(self) -> None:
        respx.get(FORNECEDOR_URL).mock(return_value=httpx.Response(200, json={"resultado": []}))
        respx.get(ORGAO_URL).mock(return_value=_orgaos())
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={"total": 0, "items": []}))
        rota = respx.get(CONTRATOS_FIM_VIGENCIA_URL).mock(
            side_effect=[
                httpx.Response(429, headers={"retry-after": "0"}),
                httpx.Response(200, json={"resultado": [_contrato_compras()]}),
                httpx.Response(200, json={"resultado": []}),
            ]
        )
        res = await client.contratos_vigentes(CNPJ, aguardar_s=20)
        assert rota.call_count == 3
        assert res.varredura.feitos == 2 and not res.varredura.falhas
        assert len(res.contratos) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_pncp_fora_do_ar_nao_derruba_o_resultado_do_compras(self) -> None:
        respx.get(FORNECEDOR_URL).mock(return_value=httpx.Response(200, json={"resultado": []}))
        respx.get(ORGAO_URL).mock(return_value=_orgaos())
        respx.get(SEARCH_URL).mock(side_effect=httpx.ConnectError("reset"))
        respx.get(CONTRATOS_FIM_VIGENCIA_URL).mock(
            return_value=httpx.Response(200, json={"resultado": [_contrato_compras()]})
        )
        res = await client.contratos_vigentes(CNPJ, aguardar_s=30, codigos_orgao=["52111"])
        assert not res.pncp_ok
        assert len(res.contratos) == 1
        texto = tools.formatar(res)
        assert "PNCP: **falhou**" in texto

    @pytest.mark.asyncio
    @respx.mock
    async def test_codigos_orgao_restringem_a_varredura(self) -> None:
        respx.get(FORNECEDOR_URL).mock(return_value=httpx.Response(200, json={"resultado": []}))
        respx.get(ORGAO_URL).mock(return_value=_orgaos())
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={"total": 0, "items": []}))
        rota = respx.get(CONTRATOS_FIM_VIGENCIA_URL).mock(
            return_value=httpx.Response(200, json={"resultado": []})
        )
        res = await client.contratos_vigentes(CNPJ, aguardar_s=20, codigos_orgao=["26270"])
        assert rota.call_count == 1
        assert res.escopo_restrito and res.varredura.total == 1
        assert "Nenhum contrato vigente" in tools.formatar(res)


class TestConLicitacao:
    def _item(self, **extra: object) -> dict[str, object]:
        return {
            "orgao": "MINISTÉRIO DA DEFESA - Comando da Aeronáutica",
            "objeto": "Climatização CINDACTA I",
            "numero_contrato": "00116",
            "assinatura": "2024-09-03",
            "vigencia_inicio": "2024-09-03",
            "vigencia_fim": FIM,
            "valor_contratado": 803964.0,
            "contrato_pncp_id": "00394429000100-2-000503/2024",
            **extra,
        }

    def test_numero_ganha_o_ano_da_assinatura(self) -> None:
        assert client._contrato_conlicitacao(self._item()).numero == "00116/2024"

    def test_une_por_numero_de_controle_do_pncp(self) -> None:
        compras = [client._contrato_compras(_contrato_compras())]
        unidos = client.unir(compras, [], [client._contrato_conlicitacao(self._item())])
        assert len(unidos) == 1
        assert unidos[0].fontes == {"Compras.gov.br", "ConLicitação"}
        assert unidos[0].valor_global == 803963.54  # o Compras.gov.br manda no valor

    def test_sem_controle_une_por_numero_ano_e_valor(self) -> None:
        compras = [client._contrato_compras(_contrato_compras(numeroControlePncpContrato=None))]
        mesmo = client._contrato_conlicitacao(self._item(contrato_pncp_id=None, valor_contratado=803964.0))
        outro_numero = client._contrato_conlicitacao(
            self._item(contrato_pncp_id=None, numero_contrato="00999", valor_contratado=5.0, vigencia_fim="2031-01-01")
        )
        unidos = client.unir(compras, [], [mesmo, outro_numero])
        assert len(unidos) == 2
        assert {tuple(sorted(c.fontes)) for c in unidos} == {
            ("Compras.gov.br", "ConLicitação"),
            ("ConLicitação",),
        }

    @pytest.mark.asyncio
    async def test_sem_credencial_a_fonte_cai_com_aviso(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for nome in ("CONLICITACAO_LOGIN", "CONLICITACAO_SITE_PASSWORD", "CONLICITACAO_TOKEN"):
            monkeypatch.delenv(nome, raising=False)
        lista, erro = await client._contratos_conlicitacao(CNPJ)
        assert lista == [] and erro


class TestPrazoVencidoNoCompras:
    def test_contrato_com_fim_no_passado_vai_para_confirmar_prorrogacao(self) -> None:
        antigo = client.ContratoVigente(
            fontes={"Compras.gov.br"}, orgao="IF GOIANO", numero="00001/2021",
            data_fim="2023-01-06", valor_global=141279.92,
        )
        atual = client.ContratoVigente(
            fontes={"Compras.gov.br"}, orgao="UFAM", numero="00034/2024",
            data_fim=FIM, valor_global=1000.0,
        )
        assert not antigo.vigente() and atual.vigente()
        v = client.Varredura(cnpj=CNPJ, total=1, feitos=1, concluida_em=1.0)
        res = client.Resultado(
            cnpj=CNPJ, razao_social="X", habilitado=True, contratos=[antigo, atual],
            pncp_ok=True, pncp_erro=None, varredura=v, escopo_restrito=False,
        )
        texto = tools.formatar(res)
        assert "**1 contratos vigentes**" in texto and "R$ 1.000,00" in texto
        assert "Confirmar prorrogação (1)" in texto and "00001/2021" in texto
        assert "141.279,92" in texto
        # o valor do contrato a confirmar não entra na soma dos vigentes
        assert "valor global somado R$ 1.000,00" in texto


class TestVerificarProrrogacoes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_ativo_no_contratos_gov_vira_prorrogado_e_ausente_nao_vira_encerrado(self) -> None:
        respx.get(f"{CONTRATO_POR_UG_URL}/113205").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": 1, "numero": "00005/2022", "vigencia_fim": "2027-02-07",
                        "valor_global": "130.333,20", "unidade_codigo": "113205",
                        "fornecedor": {"cnpj_cpf_idgener": "03.496.338/0001-74", "nome": "REALMAK"},
                    },
                    {
                        "id": 2, "numero": "00005/2022", "vigencia_fim": "2027-01-01",
                        "fornecedor": {"cnpj_cpf_idgener": "11.111.111/0001-91", "nome": "OUTRA"},
                    },
                ],
            )
        )
        respx.get(f"{CONTRATO_POR_UG_URL}/158124").mock(return_value=httpx.Response(200, json=[]))
        prorrogado = client.ContratoVigente(
            fontes={"Compras.gov.br"}, numero="00005/2022", data_fim="2026-02-07",
            valor_global=122846.76, codigo_ug="113205",
        )
        encerrado = client.ContratoVigente(
            fontes={"Compras.gov.br"}, numero="00011/2020", data_fim="2025-09-30", codigo_ug="158124",
        )
        pendentes = await client.verificar_prorrogacoes(CNPJ, [prorrogado, encerrado])
        assert pendentes == 0
        assert prorrogado.verificado == "prorrogado" and prorrogado.vigente()
        assert prorrogado.data_fim == "2027-02-07" and prorrogado.valor_global == 130333.20
        assert "Contratos.gov.br" in prorrogado.fontes
        # ausente da lista da UG não prova que acabou: segue para confirmação manual
        assert encerrado.verificado == "nao_listado" and not encerrado.vigente()

    @pytest.mark.asyncio
    @respx.mock
    async def test_ug_lenta_deixa_pendente_sem_derrubar_a_resposta(self) -> None:
        respx.get(f"{CONTRATO_POR_UG_URL}/158124").mock(side_effect=httpx.ReadTimeout("lento"))
        c = client.ContratoVigente(
            fontes={"Compras.gov.br"}, numero="00011/2020", data_fim="2025-09-30", codigo_ug="158124"
        )
        pendentes = await client.verificar_prorrogacoes(CNPJ, [c], orcamento_s=15)
        assert pendentes == 1 and c.verificado is None
        res = client.Resultado(
            cnpj=CNPJ, razao_social="X", habilitado=True, contratos=[c], pncp_ok=True, pncp_erro=None,
            varredura=client.Varredura(cnpj=CNPJ, total=1, feitos=1, concluida_em=1.0),
            escopo_restrito=False,
        )
        assert "Confirmar prorrogação (1)" in tools.formatar(res)


class TestTool:
    @pytest.mark.asyncio
    async def test_cnpj_invalido_nao_consulta_nada(self) -> None:
        ctx = MagicMock()
        ctx.info = AsyncMock()
        texto = await tools.contratos_vigentes_por_cnpj("123", ctx)
        assert "CNPJ inválido" in texto
        assert not client._VARREDURAS

    def test_varredura_em_andamento_avisa_que_e_parcial(self) -> None:
        v = client.Varredura(cnpj=CNPJ, total=1000, feitos=100)
        res = client.Resultado(
            cnpj=CNPJ, razao_social=None, habilitado=None, contratos=[], pncp_ok=True,
            pncp_erro=None, varredura=v, escopo_restrito=False,
        )
        texto = tools.formatar(res)
        assert "varredura em andamento" in texto and "100 de 1000" in texto
        assert "parcial" in texto
