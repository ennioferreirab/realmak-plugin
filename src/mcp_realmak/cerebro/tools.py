"""Ferramentas do cérebro (Galeed): consulta e envio de documentos ao acervo.

A chave usada em cada chamada é a do próprio usuário, tirada do token Bearer
verificado na requisição. Cada chave está presa a exatamente um cérebro. Para quem
entrou pelo login de pessoa (OAuth), vai a chave de serviço do servidor com o
e-mail da pessoa no header X-Galeed-Act-As, e vale o grant dela.
"""

from __future__ import annotations

import base64
import binascii
import json
import shlex
from typing import Annotated, Any, Literal
from urllib.parse import quote

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import get_access_token
from pydantic import Field

from ..capping import dumps
from ..config import NOMES_EMPRESAS, Settings, load_settings
from ..licitacao import arquivos
from .client import CONTEXTO_ENVIO_MAX_BYTES, GaleedApiError, GaleedClient
from .empresas import EMPRESA_DESC, Empresa, EmpresaLiberada, get_empresas

Sistema = Literal["macos", "linux", "windows"]
AcaoEnvio = Literal["enviar", "substituir"]
LIMITE_DIRETO = 1024 * 1024  # 1 MB direto; acima disso, link assinado de upload
LIMITE_ARQUIVOS_PASTA = 100

