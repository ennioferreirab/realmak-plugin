"""Resolve a fonte da licitação e usa o CRM para conferir/criar o card."""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastmcp.exceptions import ToolError

from ..compras._shared.http_client import http_get
from ..compras.dadosabertos import client as dados_abertos
from ..compras.dadosabertos.constants import API_BASE as COMPRAS_API
from ..compras.dadosabertos.schemas import Licitacao
from ..compras.exceptions import HttpClientError
from ..compras.pncp import client as pncp
from ..config import load_settings
from ..conlicitacao.format import link_licitacao
from ..conlicitacao.tools import get_site_client
from .client import OdooApiError, OdooClient


def _link_card(card: dict) -> str:
    base = load_settings().oauth_public_url.rstrip("/")
    caminho = f"/odoo/licitacoes/{card['id']}"
    return f"{base}{caminho}" if base else caminho


def _proximos_passos(
    fonte: str,
    *,
    etapa: str | None = None,
    criado: bool = False,
    somente_conferir: bool = False,
) -> list[str]:
    if somente_conferir:
        if fonte in ("pncp", "conlicitacao"):
            return [
                "Use somente_conferir=false para criar o card no Acervo. "
                "A plataforma completa os campos pela fonte e inicia download, extração e classificação (Jev) automaticamente na chegada."
            ]
        return [
            "Use somente_conferir=false para criar o card no Acervo com todos os campos encontrados no portal; "
            "depois baixe o edital e os anexos do portal e envie com licitacao_enviar_arquivo(destino='documento')."
        ]
    etapa_texto = (etapa or "").strip()
    em_acervo = not etapa_texto or etapa_texto.casefold() == "acervo"
    if not em_acervo:
        return [f"Card já está na etapa {etapa_texto}."]
    prefixo = "Card criado no Acervo." if criado else "Card já está no Acervo."
    if fonte in ("pncp", "conlicitacao"):
        return [
            f"{prefixo} A plataforma completa os campos pela fonte e inicia o download, "
            "a extração e a classificação (Jev) dos documentos automaticamente no Acervo."
        ]
    return [
        f"{prefixo} Baixe o edital e os anexos do portal oficial e envie com "
        "licitacao_enviar_arquivo(destino='documento') para extração e classificação (Jev) no Acervo."
    ]


async def existente(odoo: OdooClient, **referencia: Any) -> dict | None:
    try:
        return (await odoo.chamar("pasta", referencia))["licitacao"]
    except OdooApiError as exc:
        if exc.status != 404:
            raise
        return None


def resultado(card: dict, criado: bool, tentativas: list[str], **campos: Any) -> dict:
    return {
        "licitacao": card, "chave": card["chave"], "fonte": card["fonte"],
        "link_card": _link_card(card),
        "criado": criado, "ja_existia": not criado, "tentativas": tentativas,
        "proximos_passos": _proximos_passos(card["fonte"], etapa=card.get("etapa"), criado=criado),
        **campos,
    }


def numero_edital(valor: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"\s*(?:[A-Za-z]+/)?(\d+)\s*/\s*(\d{4})\s*", valor)
    return (int(match[1]), int(match[2])) if match else None


async def localizar_pncp(dados: dict, data: date | None) -> tuple[str, int, int] | None:
    busca = dados.get("processo") or dados.get("orgao")
    edital = numero_edital(dados.get("edital", ""))
    if not busca and not (dados.get("uasg") and edital):
        return None
    if not busca:
        busca = dados["uasg"]
    pagina = await pncp.pesquisar(busca, tamanho=50)
    if pagina.total > 50:
        raise ToolError("Busca no PNCP incompleta. Informe o link ou controle PNCP.")
    candidatos = []
    for item in pagina.documentos:
        if not item.numero_controle_pncp:
            continue
        if edital and item.ano != edital[1]:
            continue
        ref = pncp.resolver_compra(numero_controle_pncp=item.numero_controle_pncp)
        detalhe = await consultar_pncp(ref)
        if detalhe.get("numeroControlePNCP") and corresponde_pncp(detalhe, dados, data):
            candidatos.append(ref)
    if len(set(candidatos)) > 1:
        raise ToolError("Busca no PNCP ambígua ou incompleta. Informe o link ou controle PNCP.")
    return candidatos[0] if candidatos else None


