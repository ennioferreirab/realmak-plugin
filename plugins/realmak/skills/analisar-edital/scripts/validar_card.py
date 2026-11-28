#!/usr/bin/env python3
"""Confere os campos do card (seções v2) em edital.json, habilitacao.json e indice-envio.json.

Uso: python3 validar_card.py <pasta analise/ ou arquivo.json> [...]
  Pasta: confere edital.json, habilitacao.json e, se existirem, ../../montagem-proposta/indice-envio.json.
  Sai com 1 e lista o que corrigir; 0 quando tudo confere. Todos os campos são opcionais (análise antiga passa).

Regras (CONTRATO.md, "Campos da disposição v2"):
- edital.json: `convocacao` {modo: separada|conjunta, fonte}; `atencao[]` com `situacao` aberto|resolvido,
  `resolucao` (obrigatória quando resolvido) e `destino` {tipo, ref}; sem micro-prazo em `prazos[]`.
- habilitacao.json (empresas[].exigencias[]) e indice-envio.json (itens[]): `depende_lance` booleano; item da
  etapa proposta que carrega preço (proposta ajustada, planilha, anexo com preço) precisa de `depende_lance: true`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MODOS_CONVOCACAO = ("separada", "conjunta")
SITUACOES_ATENCAO = ("aberto", "resolvido")
TIPOS_DESTINO = ("exigencia", "precificacao", "tecnica", "edital", "etapa")
ETAPAS_DESTINO = ("sessao", "proposta", "habilitacao", "contrato")
# Micro-prazo (horas/minutos) não é prazo de etapa: só a data da sessão; o resto é momento.
MICRO_PRAZO_RE = re.compile(
    r"\b\d+\s*(?:h|hs|hr|hrs|horas?|min|minutos?)\b|\b(?:uma|duas|tr[eê]s|quatro|meia)\s+horas?\b",
    re.IGNORECASE,
)
# Documento da etapa proposta que leva o preço final (proposta ajustada, planilha, anexo com preço).
DEPENDE_LANCE_RE = re.compile(r"proposta|planilha|composi[cç][aã]o|pre[cç]o|lance|custos", re.IGNORECASE)


def depende_do_lance(item: dict) -> bool:
    """Pela regra: `depende_lance` explícito vale; sem ele, item da etapa proposta com preço no rótulo."""
    if isinstance(item.get("depende_lance"), bool):
        return item["depende_lance"]
    if item.get("etapa_envio") != "proposta":
        return False
    texto = " ".join(str(item.get(c) or "") for c in ("rotulo", "exigencia", "nome"))
    return bool(DEPENDE_LANCE_RE.search(texto))


def _texto(valor: object) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def validar_edital(edital: dict) -> list[str]:
    erros: list[str] = []
    conv = edital.get("convocacao")
    if conv is not None:
        if not isinstance(conv, dict) or conv.get("modo") not in MODOS_CONVOCACAO:
            erros.append("convocacao.modo deve ser 'separada' ou 'conjunta'")
        elif not _texto(conv.get("fonte")):
            erros.append("convocacao.fonte obrigatória (item do edital)")
    ids_hab = {h.get("id") for h in edital.get("habilitacao") or [] if isinstance(h, dict) and h.get("id")}
    for i, ponto in enumerate(edital.get("atencao") or []):
        nome = f"atencao[{i}]"
        situacao = ponto.get("situacao")
        if situacao is not None and situacao not in SITUACOES_ATENCAO:
            erros.append(f"{nome}.situacao deve ser 'aberto' ou 'resolvido'")
        if situacao == "resolvido" and not _texto(ponto.get("resolucao")):
            erros.append(f"{nome}.resolucao obrigatória quando resolvido (frase curta)")
        if ponto.get("resolucao") is not None and len(str(ponto["resolucao"])) > 160:
            erros.append(f"{nome}.resolucao com mais de 160 caracteres")
        destino = ponto.get("destino")
        if situacao == "resolvido" and not isinstance(destino, dict):
            erros.append(f"{nome}.destino obrigatório quando resolvido")
        if destino is None:
            continue
        if not isinstance(destino, dict) or destino.get("tipo") not in TIPOS_DESTINO:
            erros.append(f"{nome}.destino.tipo deve ser um de {', '.join(TIPOS_DESTINO)}")
            continue
        tipo, ref = destino["tipo"], destino.get("ref")
        if tipo in ("exigencia", "etapa") and not _texto(ref):
            erros.append(f"{nome}.destino.ref obrigatório para tipo '{tipo}'")
        elif tipo == "etapa" and ref not in ETAPAS_DESTINO:
            erros.append(f"{nome}.destino.ref de etapa deve ser um de {', '.join(ETAPAS_DESTINO)}")
        elif tipo == "exigencia" and ids_hab and ref not in ids_hab:
            erros.append(f"{nome}.destino.ref '{ref}' não existe em habilitacao[].id do edital")
    for i, prazo in enumerate(edital.get("prazos") or []):
        for campo in ("prazo", "data", "momento"):
            if MICRO_PRAZO_RE.search(str(prazo.get(campo) or "")):
                erros.append(
                    f"prazos[{i}].{campo} traz micro-prazo (horas/minutos); "
                    "use só a data da sessão ou o momento ('quando o pregoeiro pedir')"
                )
    return erros


def _validar_itens(itens: list, nome: str) -> list[str]:
    erros = []
    for i, item in enumerate(itens):
        if not isinstance(item, dict):
            continue
        flag = item.get("depende_lance")
        if flag is not None and not isinstance(flag, bool):
            erros.append(f"{nome}[{i}].depende_lance deve ser booleano")
        elif flag is not True and depende_do_lance(item):
            erros.append(f"{nome}[{i}] ({item.get('exigencia') or item.get('rotulo')}): marque depende_lance: true")
    return erros


def validar_habilitacao(hab: dict) -> list[str]:
    erros: list[str] = []
    for e, empresa in enumerate(hab.get("empresas") or []):
        erros += _validar_itens(empresa.get("exigencias") or [], f"empresas[{e}].exigencias")
    return erros


def validar_indice(indice: dict) -> list[str]:
    erros = _validar_itens(indice.get("itens") or [], "itens")
    for i, item in enumerate(indice.get("itens") or []):
        if item.get("depende_lance") is True and item.get("situacao") == "OK" and item.get("lance_informado") is not True:
            erros.append(f"itens[{i}] ({item.get('exigencia')}): depende do lance e não pode estar OK sem lance_informado: true")
    return erros


def validar_pasta(pasta: Path) -> dict[str, list[str]]:
    alvos = {
        "edital.json": (pasta / "edital.json", validar_edital),
        "habilitacao.json": (pasta / "habilitacao.json", validar_habilitacao),
        "indice-envio.json": (pasta.parent / "montagem-proposta" / "indice-envio.json", validar_indice),
    }
    saida: dict[str, list[str]] = {}
    for nome, (caminho, funcao) in alvos.items():
        if caminho.exists():
            saida[nome] = funcao(json.loads(caminho.read_text(encoding="utf-8")))
    return saida


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    total = 0
    for arg in argv:
        caminho = Path(arg)
        if caminho.is_dir():
            resultado = validar_pasta(caminho)
        else:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            funcao = {"edital": validar_edital, "habilitacao": validar_habilitacao}.get(
                caminho.stem.split("-")[0], validar_indice if caminho.stem.startswith("indice") else validar_edital
            )
            resultado = {caminho.name: funcao(dados)}
        for nome, erros in resultado.items():
            total += len(erros)
            print(f"{nome}: {'OK' if not erros else str(len(erros)) + ' problema(s)'}")
            for erro in erros:
                print(f"  - {erro}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