OS_DESC = (
    "Sistema do computador onde o analista vai abrir os arquivos originais: macos, linux ou "
    "windows. Os analistas da Realmak usam windows: passe 'windows', salvo indicação de outro sistema (o servidor exige). "
    "O link a entregar é original.link (válido por 30 minutos; abre a visualização com botão para baixar, "
    "ou '?b=1' para baixar direto); sem ele, original.brain_link (Abrir) e original.brain_download_link (Baixar). "
    "Sempre exatamente como veio."
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


def sem_link_de_arquivo(valor: Any) -> Any:
    """Tira os links `file://` (os_open_link) que o gateway ainda manda: só abrem na rede interna."""
    if isinstance(valor, dict):
        return {k: sem_link_de_arquivo(v) for k, v in valor.items() if k != "os_open_link"}
    if isinstance(valor, list):
        return [sem_link_de_arquivo(v) for v in valor]
    return valor


def com_links_de_arquivo(
    valor: Any,
    settings: Settings,
    email: str,
    empresa: Empresa,
    _cache: dict[str, dict[str, Any]] | None = None,
) -> Any:
    """Para a pessoa logada, troca os links do painel (pedem login) pelo link curto único (/a/<codigo>).

    Vale para cada `original` com slug da página (`original.slug` ou `slug` ao lado). Sem slug, fica como veio.
    """
    cache = {} if _cache is None else _cache
    if isinstance(valor, list):
        return [com_links_de_arquivo(v, settings, email, empresa, cache) for v in valor]
    if not isinstance(valor, dict):
        return valor
    saida = {k: com_links_de_arquivo(v, settings, email, empresa, cache) for k, v in valor.items()}
    original = saida.get("original")
    if isinstance(original, dict):
        slug = next((s for s in (original.get("slug"), valor.get("slug")) if isinstance(s, str) and s), None)
        if slug:
            curto = cache.get(slug)
            if curto is None:
                nome = ""
                if isinstance(original.get("file_path"), str):
                    nome = original["file_path"].replace("\\", "/").rsplit("/", 1)[-1]
                dados = {"t": "cerebro", "e": email, "m": empresa, "s": slug}
                curto = arquivos.link_curto(settings, dados, nome=nome)
                cache[slug] = curto
            saida["original"] = {
                **{k: v for k, v in original.items() if k not in ("brain_link", "brain_download_link")},
                **curto,
            }
    return saida


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
    payload = sem_link_de_arquivo(data if isinstance(data, dict) else {"resultado": data})
    email = (request_access().claims or {}).get("email")
    settings = load_settings()
    if email and arquivos.links_disponiveis(settings):
        payload = com_links_de_arquivo(payload, settings, email, empresa)
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
            case 409:
                return f"Cérebro: conflito ou documento ambíguo (409): {corpo}. Informe o sha256 exato obtido em cerebro_buscar."
            case 413:
                return f"Cérebro: arquivo acima do limite permitido (413): {corpo}."
            case 415:
                return f"Cérebro: tipo de arquivo não suportado (415): {corpo}."
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
    include_facts: Annotated[bool | None, Field(description="Se verdadeiro, anexa os fatos tipados relacionados à busca (seguem o mesmo filtro de incluir_historico; omitidos vão em historico_omitido.fatos).")] = None,
    os: Annotated[Sistema | None, Field(description=OS_DESC)] = None,
    empresa: Annotated[Empresa, Field(description=EMPRESA_DESC)] = "realmak",
    incluir_historico: Annotated[bool, Field(description="Padrão false (traz só documentos vigentes e devolve historico_omitido.aviso quando há versões anteriores/vencidas ocultas). Passe true só quando a pessoa pedir o histórico/versão antiga ou for preciso provar o que foi entregue numa licitação ou contrato.")] = False,
) -> str:
    """Busca no cérebro da empresa escolhida (texto e semântica) e devolve trechos com fonte, estado_documento (vigente|substituido|vencido, rotulo e substituido_por), comentarios ({total, ultimos}) e nota_revisao (quando existirem), além do link curto do arquivo original (original.link, 30 minutos), sem redigir resposta. Por padrão (incluir_historico=false) retorna só os documentos vigentes e informa historico_omitido.aviso quando houver versões anteriores ou vencidas ocultas. Sempre mostre à pessoa os comentarios e nota_revisao devolvidos. Use para qualquer pergunta sobre funcionários, responsáveis técnicos, atestados, CATs, ARTs, contratos, licitações e atas. Não gasta LLM. Monte a resposta a partir dos trechos e diga o que ficou sem confirmação."""
    return await executar(empresa, "retrieve", query, limit, include_facts, os, incluir_historico)


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
    incluir_historico: Annotated[bool, Field(description="Padrão false (omite fatos de documentos substituídos ou vencidos e traz historico_omitido.aviso). Passe true só quando a pessoa pedir versão antiga ou histórico.")] = False,
) -> str:
    """Lista fatos registrados no cérebro, com status, confiança, estado_documento e janela de validade. Por padrão (incluir_historico=false) omite fatos de documentos substituídos ou vencidos e informa historico_omitido.aviso. Informação registrada não comprova validade documental nem atendimento a edital. Não gasta LLM. Pagina por cursor: quando a resposta trouxer 'cursor', há mais páginas."""
    return await executar(empresa, "facts", dim=dim, area=area, status=status, as_of=as_of,
                          min_confidence=min_confidence, limit=limit, cursor=cursor, os=os,
                          incluir_historico=incluir_historico)


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
    incluir_historico: Annotated[bool, Field(description="Padrão false (omite provas de documentos substituídos ou vencidos e traz historico_omitido.aviso). Passe true só quando a pessoa pedir versão antiga ou histórico.")] = False,
) -> str:
    """Provas dos registros: para cada id devolvido por cerebro_consulta, o documento, a posição, estado_documento, comentarios ({total, ultimos}), nota_revisao e o trecho literal de cada valor, com o arquivo original (original.file_path e original.link, válido por 30 minutos; sem ele, original.brain_link e original.brain_download_link). Por padrão (incluir_historico=false) omite provas de documentos substituídos ou vencidos e informa historico_omitido.aviso. Sempre mostre à pessoa os comentarios e nota_revisao devolvidos. Não gasta LLM."""
    return await executar(empresa, "provas", list(ids), os, incluir_historico)


def _nome_base(caminho: str) -> str:
    limpo = caminho.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not limpo or limpo in (".", ".."):
        raise ToolError(f"Cérebro: nome de arquivo inválido: {caminho!r}.")
    return limpo


def _montar_contexto(
    acao: AcaoEnvio,
    comentario: str | None,
    email: str,
    substitui_sha256: str | None,
    substitui_caminho: str | None,
) -> dict[str, Any]:
    sha = (substitui_sha256 or "").strip()
    caminho = (substitui_caminho or "").strip()
    if acao == "substituir" and not (sha or caminho):
        raise ToolError(
            "Cérebro: para acao='substituir', informe substitui_sha256 ou substitui_caminho "
            "(busque o documento antigo com cerebro_buscar)."
        )
    if sha or caminho:
        acao = "substituir"
    contexto: dict[str, Any] = {"origem": "mcp", "acao": acao}
    if comentario and comentario.strip():
        contexto["comentario"] = comentario.strip()
    if email:
        contexto["quem"] = email
    if sha or caminho:
        substitui: dict[str, str] = {}
        if sha:
            substitui["sha256"] = sha
        if caminho:
            substitui["caminho_rel"] = caminho
        contexto["substitui"] = substitui
    codificado = quote(json.dumps(contexto, ensure_ascii=False, separators=(",", ":")), safe="")
    if len(codificado.encode("ascii")) > CONTEXTO_ENVIO_MAX_BYTES:
        raise ToolError("Cérebro: contexto do envio excede o limite de 8 KB. Encurte o comentario.")
    return contexto


