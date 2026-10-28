"""Resumo dos dados do ConLicitação: tira o que é sensível e encurta o que é longo."""

from __future__ import annotations

import re
from typing import Any

FRONT_URL = "https://consulteonline.conlicitacao.com.br/biddings/{id}"

_DOWNLOAD = re.compile(r"(?:https?://[^\s\"']*)?/boletim_web/public/api/download\?[^\s\"']*")
_AUTH = re.compile(r"auth=[A-Za-z0-9_\-\.]{12,}")
_DATE_KEYS = ("message_date", "date", "data", "published_at", "created_at", "updated_at")


def link_licitacao(licitacao_id: Any) -> str | None:
    return FRONT_URL.format(id=licitacao_id) if isinstance(licitacao_id, int) else None


def scrub(value: Any) -> Any:
    """Remove links de download assinados de qualquer texto aninhado."""
    if isinstance(value, str):
        return _AUTH.sub("auth=***", _DOWNLOAD.sub("[link de download omitido]", value))
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    return value


def truncar(text: Any, limit: int = 400) -> Any:
    if isinstance(text, str) and len(text) > limit:
        return text[:limit] + "…"
    return text


def nomes_de_arquivo(docs: Any) -> list[str]:
    """Só os nomes dos arquivos; as URLs assinadas nunca saem."""
    if not isinstance(docs, list):
        return []
    return [str(d["filename"]) for d in docs if isinstance(d, dict) and d.get("filename")]


def _scalar(v: Any) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def resumir_item_site(item: dict) -> dict:
    """Linha de resultado da busca no site: campos simples, textos longos encurtados."""
    out: dict[str, Any] = {}
    for key, value in item.items():
        if key in ("edicts", "status_bidding_info", "bidding_info"):
            continue
        if _scalar(value):
            out[key] = truncar(scrub(value), 500)
        elif isinstance(value, dict) and len(value) <= 6 and all(_scalar(v) for v in value.values()):
            out[key] = scrub(value)
    out["arquivos_do_edital"] = nomes_de_arquivo(item.get("edicts"))
    link = link_licitacao(item.get("id"))
    if link:
        out["link"] = link
    return out


def ordenar_por_data(entries: Any) -> list[Any]:
    """Ordena bidding_info por data crescente; sem data legível, mantém no fim na ordem original."""
    if not isinstance(entries, list):
        return []

    def chave(indexed: tuple[int, Any]) -> tuple[int, str, int]:
        idx, entry = indexed
        if isinstance(entry, dict):
            for k in _DATE_KEYS:
                v = entry.get(k)
                if isinstance(v, str) and v:
                    return (0, v, idx)
        return (1, "", idx)

    return [e for _, e in sorted(enumerate(entries), key=chave)]


def situacoes(status_bidding_info: Any) -> list[dict]:
    if not isinstance(status_bidding_info, list):
        return []
    return [
        {"nome": s.get("status_name"), "atualizado_em": s.get("updated_at"), "validade": s.get("expiration_date")}
        for s in status_bidding_info
        if isinstance(s, dict) and isinstance(s.get("status_name"), str) and s["status_name"].strip()
    ]


def detalhar_licitacao(data: dict) -> dict:
    """Licitação completa sem URLs assinadas. Ordem: identificação, situação, avisos e itens por último."""
    pesado = {"edicts", "status_bidding_info", "bidding_info", "itens", "itens_json"}
    out: dict[str, Any] = {"id": data.get("id"), "link": link_licitacao(data.get("id"))}
    for key, value in data.items():
        if key in pesado or key == "id":
            continue
        out[key] = scrub(value)
    out["arquivos_do_edital"] = nomes_de_arquivo(data.get("edicts"))
    out["situacoes"] = situacoes(data.get("status_bidding_info"))
    out["bidding_info_em_ordem_de_data"] = scrub(ordenar_por_data(data.get("bidding_info")))
    for key in ("itens", "itens_json"):
        if key in data:
            out[key] = scrub(data[key])
    return out


def resumir_licitacao_boletim(lic: dict) -> dict:
    orgao = lic.get("orgao") if isinstance(lic.get("orgao"), dict) else {}
    return {
        "id": lic.get("id"),
        "link": link_licitacao(lic.get("id")),
        "orgao": orgao.get("nome"),
        "uasg": orgao.get("codigo"),
        "uf": orgao.get("uf"),
        "cidade": orgao.get("cidade"),
        "edital": lic.get("edital"),
        "processo": lic.get("processo"),
        "situacao": lic.get("situacao"),
        "objeto": truncar(lic.get("objeto"), 300),
        "datahora_abertura": lic.get("datahora_abertura"),
        "datahora_prazo": lic.get("datahora_prazo"),
        "datahora_visita": lic.get("datahora_visita"),
        "valor_estimado": lic.get("valor_estimado"),
        "preco_edital": lic.get("preco_edital"),
        "arquivos_do_edital": nomes_de_arquivo(lic.get("documento")),
    }


def resumir_acompanhamento(ac: dict) -> dict:
    orgao = ac.get("orgao") if isinstance(ac.get("orgao"), dict) else {}
    return {
        "id": ac.get("id"),
        "licitacao_id": ac.get("licitacao_id"),
        "orgao": orgao.get("nome"),
        "uf": orgao.get("uf"),
        "edital": ac.get("edital"),
        "processo": ac.get("processo"),
        "data_fonte": ac.get("data_fonte"),
        "objeto": truncar(ac.get("objeto"), 200),
        "sintese": truncar(ac.get("sintese"), 600),
    }


def casa_busca(texto: str, *valores: Any) -> bool:
    alvo = texto.casefold()
    return any(isinstance(v, str) and alvo in v.casefold() for v in valores)
