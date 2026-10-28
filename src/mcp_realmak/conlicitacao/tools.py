"""Ferramentas do ConLicitação, somente leitura.

Busca e detalhe usam o site (login com cookie de sessão). Filtros, boletins e
pregões monitorados usam a API oficial (token). Não há ferramentas de escrita
nem de download de edital.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from ..capping import dumps
from ..config import load_settings
from .api import ConlicitacaoApiClient
from .errors import ConlicitacaoError
from .format import (
    casa_busca,
    detalhar_licitacao,
    resumir_acompanhamento,
    resumir_item_site,
    resumir_licitacao_boletim,
    scrub,
)
from .site import ConlicitacaoSiteClient

log = logging.getLogger("mcp_realmak.conlicitacao")

UF_IDS = {
    "AC": 1, "AL": 2, "AM": 3, "AP": 4, "BA": 5, "CE": 6, "DF": 7, "ES": 8, "GO": 9, "MA": 10,
    "MG": 11, "MS": 12, "MT": 13, "PA": 14, "PB": 15, "PE": 16, "PI": 17, "PR": 18, "RJ": 19,
    "RN": 20, "RO": 21, "RR": 22, "RS": 23, "SC": 24, "SE": 25, "SP": 26, "TO": 27,
}
MODALIDADES = {"dispensa": 7, "pregao_eletronico": 10, "concorrencia": 4}

# Clientes únicos do processo: guardam a sessão do site e o lock de login.
_site: ConlicitacaoSiteClient | None = None
_site_key: tuple | None = None


def get_site_client() -> ConlicitacaoSiteClient:
    global _site, _site_key
    s = load_settings()
    key = (s.conlicitacao_url, s.conlicitacao_login, s.conlicitacao_site_password, s.conlicitacao_session_file)
    if _site is None or _site_key != key:
        _site = ConlicitacaoSiteClient(
            s.conlicitacao_url, s.conlicitacao_login, s.conlicitacao_site_password, s.conlicitacao_session_file
        )
        _site_key = key
    return _site


def get_api_client() -> ConlicitacaoApiClient:
    s = load_settings()
    return ConlicitacaoApiClient(s.conlicitacao_url, s.conlicitacao_token)


def _falha(exc: Exception) -> ToolError:
    if isinstance(exc, ConlicitacaoError):
        return ToolError(f"ConLicitação: {exc}")
    log.warning("Erro inesperado no ConLicitação: %s", type(exc).__name__)
    return ToolError("ConLicitação: erro inesperado ao consultar. Tente de novo.")


def _paginacao(data: dict, default_page: int) -> dict:
    pag = data.get("pagination") if isinstance(data.get("pagination"), dict) else {}
    return {
        "pagina": pag.get("page", data.get("page", default_page)),
        "total_paginas": pag.get("total_pages", data.get("total_pages")),
        "total_registros": pag.get("total_entries", data.get("total_entries")),
    }


async def conlicitacao_buscar_licitacao(
    uasg: Annotated[str | None, Field(description="Código UASG do órgão. Use junto com numero_edital (ex.: 160089).")] = None,
    numero_edital: Annotated[str | None, Field(description="Número do edital como 112/2026 (com a barra). Use junto com uasg.")] = None,
    processo: Annotated[str | None, Field(description="Número do processo administrativo, como está no edital.")] = None,
    id_conlicitacao: Annotated[int | None, Field(description="ID da licitação no ConLicitação.")] = None,
    orgao: Annotated[str | None, Field(description="Nome do órgão (texto).")] = None,
    objeto: Annotated[str | None, Field(description="Palavras do objeto da licitação.")] = None,
    itens: Annotated[str | None, Field(description="Palavras da descrição dos itens.")] = None,
    uf: Annotated[str | None, Field(description="Sigla da UF do órgão, como DF ou GO.")] = None,
    modalidade: Annotated[Literal["dispensa", "pregao_eletronico", "concorrencia"] | None, Field(description="Modalidade.")] = None,
    somente_vigentes: Annotated[bool, Field(description="Só licitações com sessão ainda por vir.")] = False,
    busca_exata: Annotated[bool, Field(description="Para orgao, objeto e itens: não aceita variações das palavras.")] = False,
    pagina: Annotated[int, Field(ge=1, description="Página (20 resultados por página).")] = 1,
) -> str:
    """Acha uma licitação no site do ConLicitação. Comece pelo dado mais exato do edital: uasg com numero_edital, ou o processo, ou o id_conlicitacao. A busca só alcança licitações classificadas nas atividades contratadas pela Realmak; fora desse perfil, use as ferramentas de compras (PNCP). Devolve uma lista resumida com id, link para abrir no site, órgão, objeto, datas e situação; para itens, datas completas e impugnações use conlicitacao_detalhe_licitacao."""
    filtros: list[tuple[str, str | int]] = []
    if uasg:
        filtros.append(("orgao_uasg", uasg.strip()))
    if numero_edital:
        filtros.append(("notice_number", numero_edital.strip()))
    if processo:
        filtros.append(("processo", processo.strip()))
    if id_conlicitacao:
        filtros.append(("id", id_conlicitacao))
    if orgao:
        filtros.append(("nome_orgao", orgao.strip()))
    if objeto:
        filtros.append(("objeto", objeto.strip()))
    if itens:
        filtros.append(("itens", itens.strip()))
    if uf:
        sigla = uf.strip().upper()
        if sigla not in UF_IDS:
            raise ToolError(f"UF inválida: {uf!r}. Use a sigla, como DF ou GO.")
        filtros.append(("orgao_estado_id[]", UF_IDS[sigla]))
    if modalidade:
        filtros.append(("modalities_ids[]", MODALIDADES[modalidade]))
    if somente_vigentes:
        filtros.append(("vigente_somente", "true"))
    if busca_exata and (orgao or objeto or itens):
        filtros.append(("exact_search", "true"))
    if not filtros:
        raise ToolError("Informe pelo menos um filtro (uasg e numero_edital, processo, id, órgão, objeto, UF...).")
    try:
        data = await get_site_client().buscar(filtros, pagina)
    except Exception as exc:  # noqa: BLE001
        raise _falha(exc) from None
    biddings = data.get("biddings") if isinstance(data.get("biddings"), list) else []
    return dumps(
        {
            "total_registros": data.get("total_entries"),
            "total_paginas": data.get("total_pages"),
            "pagina": pagina,
            "licitacoes": [resumir_item_site(b) for b in biddings if isinstance(b, dict)],
        }
    )


async def conlicitacao_detalhe_licitacao(
    id_conlicitacao: Annotated[int, Field(gt=0, description="ID da licitação no ConLicitação (vem da busca).")],
    incluir_resumo: Annotated[bool, Field(description="Anexa o resumo gerado pelo ConLicitação, quando existir.")] = False,
) -> str:
    """Licitação completa do site do ConLicitação: objeto, modalidade, itens, datas, situações, garantias, link do edital no portal de origem e nomes dos arquivos do edital. Os avisos, esclarecimentos e impugnações publicados vêm em 'bidding_info_em_ordem_de_data', do mais antigo ao mais recente: eles podem mudar exigências e datas em relação ao PDF do edital. Não devolve links de download."""
    client = get_site_client()
    try:
        data = await client.obter_licitacao(id_conlicitacao)
        out = detalhar_licitacao(data)
        if incluir_resumo:
            out["resumo_conlicitacao"] = scrub(await client.obter_resumo(id_conlicitacao))
    except Exception as exc:  # noqa: BLE001
        raise _falha(exc) from None
    return dumps(out)


async def conlicitacao_listar_filtros() -> str:
    """Lista os filtros da Realmak no ConLicitação, com o id do filtro e o último boletim fechado. Ponto de partida para conlicitacao_listar_boletins e conlicitacao_ler_boletim."""
    try:
        data = await get_api_client().filtros()
    except Exception as exc:  # noqa: BLE001
        raise _falha(exc) from None
    return dumps(data)


async def conlicitacao_listar_boletins(
    filtro_id: Annotated[int, Field(gt=0, description="ID do filtro (de conlicitacao_listar_filtros).")],
    pagina: Annotated[int, Field(ge=1)] = 1,
    por_pagina: Annotated[int, Field(ge=1, le=100)] = 20,
    ordem: Annotated[Literal["asc", "desc"], Field(description="desc = mais recentes primeiro.")] = "desc",
) -> str:
    """Lista os boletins de um filtro (o boletim fecha três vezes por dia e não muda depois de fechado). Paginado: use pagina e por_pagina."""
    try:
        data = await get_api_client().boletins(filtro_id, pagina, por_pagina, ordem)
    except Exception as exc:  # noqa: BLE001
        raise _falha(exc) from None
    return dumps(data)


async def conlicitacao_ler_boletim(
    boletim_id: Annotated[int, Field(gt=0, description="ID do boletim (de conlicitacao_listar_boletins).")],
    secao: Annotated[Literal["licitacoes", "acompanhamentos"], Field(description="Qual parte do boletim ler.")] = "licitacoes",
    busca: Annotated[str | None, Field(description="Filtra por texto no objeto, órgão, edital ou processo (sem diferenciar maiúsculas).")] = None,
    pagina: Annotated[int, Field(ge=1)] = 1,
    por_pagina: Annotated[int, Field(ge=1, le=50)] = 20,
) -> str:
    """Lê um boletim de forma resumida e paginada. Um boletim traz centenas de licitações; esta ferramenta devolve só uma página com órgão, UASG, edital, objeto encurtado, datas e valores, e os nomes (nunca os links) dos arquivos do edital. Use 'busca' para achar algo no boletim e 'pagina' para avançar. 'acompanhamentos' são os resultados e atas das licitações já acompanhadas; não são as mensagens do pregão."""
    try:
        data = await get_api_client().boletim(boletim_id)
    except Exception as exc:  # noqa: BLE001
        raise _falha(exc) from None
    brutos = data.get("licitacoes" if secao == "licitacoes" else "acompanhamentos")
    brutos = [b for b in brutos if isinstance(b, dict)] if isinstance(brutos, list) else []
    if busca:
        brutos = [
            b for b in brutos
            if casa_busca(
                busca, b.get("objeto"), b.get("edital"), b.get("processo"), b.get("sintese"),
                (b.get("orgao") or {}).get("nome") if isinstance(b.get("orgao"), dict) else None,
            )
        ]
    total = len(brutos)
    inicio = (pagina - 1) * por_pagina
    fatia = brutos[inicio : inicio + por_pagina]
    resumir = resumir_licitacao_boletim if secao == "licitacoes" else resumir_acompanhamento
    cab: dict[str, Any] = data.get("boletim") if isinstance(data.get("boletim"), dict) else {}
    return dumps(
        {
            "boletim": {
                "id": cab.get("id"),
                "numero_edicao": cab.get("numero_edicao"),
                "datahora_fechamento": cab.get("datahora_fechamento"),
                "quantidade_licitacoes": cab.get("quantidade_licitacoes"),
                "quantidade_acompanhamentos": cab.get("quantidade_acompanhamentos"),
            },
            "secao": secao,
            "busca": busca,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "total_nesta_secao": total,
            "tem_mais": inicio + por_pagina < total,
            "itens": [resumir(b) for b in fatia],
        }
    )


async def conlicitacao_pregoes_monitorados(
    pagina: Annotated[int, Field(ge=1)] = 1,
    por_pagina: Annotated[int, Field(ge=1, le=50)] = 15,
) -> str:
    """Lista os pregões eletrônicos monitorados no ConLicitação (acompanhamento do chat da sessão), com situação, datas, órgão e se há mensagens novas. O id da licitação (bidding_id) serve em conlicitacao_mensagens_pregao. Só lista: não liga nem desliga monitoramento."""
    try:
        data = await get_api_client().monitoradas(pagina, por_pagina)
    except Exception as exc:  # noqa: BLE001
        raise _falha(exc) from None
    lista = data.get("electronics_trading") or data.get("electronic_trading")
    lista = lista if isinstance(lista, list) else []
    itens = []
    for t in lista:
        if not isinstance(t, dict):
            continue
        b = t.get("bidding") if isinstance(t.get("bidding"), dict) else {}
        corpo = b.get("public_body") if isinstance(b.get("public_body"), dict) else {}
        itens.append(
            {
                "bidding_id": t.get("bidding_id"),
                "situacao": t.get("trading_situation"),
                "edital": b.get("edital") or t.get("edital"),
                "orgao": corpo.get("nome"),
                "uasg": corpo.get("uasg") or t.get("uasg"),
                "objeto": b.get("objeto") and str(b["objeto"])[:300],
                "inicio": t.get("initial_date"),
                "fim": t.get("final_date"),
                "ultima_mensagem": t.get("last_message_time"),
                "tem_mensagens": t.get("have_messages"),
                "tem_mensagens_novas": t.get("have_new_messages"),
            }
        )
    return dumps(
        {
            "pagina": data.get("page", pagina),
            "total_paginas": data.get("total_pages"),
            "total_registros": data.get("total_entries"),
            "pregoes": itens,
        }
    )


async def conlicitacao_mensagens_pregao(
    bidding_id: Annotated[int, Field(gt=0, description="ID da licitação monitorada (bidding_id).")],
    pagina: Annotated[int, Field(ge=1)] = 1,
    por_pagina: Annotated[int, Field(ge=1, le=100)] = 50,
) -> str:
    """Mensagens do chat de um pregão monitorado (pregoeiro, fornecedores e sistema), com horário. A licitação precisa estar monitorada. Paginado."""
    try:
        data = await get_api_client().mensagens(bidding_id, pagina, por_pagina)
    except Exception as exc:  # noqa: BLE001
        raise _falha(exc) from None
    msgs = data.get("trading_messages") if isinstance(data.get("trading_messages"), list) else []
    return dumps(
        {
            "bidding_id": data.get("bidding_id", bidding_id),
            **_paginacao(data, pagina),
            "mensagens": [
                {
                    "horario": m.get("message_time"),
                    "quem": m.get("message_holder"),
                    "texto": m.get("message_highlight"),
                    "lote": m.get("lot"),
                }
                for m in msgs
                if isinstance(m, dict)
            ],
        }
    )


def build_conlicitacao_server() -> FastMCP:
    mcp = FastMCP("conlicitacao")
    ro: dict[str, Any] = {"readOnlyHint": True, "openWorldHint": True}
    for fn in (
        conlicitacao_buscar_licitacao,
        conlicitacao_detalhe_licitacao,
        conlicitacao_listar_filtros,
        conlicitacao_listar_boletins,
        conlicitacao_ler_boletim,
        conlicitacao_pregoes_monitorados,
        conlicitacao_mensagens_pregao,
    ):
        mcp.tool(fn, tags={"conlicitacao"}, annotations=ro)
    return mcp
