#!/usr/bin/env python3
"""Aplica um pedido de precificação (card: "Nova precificação") ao precificacao.json atual.

Só Python da biblioteca padrão. Parte da precificação existente, não refaz custos do zero.

    python aplicar_pedido.py precificacao.json pedido.json saida.json [--dados dados.json --dados-saida dados-novo.json]

Modos do pedido (percentuais em pontos percentuais, valores em reais):
  preco      -> preço mensal informado em `preco_mensal`
  desconto   -> valor_estimado x (1 - desconto_pct/100), dividido pelos meses da vigência
  margem     -> preço = custo / (1 - tributos - margem)
  premissas  -> recalcula o custo (folha_pct, pecas_fator, tributos_pct) e acha o preço pela margem

Margem = (preço x (1 - tributos) - custo) / preço. Sai com código 2 e mensagem em stderr se o pedido ou a
precificação atual não permitem o cálculo (nunca inventa número).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

MODOS = ("preco", "desconto", "margem", "premissas")
MARGEM_MINIMA_PADRAO = 10.0
LIMITE_ORCADO_PCT = 75.0


class PedidoInvalido(ValueError):
    pass


def numero(valor, rotulo, *, positivo=False):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise PedidoInvalido(f"{rotulo} deve ser número")
    if positivo and valor <= 0:
        raise PedidoInvalido(f"{rotulo} deve ser maior que zero")
    return float(valor)


def reais(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(valor):
    return f"{valor:.2f}".replace(".", ",") + "%"


def componente(dados, nome):
    for item in dados.get("componentes") or []:
        if isinstance(item, dict) and item.get("componente") == nome and isinstance(item.get("valor_mensal"), (int, float)):
            return float(item["valor_mensal"])
    return None


def validar_pedido(pedido):
    if not isinstance(pedido, dict):
        raise PedidoInvalido("pedido deve ser objeto")
    modo = pedido.get("modo")
    if modo not in MODOS:
        raise PedidoInvalido(f"modo deve ser um de {', '.join(MODOS)}")
    if modo == "preco":
        numero(pedido.get("preco_mensal"), "preco_mensal", positivo=True)
    elif modo == "desconto":
        d = numero(pedido.get("desconto_pct"), "desconto_pct")
        if not 0 <= d < 100:
            raise PedidoInvalido("desconto_pct deve estar entre 0 e 100")
    elif modo == "margem":
        numero(pedido.get("margem_pct"), "margem_pct")
    else:
        prem = pedido.get("premissas")
        if not isinstance(prem, dict) or not any(prem.get(k) is not None for k in ("folha_pct", "pecas_fator", "tributos_pct", "margem_pct")):
            raise PedidoInvalido("premissas deve trazer ao menos um de folha_pct, pecas_fator, tributos_pct, margem_pct")
        if prem.get("folha_pct") is not None and numero(prem["folha_pct"], "folha_pct") <= -100:
            raise PedidoInvalido("folha_pct deve ser maior que -100")
        if prem.get("pecas_fator") is not None:
            numero(prem["pecas_fator"], "pecas_fator", positivo=True)
        if prem.get("tributos_pct") is not None:
            t = numero(prem["tributos_pct"], "tributos_pct")
            if not 0 <= t < 100:
                raise PedidoInvalido("tributos_pct deve estar entre 0 e 100")
        if prem.get("margem_pct") is not None:
            numero(prem["margem_pct"], "margem_pct")
    return modo


def preco_pela_margem(custo, tributos, margem):
    """Preço mensal em que (preço x (1 - tributos) - custo) / preço = margem (frações)."""
    divisor = 1 - tributos - margem
    if divisor <= 0:
        raise PedidoInvalido("tributos e margem somam 100% ou mais: não existe preço que feche essa margem")
    return custo / divisor


def margem_do_preco(preco, custo, tributos):
    return (preco * (1 - tributos) - custo) / preco * 100


def classificar(margem_pct, preco_global, valor_estimado, margem_minima):
    """Retorna (exequivel, avisos). Inexequível nunca é escondido."""
    avisos = []
    nivel = "sim"
    if margem_pct < 0:
        nivel = "nao"
        avisos.append(f"Margem negativa ({pct(margem_pct)}): o preço não cobre custo e tributos.")
    elif margem_pct < margem_minima:
        nivel = "no_limite"
        avisos.append(f"Margem {pct(margem_pct)} abaixo da mínima de {pct(margem_minima)}.")
    if valor_estimado and preco_global < valor_estimado * LIMITE_ORCADO_PCT / 100:
        nivel = "nao"
        avisos.append(
            f"Preço global abaixo de {LIMITE_ORCADO_PCT:.0f}% do valor orçado ({reais(valor_estimado * LIMITE_ORCADO_PCT / 100)}): "
            "presunção de inexequibilidade, exige demonstração de custos."
        )
    return nivel, avisos


def calcular(atual, pedido, agora=None):
    """Devolve a precificação nova a partir da atual e do pedido. Não altera `atual`."""
    modo = validar_pedido(pedido)
    custo_atual = atual.get("custo_mensal")
    if isinstance(custo_atual, bool) or not isinstance(custo_atual, (int, float)) or custo_atual <= 0:
        raise PedidoInvalido("precificacao.json atual sem custo_mensal: não há base para aplicar o pedido")
    tributos_pct = atual.get("tributos_pct")
    if isinstance(tributos_pct, bool) or not isinstance(tributos_pct, (int, float)):
        raise PedidoInvalido("precificacao.json atual sem tributos_pct: não há base para aplicar o pedido")
    preco_atual = atual.get("preco_mensal")
    if isinstance(preco_atual, bool) or not isinstance(preco_atual, (int, float)) or preco_atual <= 0:
        raise PedidoInvalido("precificacao.json atual sem preco_mensal: não há base para aplicar o pedido")
    valor_estimado = atual.get("valor_estimado") if isinstance(atual.get("valor_estimado"), (int, float)) else None
    vig = atual.get("vigencia_precificacao") or {}
    meses = vig.get("meses_iniciais")
    if isinstance(meses, bool) or not isinstance(meses, (int, float)) or meses <= 0:
        pg = atual.get("preco_global")
        meses = round(pg / preco_atual) if isinstance(pg, (int, float)) and pg > 0 else None
    if not meses:
        raise PedidoInvalido("precificacao.json atual sem vigência em meses (vigencia_precificacao.meses_iniciais)")
    meses = int(meses)
    margem_minima = atual.get("margem_minima_pct")
    margem_minima = float(margem_minima) if isinstance(margem_minima, (int, float)) and not isinstance(margem_minima, bool) else MARGEM_MINIMA_PADRAO

    novo = copy.deepcopy(atual)
    mo = componente(atual, "mao_de_obra")
    pecas = componente(atual, "pecas")
    custo = float(custo_atual)
    tributos = float(tributos_pct)
    margem_alvo = None  # margem do pedido, quando ele a fixa

    if modo == "preco":
        preco = float(pedido["preco_mensal"])
        rotulo = f"preço mensal de {reais(preco)}"
    elif modo == "desconto":
        if not valor_estimado:
            raise PedidoInvalido("precificacao.json atual sem valor_estimado: o desconto não tem base")
        d = float(pedido["desconto_pct"])
        preco = valor_estimado * (1 - d / 100) / meses
        rotulo = f"desconto de {pct(d)} sobre o valor estimado"
    elif modo == "margem":
        margem_alvo = float(pedido["margem_pct"])
        preco = preco_pela_margem(custo, tributos / 100, margem_alvo / 100)
        rotulo = f"margem de {pct(margem_alvo)}"
    else:
        prem = pedido["premissas"]
        partes = []
        if prem.get("folha_pct") is not None:
            if mo is None:
                raise PedidoInvalido("precificacao.json atual sem componente mao_de_obra: folha_pct não tem base")
            f = float(prem["folha_pct"])
            custo += mo * f / 100
            novo_mo = mo * (1 + f / 100)
            partes.append(f"folha {f:+.1f}%".replace(".", ","))
        else:
            novo_mo = mo
        if prem.get("pecas_fator") is not None:
            if pecas is None:
                raise PedidoInvalido("precificacao.json atual sem componente pecas: pecas_fator não tem base")
            k = float(prem["pecas_fator"])
            custo += pecas * (k - 1)
            novo_pecas = pecas * k
            partes.append(f"peças ×{k:g}".replace(".", ","))
        else:
            novo_pecas = pecas
        if prem.get("tributos_pct") is not None:
            tributos = float(prem["tributos_pct"])
            partes.append(f"tributos {pct(tributos)}")
        margem_alvo = float(prem["margem_pct"]) if prem.get("margem_pct") is not None else float(atual.get("margem_pct") or 0)
        if prem.get("margem_pct") is not None:
            partes.append(f"margem {pct(margem_alvo)}")
        preco = preco_pela_margem(custo, tributos / 100, margem_alvo / 100)
        rotulo = "premissas (" + ", ".join(partes) + ")"
        for item in novo.get("componentes") or []:
            if item.get("componente") == "mao_de_obra" and novo_mo is not None:
                item["valor_mensal"] = round(novo_mo, 2)
            if item.get("componente") == "pecas" and novo_pecas is not None:
                item["valor_mensal"] = round(novo_pecas, 2)

    if preco <= 0:
        raise PedidoInvalido("o pedido resulta em preço zerado ou negativo")

    margem = margem_do_preco(preco, custo, tributos / 100)
    preco_global = preco * meses
    exequivel, avisos = classificar(margem, preco_global, valor_estimado, margem_minima)

    # Preço-alvo anterior: mesmo preço de antes, avaliado com o custo e os tributos de agora.
    anterior = float(preco_atual)
    margem_anterior = margem_do_preco(anterior, custo, tributos / 100)
    exeq_anterior, _ = classificar(margem_anterior, anterior * meses, valor_estimado, margem_minima)

    # Preço na margem mínima (piso) e no limite de 75% do orçado, como referências fixas.
    piso = preco_pela_margem(custo, tributos / 100, margem_minima / 100)
    cenarios = [
        {"nome": f"Pedido: {rotulo}", "preco_mensal": round(preco, 2), "preco_global": round(preco_global, 2),
         "margem_pct": round(margem, 2), "exequivel": exequivel, "origem": "pedido"},
        {"nome": "Preço-alvo anterior", "preco_mensal": round(anterior, 2), "preco_global": round(anterior * meses, 2),
         "margem_pct": round(margem_anterior, 2), "exequivel": exeq_anterior, "origem": "anterior"},
        {"nome": f"Margem mínima ({pct(margem_minima)})", "preco_mensal": round(piso, 2), "preco_global": round(piso * meses, 2),
         "margem_pct": round(margem_minima, 2), "exequivel": classificar(margem_minima, piso * meses, valor_estimado, margem_minima)[0]},
    ]
    if valor_estimado:
        limite_global = valor_estimado * LIMITE_ORCADO_PCT / 100
        limite = limite_global / meses
        m_lim = margem_do_preco(limite, custo, tributos / 100)
        cenarios.append({"nome": f"Limite de {LIMITE_ORCADO_PCT:.0f}% do valor orçado", "preco_mensal": round(limite, 2),
                         "preco_global": round(limite_global, 2), "margem_pct": round(m_lim, 2),
                         "exequivel": "no_limite" if m_lim >= 0 else "nao"})

    sens = []
    if mo is not None:
        base_mo = novo_mo if modo == "premissas" and novo_mo is not None else mo
        sens.append({"rotulo": "Mão de obra +10%", "margem_pct": round(margem_do_preco(preco, custo + base_mo * 0.10, tributos / 100), 2)})
    if pecas is not None and pecas > 0:
        base_p = novo_pecas if modo == "premissas" and novo_pecas is not None else pecas
        sens.append({"rotulo": "Peças +20%", "margem_pct": round(margem_do_preco(preco, custo + base_p * 0.20, tributos / 100), 2)})
    sens.append({"rotulo": "Tributos +1 p.p.", "margem_pct": round(margem_do_preco(preco, custo, (tributos + 1) / 100), 2)})
    sens.append({"rotulo": "Preço −5%", "margem_pct": round(margem_do_preco(preco * 0.95, custo, tributos / 100), 2)})

    for item in novo.get("componentes") or []:
        if item.get("componente") == "tributos":
            item["valor_mensal"] = round(preco * tributos / 100, 2)
        elif item.get("componente") == "margem":
            item["valor_mensal"] = round(preco * (1 - tributos / 100) - custo, 2)

    novo.update({
        "gerado_em": (agora or datetime.now()).strftime("%Y-%m-%dT%H:%M"),
        "custo_mensal": round(custo, 2),
        "preco_mensal": round(preco, 2),
        "preco_global": round(preco_global, 2),
        "margem_pct": round(margem, 2),
        "tributos_pct": round(tributos, 2),
        "exequivel": exequivel,
        "piso_sugerido": round(piso, 2),
        "cenarios": cenarios,
        "sensibilidade": sens,
        "pedido": copy.deepcopy(pedido),
        "preco_anterior": {"preco_mensal": round(anterior, 2), "preco_global": round(anterior * meses, 2),
                           "margem_pct": round(margem_anterior, 2)},
        "avisos_pedido": avisos,
    })
    if isinstance(atual.get("bdi_pct"), (int, float)) and not isinstance(atual.get("bdi_pct"), bool):
        novo["bdi_pct"] = round((preco / custo - 1) * 100, 2)
    frase = (f"Pedido: {rotulo}. Preço mensal {reais(preco)}, global {reais(preco_global)} em {meses} meses, "
             f"margem {pct(margem)}, exequibilidade: {exequivel.replace('_', ' ')}.")
    if avisos:
        frase += " " + " ".join(avisos)
    if pedido.get("recado"):
        frase += f" Recado considerado: {str(pedido['recado']).strip()}"
    if vig.get("recomendacao"):
        frase += " " + str(vig["recomendacao"]).strip()
    novo["resumo"] = frase
    return novo


def ajustar_dados_planilha(dados, pedido, resultado):
    """Dados da planilha de composição (`dados.json` de preencher_planilha.py) ajustados ao pedido."""
    novo = copy.deepcopy(dados)
    prem = novo.setdefault("premissas", {})
    fonte = f"Pedido de precificação de {pedido.get('pedido_em') or 'data não informada'}"
    prem["preco_mensal"] = {"valor": resultado["preco_mensal"], "fonte": fonte}
    if pedido.get("modo") == "premissas":
        p = pedido["premissas"]
        if p.get("tributos_pct") is not None:
            prem["tributos"] = {"valor": round(float(p["tributos_pct"]) / 100, 6), "fonte": fonte}
        if p.get("folha_pct") is not None:
            k = 1 + float(p["folha_pct"]) / 100
            for linha in novo.get("mao_de_obra") or []:
                if isinstance(linha, list):
                    for i in (2, 4):  # salário/honorário e benefícios
                        if len(linha) > i and isinstance(linha[i], (int, float)):
                            linha[i] = round(linha[i] * k, 2)
        if p.get("pecas_fator") is not None:
            k = float(p["pecas_fator"])
            for linha in novo.get("pecas") or []:
                if isinstance(linha, list) and len(linha) > 2 and isinstance(linha[2], (int, float)):
                    linha[2] = round(linha[2] * k, 2)
            grupo = (novo.get("operacao") or {}).get("pecas")
            if isinstance(grupo, dict) and isinstance(grupo.get("mensal"), (int, float)):
                grupo["mensal"] = round(grupo["mensal"] * k, 2)
    return novo


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("precificacao")
    ap.add_argument("pedido")
    ap.add_argument("saida")
    ap.add_argument("--dados", help="dados.json da planilha de composição, para ajustar ao pedido")
    ap.add_argument("--dados-saida", help="onde gravar o dados.json ajustado")
    args = ap.parse_args(argv)
    try:
        atual = json.loads(Path(args.precificacao).read_text(encoding="utf-8"))
        pedido = json.loads(Path(args.pedido).read_text(encoding="utf-8"))
        resultado = calcular(atual, pedido)
        if args.dados:
            if not args.dados_saida:
                raise PedidoInvalido("--dados exige --dados-saida")
            dados = json.loads(Path(args.dados).read_text(encoding="utf-8"))
            Path(args.dados_saida).write_text(
                json.dumps(ajustar_dados_planilha(dados, pedido, resultado), ensure_ascii=False, indent=1), encoding="utf-8")
    except (PedidoInvalido, OSError, json.JSONDecodeError) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2
    Path(args.saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: resultado[k] for k in ("preco_mensal", "preco_global", "margem_pct", "exequivel")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
