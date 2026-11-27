#!/usr/bin/env python3
"""Emite ou reaproveita certidões públicas sem navegador e confere o PDF."""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

TJDFT_BASE = "https://cnc-api.tjdft.jus.br/api/ext"
TJDFT_ORIGIN = "https://cnc.tjdft.jus.br"
TJDFT_TIPOS = ("FALENCIA_CONCORDATA", "CRIMINAL", "CIVEL", "ESPECIAL")

SEFAZ_GO_FORM_URL = "https://www.sefaz.go.gov.br/Certidao/Emissao/"
SEFAZ_GO_POST_URL = "https://www.sefaz.go.gov.br/Certidao/Emissao/certidao.asp"

EMISSORES_AUTOMATICOS = {
    "tjdft": {
        "orgao": "TJDFT",
        "tipos": list(TJDFT_TIPOS),
        "padrao": "FALENCIA_CONCORDATA",
        "url": "https://cnc.tjdft.jus.br/",
    },
    "sefaz-go": {
        "orgao": "SEFAZ-GO",
        "tipos": ["01"],
        "padrao": "01",
        "url": SEFAZ_GO_FORM_URL,
    },
}


def limpar_cnpj(cnpj: str) -> str:
    digitos = re.sub(r"\D+", "", cnpj or "")
    if len(digitos) != 14:
        raise ValueError(f"CNPJ inválido (esperado 14 dígitos): {cnpj!r}")
    return digitos


def formatar_cnpj(digitos: str) -> str:
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"


def normalizar_data_iso(valor: str | None) -> str | None:
    if not valor:
        return None
    texto = valor.strip()
    m_iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m_iso:
        return f"{m_iso.group(1)}-{m_iso.group(2)}-{m_iso.group(3)}"
    m_br = re.search(r"(\d{2})/(\d{2})/(\d{4})", texto)
    if m_br:
        return f"{m_br.group(3)}-{m_br.group(2)}-{m_br.group(1)}"
    return None