async def cerebro_enviar(
    empresa: Annotated[Empresa, Field(description=EMPRESA_DESC)] = "realmak",
    nome: Annotated[str | None, Field(description="Nome de um arquivo único com extensão (ex.: Realmak-Sublime_03496338000174_2026-11-25.pdf). Para enviar vários arquivos de uma pasta numa chamada, use 'nomes'.")] = None,
    nomes: Annotated[list[str] | None, Field(min_length=1, max_length=LIMITE_ARQUIVOS_PASTA, description="Lista de arquivos (ou caminhos locais de uma pasta) para enviar em lote numa chamada. Devolve um link assinado por arquivo e um comando único de envio.")] = None,
    conteudo_texto: Annotated[str | None, Field(description="Conteúdo de texto UTF-8 de um arquivo único, até 1 MB. Não use com 'nomes'.")] = None,
    conteudo_base64: Annotated[str | None, Field(description="Conteúdo binário em base64 de um arquivo único, até 1 MB. Para arquivo maior que 1 MB, omita o conteúdo para receber o link assinado de envio (curl --upload-file).")] = None,
    comentario: Annotated[str | None, Field(max_length=2000, description="O que a pessoa disse sobre o arquivo ou pasta (finalidade, data, o que atualiza).")] = None,
    acao: Annotated[AcaoEnvio, Field(description="'enviar' para documento novo ou 'substituir' para atualizar documento existente no acervo (busque o antigo com cerebro_buscar e informe substitui_sha256 ou substitui_caminho).")] = "enviar",
    substitui_sha256: Annotated[str | None, Field(description="SHA-256 do documento antigo a substituir (obtido com cerebro_buscar ou cerebro_provas). Em acao='substituir', envie junto com substitui_caminho sempre que possível.")] = None,
    substitui_caminho: Annotated[str | None, Field(description="Caminho relativo do documento antigo no acervo (ex.: realmak\\habilitacao\\certidoes\\vigentes\\arquivo.pdf). Em acao='substituir', envie junto com substitui_sha256 para evitar ambiguidade se o mesmo SHA existir em mais de uma pasta.")] = None,
) -> str:
    """Envia um arquivo ou uma pasta (vários arquivos) ao cérebro da empresa escolhida, com comentário e contexto. Nunca apaga nem move documentos existentes. Até 1 MB de arquivo único vai direto em conteudo_texto ou conteudo_base64; arquivo maior (até 100 MB) ou pasta (nomes) devolve links assinados de uso único (15 minutos) e comando curl --upload-file. Para atualizar um documento existente (ex.: cartão CNPJ novo, certidão renovada), busque o antigo com cerebro_buscar e envie com acao='substituir', substitui_sha256 e substitui_caminho. Depois, confirme o estado (recebido -> na_caixa -> organizado/revisao/duplicado/recusado) e destino final com cerebro_envios."""
    if bool(nome) == bool(nomes):
        raise ToolError("Cérebro: informe 'nome' (arquivo único) ou 'nomes' (lista de arquivos de uma pasta), não os dois.")
    if conteudo_texto is not None and conteudo_base64 is not None:
        raise ToolError("Cérebro: informe conteudo_texto ou conteudo_base64, não os dois.")
    if nomes and (conteudo_texto is not None or conteudo_base64 is not None):
        raise ToolError("Cérebro: para enviar vários arquivos ('nomes'), não envie conteúdo direto; use os links assinados devolvidos.")

    client, _ = await client_for_request(empresa)
    access = request_access()
    email = str((access.claims or {}).get("email") or "")
    settings = load_settings()
    contexto = _montar_contexto(acao, comentario, email, substitui_sha256, substitui_caminho)

    if nomes:
        if not email or not arquivos.links_disponiveis(settings):
            raise ToolError("Cérebro: envio por link exige login de pessoa (OAuth) e URL pública configurada neste servidor.")
        envios: list[dict[str, Any]] = []
        comandos: list[str] = []
        for caminho_local in nomes:
            nome_arquivo = _nome_base(caminho_local)
            dados = {"t": "cerebro_enviar", "e": email, "m": empresa, "n": nome_arquivo, "c": contexto}
            link_info = arquivos.link(settings, "cerebro-envio/", dados)
            cmd = f"curl -fsS --upload-file {shlex.quote(caminho_local)} {shlex.quote(link_info['url'])}"
            envios.append({"caminho": caminho_local, "nome": nome_arquivo, **link_info, "comando": cmd})
            comandos.append(cmd)
        return dumps({
            "empresa": empresa,
            "total": len(envios),
            "envios": envios,
            "comando": " && ".join(comandos),
            "expira_em": envios[0]["expira_em"],
            "limite_mb": max(settings.arquivo_max_bytes, arquivos.CEREBRO_ENVIO_MAX_BYTES) // (1024 * 1024),
        })

    assert nome is not None
    nome_arquivo = _nome_base(nome)
    if conteudo_texto is None and conteudo_base64 is None:
        if not email or not arquivos.links_disponiveis(settings):
            raise ToolError("Cérebro: envio por link exige login de pessoa (OAuth) e URL pública configurada neste servidor.")
        dados = {"t": "cerebro_enviar", "e": email, "m": empresa, "n": nome_arquivo, "c": contexto}
        link_info = arquivos.link(settings, "cerebro-envio/", dados)
        return dumps({
            "empresa": empresa,
            "nome": nome_arquivo,
            **link_info,
            "comando": f"curl -fsS --upload-file {shlex.quote(nome)} {shlex.quote(link_info['url'])}",
            "limite_mb": max(settings.arquivo_max_bytes, arquivos.CEREBRO_ENVIO_MAX_BYTES) // (1024 * 1024),
        })

    if conteudo_texto is not None:
        conteudo = conteudo_texto.encode("utf-8")
        content_type = "text/plain; charset=utf-8"
    else:
        try:
            conteudo = base64.b64decode(conteudo_base64 or "", validate=True)
        except (binascii.Error, ValueError):
            raise ToolError("Cérebro: conteudo_base64 inválido.") from None
        content_type = "application/octet-stream"
    if not conteudo:
        raise ToolError("Cérebro: arquivo vazio.")
    if len(conteudo) > LIMITE_DIRETO:
        raise ToolError("Cérebro: acima de 1 MB direto na chamada. Chame sem conteúdo para receber o link de envio.")
    try:
        status, resp = await client.enviar(nome_arquivo, conteudo, contexto=contexto, content_type=content_type)
    except GaleedApiError as exc:
        raise ToolError(explicar_erro(exc)) from None
    corpo = (
        {"empresa": empresa, "http_status": status, "repetido": status == 200, **resp}
        if isinstance(resp, dict)
        else {"empresa": empresa, "http_status": status, "repetido": status == 200, "resultado": resp}
    )
    return dumps(corpo)


