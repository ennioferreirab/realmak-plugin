"""Ferramentas do cérebro (Galeed), só leitura.

A chave usada em cada chamada é a do próprio usuário, tirada do token Bearer
verificado na requisição. Cada chave está presa a exatamente um cérebro. Para quem
entrou pelo login de pessoa (OAuth), vai a chave de serviço do servidor com o
e-mail da pessoa no header X-Galeed-Act-As, e vale o grant dela.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import get_access_token
from pydantic import Field

from ..capping import dumps
from ..config import Settings, load_settings
from .client import GaleedApiError, GaleedClient

Sistema = Literal["macos", "linux", "windows"]

OS_DESC = (
    "Sistema do computador onde o analista vai abrir os arquivos originais: macos, linux ou "
    "windows. Os analistas da Realmak usam windows: passe 'windows'. Define o link "
    "original.os_open_link; entregue o link exatamente como veio."
)

REGISTROS_TAG = "registros"


def client_for_access(
    access: AccessToken, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> GaleedClient:
    email = (access.claims or {}).get("email") if isinstance(access, AccessToken) else None
    if email:
        return GaleedClient(
            settings.galeed_api_url, settings.galeed_service_key, timeout=settings.galeed_timeout_s,
            transport=transport, act_as=email,
        )
    return GaleedClient(settings.galeed_api_url, access.token, timeout=settings.galeed_timeout_s, transport=transport)


def client_for_request() -> GaleedClient:
    settings = load_settings()
    if not settings.galeed_configured:
        raise ToolError("Cérebro: o servidor não tem GALEED_API_URL configurado.")
    access = get_access_token()
    if access is None or not access.token:
        raise ToolError("Cérebro: requisição sem chave. Envie o cabeçalho Authorization: Bearer <chave>.")
    return client_for_access(access, settings)


def explicar_erro(exc: Exception) -> str:
    """Traduz o erro do gateway numa mensagem que diz o que fazer."""
    if isinstance(exc, GaleedApiError):
        corpo = exc.body or str(exc)
        match exc.status:
            case 401:
                return "Cérebro: chave inválida ou revogada (401). Peça uma chave nova a quem administra o cérebro."
            case 402:
                return (
                    "Cérebro: o limite diário de custo deste cérebro foi atingido (402). "
                    "Tente amanhã ou avise quem administra o cérebro."
                )
            case 403:
                return f"Cérebro: esta chave não tem permissão para isso (403): {corpo}"
            case 429:
                return "Cérebro: limite de requisições atingido (429). Aguarde alguns segundos e tente de novo."
            case 400:
                return f"Cérebro: requisição inválida (400): {corpo}. Ajuste os argumentos e tente de novo."
            case 404:
                return f"Cérebro: não encontrado (404): {corpo}."
            case 0:
                return f"Cérebro: falha de conexão com o gateway: {exc}. Tente de novo em instantes."
            case _:
                return f"Cérebro: erro do gateway (HTTP {exc.status}): {corpo}."
    return f"Cérebro: erro inesperado: {type(exc).__name__}."


def explicar_erro_registros(exc: Exception, ferramenta: str) -> str:
    """Nas ferramentas de registros, 403/404/503 têm outro sentido."""
    if isinstance(exc, GaleedApiError):
        corpo = exc.body or str(exc)
        match exc.status:
            case 400 if ferramenta == "cerebro_consulta":
                return (
                    f"Cérebro: consulta recusada (400): {corpo}. As tabelas e colunas estão em "
                    "cerebro_esquema (information_schema e pg_catalog não estão disponíveis). "
                    "Confira os nomes lá e tente de novo."
                )
            case 403:
                return (
                    "Cérebro: esta chave não lê o dataset de registros (403). Ele exige uma chave "
                    "com acesso total a um cérebro com o módulo de registros ligado. "
                    "Use cerebro_fatos ou cerebro_buscar."
                )
            case 404:
                return "Cérebro: este servidor não tem o dataset de registros (404). Use cerebro_fatos ou cerebro_buscar."
            case 503:
                return (
                    f"Cérebro: o dataset de registros ainda não está disponível (503): {corpo}. "
                    "Tente mais tarde ou use cerebro_fatos."
                )
            case 429:
                return (
                    f"Cérebro: servidor ocupado ou limite de taxa atingido (429): {corpo}. "
                    "Tente de novo em instantes, sem disparar várias consultas em paralelo."
                )
    return explicar_erro(exc)


async def cerebro_buscar(
    query: Annotated[str, Field(description="A busca em linguagem natural. Use nomes, números e termos do documento.")],
    limit: Annotated[int | None, Field(ge=1, le=20, description="Máximo de trechos (padrão 8, teto 20).")] = None,
    include_facts: Annotated[bool | None, Field(description="Se verdadeiro, anexa os fatos tipados relacionados à busca.")] = None,
    os: Annotated[Sistema | None, Field(description=OS_DESC)] = None,
) -> str:
    """Busca no cérebro da Realmak (texto e semântica) e devolve trechos com fonte e link do arquivo original, sem redigir resposta. Use para qualquer pergunta sobre funcionários, responsáveis técnicos, atestados, CATs, ARTs, contratos, licitações e atas. Não gasta LLM. Monte a resposta a partir dos trechos e diga o que ficou sem confirmação."""
    try:
        return dumps(await client_for_request().retrieve(query, limit, include_facts, os))
    except GaleedApiError as exc:
        raise ToolError(explicar_erro(exc)) from None


async def cerebro_fatos(
    dim: Annotated[str | None, Field(description="Dimensão dos fatos (ex.: decisions, action_items, precos). Padrão: decisions.")] = None,
    area: Annotated[str | None, Field(description="Filtra por área de conhecimento (trecho do nome).")] = None,
    status: Annotated[Literal["fact", "archived"] | None, Field(description="fact = vigente; archived = superado.")] = None,
    as_of: Annotated[str | None, Field(description="Data ISO 8601: o que era verdade nessa data.")] = None,
    min_confidence: Annotated[float | None, Field(ge=0, le=1, description="Confiança mínima, de 0 a 1.")] = None,
    limit: Annotated[int | None, Field(ge=1, le=200, description="Máximo de fatos por página (padrão 50, teto 200).")] = None,
    cursor: Annotated[str | None, Field(description="Cursor da página seguinte, devolvido na resposta anterior.")] = None,
    os: Annotated[Sistema | None, Field(description=OS_DESC)] = None,
) -> str:
    """Lista fatos consolidados do cérebro, só os verificados, com status, confiança e janela de validade. Não gasta LLM. Pagina por cursor: quando a resposta trouxer 'cursor', há mais páginas."""
    try:
        data = await client_for_request().facts(
            dim=dim, area=area, status=status, as_of=as_of, min_confidence=min_confidence,
            limit=limit, cursor=cursor, os=os,
        )
        return dumps(data)
    except GaleedApiError as exc:
        raise ToolError(explicar_erro(exc)) from None


async def cerebro_esquema() -> str:
    """Esquema do dataset de registros tipados: tabelas, colunas, domínios de valor, regras de leitura, cobertura e exemplos de SQL. Chame uma vez por conversa, antes do primeiro cerebro_consulta. Não gasta LLM."""
    try:
        return dumps(await client_for_request().esquema())
    except GaleedApiError as exc:
        raise ToolError(explicar_erro_registros(exc, "cerebro_esquema")) from None


async def cerebro_consulta(
    sql: Annotated[str, Field(description="Um SELECT ou WITH (PostgreSQL). Tabelas e colunas como o cerebro_esquema mostra.")],
    limite: Annotated[int | None, Field(ge=1, le=5000, description="Máximo de linhas (padrão 500, teto 5000).")] = None,
) -> str:
    """Executa uma consulta SQL de leitura sobre o dataset de registros e devolve as linhas e a cobertura das tabelas. Use para perguntas que precisam de todos os casos: contar, somar, tirar média, listar. Chame cerebro_esquema antes: os nomes vêm de lá, e information_schema e pg_catalog são recusados. Guarde os ids dos registros usados e cite as provas com cerebro_provas. Não gasta LLM."""
    try:
        return dumps(await client_for_request().consulta(sql, limite))
    except GaleedApiError as exc:
        raise ToolError(explicar_erro_registros(exc, "cerebro_consulta")) from None


async def cerebro_provas(
    ids: Annotated[list[str], Field(max_length=200, description="Ids de registro devolvidos por cerebro_consulta (até 200).")],
    os: Annotated[Sistema | None, Field(description=OS_DESC)] = None,
) -> str:
    """Provas dos registros: para cada id devolvido por cerebro_consulta, o documento, a posição e o trecho literal de cada valor, com o arquivo original (original.file_path e original.os_open_link). Não gasta LLM."""
    try:
        return dumps(await client_for_request().provas(list(ids), os))
    except GaleedApiError as exc:
        raise ToolError(explicar_erro_registros(exc, "cerebro_provas")) from None


INSTRUCOES = (
    "Cérebro da Realmak:\n"
    "- Pergunta sobre pessoa, assunto ou documento: cerebro_buscar (include_facts=true anexa os "
    "fatos) e cerebro_fatos. Monte a resposta a partir dos trechos.\n"
    "- Pergunta que precisa de todos os casos (contar, somar, listar): cerebro_esquema uma vez, "
    "depois cerebro_consulta e cerebro_provas, quando essas ferramentas estiverem disponíveis.\n"
    "- Passe os='windows' nas leituras: os analistas usam Windows.\n"
    "- Resultado com 'original': termine a resposta com a seção Arquivos (nome, os_open_link exatamente "
    "como veio, file_path), um item por sha256. Sem 'original', a fonte é só texto indexado: não monte link.\n"
    "- Erro do cérebro diz o que mudar; não repita a mesma chamada sem mudar nada."
)


def build_cerebro_server() -> FastMCP:
    mcp = FastMCP("cerebro")
    ro: dict[str, Any] = {"readOnlyHint": True, "openWorldHint": False}
    mcp.tool(cerebro_buscar, tags={"cerebro"}, annotations=ro)
    mcp.tool(cerebro_fatos, tags={"cerebro"}, annotations=ro)
    mcp.tool(cerebro_esquema, tags={"cerebro", REGISTROS_TAG}, annotations=ro)
    mcp.tool(cerebro_consulta, tags={"cerebro", REGISTROS_TAG}, annotations=ro)
    mcp.tool(cerebro_provas, tags={"cerebro", REGISTROS_TAG}, annotations=ro)
    return mcp
