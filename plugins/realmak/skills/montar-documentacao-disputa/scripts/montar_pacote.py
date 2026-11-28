#!/usr/bin/env python3
"""Monta o pacote de envio de uma licitação: um PDF por exigência com nome legível, ordenado por etapa e edital.

Uso: python3 montar_pacote.py plano.json

plano.json:
{
  "saida": "/tmp/pacote-<id>",
  "indice_json": "agents/montagem-proposta/indice-envio.json",
  "licitacao": "PE 35/2026 – TJMA",
  "empresa": "REALMAK SERVIÇOS E COMÉRCIO LTDA",
  "limite_mb": 10,
  "itens": [
    {
      "etapa_envio": "habilitacao",
      "ordem_edital": 1,
      "item_edital": "10.6.1 II",
      "nome": "Ato constitutivo – 18ª alteração contratual",
      "exigencia": "Ato constitutivo e alterações",
      "fontes": ["/caminho/a.pdf", "/caminho/b.docx"],
      "assinaturas": [{"nome": "Fulano", "papel": "Representante", "assinado": true, "forma": "modelo"}],
      "status": "ok",
      "obs": "",
      "nao_enviar": false,
      "depende_lance": false,
      "lance_informado": false
    }
  ]
}
etapa_envio: "sessao" (para participar da sessão), "proposta" (proposta e anexos) ou "habilitacao" (padrão), nessa ordem.
Itens sem fontes entram apenas no indice-envio.json (intermediário), como pendência.
Passo manual no portal (declarações do sistema, cadastro da proposta, "Enviar anexo") é ignorado em qualquer etapa: não vira item nem aviso.
depende_lance: true nos itens que dependem do preço final (proposta ajustada, planilha, anexo com preço). Sem o campo, o
script infere pelo rótulo nos itens da etapa proposta. O item só sai OK com lance_informado: true; sem ele fica PENDENTE
com o motivo "Gerada com o preço de referência; refazer com o lance final". O campo vai para o indice_json.
Não gera "00 - INDICE DE ENVIO.pdf" nem usa prefixos internos (H-xx, P-xx) nos nomes de arquivos.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter

CONVERTE = {
    ".doc",
    ".docx",
    ".odt",
    ".rtf",
    ".xls",
    ".xlsx",
    ".ods",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".txt",
}
ETAPAS_VALIDAS = ("sessao", "proposta", "habilitacao")
PREFIXO_INTERNO_RE = re.compile(r"^(?:00|[HPD]-\d{1,3})\s*[-–—]\s*", re.IGNORECASE)
# Passo manual no portal (clicar, marcar, cadastrar) não é documento: não vira item em nenhuma etapa.
PASSO_PORTAL_RE = re.compile(
    r"declara\w*\s+(?:no|do|de)\s+(?:sistema|portal)\b"
    r"|\b(?:marcar|cadastrar|clicar|preencher)\b[^.\n]{0,80}\b(?:portal|sistema|compras\.?gov)"
    r"|\bcadastr\w*\s+(?:d[ao]\s+)?proposta\b"
    r"|\benviar\s+anexo\b",
    re.IGNORECASE,
)


# Documento da etapa proposta que leva o preço final (mesma regra de analisar-edital/scripts/validar_card.py).
DEPENDE_LANCE_RE = re.compile(r"proposta|planilha|composi[cç][aã]o|pre[cç]o|lance|custos", re.IGNORECASE)
MOTIVO_LANCE = "Gerada com o preço de referência; refazer com o lance final"


def depende_do_lance(item: dict, etapa: str) -> bool:
    if isinstance(item.get("depende_lance"), bool):
        return item["depende_lance"]
    if etapa != "proposta":
        return False
    texto = " ".join(str(item.get(c) or "") for c in ("exigencia", "nome"))
    return bool(DEPENDE_LANCE_RE.search(texto))


def passo_manual_portal(item: dict) -> bool:
    texto = " ".join(str(item.get(c) or "") for c in ("exigencia", "nome"))
    return bool(PASSO_PORTAL_RE.search(texto))


def nome_seguro(texto: str) -> str:
    limpo = PREFIXO_INTERNO_RE.sub("", str(texto or "")).strip()
    limpo = re.sub(r'[\\/:*?"<>|\r\n]+', " ", limpo)
    return re.sub(r"\s+", " ", limpo).strip()[:150] or "Documento"


def para_pdf(fonte: str | Path, tmp: str) -> Path:
    fonte = Path(fonte)
    if fonte.suffix.lower() == ".pdf":
        return fonte
    if fonte.suffix.lower() not in CONVERTE:
        raise ValueError(f"formato sem conversão: {fonte.name}")
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("LibreOffice (soffice) não encontrado para converter " + fonte.name)
    destino = Path(tempfile.mkdtemp(dir=tmp))
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(destino), str(fonte)],
        check=True,
        capture_output=True,
        timeout=300,
        env={"HOME": str(destino), "PATH": "/usr/bin:/bin"},
    )
    pdf = destino / (fonte.stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError("conversão falhou: " + fonte.name)
    return pdf


def _normalizar_etapa(valor: str | None) -> str:
    if valor in ETAPAS_VALIDAS:
        return valor
    return "habilitacao"


def _normalizar_ordem(valor: object, padrao: int) -> int:
    try:
        num = int(valor)
        if 1 <= num <= 999:
            return num
    except (TypeError, ValueError):
        pass
    return max(1, min(999, padrao))


def montar(plano: dict) -> dict:
    saida = Path(plano["saida"])
    saida.mkdir(parents=True, exist_ok=True)
    limite = plano.get("limite_mb")
    linhas, avisos = [], []
    nomes_usados: set[str] = set()
    contadores_etapa = dict.fromkeys(ETAPAS_VALIDAS, 0)

    with tempfile.TemporaryDirectory() as tmp:
        for item in plano["itens"]:
            if passo_manual_portal(item):
                continue
            etapa = _normalizar_etapa(item.get("etapa_envio"))
            contadores_etapa[etapa] += 1
            ordem_edital = _normalizar_ordem(item.get("ordem_edital"), contadores_etapa[etapa])
            item_edital = str(item.get("item_edital") or "").strip()[:80]
            nome_limpo = nome_seguro(item.get("nome") or item.get("exigencia") or "Documento")

            linha = {
                "etapa_envio": etapa,
                "ordem_edital": ordem_edital,
                "item_edital": item_edital,
                "nome": nome_limpo,
                "exigencia": item.get("exigencia") or nome_limpo,
                "status": item.get("status"),
                "obs": item.get("obs"),
                "assinaturas": item.get("assinaturas"),
                "nao_enviar": bool(item.get("nao_enviar", False)),
                "bloqueia": item.get("bloqueia"),
                "momento": item.get("momento"),
                "risco_inabilitacao": item.get("risco_inabilitacao"),
                "motivo_bloqueio": item.get("motivo_bloqueio"),
                "depende_lance": depende_do_lance(item, etapa),
                "lance_informado": item.get("lance_informado") is True,
            }
            assinaturas = item.get("assinaturas") or []
            faltam_assinar = [a.get("nome") or "?" for a in assinaturas if not a.get("assinado")]
            linha["status"] = item.get("status") or ("ok" if item.get("fontes") else "pendente")
            if faltam_assinar:
                linha["status"] = "pendente"
                if not linha.get("obs"):
                    linha["obs"] = "Falta a assinatura de " + ", ".join(faltam_assinar)

            if linha["depende_lance"] and item.get("lance_informado") is not True:
                linha["status"] = "pendente"
                if not linha.get("obs"):
                    linha["obs"] = MOTIVO_LANCE

            fontes = item.get("fontes") or []
            if fontes:
                escritor = PdfWriter()
                try:
                    for f in fontes:
                        for pagina in PdfReader(str(para_pdf(f, tmp))).pages:
                            escritor.add_page(pagina)
                except Exception as exc:  # fonte ilegível: vira pendência, o resto do pacote segue
                    linha.update(status="pendente", obs=f"não montado: {exc}")
                    avisos.append(f"{nome_limpo}: {exc}")
                else:
                    if hasattr(escritor, "compress_identical_objects"):
                        escritor.compress_identical_objects()
                    candidato = f"{nome_limpo}.pdf"
                    sufixo = 2
                    while candidato.lower() in nomes_usados:
                        candidato = f"{nome_limpo} ({sufixo}).pdf"
                        sufixo += 1
                    nomes_usados.add(candidato.lower())
                    destino = saida / candidato
                    with open(destino, "wb") as fh:
                        escritor.write(fh)
                    mb = destino.stat().st_size / 1_048_576
                    linha.update(arquivo=destino.name, paginas=len(escritor.pages), mb=round(mb, 2))
                    if limite and mb > limite:
                        avisos.append(
                            f"{destino.name}: {mb:.1f} MB acima do limite de {limite} MB do portal"
                        )
            linhas.append(linha)

    linhas.sort(key=lambda x: (ETAPAS_VALIDAS.index(x["etapa_envio"]), x["ordem_edital"]))

    indice_json_path = plano.get("indice_json")
    if indice_json_path:
        destino_json = Path(indice_json_path)
        destino_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "itens": [
                {
                    "etapa_envio": item_linha["etapa_envio"],
                    "ordem_edital": item_linha["ordem_edital"],
                    **({"item_edital": item_linha["item_edital"]} if item_linha["item_edital"] else {}),
                    "exigencia": item_linha["exigencia"],
                    **({"arquivo": item_linha["arquivo"]} if item_linha.get("arquivo") else {}),
                    "situacao": "OK" if item_linha["status"] == "ok" else "PENDENTE",
                    "motivo": item_linha.get("obs") or "",
                    **({"nao_enviar": True} if item_linha.get("nao_enviar") else {}),
                    **({"depende_lance": True} if item_linha.get("depende_lance") else {}),
                    **(
                        {"lance_informado": True}
                        if item_linha.get("depende_lance") and item_linha.get("lance_informado")
                        else {}
                    ),
                    **(
                        {"bloqueia": bool(item_linha["bloqueia"])}
                        if item_linha.get("bloqueia") is not None
                        else {}
                    ),
                    **({"momento": item_linha["momento"]} if item_linha.get("momento") else {}),
                    **(
                        {"risco_inabilitacao": bool(item_linha["risco_inabilitacao"])}
                        if item_linha.get("risco_inabilitacao") is not None
                        else {}
                    ),
                    **(
                        {"motivo_bloqueio": item_linha["motivo_bloqueio"]}
                        if item_linha.get("motivo_bloqueio")
                        else {}
                    ),
                }
                for item_linha in linhas
            ]
        }
        destino_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    return {
        "indice_json": str(indice_json_path) if indice_json_path else None,
        "arquivos": linhas,
        "avisos": avisos,
        "pendencias": [item_linha for item_linha in linhas if item_linha["status"] != "ok"],
    }


if __name__ == "__main__":
    print(
        json.dumps(
            montar(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))),
            ensure_ascii=False,
            indent=1,
        )
    )