def corresponde_pncp(item: dict, dados: dict, data: date | None) -> bool:
    unidade = item.get("unidadeOrgao") or {}
    uasg = dados.get("uasg")
    processo = dados.get("processo")
    edital = numero_edital(dados.get("edital", ""))
    if uasg and unidade.get("codigoUnidade") != uasg:
        return False
    if processo and item.get("processo") != processo:
        return False
    if edital and numero_edital(f"{item.get('numeroCompra')}/{item.get('anoCompra')}") != edital:
        return False
    datas = ("dataPublicacaoPncp", "dataAberturaProposta", "dataEncerramentoProposta")
    if data and not any(str(item.get(campo, "")).startswith(data.isoformat()) for campo in datas):
        return False
    orgao = dados.get("orgao")
    nome = (item.get("orgaoEntidade") or {}).get("razaoSocial") or ""
    return bool(processo or (edital and (uasg or (orgao and orgao.casefold() in nome.casefold()))))


async def consultar_pncp(ref: tuple[str, int, int]) -> dict:
    cnpj, ano, sequencial = ref
    return await http_get(f"{pncp.CONTRATACAO_DETALHE_URL}/{cnpj}/compras/{ano}/{sequencial}")


def dados_pncp(item: dict) -> dict:
    unidade = item.get("unidadeOrgao") or {}
    orgao = item.get("orgaoEntidade") or {}
    return {
        "objeto": item.get("objetoCompra"), "orgao": orgao.get("razaoSocial"),
        "uasg": unidade.get("codigoUnidade"), "cidade": unidade.get("municipioNome"),
        "uf": unidade.get("ufSigla"), "edital": f"{item['numeroCompra']}/{item['anoCompra']}",
        "modalidade": item.get("modalidadeNome"),
        "processo": item.get("processo"), "situacao": item.get("situacaoCompraNome"),
        "abertura": item.get("dataAberturaProposta"), "prazo": item.get("dataEncerramentoProposta"),
        "valor_estimado": item.get("valorTotalEstimado"),
    }


async def localizar_conlicitacao(dados: dict, data: date | None) -> int | None:
    filtros = [(campo, dados[chave]) for campo, chave in (
        ("orgao_uasg", "uasg"), ("notice_number", "edital"),
        ("processo", "processo"), ("nome_orgao", "orgao"),
    ) if dados.get(chave)]
    if not (dados.get("processo") or (dados.get("edital") and (dados.get("uasg") or dados.get("orgao")))):
        return None
    pagina = await get_site_client().buscar(filtros, 1)
    linhas = pagina.get("biddings")
    if not isinstance(linhas, list):
        raise ToolError("ConLicitação não devolveu uma lista de resultados. Tente novamente.")
    if data and len(linhas) > 1:
        filtradas = [linha for linha in linhas if any(
            str(linha.get(campo, "")).startswith(data.isoformat())
            for campo in ("datahora_abertura", "datahora_prazo", "datahora_documento", "data_validade")
        )]
        if filtradas:
            linhas = filtradas
    if len(linhas) > 1 or (pagina.get("total_pages") or 0) > 1:
        raise ToolError("Busca no ConLicitação ambígua. Informe o link ou ID exato.")
    return int(linhas[0]["id"]) if linhas else None


async def duplicado_outra_fonte(odoo: OdooClient, dados: dict) -> dict | None:
    processo = dados.get("processo")
    edital = dados.get("edital")
    uasg = dados.get("uasg")
    if not processo and not (edital and uasg):
        return None
    encontrados = {}
    termos = [(processo, None), (edital, uasg)]
    for termo, filtro_uasg in termos:
        if not termo:
            continue
        busca = await odoo.chamar("buscar", {"texto": termo, "uasg": filtro_uasg, "limite": 50})
        if busca["total"] > 50:
            raise ToolError("Busca de duplicados muito ampla. Informe um identificador oficial.")
        for linha in busca["licitacoes"]:
            card = await existente(odoo, licitacao_id=linha["id"])
            if card and (
                (processo and card.get("processo") == processo)
                or (uasg and card.get("uasg") == uasg and numero_edital(edital or "")
                    and numero_edital(card.get("edital") or "") == numero_edital(edital))
            ):
                encontrados[card["id"]] = card
    if len(encontrados) > 1:
        raise ToolError("Há mais de um card compatível no CRM. Confira os cards antes de criar.")
    return next(iter(encontrados.values()), None)


