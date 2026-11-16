"""Consulta a base de custos e devolve os valores para a planilha de proposta.

Uso:
    python consultar_base.py base-custos.json --empresa aforca
    python consultar_base.py base-custos.json --empresa aforca --cargo "Técnico de manutenção" [--cenario base|conservador|otimista]
    python consultar_base.py base-custos.json --listar

Sem --cargo, mostra tributos, encargos e administração central da empresa.
Com --cargo, mostra a linha pronta para a aba Custos MO do modelo:
    C (salário/honorário base), D (encargos/adicionais) e E (benefícios/despesas),
    de modo que C × (1 + D) + E feche no custo mensal de referência do cenário.

Cenário: base = mediana, conservador = máximo, otimista = mínimo da faixa.
Quando a empresa não tem o cargo, usa a faixa do grupo e avisa.
"""

import argparse
import json
import sys
import unicodedata

CENARIOS = {"base": "med", "conservador": "max", "otimista": "min"}
DIAS_BENEFICIO = 21
DESCONTO_VT = 0.06


def chave(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode()
    return t.lower().strip()


def achar_cargo(lista, cargo, empresa=None, vinculo="clt"):
    for c in lista:
        mesmo = chave(c["cargo"]) == chave(cargo) and c["vinculo"] == vinculo
        if mesmo and (empresa is None or c["empresa"] == empresa):
            return c
    return None


def empresa_slug(base, nome):
    k = chave(nome).replace(" ", "")
    for slug, e in base["empresas"].items():
        if slug == k or chave(e["nome"]).replace(" ", "") == k:
            return slug
    sys.exit(f"Empresa '{nome}' não está na base. Disponíveis: {', '.join(base['empresas'])}")


def resumo_empresa(base, slug):
    e = base["empresas"][slug]
    return {
        "empresa": e["nome"],
        "competencia": base["competencia"],
        "aliquota_tributos": e["tributos"].get("aliquota"),
        "retencao_tipica": e["tributos"].get("retencao_tipica"),
        "pendencia_tributos": e["tributos"].get("pendente"),
        "encargos_sociais": e["encargos_sociais"],
        "beneficios": e["beneficios"],
        "administracao_central_mensal": e["administracao_central"]["custo_mensal"],
    }


def linha_custos_mo(base, slug, cargo, cenario, vinculo):
    campo = CENARIOS[cenario]
    empresa = base["empresas"][slug]
    faixa = achar_cargo(base["cargos_por_empresa"], cargo, slug, vinculo)
    origem = f"faixa da {empresa['nome']}"
    if not faixa:
        faixa = achar_cargo(base["cargos_grupo"], cargo, vinculo=vinculo)
        origem = "faixa do grupo (a empresa não tem esse cargo na planilha)"
    if not faixa:
        disponiveis = sorted({c["cargo"] for c in base["cargos_grupo"]})
        sys.exit(f"Cargo '{cargo}' não está na base. Disponíveis: {', '.join(disponiveis)}")

    custo = faixa["custo_mensal"][campo]
    if vinculo == "prestador" or not faixa.get("salario_base"):
        return {
            "cargo": faixa["cargo"],
            "origem": origem,
            "cenario": cenario,
            "n_pessoas": faixa["n"],
            "C_salario_base": round(custo, 2),
            "D_encargos_adicionais": 0.0,
            "E_beneficios": 0.0,
            "custo_mensal_referencia": custo,
            "custo_hora_referencia": faixa["custo_hora"][campo],
            "nota": "prestador: honorário mensal cheio em C, sem encargos",
        }

    salario = faixa["salario_base"][campo]
    peric = faixa.get("periculosidade") or 0.0
    c = salario * (1 + peric)
    d = empresa["encargos_sociais"]["total"] or 0.0
    ben = empresa["beneficios"]
    beneficios = max(
        0.0,
        ((ben.get("vr_dia") or 0) + (ben.get("vt_dia") or 0)) * DIAS_BENEFICIO
        - DESCONTO_VT * salario,
    )
    composicao = c * (1 + d) + beneficios
    outros = custo - composicao
    avisos = []
    if "grupo" in origem:
        # O custo de outra empresa traz o regime de encargos dela; aqui vale só a composição legal.
        avisos.append(
            "faixa de salário vinda de outras empresas do grupo; a linha usa a composição legal da empresa escolhida, "
            f"e o custo de referência do grupo foi {custo:.2f}"
        )
        outros = 0.0
    elif outros < 0:
        avisos.append(
            "custo de referência abaixo da composição legal; a linha usa a composição legal (mais conservadora)"
        )
        outros = 0.0
    elif outros > 0.25 * custo:
        avisos.append(
            "mais de 25% do custo vem de itens fora da composição legal (horas extras, diferenças, gratificações); "
            "confirme se o contrato terá esses itens antes de usar o custo cheio"
        )
    e = beneficios + outros
    return {
        "cargo": faixa["cargo"],
        "origem": origem,
        "cenario": cenario,
        "n_pessoas": faixa["n"],
        "C_salario_base": round(c, 2),
        "D_encargos_adicionais": round(d, 4),
        "E_beneficios": round(e, 2),
        "E_detalhe": {"vr_vt": round(beneficios, 2), "outros_itens_folha": round(outros, 2)},
        "custo_mensal_linha": round(c * (1 + d) + e, 2),
        "custo_mensal_referencia": custo,
        "custo_hora_referencia": faixa["custo_hora"][campo],
        "avisos": avisos,
        "nota": (
            "C = salário da faixa com periculosidade; D = encargos sociais da empresa; "
            "E = VR + VT de 21 dias menos 6% de VT, mais os demais itens da folha que completam o custo de referência"
        ),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("base")
    ap.add_argument("--empresa")
    ap.add_argument("--cargo")
    ap.add_argument("--cenario", choices=CENARIOS, default="base")
    ap.add_argument(
        "--prestador", action="store_true", help="usar a faixa de prestador de serviço"
    )
    ap.add_argument("--listar", action="store_true", help="lista empresas e cargos da base")
    a = ap.parse_args()
    with open(a.base, encoding="utf-8") as f:
        base = json.load(f)

    if a.listar or not a.empresa:
        saida = {
            "competencia": base["competencia"],
            "empresas": {
                k: e["nome"] for k, e in base["empresas"].items() if not k.startswith("_")
            },
            "cargos": sorted({(c["cargo"], c["vinculo"]) for c in base["cargos_grupo"]}),
            "alertas": base["alertas"],
        }
    else:
        slug = empresa_slug(base, a.empresa)
        saida = resumo_empresa(base, slug)
        if a.cargo:
            saida["custos_mo"] = linha_custos_mo(
                base, slug, a.cargo, a.cenario, "prestador" if a.prestador else "clt"
            )
    print(json.dumps(saida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