async def cerebro_envios(
    empresa: Annotated[Empresa, Field(description=EMPRESA_DESC)] = "realmak",
    limite: Annotated[int | None, Field(ge=1, le=200, description="Máximo de envios recentes a retornar (1–200, padrão 50).")] = None,
    sha256: Annotated[str | None, Field(description="Filtra pelo SHA-256 (64 hex) do arquivo enviado.")] = None,
    envio_id: Annotated[str | None, Field(description="Filtra pelo UUID do envio devolvido por cerebro_enviar.")] = None,
) -> str:
    """Consulta o andamento dos envios ao cérebro da empresa (estados: recebido, na_caixa, organizado, revisao, duplicado, recusado; destino final e motivo de revisão). Use após cerebro_enviar para confirmar que o documento entrou na pasta correta."""
    return await executar(empresa, "envios", limite=limite, sha256=sha256, envio_id=envio_id)


async def cerebro_comentar(
    texto: Annotated[str, Field(min_length=1, max_length=4000, description="Texto do comentário/anotação a registrar no documento (até 4000 caracteres).")],
    empresa: Annotated[Empresa, Field(description=EMPRESA_DESC)] = "realmak",
    sha256: Annotated[str | None, Field(description="SHA-256 (64 hex) do documento existente no cérebro (preferível, evita ambiguidade).")] = None,
    caminho: Annotated[str | None, Field(description="Caminho relativo ou nome único do arquivo no acervo, quando não tiver o SHA-256.")] = None,
) -> str:
    """Registra um comentário/anotação em um documento que já está no cérebro da empresa (histórico só de acréscimo; não edita nem apaga). O comentário passa a aparecer em cerebro_buscar e cerebro_provas. Prefira passar sha256 obtido em cerebro_buscar para evitar erro 409 por nome ambíguo."""
    texto_limpo = texto.strip()
    sha = (sha256 or "").strip() or None
    cam = (caminho or "").strip() or None
    if not texto_limpo:
        raise ToolError("Cérebro: informe o texto do comentário.")
    if not sha and not cam:
        raise ToolError("Cérebro: informe sha256 ou caminho do documento a comentar.")
    return await executar(empresa, "comentar", texto_limpo, sha256=sha, caminho=cam)


