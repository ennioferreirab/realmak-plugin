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
from ..config import NOMES_EMPRESAS, Settings, load_settings
from .client import GaleedApiError, GaleedClient
from .empresas import EMPRESA_DESC, Empresa, EmpresaLiberada, get_empresas

Sistema = Literal["macos", "linux", "windows"]

OS_DESC = (
    "Sistema do computador onde o analista vai abrir os arquivos originais: macos, linux ou "
    "windows. Os analistas da Realmak usam windows: passe 'windows', salvo indicação de outro sistema. Define o link "
    "original.os_open_link; entregue o link exatamente como veio."
)

REGISTROS_TAG = "registros"


def client_for_access(
    access: AccessToken, settings: Settings, transport: httpx.AsyncBaseTransport | None = None,
    empresa: Empresa = "realmak",
) -> GaleedClient:
    email = (access.claims or {}).get("email")
    return GaleedClient(
        settings.galeed_api_url, settings.service_keys.get(empresa, "") if email else access.token,
        timeout=settings.galeed_timeout_s, transport=transport, act_as=email or "",
    )


def request_access() -> AccessToken:
    access = get_access_token()
    if access is None or not access.token:
        raise ToolError("Cérebro: requisição sem chave. Envie o cabeçalho Authorization: Bearer <chave>.")
    return access


async def sem_acesso(empresa: Empresa, access: AccessToken) -> ToolError:
    liberadas = await get_empresas().empresas_liberadas(access)
    nomes = ", ".join(NOMES_EMPRESAS[e.empresa] for e in liberadas) or "nenhuma"
    return ToolError(f"Você não tem acesso à empresa {NOMES_EMPRESAS[empresa]}. Empresas liberadas: {nomes}. Veja cerebro_empresas.")


async def client_for_request(empresa: Empresa = "realmak") -> tuple[GaleedClient, EmpresaLiberada]:
    settings = load_settings()
    if not settings.galeed_configured:
        raise ToolError("Cérebro: o servidor não tem GALEED_API_URL configurado.")
    if empresa not in settings.service_keys:
        raise ToolError(f"A empresa {NOMES_EMPRESAS[empresa]} não está configurada neste servidor.")
    access = request_access()
    descoberta = await get_empresas(settings).descobrir(access)
    liberada = next((e for e in descoberta.empresas if e.empresa == empresa), None)
    if not liberada:
        if not (access.claims or {}).get("email") and descoberta.empresas:
            nome = NOMES_EMPRESAS[descoberta.empresas[0].empresa]
            raise ToolError(f"Esta chave só lê a empresa {nome}.")
        if empresa in descoberta.indisponiveis:
            raise ToolError(f"Cérebro da empresa {NOMES_EMPRESAS[empresa]} indisponível. Tente de novo em instantes.")
        raise await sem_acesso(empresa, access)
    return client_for_access(access, settings, empresa=empresa), liberada


async def executar(empresa: Empresa, metodo: str, *args, **kwargs) -> str:
    client, acesso = await client_for_request(empresa)
    try:
        data = await getattr(client, metodo)(*args, **kwargs)
    except GaleedApiError as exc:
        if exc.status == 403:
            access = request_access()
            directory = get_empresas()
            directory.invalidar(access, empresa)
            fresh = await directory.descobrir(access)
            if not any(e.empresa == empresa for e in fresh.empresas):
                if empresa in fresh.indisponiveis:
                    raise ToolError(f"Cérebro da empresa {NOMES_EMPRESAS[empresa]} indisponível. Tente de novo em instantes.") from None
                raise await sem_acesso(empresa, access) from None
            if metodo in ("retrieve", "facts"):
                raise await sem_acesso(empresa, access) from None
        if metodo in ("esquema", "consulta", "provas"):
            raise ToolError(explicar_erro_registros(exc, "cerebro_" + metodo, empresa)) from None
        raise ToolError(explicar_erro(exc)) from None
    # Origem e escopo vêm antes do conteúdo: sobrevivem ao corte de respostas grandes.
    result: dict[str, Any] = {"empresa": empresa}
    if acesso.nivel == "parcial":
        result["acesso"] = {"nivel": "parcial", "areas": list(acesso.areas)}
    payload = data if isinstance(data, dict) else {"resultado": data}
    result.update({k: v for k, v in payload.items() if k not in ("empresa", "acesso")})
    return dumps(result)


