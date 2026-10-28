"""HTTP client for the Dados Abertos Compras.gov.br API.

Base URL: https://dadosabertos.compras.gov.br
Auth: None required (public API)
Page size: 10-500 (API requirement)
Response format: {"resultado": [...], "totalRegistros": N, "totalPaginas": N}
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from typing import Any, TypeVar

from mcp_realmak.compras._shared.cache import ttl_cache
from mcp_realmak.compras._shared.http_client import http_get

from .constants import (
    COMPRAS_SEM_LICITACAO_URL,
    CONTRATOS_URL,
    DEFAULT_PAGE_SIZE,
    FORNECEDOR_URL,
    GRUPO_MATERIAL_URL,
    ITEM_MATERIAL_URL,
    ITEM_SERVICO_URL,
    LICITACOES_URL,
    MAX_PAGE_SIZE,
    MIN_PAGE_SIZE,
    PDM_MATERIAL_URL,
    PESQUISA_PRECO_MATERIAL_URL,
    PESQUISA_PRECO_SERVICO_URL,
    PREGOES_URL,
    UASG_URL,
)
from .schemas import (
    ContratoDA,
    ContratoDAResultado,
    FornecedorDA,
    FornecedorDAResultado,
    GrupoMaterial,
    GrupoMaterialResultado,
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

_PRECO_DATA_MINIMA = "2000-01-01"
_CATALOGO_TTL = 24 * 3600.0  # catalogs change rarely; downloading them is the slow part
_CATALOGO_CONCORRENCIA = 8

T = TypeVar("T")


def _ensure_min_page_size(tamanho: int) -> int:
    """API requires tamanhoPagina between 10 and 500."""
    return max(tamanho, MIN_PAGE_SIZE)


def _parse_licitacao(item: dict[str, Any]) -> Licitacao:
    return Licitacao(
        id_compra=item.get("id_compra"),
        identificador=item.get("identificador"),
        numero_processo=item.get("numero_processo"),
        uasg=item.get("uasg"),
        modalidade=item.get("modalidade"),
        nome_modalidade=item.get("nome_modalidade"),
        numero_aviso=item.get("numero_aviso"),
        situacao_aviso=item.get("situacao_aviso"),
        tipo_pregao=item.get("tipo_pregao"),
        objeto=item.get("objeto"),
        valor_estimado_total=item.get("valor_estimado_total"),
        valor_homologado_total=item.get("valor_homologado_total"),
        numero_itens=item.get("numero_itens"),
        data_publicacao=item.get("data_publicacao"),
        data_abertura_proposta=item.get("data_abertura_proposta"),
        nome_responsavel=item.get("nome_responsavel"),
        funcao_responsavel=item.get("funcao_responsavel"),
        endereco_entrega_edital=item.get("endereco_entrega_edital"),
    )


def _parse_contrato_da(item: dict[str, Any]) -> ContratoDA:
    return ContratoDA(
        codigo_orgao=item.get("codigoOrgao"),
        nome_orgao=item.get("nomeOrgao"),
        codigo_unidade_gestora=item.get("codigoUnidadeGestora"),
        nome_unidade_gestora=item.get("nomeUnidadeGestora"),
        numero_contrato=item.get("numeroContrato"),
        nome_modalidade_compra=item.get("nomeModalidadeCompra"),
        nome_tipo=item.get("nomeTipo"),
        nome_categoria=item.get("nomeCategoria"),
        ni_fornecedor=item.get("niFornecedor"),
        nome_fornecedor=item.get("nomeRazaoSocialFornecedor"),
        processo=item.get("processo"),
        objeto=item.get("objeto"),
        data_vigencia_inicial=item.get("dataVigenciaInicial"),
        data_vigencia_final=item.get("dataVigenciaFinal"),
        valor_global=item.get("valorGlobal"),
        valor_parcela=item.get("valorParcela"),
        valor_acumulado=item.get("valorAcumulado"),
    )


def _parse_fornecedor_da(item: dict[str, Any]) -> FornecedorDA:
    return FornecedorDA(
        cnpj=item.get("cnpj"),
        cpf=item.get("cpf"),
        nome_razao_social=item.get("nomeRazaoSocialFornecedor"),
        uf_sigla=item.get("ufSigla"),
        nome_municipio=item.get("nomeMunicipio"),
        porte_empresa_nome=item.get("porteEmpresaNome"),
        natureza_juridica_nome=item.get("naturezaJuridicaNome"),
        nome_cnae=item.get("nomeCnae"),
        ativo=item.get("ativo"),
        habilitado_licitar=item.get("habilitadoLicitar"),
    )


def _parse_grupo_material(item: dict[str, Any]) -> GrupoMaterial:
    return GrupoMaterial(
        codigo_grupo=item.get("codigoGrupo"),
        nome_grupo=item.get("nomeGrupo"),
        status_grupo=item.get("statusGrupo"),
    )


def _parse_pdm(item: dict[str, Any]) -> PdmMaterial:
    return PdmMaterial(
        codigo_pdm=item.get("codigoPdm"),
        nome_pdm=item.get("nomePdm"),
        nome_classe=item.get("nomeClasse"),
        nome_grupo=item.get("nomeGrupo"),
    )


def _parse_item_material(item: dict[str, Any]) -> ItemMaterial:
    return ItemMaterial(
        codigo_item=item.get("codigoItem"),
        descricao_item=item.get("descricaoItem"),
        codigo_grupo=item.get("codigoGrupo"),
        codigo_classe=item.get("codigoClasse"),
        codigo_pdm=item.get("codigoPdm"),
        status_item=item.get("statusItem"),
    )


def _parse_item_servico(item: dict[str, Any]) -> ItemServico:
    return ItemServico(
        codigo_servico=item.get("codigoServico"),
        nome_servico=item.get("nomeServico"),
        codigo_secao=item.get("codigoSecao"),
        codigo_divisao=item.get("codigoDivisao"),
        codigo_grupo=item.get("codigoGrupo"),
        codigo_classe=item.get("codigoClasse"),
        status_servico=item.get("statusServico"),
    )


def _opt_str(value: Any) -> str | None:
    """The API returns some ids as int in one endpoint and str in another."""
    return None if value is None else str(value)


def _parse_preco(item: dict[str, Any]) -> PrecoPraticado:
    return PrecoPraticado(
        id_compra=_opt_str(item.get("idCompra")),
        data_compra=item.get("dataCompra"),
        codigo_item_catalogo=item.get("codigoItemCatalogo"),
        descricao_item=item.get("descricaoItem"),
        quantidade=item.get("quantidade"),
        preco_unitario=item.get("precoUnitario"),
        unidade=(
            item.get("siglaUnidadeFornecimento")
            or item.get("siglaUnidadeMedida")
            or item.get("nomeUnidadeMedida")
        ),
        nome_fornecedor=item.get("nomeFornecedor"),
        ni_fornecedor=item.get("niFornecedor"),
        marca=item.get("marca"),
        codigo_uasg=_opt_str(item.get("codigoUasg")),
        nome_uasg=item.get("nomeUasg"),
        nome_orgao=item.get("nomeOrgao"),
        uf=item.get("estado"),
        municipio=item.get("municipio"),
        esfera=item.get("esfera"),
        poder=item.get("poder"),
    )


def _parse_uasg(item: dict[str, Any]) -> Uasg:
    return Uasg(
        codigo_uasg=item.get("codigoUasg"),
        nome_uasg=item.get("nomeUasg"),
        cnpj_cpf_orgao=item.get("cnpjCpfOrgao"),
        sigla_uf=item.get("siglaUf"),
        nome_municipio=item.get("nomeMunicipio"),
        uso_sisg=item.get("usoSisg"),
        status_uasg=item.get("statusUasg"),
    )


async def buscar_licitacoes(
    data_publicacao_inicial: str,
    data_publicacao_final: str,
    uasg: int | None = None,
    modalidade: int | None = None,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> LicitacaoResultado:
    """Search legacy procurement processes (SIASG)."""
    params: dict[str, str] = {
        "data_publicacao_inicial": data_publicacao_inicial,
        "data_publicacao_final": data_publicacao_final,
        "pagina": str(pagina),
        "tamanhoPagina": str(_ensure_min_page_size(tamanho)),
    }
    if uasg is not None:
        params["uasg"] = str(uasg)
    if modalidade is not None:
        params["modalidade"] = str(modalidade)

    data: dict[str, Any] = await http_get(LICITACOES_URL, params=params)
    items = data.get("resultado", [])
    licitacoes = [_parse_licitacao(i) for i in items] if isinstance(items, list) else []
    return LicitacaoResultado(
        total=data.get("totalRegistros", len(licitacoes)),
        licitacoes=licitacoes,
    )


async def buscar_pregoes(
    data_edital_inicial: str,
    data_edital_final: str,
    co_uasg: int | None = None,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> LicitacaoResultado:
    """Search electronic auction processes (pregões)."""
    params: dict[str, str] = {
        "dt_data_edital_inicial": data_edital_inicial,
        "dt_data_edital_final": data_edital_final,
        "pagina": str(pagina),
        "tamanhoPagina": str(_ensure_min_page_size(tamanho)),
    }
    if co_uasg is not None:
        params["co_uasg"] = str(co_uasg)

    data: dict[str, Any] = await http_get(PREGOES_URL, params=params)
    items = data.get("resultado", [])
    licitacoes = [_parse_licitacao(i) for i in items] if isinstance(items, list) else []
    return LicitacaoResultado(
        total=data.get("totalRegistros", len(licitacoes)),
        licitacoes=licitacoes,
    )


async def buscar_dispensas(
    ano_aviso: int,
    co_uasg: int | None = None,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> LicitacaoResultado:
    """Search purchases without bidding (dispensas/inexigibilidades)."""
    params: dict[str, str] = {
        "dt_ano_aviso": str(ano_aviso),
        "pagina": str(pagina),
        "tamanhoPagina": str(_ensure_min_page_size(tamanho)),
    }
    if co_uasg is not None:
        params["co_uasg"] = str(co_uasg)

    data: dict[str, Any] = await http_get(COMPRAS_SEM_LICITACAO_URL, params=params)
    items = data.get("resultado", [])
    licitacoes = [_parse_licitacao(i) for i in items] if isinstance(items, list) else []
    return LicitacaoResultado(
        total=data.get("totalRegistros", len(licitacoes)),
        licitacoes=licitacoes,
    )


async def buscar_contratos(
    data_vigencia_inicial_min: str,
    data_vigencia_inicial_max: str,
    codigo_orgao: str | None = None,
    ni_fornecedor: str | None = None,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> ContratoDAResultado:
    """Search public contracts."""
    params: dict[str, str] = {
        "dataVigenciaInicialMin": data_vigencia_inicial_min,
        "dataVigenciaInicialMax": data_vigencia_inicial_max,
        "pagina": str(pagina),
        "tamanhoPagina": str(_ensure_min_page_size(tamanho)),
    }
    if codigo_orgao:
        params["codigoOrgao"] = codigo_orgao
    if ni_fornecedor:
        params["niFornecedor"] = ni_fornecedor

    data: dict[str, Any] = await http_get(CONTRATOS_URL, params=params)
    items = data.get("resultado", [])
    contratos = [_parse_contrato_da(i) for i in items] if isinstance(items, list) else []
    return ContratoDAResultado(
        total=data.get("totalRegistros", len(contratos)),
        contratos=contratos,
    )


async def consultar_fornecedor(
    cnpj: str | None = None,
    cpf: str | None = None,
    ativo: bool = True,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> FornecedorDAResultado:
    """Search suppliers by CNPJ or CPF."""
    params: dict[str, str] = {
        "ativo": str(ativo).lower(),
        "pagina": str(pagina),
        "tamanhoPagina": str(_ensure_min_page_size(tamanho)),
    }
    if cnpj:
        params["cnpj"] = cnpj
    if cpf:
        params["cpf"] = cpf

    data: dict[str, Any] = await http_get(FORNECEDOR_URL, params=params)
    items = data.get("resultado", [])
    fornecedores = [_parse_fornecedor_da(i) for i in items] if isinstance(items, list) else []
    return FornecedorDAResultado(
        total=data.get("totalRegistros", len(fornecedores)),
        fornecedores=fornecedores,
    )


async def listar_grupos_material(pagina: int = 1) -> GrupoMaterialResultado:
    """List CATMAT material groups."""
    params: dict[str, str] = {"pagina": str(pagina)}
    data: dict[str, Any] = await http_get(GRUPO_MATERIAL_URL, params=params)
    items = data.get("resultado", [])
    grupos = [_parse_grupo_material(i) for i in items] if isinstance(items, list) else []
    return GrupoMaterialResultado(
        total=data.get("totalRegistros", len(grupos)),
        grupos=grupos,
    )


async def buscar_material(
    descricao: str | None = None,
    codigo_grupo: int | None = None,
    codigo_classe: int | None = None,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> ItemMaterialResultado:
    """Search CATMAT material items."""
    params: dict[str, str] = {
        "pagina": str(pagina),
        "tamanhoPagina": str(_ensure_min_page_size(tamanho)),
    }
    if descricao:
        params["descricaoItem"] = descricao
    if codigo_grupo is not None:
        params["codigoGrupo"] = str(codigo_grupo)
    if codigo_classe is not None:
        params["codigoClasse"] = str(codigo_classe)

    data: dict[str, Any] = await http_get(ITEM_MATERIAL_URL, params=params)
    items = data.get("resultado", [])
    itens = [_parse_item_material(i) for i in items] if isinstance(items, list) else []
    return ItemMaterialResultado(
        total=data.get("totalRegistros", len(itens)),
        itens=itens,
    )


async def buscar_servico(
    codigo_servico: int | None = None,
    codigo_grupo: int | None = None,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> ItemServicoResultado:
    """Search CATSER service items."""
    params: dict[str, str] = {
        "pagina": str(pagina),
        "tamanhoPagina": str(_ensure_min_page_size(tamanho)),
    }
    if codigo_servico is not None:
        params["codigoServico"] = str(codigo_servico)
    if codigo_grupo is not None:
        params["codigoGrupo"] = str(codigo_grupo)

    data: dict[str, Any] = await http_get(ITEM_SERVICO_URL, params=params)
    items = data.get("resultado", [])
    itens = [_parse_item_servico(i) for i in items] if isinstance(items, list) else []
    return ItemServicoResultado(
        total=data.get("totalRegistros", len(itens)),
        itens=itens,
    )


def _preco_filters(
    data_compra_inicio: str | None,
    data_compra_fim: str | None,
    codigo_uasg: str | None,
    uf: str | None,
    esfera: str | None,
    poder: str | None,
) -> dict[str, str]:
    filters: dict[str, str] = {}
    # The API silently ignores the date filter unless BOTH bounds are sent
    # (it then returns every purchase), so complete the missing one.
    if data_compra_inicio or data_compra_fim:
        filters["dataCompraInicio"] = data_compra_inicio or _PRECO_DATA_MINIMA
        filters["dataCompraFim"] = data_compra_fim or date.today().isoformat()
    if codigo_uasg:
        filters["codigoUasg"] = codigo_uasg
    if uf:
        filters["estado"] = uf.upper()
    if esfera:
        filters["esfera"] = esfera.upper()
    if poder:
        filters["poder"] = poder.upper()
    return filters


async def pesquisar_preco_material(
    codigo: str,
    tipo: str = "codigoItemCatalogo",
    data_compra_inicio: str | None = None,
    data_compra_fim: str | None = None,
    codigo_uasg: str | None = None,
    uf: str | None = None,
    esfera: str | None = None,
    poder: str | None = None,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> PrecoResultado:
    """Search unit prices paid for a CATMAT material (Pesquisa de Preço)."""
    params: dict[str, str] = {
        "tipo": tipo,
        "codigo": codigo,
        "pagina": str(pagina),
        "tamanhoPagina": str(_ensure_min_page_size(tamanho)),
        **_preco_filters(data_compra_inicio, data_compra_fim, codigo_uasg, uf, esfera, poder),
    }
    data: dict[str, Any] = await http_get(PESQUISA_PRECO_MATERIAL_URL, params=params)
    items = data.get("resultado", [])
    precos = [_parse_preco(i) for i in items] if isinstance(items, list) else []
    return PrecoResultado(total=data.get("totalRegistros", len(precos)), precos=precos)


async def pesquisar_preco_servico(
    codigo_item_catalogo: int,
    data_compra_inicio: str | None = None,
    data_compra_fim: str | None = None,
    codigo_uasg: str | None = None,
    uf: str | None = None,
    esfera: str | None = None,
    poder: str | None = None,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> PrecoResultado:
    """Search unit prices paid for a CATSER service (Pesquisa de Preço)."""
    params: dict[str, str] = {
        "codigoItemCatalogo": str(codigo_item_catalogo),
        "pagina": str(pagina),
        "tamanhoPagina": str(_ensure_min_page_size(tamanho)),
        **_preco_filters(data_compra_inicio, data_compra_fim, codigo_uasg, uf, esfera, poder),
    }
    data: dict[str, Any] = await http_get(PESQUISA_PRECO_SERVICO_URL, params=params)
    items = data.get("resultado", [])
    precos = [_parse_preco(i) for i in items] if isinstance(items, list) else []
    return PrecoResultado(total=data.get("totalRegistros", len(precos)), precos=precos)


async def buscar_uasg(
    codigo_uasg: str | None = None,
    sigla_uf: str | None = None,
    status_uasg: bool = True,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> UasgResultado:
    """Search UASG (administrative units)."""
    params: dict[str, str] = {
        "statusUasg": str(status_uasg).lower(),
        "pagina": str(pagina),
        "tamanhoPagina": str(_ensure_min_page_size(tamanho)),
    }
    if codigo_uasg:
        params["codigoUasg"] = codigo_uasg
    if sigla_uf:
        params["siglaUf"] = sigla_uf

    data: dict[str, Any] = await http_get(UASG_URL, params=params)
    items = data.get("resultado", [])
    uasgs = [_parse_uasg(i) for i in items] if isinstance(items, list) else []
    return UasgResultado(
        total=data.get("totalRegistros", len(uasgs)),
        uasgs=uasgs,
    )


async def _carregar_catalogo(
    url: str,
    filtros: dict[str, str],
    parse: Callable[[dict[str, Any]], T],
) -> list[T]:
    """Download every page of a catalog endpoint (pages after the first in parallel)."""
    base = {"tamanhoPagina": str(MAX_PAGE_SIZE), **filtros}
    primeira: dict[str, Any] = await http_get(url, params={**base, "pagina": "1"})
    paginas = [primeira]
    total_paginas = int(primeira.get("totalPaginas") or 1)
    if total_paginas > 1:
        limite = asyncio.Semaphore(_CATALOGO_CONCORRENCIA)

        async def _pagina(numero: int) -> dict[str, Any]:
            async with limite:
                dados: dict[str, Any] = await http_get(url, params={**base, "pagina": str(numero)})
                return dados

        paginas += await asyncio.gather(*(_pagina(n) for n in range(2, total_paginas + 1)))

    itens: list[T] = []
    for pagina in paginas:
        resultado = pagina.get("resultado", [])
        if isinstance(resultado, list):
            itens.extend(parse(i) for i in resultado)
    return itens


@ttl_cache(ttl=_CATALOGO_TTL, maxsize=2)
async def carregar_pdms() -> list[PdmMaterial]:
    """All active CATMAT PDMs (~15k). The API has no working text filter, so search locally."""
    return await _carregar_catalogo(PDM_MATERIAL_URL, {"statusPdm": "true"}, _parse_pdm)


@ttl_cache(ttl=_CATALOGO_TTL, maxsize=2)
async def carregar_servicos() -> list[ItemServico]:
    """All active CATSER services (~3k). The API has no working text filter, so search locally."""
    return await _carregar_catalogo(
        ITEM_SERVICO_URL, {"statusServico": "true"}, _parse_item_servico
    )