async def localizar_compras_historico(dados: dict, data: date) -> Licitacao | None:
    dia = data.isoformat()
    pagina = await dados_abertos.buscar_licitacoes(dia, dia, uasg=int(dados["uasg"]), tamanho=100)
    candidatos = [item for item in pagina.licitacoes if (
        (dados.get("processo") and item.numero_processo == dados["processo"])
        or (dados.get("edital") and (item.numero_aviso, data.year) == numero_edital(dados["edital"]))
    )]
    if len(candidatos) > 1 or pagina.total > 100:
        raise ToolError("Busca nos Dados Abertos ambígua ou incompleta. Informe o link oficial.")
    return candidatos[0] if candidatos else None


async def criar(
    odoo: OdooClient, link: str | None, id_conlicitacao: int | None,
    controle_pncp: str | None, dados: dict, data: date | None,
    empresa: str | None, somente_conferir: bool,
) -> dict:
    tentativas = ["ConLicitação"]
    ref = pncp.resolver_compra(numero_controle_pncp=controle_pncp) if controle_pncp else None
    compras_id = None
    link_portal = False
    if link:
        url = urlsplit(link)
        if url.scheme not in ("https", "http") or not url.hostname or url.username or url.password:
            raise ToolError("Informe um link público HTTP(S) da página oficial.")
        if url.hostname == "consulteonline.conlicitacao.com.br":
            match = re.fullmatch(r"/biddings/(\d+)/?", url.path)
            if not match:
                raise ToolError("Informe o link de detalhe do ConLicitação (/biddings/<id>).")
            id_conlicitacao = int(match[1])
        elif url.hostname == "pncp.gov.br":
            match = re.fullmatch(r"/(?:app/)?editais/(\d{14})/(\d{4})/(\d+)/?", url.path)
            if not match:
                raise ToolError("Informe o link de detalhe do PNCP (/app/editais/CNPJ/ano/sequencial).")
            ref = (match[1], int(match[2]), int(match[3]))
        elif url.hostname in (
            "www.compras.gov.br", "compras.gov.br", "cnetmobile.estaleiro.serpro.gov.br",
            "www.comprasnet.gov.br", "comprasnet.gov.br",
        ):
            compra = parse_qs(url.query).get("compra", [""])[0]
            if re.fullmatch(r"\d{17}", compra):
                compras_id = compra
                dados.setdefault("uasg", compra[:6])
                dados.setdefault("edital", f"{int(compra[8:13])}/{compra[13:]}")
        else:
            link_portal = not ref
    # Um controle oficial permite enriquecer a consulta ao ConLicitação antes da escolha da fonte.
    detalhe = await consultar_pncp(ref) if ref and not id_conlicitacao else None
    if detalhe:
        dados = {**{k: v for k, v in dados_pncp(detalhe).items() if v not in (None, "")}, **dados}
    con_id = id_conlicitacao or await localizar_conlicitacao(dados, None if ref else data)
    if con_id:
        referencia = {"conlicitacao_id": con_id}
        conferencia = await odoo.chamar("importar", {**referencia, "somente_conferir": True})
        if card := conferencia["licitacao"]:
            return resultado(card, False, tentativas)
        if somente_conferir:
            return {
                "criado": False, "ja_existia": False, "chave": str(con_id), "fonte": "conlicitacao",
                "licitacao": None, "fonte_url": link_licitacao(con_id), "tentativas": tentativas,
                "proximos_passos": _proximos_passos("conlicitacao", somente_conferir=True),
            }
        pedido_importar: dict[str, Any] = {
            **referencia,
            **({"dados": dados} if dados else {}),
            **({"empresa": empresa} if empresa else {}),
        }
        gravado = await odoo.chamar("importar", pedido_importar)
        extras: dict[str, Any] = {"preparacao": gravado["preparacao"]}
        if "atualizado" in gravado:
            extras["atualizado"] = gravado["atualizado"]
        if "campos_vazios" in gravado:
            extras["campos_vazios"] = gravado["campos_vazios"]
        return resultado(gravado["licitacao"], gravado["criado"], tentativas, **extras)
    tentativas.append("PNCP")
    if not ref:
        try:
            candidato = await localizar_pncp(dados, data)
            if candidato:
                detalhe = await consultar_pncp(candidato)
                if detalhe.get("numeroControlePNCP"):
                    ref = candidato
                    dados.update({k: v for k, v in dados_pncp(detalhe).items() if v not in (None, "")})
        except HttpClientError:
            if not link_portal:
                raise
            tentativas.append("PNCP: consulta indisponível; seguindo com a URL informada se Compras.gov não confirmar.")
        else:
            if not ref:
                tentativas.append("PNCP: sem correspondência confirmada.")
    identificador = None
    if not ref and compras_id:
        tentativas.append("Compras.gov / Dados Abertos")
        resposta = await http_get(
            f"{COMPRAS_API}/modulo-contratacoes/1.1_consultarContratacoes_PNCP_14133_Id",
            params={"tipo": "idCompra", "codigo": compras_id},
        )
        linhas = [linha for linha in resposta.get("resultado", []) if linha.get("idCompra") == compras_id]
        if len(linhas) != 1:
            raise ToolError("Compras.gov não confirmou uma compra única para este link.")
        linha = linhas[0]
        if controle := linha.get("numeroControlePNCP"):
            ref = pncp.resolver_compra(numero_controle_pncp=controle)
            detalhe = await consultar_pncp(ref)
            if detalhe.get("numeroControlePNCP"):
                dados.update({k: v for k, v in dados_pncp(detalhe).items() if v not in (None, "")})
        else:
            dados.update({k: v for k, v in {
                "objeto": linha.get("objetoCompra"), "processo": linha.get("processo"),
                "orgao": linha.get("orgaoEntidadeRazaoSocial"), "uf": linha.get("unidadeOrgaoUfSigla"),
            }.items() if v not in (None, "")})
    if ref:
        if not detalhe or not detalhe.get("numeroControlePNCP"):
            raise ToolError("PNCP não confirmou o identificador da licitação.")
        fonte, identificador, link = "pncp", detalhe["numeroControlePNCP"], pncp.link_portal_edital(*ref)
    else:
        if not compras_id:
            tentativas.append("Compras.gov / Dados Abertos")
        if not compras_id and data and dados.get("uasg") and data.year <= 2020:
            try:
                compra = await localizar_compras_historico(dados, data)
            except HttpClientError:
                if not link_portal:
                    raise
                tentativas.append("Dados Abertos: consulta indisponível; seguindo com a URL informada.")
            else:
                if compra:
                    compras_id = compra.id_compra or compra.identificador
                    dados.update({k: v for k, v in {
                        "objeto": compra.objeto, "abertura": compra.data_abertura_proposta,
                        "valor_estimado": compra.valor_estimado_total,
                    }.items() if v not in (None, "")})
                else:
                    tentativas.append("Dados Abertos: sem correspondência confirmada.")
        if compras_id:
            fonte, identificador = "compras", compras_id
        elif link:
            fonte = "portal"
            tentativas.append("Portal: conferência pela URL canônica; sem confirmação pelo Compras.gov.")
        else:
            return {
                "criado": False, "ja_existia": False, "licitacao": None, "tentativas": tentativas,
                "proximos_passos": ["Busque o edital na internet ou no portal do órgão e chame "
                                    "licitacao_criar com o link oficial e os identificadores disponíveis."],
            }
    parametros = {"fonte": fonte, "identificador": identificador, "url": link, "dados": dados, "empresa": empresa}
    conferencia = await odoo.chamar("criar", {**parametros, "somente_conferir": True})
    card = conferencia["licitacao"]
    if card and (somente_conferir or not dados):
        return resultado(card, False, tentativas, atualizado=False)
    if not card:
        duplicado = await duplicado_outra_fonte(odoo, dados)
        if duplicado:
            return resultado(duplicado, False, tentativas, atualizado=False)
    if somente_conferir:
        return {
            "licitacao": None, "chave": conferencia["chave"], "fonte": fonte,
            "criado": False, "ja_existia": False, "tentativas": tentativas,
            "proximos_passos": _proximos_passos(fonte, somente_conferir=True),
        }
    gravado = await odoo.chamar("criar", parametros)
    extras_criar: dict[str, Any] = {"atualizado": gravado.get("atualizado", False)}
    if "preparacao" in gravado:
        extras_criar["preparacao"] = gravado["preparacao"]
    if "campos_vazios" in gravado:
        extras_criar["campos_vazios"] = gravado["campos_vazios"]
    return resultado(gravado["licitacao"], gravado["criado"], tentativas, **extras_criar)