async def cerebro_empresas() -> str:
    """Lista as empresas liberadas, o acesso total/parcial, as áreas e o dataset de registros. Chame uma vez por conversa."""
    return dumps((await get_empresas().descobrir(request_access())).publico())


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


def explicar_erro_registros(exc: Exception, ferramenta: str, empresa: Empresa = "realmak") -> str:
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
                    f"Cérebro: esta chave não lê o dataset de registros da empresa {NOMES_EMPRESAS[empresa]} (403). Ele exige uma chave "
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
    empresa: Annotated[Empresa, Field(description=EMPRESA_DESC)] = "realmak",
) -> str:
    """Busca no cérebro da empresa escolhida (texto e semântica) e devolve trechos com fonte e link do arquivo original, sem redigir resposta. Use para qualquer pergunta sobre funcionários, responsáveis técnicos, atestados, CATs, ARTs, contratos, licitações e atas. Não gasta LLM. Monte a resposta a partir dos trechos e diga o que ficou sem confirmação."""
    return await executar(empresa, "retrieve", query, limit, include_facts, os)


async def cerebro_fatos(
    dim: Annotated[str | None, Field(description="Dimensão dos fatos (ex.: decisions, action_items, precos). Padrão: decisions.")] = None,
    area: Annotated[str | None, Field(description="Filtra por área de conhecimento (trecho do nome).")] = None,
    status: Annotated[Literal["fact", "archived"] | None, Field(description="fact = vigente; archived = superado.")] = None,
    as_of: Annotated[str | None, Field(description="Data ISO 8601: o que era verdade nessa data.")] = None,
    min_confidence: Annotated[float | None, Field(ge=0, le=1, description="Confiança mínima, de 0 a 1.")] = None,
    limit: Annotated[int | None, Field(ge=1, le=200, description="Máximo de fatos por página (padrão 50, teto 200).")] = None,
    cursor: Annotated[str | None, Field(description="Cursor da página seguinte, devolvido na resposta anterior.")] = None,
    os: Annotated[Sistema | None, Field(description=OS_DESC)] = None,
    empresa: Annotated[Empresa, Field(description=EMPRESA_DESC)] = "realmak",
) -> str:
    """Lista fatos registrados no cérebro, com status, confiança e janela de validade. Informação registrada não comprova validade documental nem atendimento a edital. Não gasta LLM. Pagina por cursor: quando a resposta trouxer 'cursor', há mais páginas."""
    return await executar(empresa, "facts", dim=dim, area=area, status=status, as_of=as_of,
                          min_confidence=min_confidence, limit=limit, cursor=cursor, os=os)


async def cerebro_esquema(
    empresa: Annotated[Empresa, Field(description=EMPRESA_DESC)] = "realmak",
) -> str:
    """Esquema do dataset de registros tipados: tabelas, colunas, domínios de valor, regras de leitura, cobertura e exemplos de SQL. Chame uma vez por empresa e conversa, antes do primeiro cerebro_consulta. Não gasta LLM."""
    return await executar(empresa, "esquema")


async def cerebro_consulta(
    sql: Annotated[str, Field(description="Um SELECT ou WITH (PostgreSQL). Tabelas e colunas como o cerebro_esquema mostra.")],
    limite: Annotated[int | None, Field(ge=1, le=5000, description="Máximo de linhas (padrão 500, teto 5000).")] = None,
    empresa: Annotated[Empresa, Field(description=EMPRESA_DESC)] = "realmak",
) -> str:
    """Executa uma consulta SQL de leitura sobre o dataset de registros e devolve as linhas e a cobertura das tabelas. Use para perguntas que precisam de todos os casos: contar, somar, tirar média, listar. Chame cerebro_esquema antes: os nomes vêm de lá, e information_schema e pg_catalog são recusados. Guarde os ids dos registros usados e cite as provas com cerebro_provas. Não gasta LLM."""
    return await executar(empresa, "consulta", sql, limite)