async def cerebro_comentarios(
    empresa: Annotated[Empresa, Field(description=EMPRESA_DESC)] = "realmak",
    sha256: Annotated[str | None, Field(description="SHA-256 (64 hex) do documento no cérebro.")] = None,
    caminho: Annotated[str | None, Field(description="Caminho relativo ou nome único do arquivo no acervo, quando não tiver o SHA-256.")] = None,
) -> str:
    """Lista todos os comentários registrados e a nota_revisao de um documento no cérebro da empresa. Use quando cerebro_buscar indicar mais de 3 comentários ou para conferir anotações completas."""
    sha = (sha256 or "").strip() or None
    cam = (caminho or "").strip() or None
    if not sha and not cam:
        raise ToolError("Cérebro: informe sha256 ou caminho do documento.")
    return await executar(empresa, "comentarios", sha256=sha, caminho=cam)


INSTRUCOES = """Cérebros das empresas do grupo (Realmak, AForça, Nortfort, UNA, Sublime):
- Comece com cerebro_empresas sem argumentos ({}) uma vez por conversa: diz quais empresas você pode consultar, o nível
  de acesso (total ou parcial) e quais têm o dataset de registros.
- Nas demais ferramentas cerebro_*, passe `empresa` explicitamente: realmak, aforca, nortfort,
  una ou sublime (aliases minúsculos, nunca `brain`). Se a pergunta não diz a empresa e o contexto não deixa
  dúvida, use realmak e diga na resposta que ela se refere à Realmak. Se o contexto deixar dúvida
  sobre a empresa, pergunte antes de consultar ou enviar.
- Pergunta sobre "o grupo" ou "todas as empresas": consulte cada empresa liberada e separe a resposta
  por empresa.
- Diga sempre de que empresa veio cada resultado. Os ids de cerebro_consulta valem só para
  cerebro_provas da mesma empresa.
- Acesso parcial: diga quais áreas foram consultadas e que pode haver documentos fora delas.
- Sem acesso a uma empresa: diga isso. Não use outra empresa no lugar.
- Pergunta sobre pessoa, assunto ou documento: cerebro_buscar (include_facts=true anexa os fatos) e
  cerebro_fatos. Monte a resposta a partir dos trechos.
- Apelidos de documentos que não aparecem no texto oficial: ao buscar pelo apelido, busque também pelo título oficial:
  - cartão CNPJ -> "comprovante de inscrição e de situação cadastral"
  - CND federal / conjunta -> "certidão negativa de débitos relativos aos tributos federais"
  - CRF / FGTS -> "certificado de regularidade do fgts"
  - CNDT / trabalhista -> "certidão negativa de débitos trabalhistas"
- Documentos vigentes x substituídos/vencidos em cerebro_buscar, cerebro_fatos e cerebro_provas:
  - Responda sempre com o documento vigente (incluir_historico=false é o padrão nas três ferramentas, inclusive para `include_facts` em `cerebro_buscar`). Quando a resposta trouxer `historico_omitido.aviso`, mencione que versões anteriores/vencidas não foram mostradas.
  - Só use `incluir_historico=true` e cite versões anteriores se a pessoa pedir ou se for preciso provar o que foi entregue numa licitação ou contrato.
  - Cada item com `original.sha256` traz `estado_documento` (`vigente`, `substituido` ou `vencido`, `rotulo` e `substituido_por`). Ao citar um documento `substituido` (inclusive cópia em pasta de ata ou contrato), diga que há versão posterior — não diga que o documento estava vencido quando foi entregue.
  - `cerebro_consulta` (SQL) não filtra por estado do documento; somente `cerebro_provas` aplica o filtro.
- Pergunta que precisa de todos os casos (contar, somar, listar): confira registros=true para a empresa
  em cerebro_empresas; cerebro_esquema uma vez por empresa, depois cerebro_consulta e cerebro_provas.
  A presença das ferramentas não garante registros para todas as empresas. Sem registros, informe que
  busca e fatos não garantem contagem completa. Empresas indisponíveis não tiveram seu acesso verificado.
- cerebro_buscar/cerebro_fatos recebem `limit`; cerebro_consulta recebe `limite` (em português).
- Passe os='windows' somente em cerebro_buscar, cerebro_fatos e cerebro_provas, salvo outro sistema
  informado pelo analista. cerebro_esquema recebe só empresa; cerebro_consulta recebe sql, limite e empresa.
  cerebro_provas recebe ids como lista de strings reais da consulta, sempre na mesma empresa.
- Para enviar documento ou pasta ao acervo do cérebro, use sempre `cerebro_enviar` — nunca copie arquivos à mão para pastas ou compartilhamentos, e nunca apague nem mova documentos existentes.
  - Coloque em `comentario` o que a pessoa disse sobre o arquivo ou pasta.
  - Até 1 MB de arquivo único: envie direto (`conteudo_base64` ou `conteudo_texto`). Maior que 1 MB: chame sem conteúdo e execute o `comando` (`curl --upload-file`). Pasta / vários arquivos: passe a lista em `nomes` numa única chamada e rode o `comando` único devolvido.
  - Para documento que atualiza outro (ex.: cartão CNPJ novo, certidão renovada): busque o antigo com `cerebro_buscar`, pegue `substitui_sha256` e `substitui_caminho` do MESMO documento antigo e envie com `acao="substituir"` (se sha256 e caminho apontarem para vínculos diferentes, o servidor não altera o antigo).
  - Informe à pessoa o estado devolvido e confirme o destino final (ou motivo de revisão / resultado em `substituicao`) com `cerebro_envios`.
- Comentários e anotações em documentos existentes:
  - Quando `cerebro_buscar` ou `cerebro_provas` trouxer `comentarios` (`total`, `ultimos`) ou `nota_revisao`, mostre essas anotações à pessoa na resposta (elas registram alertas como razão social antiga, data divergente ou necessidade de emissão atualizada). Use `cerebro_comentarios` se precisar ver todos quando `total > 3`.
  - Quando a pessoa pedir para anotar ou comentar um documento já presente no cérebro, use `cerebro_comentar(empresa, sha256 ou caminho, texto)` — prefira `sha256` obtido em `cerebro_buscar` para evitar ambiguidade (409). Comentários só se acumulam; não editam nem apagam.
- Resultado com 'original': termine a resposta com a seção Arquivos, um item por sha256, em markdown e sem URL
  por extenso: '**nome** · [Visualizar](original.link)' e, na linha de baixo, 'Caminho: original.file_path'.
  Use a URL curta exatamente como veio, sem reescrever nem repetir. O link vale 30 minutos, não pede login,
  abre a visualização e traz o botão para baixar o original (no terminal, acrescente '?b=1'). Se faltar
  original.link, use '[Abrir](original.brain_link)' e '[Baixar arquivo](original.brain_download_link)' se
  existirem (exigem login do Odoo). Omita ações sem URL; sem nenhum link, só o Caminho. Sem 'original', a
  fonte é só texto indexado: não monte link.
- Em HTTP 5xx ou timeout do cérebro, aguarde e tente de novo. Se persistir, tente outra via de busca e registre a limitação.
- Em HTTP 400, corrija a consulta pelo esquema ou pela mensagem antes de reenviar.
- Nº de CAT, atestado ou contrato encontrado como pista: faça busca dirigida pelo identificador e confira o original.
"""


def build_cerebro_server() -> FastMCP:
    mcp = FastMCP("cerebro")
    ro: dict[str, Any] = {"readOnlyHint": True, "openWorldHint": False}
    escrita: dict[str, Any] = {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
    mcp.tool(cerebro_empresas, tags={"cerebro"}, annotations=ro)
    mcp.tool(cerebro_buscar, tags={"cerebro"}, annotations=ro)
    mcp.tool(cerebro_fatos, tags={"cerebro"}, annotations=ro)
    mcp.tool(cerebro_esquema, tags={"cerebro", REGISTROS_TAG}, annotations=ro)
    mcp.tool(cerebro_consulta, tags={"cerebro", REGISTROS_TAG}, annotations=ro)
    mcp.tool(cerebro_provas, tags={"cerebro", REGISTROS_TAG}, annotations=ro)
    mcp.tool(cerebro_enviar, tags={"cerebro"}, annotations=escrita)
    mcp.tool(cerebro_envios, tags={"cerebro"}, annotations=ro)
    mcp.tool(cerebro_comentar, tags={"cerebro"}, annotations=escrita)
    mcp.tool(cerebro_comentarios, tags={"cerebro"}, annotations=ro)
    return mcp