def _http_request(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 25,
) -> tuple[int, dict[str, str], bytes]:
    hdrs = {"User-Agent": UA, **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.status, dict(resp.headers), resp.read()


def extrair_texto_pdf(caminho: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    reader = PdfReader(str(caminho))
    partes = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(partes)


def detectar_divergencia_nome(nome_esperado: str | None, nome_emitido: str | None) -> str | None:
    if not nome_esperado or not nome_emitido:
        return None
    a = re.sub(r"[^A-Z0-9]+", " ", nome_esperado.upper()).strip()
    b = re.sub(r"[^A-Z0-9]+", " ", nome_emitido.upper()).strip()
    if a == b:
        return None
    sufixos = ("LTDA", "EIRELI", "ME", "EPP", "S A", "SA", "SLU")

    def sem_sufixo(s: str) -> str:
        return re.sub(rf"\b({'|'.join(sufixos)})\b", "", s).strip()

    if sem_sufixo(a) == sem_sufixo(b):
        return (
            f"Razão social no emissor ({nome_emitido}) difere apenas no tipo societário "
            f"em relação ao cadastro ({nome_esperado}); mesmo CNPJ, sem bloqueio."
        )
    return (
        f"Razão social no emissor ({nome_emitido}) difere do cadastro ({nome_esperado}); "
        "conferir se é atualização cadastral pendente na Receita."
    )


def classificar_resultado_texto(texto: str) -> str:
    up = re.sub(r"\s+", " ", texto.upper())
    if "POSITIVA COM EFEITO" in up or "POSITIVA COM EFEITOS DE NEGATIVA" in up:
        return "POSITIVA_COM_EFEITOS_DE_NEGATIVA"
    if "NADA CONSTA" in up or "CERTIDAO NEGATIVA" in up or "CERTIDÃO NEGATIVA" in up:
        return "NEGATIVA"
    if "NAO CONSTA" in up or "NÃO CONSTA" in up:
        return "NEGATIVA"
    if "POSITIVA" in up or "POSSUI DEBITO" in up or "POSSUI DÉBITO" in up:
        return "POSITIVA"
    return "INDEFINIDO"


def conferir_pdf(
    caminho: Path,
    cnpj_digitos: str,
    *,
    nome_esperado: str | None = None,
    nome_emitido: str | None = None,
    data_emissao: str | None = None,
    validade: str | None = None,
) -> dict[str, Any]:
    raw = caminho.read_bytes()
    if not raw.startswith(b"%PDF"):
        raise ValueError(f"Arquivo baixado não é um PDF válido: {caminho}")
    texto = extrair_texto_pdf(caminho)
    digitos_pdf = re.sub(r"\D+", "", texto)
    cnpj_ok = cnpj_digitos in digitos_pdf if texto else None
    resultado = classificar_resultado_texto(texto) if texto else "NAO_LIDO"

    if not validade and texto:
        m_val = re.search(
            r"VALI[DA][^\d]{0,30}(\d{2}/\d{2}/\d{4})",
            texto,
            re.IGNORECASE,
        )
        if m_val:
            validade = normalizar_data_iso(m_val.group(1))
    if not data_emissao and texto:
        m_em = re.search(
            r"EMITID[OA][^\d]{0,30}(\d{2}/\d{2}/\d{4})",
            texto,
            re.IGNORECASE,
        )
        if m_em:
            data_emissao = normalizar_data_iso(m_em.group(1))

    observacoes: list[str] = []
    if cnpj_ok is False:
        observacoes.append(f"CNPJ {formatar_cnpj(cnpj_digitos)} não localizado no texto do PDF.")
    div = detectar_divergencia_nome(nome_esperado, nome_emitido)
    if div:
        observacoes.append(div)
    if resultado == "POSITIVA":
        observacoes.append("Certidão retornou resultado POSITIVO (com débito/registro).")
    if validade:
        try:
            if datetime.strptime(validade, "%Y-%m-%d").date() < datetime.now().date():
                observacoes.append(f"Certidão já vencida em {validade}.")
        except ValueError:
            pass

    situacao = "ok"
    if cnpj_ok is False or resultado == "POSITIVA":
        situacao = "pendente"

    return {
        "situacao": situacao,
        "cnpj_conferido": cnpj_ok,
        "resultado": resultado,
        "data_emissao": data_emissao,
        "validade": validade,
        "observacoes": observacoes,
    }


def emitir_tjdft(
    *,
    cnpj_digitos: str,
    nome: str,
    tipo: str,
    saida: Path,
    recriar: bool = False,
) -> dict[str, Any]:
    tipo_up = tipo.upper()
    if tipo_up not in TJDFT_TIPOS:
        raise ValueError(f"Tipo TJDFT inválido: {tipo!r}. Use um de: {', '.join(TJDFT_TIPOS)}")

    headers_api = {
        "Origin": TJDFT_ORIGIN,
        "Referer": f"{TJDFT_ORIGIN}/",
        "Accept": "application/json",
    }
    termo_nome = (nome or "").strip().split()[0] if nome and nome.strip() else ""
    qs = urllib.parse.urlencode({"nome": termo_nome}) if termo_nome else ""
    url_pessoa = f"{TJDFT_BASE}/pessoas/{cnpj_digitos}" + (f"?{qs}" if qs else "")
    _, _, raw_pessoa = _http_request(url_pessoa, headers=headers_api)
    pessoa = json.loads(raw_pessoa.decode("utf-8"))
    nome_receita = pessoa.get("nome_receita") or nome

    payload = json.dumps(
        {
            "nome": nome_receita,
            "cpf_cnpj": cnpj_digitos,
            "nome_mae": None,
            "nome_pai": None,
            "tipo_certidao": tipo_up,
        }
    ).encode("utf-8")

    headers_post = {**headers_api, "Content-Type": "application/json"}
    _, _, raw_sol = _http_request(
        f"{TJDFT_BASE}/solicitacoes",
        method="POST",
        data=payload,
        headers=headers_post,
    )
    sol = json.loads(raw_sol.decode("utf-8"))
    cert = sol.get("certidao") or {}

    if recriar and sol.get("certidao_existente") and cert.get("id"):
        _, _, raw_sol = _http_request(
            f"{TJDFT_BASE}/solicitacoes?certidao_a_recriar={urllib.parse.quote(str(cert['id']))}",
            method="POST",
            data=payload,
            headers=headers_post,
        )
        sol = json.loads(raw_sol.decode("utf-8"))
        cert = sol.get("certidao") or {}

    url_pdf = cert.get("url_certidao")
    if not url_pdf:
        raise RuntimeError(f"TJDFT não retornou url_certidao: {sol}")

    _, _, pdf_bytes = _http_request(url_pdf)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_bytes(pdf_bytes)

    conf = conferir_pdf(
        saida,
        cnpj_digitos,
        nome_esperado=nome,
        nome_emitido=nome_receita,
        data_emissao=normalizar_data_iso(cert.get("data_emissao")),
        validade=normalizar_data_iso(cert.get("data_validade")),
    )
    obs = list(conf["observacoes"])
    reutilizada = bool(sol.get("certidao_existente")) and not recriar
    if reutilizada:
        obs.insert(0, "Reaproveitada certidão vigente já emitida no TJDFT.")

    return {
        "certidao": tipo_up.lower(),
        "emissor": "tjdft",
        "situacao": conf["situacao"],
        "cnpj": formatar_cnpj(cnpj_digitos),
        "nome_esperado": nome or None,
        "nome_emitido": nome_receita,
        "resultado": conf["resultado"],
        "data_emissao": conf["data_emissao"],
        "validade": conf["validade"],
        "reutilizada": reutilizada,
        "arquivo": str(saida),
        "observacao": " ".join(obs).strip(),
    }


def emitir_sefaz_go(
    *,
    cnpj_digitos: str,
    nome: str,
    tipo: str,
    saida: Path,
) -> dict[str, Any]:
    cnpj_fmt = formatar_cnpj(cnpj_digitos)
    form_base = {
        "Certidao.Tipo": tipo or "01",
        "Certidao.TipoDocumento": "2",
        "Certidao.NumeroDocumento": cnpj_digitos,
        "Certidao.NumeroDocumentoCNPJ": cnpj_fmt,
        "Certidao.Espolio": "N",
        "Certidao.ValidarEmissao_Emitir": "0",
        "Certidao.ConfirmaNomeContribuinte": "Sim",
    }
    headers_post = {
        "Referer": SEFAZ_GO_FORM_URL,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # Baixa o PDF diretamente na etapa de confirmação.
    data_pdf = urllib.parse.urlencode({**form_base, "Certidao.Render": "pdf"}).encode("utf-8")
    _, hdrs, raw_pdf = _http_request(
        SEFAZ_GO_POST_URL,
        method="POST",
        data=data_pdf,
        headers=headers_post,
    )
    if not raw_pdf.startswith(b"%PDF"):
        trecho = re.sub(r"<[^>]+>", " ", raw_pdf.decode("latin1", errors="replace"))
        trecho = re.sub(r"\s+", " ", trecho).strip()[:300]
        raise RuntimeError(
            f"SEFAZ-GO não devolveu PDF (Content-Type={hdrs.get('Content-Type')}): {trecho}"
        )

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_bytes(raw_pdf)

    conf = conferir_pdf(
        saida,
        cnpj_digitos,
        nome_esperado=nome,
    )
    return {
        "certidao": "cnd_estadual_go",
        "emissor": "sefaz-go",
        "situacao": conf["situacao"],
        "cnpj": cnpj_fmt,
        "nome_esperado": nome or None,
        "nome_emitido": None,
        "resultado": conf["resultado"],
        "data_emissao": conf["data_emissao"],
        "validade": conf["validade"],
        "reutilizada": False,
        "arquivo": str(saida),
        "observacao": " ".join(conf["observacoes"]).strip(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emite ou reaproveita certidões públicas sem navegador."
    )
    parser.add_argument(
        "--listar-emissores",
        action="store_true",
        help="Lista emissores automáticos suportados em JSON e sai.",
    )
    parser.add_argument("--emissor", choices=sorted(EMISSORES_AUTOMATICOS))
    parser.add_argument("--cnpj", help="CNPJ da empresa disputante (obtido via dados_empresa).")
    parser.add_argument("--nome", default="", help="Razão social ou trecho do nome da empresa.")
    parser.add_argument("--tipo", default="", help="Tipo de certidão do emissor.")
    parser.add_argument("--saida", help="Caminho do PDF de saída (ex.: /tmp/certidoes/H-11.pdf).")
    parser.add_argument(
        "--recriar",
        action="store_true",
        help="Força nova emissão no TJDFT quando a vigente vencer antes da sessão.",
    )
    args = parser.parse_args(argv)

    if args.listar_emissores:
        print(json.dumps(EMISSORES_AUTOMATICOS, ensure_ascii=False, indent=2))
        return 0

    if not args.emissor or not args.cnpj or not args.saida:
        parser.error("Informe --emissor, --cnpj e --saida (ou use --listar-emissores).")

    try:
        cnpj_digitos = limpar_cnpj(args.cnpj)
        saida = Path(args.saida)
        if args.emissor == "tjdft":
            res = emitir_tjdft(
                cnpj_digitos=cnpj_digitos,
                nome=args.nome,
                tipo=args.tipo or EMISSORES_AUTOMATICOS["tjdft"]["padrao"],
                saida=saida,
                recriar=args.recriar,
            )
        elif args.emissor == "sefaz-go":
            res = emitir_sefaz_go(
                cnpj_digitos=cnpj_digitos,
                nome=args.nome,
                tipo=args.tipo or EMISSORES_AUTOMATICOS["sefaz-go"]["padrao"],
                saida=saida,
            )
        else:
            raise ValueError(f"Emissor não suportado: {args.emissor}")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, urllib.error.URLError, RuntimeError) as exc:
        erro = {
            "emissor": args.emissor,
            "situacao": "pendente",
            "validade": None,
            "arquivo": None,
            "observacao": f"Falha na emissão automática ({exc}). Emitir manualmente em {EMISSORES_AUTOMATICOS[args.emissor]['url']}.",
        }
        print(json.dumps(erro, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