async def cerebro_provas(
    ids: Annotated[list[str], Field(max_length=200, description="Ids de registro devolvidos por cerebro_consulta (até 200). Use a mesma empresa da consulta.")],
    os: Annotated[Sistema | None, Field(description=OS_DESC)] = None,
    empresa: Annotated[Empresa, Field(description=EMPRESA_DESC)] = "realmak",
) -> str:
    """Provas dos registros: para cada id devolvido por cerebro_consulta, o documento, a posição e o trecho literal de cada valor, com o arquivo original (original.file_path e original.os_open_link). Não gasta LLM."""
    return await executar(empresa, "provas", list(ids), os)


INSTRUCOES = """Cérebros das empresas do grupo (Realmak, AForça, Nortfort, UNA, Sublime):
- Comece com cerebro_empresas sem argumentos ({}) uma vez por conversa: diz quais empresas você pode consultar, o nível
  de acesso (total ou parcial) e quais têm o dataset de registros.
- Nas outras cinco ferramentas cerebro_*, passe `empresa` explicitamente: realmak, aforca, nortfort,
  una ou sublime (aliases minúsculos, nunca `brain`). Se a pergunta não diz a empresa e o contexto não deixa
  dúvida, use realmak e diga na resposta que ela se refere à Realmak. Se o contexto deixar dúvida
  sobre a empresa, pergunte antes de consultar.
- Pergunta sobre "o grupo" ou "todas as empresas": consulte cada empresa liberada e separe a resposta
  por empresa.
- Diga sempre de que empresa veio cada resultado. Os ids de cerebro_consulta valem só para
  cerebro_provas da mesma empresa.
- Acesso parcial: diga quais áreas foram consultadas e que pode haver documentos fora delas.
- Sem acesso a uma empresa: diga isso. Não use outra empresa no lugar.
- Pergunta sobre pessoa, assunto ou documento: cerebro_buscar (include_facts=true anexa os fatos) e
  cerebro_fatos. Monte a resposta a partir dos trechos.
- Pergunta que precisa de todos os casos (contar, somar, listar): confira registros=true para a empresa
  em cerebro_empresas; cerebro_esquema uma vez por empresa, depois cerebro_consulta e cerebro_provas.
  A presença das ferramentas não garante registros para todas as empresas. Sem registros, informe que
  busca e fatos não garantem contagem completa. Empresas indisponíveis não tiveram seu acesso verificado.
- cerebro_buscar/cerebro_fatos recebem `limit`; cerebro_consulta recebe `limite` (em português).
- Passe os='windows' somente em cerebro_buscar, cerebro_fatos e cerebro_provas, salvo outro sistema
  informado pelo analista. cerebro_esquema recebe só empresa; cerebro_consulta recebe sql, limite e empresa.
  cerebro_provas recebe ids como lista de strings reais da consulta, sempre na mesma empresa.
- Resultado com 'original': termine a resposta com a seção Arquivos (nome, os_open_link exatamente
  como veio, file_path), um item por sha256. Sem 'original', a fonte é só texto indexado: não monte link.
- Erro do cérebro diz o que mudar; não repita a mesma chamada sem mudar nada.
"""


def build_cerebro_server() -> FastMCP:
    mcp = FastMCP("cerebro")
    ro: dict[str, Any] = {"readOnlyHint": True, "openWorldHint": False}
    mcp.tool(cerebro_empresas, tags={"cerebro"}, annotations=ro)
    mcp.tool(cerebro_buscar, tags={"cerebro"}, annotations=ro)
    mcp.tool(cerebro_fatos, tags={"cerebro"}, annotations=ro)
    mcp.tool(cerebro_esquema, tags={"cerebro", REGISTROS_TAG}, annotations=ro)
    mcp.tool(cerebro_consulta, tags={"cerebro", REGISTROS_TAG}, annotations=ro)
    mcp.tool(cerebro_provas, tags={"cerebro", REGISTROS_TAG}, annotations=ro)
    return mcp
