"""HTTP client for the PNCP API.

Endpoints (verified against OpenAPI spec at /v3/api-docs):
    - /contratacoes/publicacao  → buscar_contratacoes (requires dates + modalidade)
    - /contratos                → buscar_contratos (requires dates)
    - /atas                     → buscar_atas (requires dates)
    - /fornecedores             → consultar_fornecedor
    - /orgaos                   → consultar_orgao

IMPORTANT: The PNCP API has NO text search parameter (`q`).
All text filtering is done client-side after fetching results.
Date format for all endpoints: YYYYMMDD.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from mcp_realmak.compras._shared.http_client import http_get

from .constants import (
    ARQUIVO_URL_INTERNA_RE,
    ARQUIVO_URL_PUBLICA,
    ATAS_ATUALIZACAO_URL,
    ATAS_URL,
    CONTRATACOES_ATUALIZACAO_URL,
    CONTRATACOES_PROPOSTA_URL,
    CONTRATACOES_URL,
    CONTRATOS_ATUALIZACAO_URL,
    CONTRATOS_URL,
    ESFERAS,
    FORNECEDORES_URL,
    INSTRUMENTOS_COBRANCA_URL,
    MAX_DATE_RANGE_DAYS,
    MAX_PAGE_SIZE_CONTRATACOES,
    MAX_PAGE_SIZE_SEARCH,
    ORGAOS_URL,
    PCA_URL,
    PORTAL_URL,
    SEARCH_MAX_RETRIES,
    SEARCH_STATUS,
    SEARCH_STATUS_PADRAO,
    SEARCH_URL,
)
from .schemas import (
    ArquivoContratacao,
    AtaRegistroPreco,
    AtaResultado,
    Contratacao,
    ContratacaoResultado,
    Contrato,
    ContratoResultado,
    DocumentoPesquisa,
    EventoHistorico,
    Fornecedor,
    FornecedorResultado,
    InstrumentoCobranca,
    InstrumentoCobrancaResultado,
    ItemContratacao,
    ItemPca,
    OrgaoContratante,
    OrgaoResultado,
    Pca,
    PcaResultado,
    PesquisaResultado,
    ResultadoItem,
)

_DATE_RE = re.compile(r"^\d{8}$")


def normalizar_data(data: str) -> str:
    """Normalize a date string to YYYYMMDD format.

    Accepts: YYYYMMDD, YYYY-MM-DD, DD/MM/YYYY.
    Raises ValueError for invalid formats.
    """
    cleaned = data.strip()

    # Already YYYYMMDD
    if _DATE_RE.match(cleaned):
        datetime.strptime(cleaned, "%Y%m%d")  # validate
        return cleaned

    # YYYY-MM-DD
    if len(cleaned) == 10 and cleaned[4] == "-":
        dt = datetime.strptime(cleaned, "%Y-%m-%d")
        return dt.strftime("%Y%m%d")

    # DD/MM/YYYY
    if len(cleaned) == 10 and cleaned[2] == "/":
        dt = datetime.strptime(cleaned, "%d/%m/%Y")
        return dt.strftime("%Y%m%d")

    msg = f"Formato de data inválido: '{data}'. Use YYYYMMDD, YYYY-MM-DD ou DD/MM/YYYY."
    raise ValueError(msg)


def validar_periodo(data_inicial: str, data_final: str) -> None:
    """Validate that the date range does not exceed MAX_DATE_RANGE_DAYS."""
    dt_ini = datetime.strptime(data_inicial, "%Y%m%d")
    dt_fim = datetime.strptime(data_final, "%Y%m%d")
    if dt_fim < dt_ini:
        msg = f"data_final ({data_final}) é anterior a data_inicial ({data_inicial})."
        raise ValueError(msg)
    diff = (dt_fim - dt_ini).days
    if diff > MAX_DATE_RANGE_DAYS:
        msg = (
            f"Período de {diff} dias excede o máximo de {MAX_DATE_RANGE_DAYS} dias. "
            f"Reduza o intervalo entre data_inicial e data_final."
        )
        raise ValueError(msg)


def _default_data_inicial() -> str:
    """Return 30 days ago in YYYYMMDD format (sensible default)."""
    return (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")


def _default_data_final() -> str:
    """Return today in YYYYMMDD format."""
    return datetime.now().strftime("%Y%m%d")


def _filtrar_por_texto(items: list[dict[str, Any]], texto: str | None) -> list[dict[str, Any]]:
    """Filter API results client-side by text match on relevant fields."""
    if not texto:
        return items
    termo = texto.lower()
    filtered = []
    for item in items:
        searchable = " ".join(
            str(v).lower()
            for v in [
                item.get("objetoCompra"),
                item.get("objetoContrato"),
                item.get("objetoAta"),
                item.get("objetoContratacao"),
                (item.get("orgaoEntidade") or {}).get("razaoSocial"),
                (item.get("fornecedor") or {}).get("razaoSocial"),
                (item.get("fornecedor") or {}).get("nomeRazaoSocial"),
                item.get("nomeRazaoSocialFornecedor"),
            ]
            if v
        )
        if termo in searchable:
            filtered.append(item)
    return filtered


def _tamanho_contratacoes(tamanho: int, texto: str | None) -> int:
    """Page size for /contratacoes endpoints (API accepts 10 to 50).

    With a local text filter, fetch the largest page so the filter sees more.
    """
    if texto:
        return MAX_PAGE_SIZE_CONTRATACOES
    return min(max(tamanho, 10), MAX_PAGE_SIZE_CONTRATACOES)


def link_portal_edital(cnpj: str | None, ano: int | None, sequencial: int | None) -> str | None:
    """Build the public portal link for a procurement process."""
    if not (cnpj and ano and sequencial):
        return None
    return f"{PORTAL_URL}/editais/{cnpj}/{ano}/{sequencial}"


def _parse_contratacao(item: dict[str, Any]) -> Contratacao:
    """Parse a raw API response item into a Contratacao model.

    UF and município live in `unidadeOrgao`; `orgaoEntidade` only has them in
    some responses, so it is the fallback.
    """
    orgao = item.get("orgaoEntidade", {}) or {}
    unidade = item.get("unidadeOrgao", {}) or {}
    cnpj = orgao.get("cnpj")
    ano = item.get("anoCompra")
    sequencial = item.get("sequencialCompra")
    return Contratacao(
        orgao_cnpj=cnpj,
        orgao_nome=orgao.get("razaoSocial"),
        ano=ano,
        numero_sequencial=sequencial,
        numero_controle_pncp=item.get("numeroControlePNCP"),
        objeto=item.get("objetoCompra"),
        modalidade_id=item.get("modalidadeId"),
        modalidade_nome=item.get("modalidadeNome"),
        situacao_id=item.get("situacaoCompraId"),
        situacao_nome=item.get("situacaoCompraNome"),
        valor_estimado=item.get("valorTotalEstimado"),
        valor_homologado=item.get("valorTotalHomologado"),
        data_publicacao=item.get("dataPublicacaoPncp"),
        data_abertura=item.get("dataAberturaProposta"),
        data_encerramento=item.get("dataEncerramentoProposta"),
        uf=unidade.get("ufSigla") or orgao.get("ufSigla"),
        municipio=unidade.get("municipioNome") or orgao.get("municipioNome"),
        unidade_nome=unidade.get("nomeUnidade"),
        esfera=orgao.get("esferaNome") or ESFERAS.get(orgao.get("esferaId") or ""),
        srp=item.get("srp"),
        link_pncp=item.get("linkPncp") or link_portal_edital(cnpj, ano, sequencial),
        link_origem=item.get("linkSistemaOrigem") or None,
    )


def _parse_contrato(item: dict[str, Any]) -> Contrato:
    """Parse a raw API response item into a Contrato model."""
    orgao = item.get("orgaoEntidade", {}) or {}
    fornecedor = item.get("fornecedor", {}) or {}
    return Contrato(
        orgao_cnpj=orgao.get("cnpj"),
        orgao_nome=orgao.get("razaoSocial"),
        numero_contrato=item.get("numeroContratoEmpenho"),
        objeto=item.get("objetoContrato"),
        fornecedor_cnpj=fornecedor.get("cnpj") or fornecedor.get("cpfCnpj"),
        fornecedor_nome=fornecedor.get("razaoSocial") or fornecedor.get("nomeRazaoSocial"),
        valor_inicial=item.get("valorInicial"),
        valor_final=item.get("valorFinal"),
        vigencia_inicio=item.get("dataVigenciaInicio"),
        vigencia_fim=item.get("dataVigenciaFim"),
        data_publicacao=item.get("dataPublicacaoPncp"),
        situacao=item.get("nomeStatus"),
    )


def _parse_ata(item: dict[str, Any]) -> AtaRegistroPreco:
    """Parse a raw API response item into an AtaRegistroPreco model."""
    orgao = item.get("orgaoEntidade", {}) or {}
    fornecedor = item.get("fornecedor", {}) or {}
    return AtaRegistroPreco(
        orgao_cnpj=orgao.get("cnpj"),
        orgao_nome=orgao.get("razaoSocial"),
        numero_ata=item.get("numeroAta") or item.get("numeroAtaRegistroPreco"),
        objeto=(
            item.get("objetoAta") or item.get("objetoContrato") or item.get("objetoContratacao")
        ),
        fornecedor_cnpj=fornecedor.get("cnpj") or fornecedor.get("cpfCnpj"),
        fornecedor_nome=fornecedor.get("razaoSocial") or fornecedor.get("nomeRazaoSocial"),
        valor_total=item.get("valorTotal") or item.get("valorInicial"),
        vigencia_inicio=item.get("dataVigenciaInicio") or item.get("vigenciaInicio"),
        vigencia_fim=item.get("dataVigenciaFim") or item.get("vigenciaFim"),
        situacao=item.get("nomeStatus"),
    )


async def buscar_contratacoes(
    data_inicial: str,
    data_final: str,
    modalidade: int,
    *,
    texto: str | None = None,
    uf: str | None = None,
    cnpj_orgao: str | None = None,
    codigo_municipio_ibge: str | None = None,
    codigo_unidade: str | None = None,
    modo_disputa: int | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> ContratacaoResultado:
    """Search published procurement processes.

    Required by the API: dataInicial, dataFinal, codigoModalidadeContratacao.
    Text filtering is done client-side (API has no text search).
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "codigoModalidadeContratacao": str(modalidade),
        "pagina": str(pagina),
        "tamanhoPagina": str(_tamanho_contratacoes(tamanho, texto)),
    }
    if uf:
        params["uf"] = uf
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao
    if codigo_municipio_ibge:
        params["codigoMunicipioIbge"] = codigo_municipio_ibge
    if codigo_unidade:
        params["codigoUnidadeAdministrativa"] = codigo_unidade
    if modo_disputa:
        params["codigoModoDisputa"] = str(modo_disputa)

    data: dict[str, Any] = await http_get(CONTRATACOES_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []

    # Client-side text filtering
    items = _filtrar_por_texto(items, texto)

    contratacoes = [_parse_contratacao(item) for item in items]
    return ContratacaoResultado(
        total=len(contratacoes) if texto else data.get("totalRegistros", len(contratacoes)),
        total_api=data.get("totalRegistros"),
        contratacoes=contratacoes,
    )


async def buscar_contratos(
    data_inicial: str,
    data_final: str,
    *,
    texto: str | None = None,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> ContratoResultado:
    """Search public contracts.

    Required by the API: dataInicial, dataFinal.
    Text filtering is done client-side (API has no text search).
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(tamanho, 500)),
    }
    if cnpj_orgao:
        params["cnpjOrgao"] = cnpj_orgao

    data: dict[str, Any] = await http_get(CONTRATOS_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []

    # Client-side text filtering
    items = _filtrar_por_texto(items, texto)

    contratos = [_parse_contrato(item) for item in items]
    return ContratoResultado(
        total=len(contratos) if texto else data.get("totalRegistros", len(contratos)),
        contratos=contratos,
    )


async def buscar_atas(
    data_inicial: str,
    data_final: str,
    *,
    texto: str | None = None,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> AtaResultado:
    """Search price record minutes (atas de registro de preço).

    Required by the API: dataInicial, dataFinal.
    Filters by validity period (vigência), not publication date.
    Text filtering is done client-side (API has no text search).
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(tamanho, 500)),
    }
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao

    data: dict[str, Any] = await http_get(ATAS_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []

    # Client-side text filtering
    items = _filtrar_por_texto(items, texto)

    atas = [_parse_ata(item) for item in items]
    return AtaResultado(
        total=len(atas) if texto else data.get("totalRegistros", len(atas)),
        atas=atas,
    )


def _parse_fornecedor(item: dict[str, Any]) -> Fornecedor:
    """Parse a raw API response item into a Fornecedor model."""
    return Fornecedor(
        cnpj=item.get("cnpj") or item.get("cpfCnpj"),
        razao_social=item.get("razaoSocial") or item.get("nomeRazaoSocial"),
        nome_fantasia=item.get("nomeFantasia"),
        municipio=(
            item.get("municipio", {}).get("nome")
            if isinstance(item.get("municipio"), dict)
            else item.get("municipioNome")
        ),
        uf=(
            item.get("uf", {}).get("sigla")
            if isinstance(item.get("uf"), dict)
            else item.get("ufSigla")
        ),
        porte=item.get("porte") or item.get("porteEmpresa"),
        data_abertura=item.get("dataAbertura"),
    )


_ESFERA_MAP: dict[str, str] = {"F": "Federal", "E": "Estadual", "M": "Municipal", "D": "Distrital"}
_PODER_MAP: dict[str, str] = {"E": "Executivo", "L": "Legislativo", "J": "Judiciário"}


def _parse_orgao(item: dict[str, Any]) -> OrgaoContratante:
    """Parse a raw API response item into an OrgaoContratante model."""
    esfera_id = item.get("esferaId") or ""
    poder_id = item.get("poderId") or ""
    return OrgaoContratante(
        cnpj=item.get("cnpj"),
        razao_social=item.get("razaoSocial"),
        esfera=item.get("esferaNome") or _ESFERA_MAP.get(esfera_id, esfera_id),
        poder=item.get("poderNome") or _PODER_MAP.get(poder_id, poder_id),
        uf=item.get("ufSigla") or item.get("ufNome"),
        municipio=item.get("municipioNome"),
    )


async def consultar_fornecedor(cnpj: str) -> FornecedorResultado:
    """Search supplier by CNPJ."""
    params: dict[str, str] = {"cnpj": cnpj}
    data: dict[str, Any] = await http_get(FORNECEDORES_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    fornecedores = [_parse_fornecedor(item) for item in items] if isinstance(items, list) else []
    return FornecedorResultado(
        total=data.get("totalRegistros", data.get("count", len(fornecedores))),
        fornecedores=fornecedores,
    )


async def consultar_orgao(cnpj: str) -> OrgaoResultado:
    """Fetch a contracting body by CNPJ.

    The PNCP API only supports lookup by exact CNPJ at /api/pncp/v1/orgaos/{cnpj}.
    Text search is not available in the API.
    """
    from mcp_realmak.compras.exceptions import HttpClientError

    url = f"{ORGAOS_URL}/{cnpj}"
    try:
        data: dict[str, Any] = await http_get(url)
    except HttpClientError:
        return OrgaoResultado(total=0, orgaos=[])
    if isinstance(data, dict) and data.get("cnpj"):
        orgao = _parse_orgao(data)
        return OrgaoResultado(total=1, orgaos=[orgao])
    return OrgaoResultado(total=0, orgaos=[])


async def buscar_contratacoes_abertas(
    data_final: str,
    *,
    texto: str | None = None,
    modalidade: int | None = None,
    uf: str | None = None,
    cnpj_orgao: str | None = None,
    codigo_municipio_ibge: str | None = None,
    codigo_unidade: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> ContratacaoResultado:
    """Search procurement processes with open proposal submission.

    API: GET /v1/contratacoes/proposta
    Required: dataFinal, pagina.
    """
    data_fim = normalizar_data(data_final)
    params: dict[str, str] = {
        "dataFinal": data_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(_tamanho_contratacoes(tamanho, texto)),
    }
    if modalidade:
        params["codigoModalidadeContratacao"] = str(modalidade)
    if uf:
        params["uf"] = uf
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao
    if codigo_municipio_ibge:
        params["codigoMunicipioIbge"] = codigo_municipio_ibge
    if codigo_unidade:
        params["codigoUnidadeAdministrativa"] = codigo_unidade

    data: dict[str, Any] = await http_get(CONTRATACOES_PROPOSTA_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []
    items = _filtrar_por_texto(items, texto)
    contratacoes = [_parse_contratacao(item) for item in items]
    return ContratacaoResultado(
        total=len(contratacoes) if texto else data.get("totalRegistros", len(contratacoes)),
        total_api=data.get("totalRegistros"),
        contratacoes=contratacoes,
    )


async def buscar_contratacoes_atualizadas(
    data_inicial: str,
    data_final: str,
    modalidade: int,
    *,
    texto: str | None = None,
    uf: str | None = None,
    cnpj_orgao: str | None = None,
    codigo_municipio_ibge: str | None = None,
    codigo_unidade: str | None = None,
    modo_disputa: int | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> ContratacaoResultado:
    """Search procurement processes by global update date.

    API: GET /v1/contratacoes/atualizacao
    Required: dataInicial, dataFinal, codigoModalidadeContratacao, pagina.
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "codigoModalidadeContratacao": str(modalidade),
        "pagina": str(pagina),
        "tamanhoPagina": str(_tamanho_contratacoes(tamanho, texto)),
    }
    if uf:
        params["uf"] = uf
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao
    if codigo_municipio_ibge:
        params["codigoMunicipioIbge"] = codigo_municipio_ibge
    if codigo_unidade:
        params["codigoUnidadeAdministrativa"] = codigo_unidade
    if modo_disputa:
        params["codigoModoDisputa"] = str(modo_disputa)

    data: dict[str, Any] = await http_get(CONTRATACOES_ATUALIZACAO_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []
    items = _filtrar_por_texto(items, texto)
    contratacoes = [_parse_contratacao(item) for item in items]
    return ContratacaoResultado(
        total=len(contratacoes) if texto else data.get("totalRegistros", len(contratacoes)),
        total_api=data.get("totalRegistros"),
        contratacoes=contratacoes,
    )


async def buscar_contratos_atualizados(
    data_inicial: str,
    data_final: str,
    *,
    texto: str | None = None,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> ContratoResultado:
    """Search contracts by global update date.

    API: GET /v1/contratos/atualizacao
    Required: dataInicial, dataFinal, pagina.
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 500)),
    }
    if cnpj_orgao:
        params["cnpjOrgao"] = cnpj_orgao

    data: dict[str, Any] = await http_get(CONTRATOS_ATUALIZACAO_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []
    items = _filtrar_por_texto(items, texto)
    contratos = [_parse_contrato(item) for item in items]
    return ContratoResultado(
        total=len(contratos) if texto else data.get("totalRegistros", len(contratos)),
        contratos=contratos,
    )


async def buscar_atas_atualizadas(
    data_inicial: str,
    data_final: str,
    *,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> AtaResultado:
    """Search price record minutes by global update date.

    API: GET /v1/atas/atualizacao
    Required: dataInicial, dataFinal, pagina.
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 500)),
    }
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao

    data: dict[str, Any] = await http_get(ATAS_ATUALIZACAO_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []

    atas: list[AtaRegistroPreco] = []
    for item in items:
        atas.append(
            AtaRegistroPreco(
                orgao_cnpj=item.get("cnpjOrgao"),
                orgao_nome=item.get("nomeOrgao"),
                numero_ata=item.get("numeroAtaRegistroPreco"),
                objeto=item.get("objetoContratacao"),
                vigencia_inicio=item.get("vigenciaInicio"),
                vigencia_fim=item.get("vigenciaFim"),
            )
        )
    return AtaResultado(
        total=data.get("totalRegistros", len(atas)),
        atas=atas,
    )


async def consultar_contratacao_detalhe(
    cnpj: str,
    ano: int,
    sequencial: int,
) -> Contratacao:
    """Fetch a specific procurement process detail.

    API: GET /v1/orgaos/{cnpj}/compras/{ano}/{sequencial}
    """
    url = f"{ORGAOS_URL}/{cnpj}/compras/{ano}/{sequencial}"
    data: dict[str, Any] = await http_get(url)
    return _parse_contratacao(data)


def _parse_item_pca(item: dict[str, Any]) -> ItemPca:
    """Parse a PCA item from API response."""
    return ItemPca(
        numero_item=item.get("numeroItem"),
        descricao=item.get("descricaoItem"),
        quantidade_estimada=item.get("quantidadeEstimada"),
        valor_unitario=item.get("valorUnitario"),
        valor_total=item.get("valorTotal"),
        unidade_fornecimento=item.get("unidadeFornecimento"),
        categoria=item.get("categoriaItemPcaNome") or item.get("nomeClassificacaoCatalogo"),
        data_desejada=item.get("dataDesejada"),
    )


def _parse_pca(item: dict[str, Any]) -> Pca:
    """Parse a PCA from API response."""
    raw_itens = item.get("itens", [])
    return Pca(
        orgao_cnpj=item.get("orgaoEntidadeCnpj"),
        orgao_nome=item.get("orgaoEntidadeRazaoSocial"),
        ano=item.get("anoPca"),
        unidade_nome=item.get("nomeUnidade"),
        id_pca=item.get("idPcaPncp"),
        data_publicacao=item.get("dataPublicacaoPNCP"),
        itens=[_parse_item_pca(i) for i in raw_itens] if isinstance(raw_itens, list) else [],
    )


async def buscar_pca(
    ano: int,
    codigo_classificacao: str = "0",
    *,
    pagina: int = 1,
    tamanho: int = 10,
) -> PcaResultado:
    """Search Annual Procurement Plans (PCA) by year.

    API: GET /v1/pca/
    Required: anoPca, codigoClassificacaoSuperior, pagina.
    """
    params: dict[str, str] = {
        "anoPca": str(ano),
        "codigoClassificacaoSuperior": codigo_classificacao,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 500)),
    }
    data: dict[str, Any] = await http_get(PCA_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []
    pcas = [_parse_pca(item) for item in items]
    return PcaResultado(
        total=data.get("totalRegistros", len(pcas)),
        pcas=pcas,
    )


async def buscar_pca_atualizacao(
    data_inicio: str,
    data_fim: str,
    *,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> PcaResultado:
    """Search PCA by global update date.

    API: GET /v1/pca/atualizacao
    Required: dataInicio, dataFim, pagina.
    """
    dt_ini = normalizar_data(data_inicio)
    dt_fim = normalizar_data(data_fim)
    validar_periodo(dt_ini, dt_fim)

    params: dict[str, str] = {
        "dataInicio": dt_ini,
        "dataFim": dt_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 500)),
    }
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao

    data: dict[str, Any] = await http_get(f"{PCA_URL}/atualizacao", params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []
    pcas = [_parse_pca(item) for item in items]
    return PcaResultado(
        total=data.get("totalRegistros", len(pcas)),
        pcas=pcas,
    )


async def buscar_pca_usuario(
    ano: int,
    id_usuario: int,
    *,
    cnpj_orgao: str | None = None,
    codigo_classificacao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> PcaResultado:
    """Search PCA items by year and user ID.

    API: GET /v1/pca/usuario
    Required: anoPca, idUsuario, pagina.
    """
    params: dict[str, str] = {
        "anoPca": str(ano),
        "idUsuario": str(id_usuario),
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 500)),
    }
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao
    if codigo_classificacao:
        params["codigoClassificacaoSuperior"] = codigo_classificacao

    data: dict[str, Any] = await http_get(f"{PCA_URL}/usuario", params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []
    pcas = [_parse_pca(item) for item in items]
    return PcaResultado(
        total=data.get("totalRegistros", len(pcas)),
        pcas=pcas,
    )


def _parse_instrumento_cobranca(item: dict[str, Any]) -> InstrumentoCobranca:
    """Parse an instrument of billing from API response."""
    contrato = item.get("recuperarContratoDTO", {}) or {}
    tipo = item.get("tipoInstrumentoCobranca", {}) or {}
    nfe = item.get("notaFiscalEletronica", {}) or {}
    return InstrumentoCobranca(
        cnpj_orgao=item.get("cnpj"),
        ano_contrato=contrato.get("anoContrato"),
        numero_instrumento=item.get("numeroInstrumentoCobranca"),
        tipo_nome=tipo.get("nome"),
        data_emissao=item.get("dataEmissaoDocumento"),
        objeto_contrato=contrato.get("objetoContrato"),
        fornecedor_nome=nfe.get("nomeEmitente") or contrato.get("nomeRazaoSocialFornecedor"),
        fornecedor_cnpj=nfe.get("niEmitente") or contrato.get("niFornecedor"),
        valor_nf=nfe.get("valorNotaFiscal"),
        chave_nfe=item.get("chaveNFe"),
    )


async def buscar_instrumentos_cobranca(
    data_inicial: str,
    data_final: str,
    *,
    tipo: int | None = None,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> InstrumentoCobrancaResultado:
    """Search billing instruments (invoices) by inclusion date.

    API: GET /v1/instrumentoscobranca/inclusao
    Required: dataInicial, dataFinal, pagina.
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 100)),
    }
    if tipo:
        params["tipoInstrumentoCobranca"] = str(tipo)
    if cnpj_orgao:
        params["cnpjOrgao"] = cnpj_orgao

    data: dict[str, Any] = await http_get(INSTRUMENTOS_COBRANCA_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []
    instrumentos = [_parse_instrumento_cobranca(item) for item in items]
    return InstrumentoCobrancaResultado(
        total=data.get("totalRegistros", len(instrumentos)),
        instrumentos=instrumentos,
    )


# ---------------------------------------------------------------------------
# Busca textual do portal (/api/search) — sem OpenAPI, ver constants.py
# ---------------------------------------------------------------------------


def _lista_busca(valores: str | None, *, maiusculas: bool = False) -> str | None:
    """Turn 'DF, GO' or 'DF|GO' into the portal's pipe-separated format."""
    if not valores:
        return None
    partes = [v.strip() for v in re.split(r"[|,;]", valores) if v.strip()]
    if maiusculas:
        partes = [p.upper() for p in partes]
    return "|".join(partes) or None


def _parse_documento_pesquisa(item: dict[str, Any]) -> DocumentoPesquisa:
    """Parse a search hit (edital, ata or contrato)."""
    item_url = item.get("item_url") or ""
    tipo = item.get("document_type") or item.get("doc_type")
    is_edital = tipo == "edital"
    return DocumentoPesquisa(
        tipo=tipo,
        titulo=item.get("title"),
        descricao=item.get("description"),
        numero_controle_pncp=item.get("numero_controle_pncp"),
        orgao_cnpj=item.get("orgao_cnpj"),
        orgao_nome=item.get("orgao_nome"),
        unidade_nome=item.get("unidade_nome"),
        ano=_to_int(item.get("ano")),
        numero_sequencial=_to_int(item.get("numero_sequencial")),
        municipio=item.get("municipio_nome"),
        uf=item.get("uf"),
        modalidade_nome=item.get("modalidade_licitacao_nome"),
        situacao_nome=item.get("situacao_nome"),
        data_publicacao=item.get("data_publicacao_pncp"),
        # Em editais, a vigência do índice é o período de recebimento de propostas.
        data_inicio=(
            item.get("data_inicio_recebimento_propostas") if is_edital else None
        ) or item.get("data_inicio_vigencia"),
        data_fim=(item.get("data_fim_recebimento_propostas") if is_edital else None)
        or item.get("data_fim_vigencia"),
        valor_global=item.get("valor_global"),
        fornecedor_nome=item.get("fornecedor_nome"),
        fornecedor_ni=item.get("fornecedor_ni"),
        tem_resultado=item.get("tem_resultado"),
        link_pncp=_link_portal_documento(item_url),
    )


def _link_portal_documento(item_url: str) -> str | None:
    """Portal link from a search hit's item_url.

    The index uses /compras/... for editais, but the portal route is /editais/...
    """
    if not item_url.startswith("/"):
        return None
    if item_url.startswith("/compras/"):
        item_url = "/editais/" + item_url[len("/compras/") :]
    return f"{PORTAL_URL}{item_url}"


def _to_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


async def pesquisar(
    texto: str,
    *,
    tipo: str = "edital",
    status: str | None = None,
    ufs: str | None = None,
    modalidades: str | None = None,
    data_publicacao_inicio: str | None = None,
    data_publicacao_fim: str | None = None,
    pagina: int = 1,
    tamanho: int = 20,
) -> PesquisaResultado:
    """Full-text search on the PNCP portal index.

    API: GET /api/search/?q=...&tipos_documento=...&status=...
    Undocumented: an unknown status is silently treated as 'todos', so it is
    validated here against SEARCH_STATUS.
    """
    tipo = (tipo or "edital").strip().lower()
    if tipo not in SEARCH_STATUS:
        msg = f"tipo inválido: '{tipo}'. Use um de: {', '.join(SEARCH_STATUS)}."
        raise ValueError(msg)
    status = (status or SEARCH_STATUS_PADRAO[tipo]).strip().lower()
    if status not in SEARCH_STATUS[tipo]:
        msg = (
            f"status inválido para {tipo}: '{status}'. "
            f"Use um de: {', '.join(SEARCH_STATUS[tipo])}."
        )
        raise ValueError(msg)
    if not texto or not texto.strip():
        raise ValueError("Informe o texto da busca.")

    params: dict[str, str] = {
        "q": texto.strip(),
        "tipos_documento": tipo,
        "status": status,
        "ordenacao": "-data",
        "pagina": str(max(pagina, 1)),
        "tam_pagina": str(min(max(tamanho, 1), MAX_PAGE_SIZE_SEARCH)),
    }
    if ufs_param := _lista_busca(ufs, maiusculas=True):
        params["ufs"] = ufs_param
    if mod_param := _lista_busca(modalidades):
        params["modalidades"] = mod_param
    if data_publicacao_inicio:
        dt = datetime.strptime(normalizar_data(data_publicacao_inicio), "%Y%m%d")
        params["data_publicacao_inicio"] = dt.strftime("%Y-%m-%d")
    if data_publicacao_fim:
        dt = datetime.strptime(normalizar_data(data_publicacao_fim), "%Y%m%d")
        params["data_publicacao_fim"] = dt.strftime("%Y-%m-%d")

    # A busca do PNCP derruba cerca de metade das conexões (reset logo após o
    # TLS, em menos de 0,5 s), de qualquer IP e mesmo sem rajada. Como a falha
    # é rápida e às vezes vem em blocos de alguns segundos, compensa tentar
    # muitas vezes com esperas curtas: 0,5 s, 1 s, 2 s e depois 3 s (~20 s no
    # pior caso), em vez do backoff longo padrão.
    data: dict[str, Any] = await http_get(
        SEARCH_URL,
        params=params,
        max_retries=SEARCH_MAX_RETRIES,
        backoff_base=0.5,
        max_wait=3.0,
    )
    items = data.get("items", []) if isinstance(data, dict) else []
    if not isinstance(items, list):
        items = []
    return PesquisaResultado(
        total=data.get("total", len(items)) if isinstance(data, dict) else len(items),
        documentos=[_parse_documento_pesquisa(i) for i in items],
    )


# ---------------------------------------------------------------------------
# Leitura de uma contratação (/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq})
# ---------------------------------------------------------------------------

# Só contratações (tipo 1). Contratos usam -2- e atas têm sufixo -NNNNNN.
_NUMERO_CONTROLE_RE = re.compile(r"^(\d{14})-1-(\d+)/(\d{4})$")


def resolver_compra(
    cnpj: str | None = None,
    ano: int | None = None,
    sequencial: int | None = None,
    numero_controle_pncp: str | None = None,
) -> tuple[str, int, int]:
    """Return (cnpj, ano, sequencial) from explicit keys or a PNCP control number.

    Control number format: CNPJ-1-SEQUENCIAL/ANO (e.g. 00394494000136-1-001203/2026).
    """
    if numero_controle_pncp:
        m = _NUMERO_CONTROLE_RE.match(numero_controle_pncp.strip())
        if not m:
            msg = (
                f"numero_controle_pncp inválido: '{numero_controle_pncp}'. "
                "Formato esperado: CNPJ-1-SEQUENCIAL/ANO (ex.: 00394494000136-1-001203/2026)."
            )
            raise ValueError(msg)
        return m.group(1), int(m.group(3)), int(m.group(2))
    cnpj_limpo = re.sub(r"\D", "", cnpj or "")
    if len(cnpj_limpo) != 14 or not ano or not sequencial:
        msg = "Informe numero_controle_pncp ou cnpj (14 dígitos), ano e sequencial."
        raise ValueError(msg)
    return cnpj_limpo, int(ano), int(sequencial)


def _compra_url(cnpj: str, ano: int, sequencial: int) -> str:
    return f"{ORGAOS_URL}/{cnpj}/compras/{ano}/{sequencial}"


def _como_lista(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        items = data.get("data", data.get("resultado", []))
        return items if isinstance(items, list) else []
    return []


async def listar_itens_contratacao(
    cnpj: str, ano: int, sequencial: int, *, pagina: int = 1, tamanho: int = 50
) -> list[ItemContratacao]:
    """API: GET /orgaos/{cnpj}/compras/{ano}/{sequencial}/itens"""
    params = {"pagina": str(max(pagina, 1)), "tamanhoPagina": str(min(max(tamanho, 1), 50))}
    data = await http_get(f"{_compra_url(cnpj, ano, sequencial)}/itens", params=params)
    return [
        ItemContratacao(
            numero_item=i.get("numeroItem"),
            descricao=i.get("descricao"),
            material_ou_servico=i.get("materialOuServicoNome"),
            quantidade=i.get("quantidade"),
            unidade_medida=i.get("unidadeMedida"),
            valor_unitario_estimado=i.get("valorUnitarioEstimado"),
            valor_total=i.get("valorTotal"),
            situacao=i.get("situacaoCompraItemNome"),
            criterio_julgamento=i.get("criterioJulgamentoNome"),
            beneficio=i.get("tipoBeneficioNome"),
            tem_resultado=i.get("temResultado"),
        )
        for i in _como_lista(data)
    ]


async def listar_resultados_item(
    cnpj: str, ano: int, sequencial: int, numero_item: int
) -> list[ResultadoItem]:
    """API: GET /orgaos/{cnpj}/compras/{ano}/{sequencial}/itens/{numeroItem}/resultados"""
    url = f"{_compra_url(cnpj, ano, sequencial)}/itens/{numero_item}/resultados"
    data = await http_get(url)
    return [
        ResultadoItem(
            fornecedor_ni=r.get("niFornecedor"),
            fornecedor_nome=r.get("nomeRazaoSocialFornecedor"),
            porte=r.get("porteFornecedorNome"),
            quantidade_homologada=r.get("quantidadeHomologada"),
            valor_unitario_homologado=r.get("valorUnitarioHomologado"),
            valor_total_homologado=r.get("valorTotalHomologado"),
            situacao=r.get("situacaoCompraItemResultadoNome"),
            data_resultado=r.get("dataResultado"),
        )
        for r in _como_lista(data)
    ]


def url_publica_arquivo(url: str | None) -> str | None:
    """Swap the internal API host returned in file URLs for the public one."""
    if not url:
        return url
    return re.sub(ARQUIVO_URL_INTERNA_RE, ARQUIVO_URL_PUBLICA, url, count=1)


async def listar_arquivos_contratacao(
    cnpj: str, ano: int, sequencial: int
) -> list[ArquivoContratacao]:
    """API: GET /orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos"""
    params = {"pagina": "1", "tamanhoPagina": "50"}
    data = await http_get(f"{_compra_url(cnpj, ano, sequencial)}/arquivos", params=params)
    return [
        ArquivoContratacao(
            sequencial=a.get("sequencialDocumento"),
            tipo=a.get("tipoDocumentoNome") or a.get("tipoDocumentoDescricao"),
            titulo=a.get("titulo"),
            data_publicacao=a.get("dataPublicacaoPncp"),
            url=url_publica_arquivo(a.get("url") or a.get("uri")),
        )
        for a in _como_lista(data)
        if a.get("statusAtivo", True)
    ]


async def listar_historico_contratacao(
    cnpj: str, ano: int, sequencial: int
) -> list[EventoHistorico]:
    """API: GET /orgaos/{cnpj}/compras/{ano}/{sequencial}/historico (newest first)."""
    params = {"pagina": "1", "tamanhoPagina": "50"}
    data = await http_get(f"{_compra_url(cnpj, ano, sequencial)}/historico", params=params)
    eventos = [
        EventoHistorico(
            data=h.get("logManutencaoDataInclusao"),
            tipo=h.get("tipoLogManutencaoNome"),
            categoria=h.get("categoriaLogManutencaoNome"),
            documento=h.get("documentoTitulo"),
            item_numero=h.get("itemNumero"),
            justificativa=h.get("justificativa"),
            usuario=h.get("usuarioNome"),
        )
        for h in _como_lista(data)
    ]
    eventos.sort(key=lambda e: e.data or "", reverse=True)
    return eventos
