"""Ingere a planilha de custos de pessoal do grupo e grava a base de custos da precificação.

Uso:
    uv run --with openpyxl python ingerir_custos.py PLANILHA.xls[x] PASTA_SAIDA [--competencia AAAA-MM]

Lê a planilha no formato "TODOS_FUNCIONARIOS" (uma aba de composição por pessoa, abas de
segmento com lucro/impostos e despesas fixas, aba Faturamento com a alíquota por empresa) e grava:

    base-custos.json   fonte da skill: faixas por cargo, tributos e encargos por empresa
    base-custos.xlsx   a mesma base para leitura e conferência

A base não leva nome de pessoa. Cargos administrativos e sócios entram só no total de
administração central de cada empresa.
"""

import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import unicodedata
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L

VERSAO = 1

EMPRESAS = {
    "realmak": "Realmak",
    "aforca": "AForça",
    "nortfort": "Nortfort",
    "una": "UNA",
    "alfa": "Alfa",
}

# Ordem importa: o primeiro padrão que casar define o cargo.
CARGOS = [
    (r"aux\w*\.? ?t[eé]c", "Auxiliar técnico"),
    (r"eletrot[eé]cnic", "Eletrotécnico"),
    (r"^t[eé]c", "Técnico de manutenção"),
    (r"ajudante", "Ajudante geral"),
    (r"meio oficial", "Meio oficial"),
    (r"^oficial", "Oficial"),
    (r"eng\w* ?mec", "Engenheiro mecânico"),
    (r"eng\w* ?el[eé]t", "Engenheiro eletricista"),
    (r"eng\w* ?civil", "Engenheiro civil"),
    (r"vidraceir", "Vidraceiro"),
    (r"^eng", "Engenheiro"),
]

SETORES_EXECUCAO = {"execucao", "engenharia", "proposta"}

ROTULOS = {
    "salario": "1.1",
    "subtotal": "1.3",
    "inss_desc": "INSS",
    "vr": "Vale Refei",
    "vt": "Vale Transp",
    "grupo_a": "3.1",
    "grupo_b": "3.2",
    "grupo_c": "3.3",
    "grupo_d": "3.4",
    "grupo_e": "3.5",
    "encargos": "VALOR DOS ENCARGOS",
    "insumos": "IV.",
    "custo": "VII.",
    "horas": "HORAS DE TRAB",
}

ADICIONAIS = {
    "a)": "gratificacao",
    "b)": "insalubridade",
    "c)": "periculosidade",
    "d)": "hora_extra",
}


def brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def chave(texto):
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def empresa_de(texto):
    k = chave(texto).replace(" ", "")
    for slug in EMPRESAS:
        if k.startswith(slug):
            return slug
    return None


def cargo_de(funcao):
    f = chave(funcao)
    for padrao, nome in CARGOS:
        if re.search(padrao, f):
            return nome
    return None


def abrir(caminho):
    """Abre .xlsx direto; converte .xls com o LibreOffice numa pasta temporária."""
    caminho = Path(caminho)
    if caminho.suffix.lower() == ".xlsx":
        return load_workbook(caminho, data_only=True)
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        sys.exit(
            "Planilha .xls precisa do LibreOffice (soffice) para converter. Salve como .xlsx."
        )
    tmp = Path(tempfile.mkdtemp())
    origem = tmp / "entrada.xls"
    shutil.copy(caminho, origem)
    subprocess.run(
        [soffice, "--headless", "--convert-to", "xlsx", "--outdir", str(tmp), str(origem)],
        check=True,
        capture_output=True,
    )
    return load_workbook(tmp / "entrada.xlsx", data_only=True)


def linhas_por_rotulo(ws):
    achadas = {}
    for r in range(1, min(ws.max_row, 140) + 1):
        a = ws.cell(r, 1).value
        if not isinstance(a, str):
            continue
        a = a.strip()
        for campo, prefixo in ROTULOS.items():
            if campo not in achadas and a.startswith(prefixo):
                achadas[campo] = r
    return achadas


def total_do_grupo(ws, inicio):
    """Percentual na coluna B da linha TOTAL: que vem depois do título do grupo."""
    for r in range(inicio, inicio + 14):
        a = ws.cell(r, 1).value
        if isinstance(a, str) and a.strip().upper().startswith("TOTAL"):
            return num(ws.cell(r, 2).value)
    return None


def ler_pessoa(ws):
    """Uma aba de composição de custo de uma pessoa. Devolve None se não for desse tipo."""
    if not str(ws["A3"].value or "").strip().startswith("II"):
        return None
    lin = linhas_por_rotulo(ws)
    if "salario" not in lin or "custo" not in lin:
        return None
    setor = chave(ws["D2"].value)
    empresa_txt = ws["B2"].value
    vinculo = "prestador" if "prestador" in chave(empresa_txt) else "clt"
    custo = num(ws.cell(lin["custo"], 2).value) or num(ws["H29"].value)
    horas = num(ws.cell(lin["horas"], 2).value) if "horas" in lin else None
    salario = num(ws.cell(lin["salario"], 2).value)
    adicionais = {}
    for r in range(lin["salario"] + 1, lin.get("subtotal", lin["salario"] + 10)):
        a = str(ws.cell(r, 1).value or "").strip()
        for pref, nome in ADICIONAIS.items():
            if a.startswith(pref):
                adicionais[nome] = num(ws.cell(r, 2).value) or 0.0
    vr = num(ws.cell(lin["vr"], 2).value) if "vr" in lin else None
    vt = num(ws.cell(lin["vt"], 2).value) if "vt" in lin else None
    grupos = {
        g: total_do_grupo(ws, lin[g])
        for g in ("grupo_a", "grupo_b", "grupo_c", "grupo_d", "grupo_e")
        if g in lin
    }
    encargos = num(ws.cell(lin["encargos"], 2).value) if "encargos" in lin else None
    return {
        "aba": ws.title,
        "empresa": empresa_de(empresa_txt),
        "empresa_txt": str(empresa_txt or "").strip(),
        "vinculo": vinculo,
        "funcao": str(ws["C2"].value or "").strip(),
        "cargo": cargo_de(re.sub(r"^a pagar ", "", chave(ws["A2"].value)))
        if chave(ws["A2"].value).startswith("a pagar")
        and cargo_de(re.sub(r"^a pagar ", "", chave(ws["A2"].value)))
        else cargo_de(ws["C2"].value),
        "setor": setor,
        "segmento": str(ws["E2"].value or "").strip(),
        # Composição montada para proposta: aba ou nome começando com "A pagar".
        "modelo_proposta": chave(ws.title).startswith("a pagar")
        or chave(ws["A2"].value).startswith("a pagar"),
        "salario": salario,
        "adicionais": adicionais,
        "vr_dia": vr,
        "vt_dia": vt,
        "encargos_grupos": grupos,
        "encargos_pct": encargos,
        "custo_mensal": custo,
        "horas_mes": horas,
    }


def faixa(valores):
    v = sorted(x for x in valores if x is not None)
    if not v:
        return None
    return {
        "min": round(v[0], 2),
        "med": round(statistics.median(v), 2),
        "media": round(statistics.fmean(v), 2),
        "max": round(v[-1], 2),
    }


def moda(valores):
    v = [round(x, 4) for x in valores if x is not None]
    return statistics.mode(v) if v else None


def ler_faturamento(ws):
    cab = {chave(ws.cell(1, c).value): c for c in range(1, ws.max_column + 1)}
    ce, ci, cr = cab.get("empresa"), cab.get("imposto"), cab.get("impostos retido")
    if not (ce and ci):
        return {}
    por = {}
    for r in range(2, ws.max_row + 1):
        emp = empresa_de(ws.cell(r, ce).value)
        aliq = num(ws.cell(r, ci).value)
        if not emp or aliq is None:
            continue
        d = por.setdefault(emp, {"aliquotas": [], "retencoes": []})
        d["aliquotas"].append(aliq)
        ret = num(ws.cell(r, cr).value) if cr else None
        if ret is not None and 0 <= ret < 0.5:
            d["retencoes"].append(ret)
    saida = {}
    for emp, d in por.items():
        saida[emp] = {
            "aliquota": moda(d["aliquotas"]),
            "aliquotas_vistas": sorted({round(x, 4) for x in d["aliquotas"]}),
            "retencao_tipica": moda(d["retencoes"]),
            "notas": len(d["aliquotas"]),
            "fonte": f"aba {ws.title}, coluna Imposto",
        }
    return saida


def ler_segmento(ws):
    """Aba de segmento: lucro/impostos no topo, despesas mensais da empresa na lista."""
    if chave(ws["A1"].value) != "cem por cento":
        return None
    seg = {"aba": ws.title, "markups": [], "despesas": [], "rota": None}
    for r in range(1, ws.max_row + 1):
        if chave(ws.cell(r, 1).value) == "cem por cento":
            lucro, imp, adic = (num(ws.cell(r + 1, c).value) for c in (2, 3, 4))
            if lucro is not None:
                seg["markups"].append({"lucro": lucro, "impostos": imp, "adicionais": adic or 0.0})
    # Rota: KM/DIA e V. LT da primeira rota
    cab = {chave(ws.cell(1, c).value): c for c in range(1, ws.max_column + 1)}
    if "kmdia" in cab and "v lt" in cab:
        km, lt = num(ws.cell(2, cab["kmdia"]).value), num(ws.cell(2, cab["v lt"]).value)
        if km is not None:
            seg["rota"] = {"km_dia": km, "preco_litro": lt}
    ignorar = ("funcionarios", "equipe", "rota", "custo", "valor", "descricao", "pecas")
    bloco = "despesa"
    for r in range(1, ws.max_row + 1):
        a = ws.cell(r, 1).value
        k = chave(a)
        if k.startswith("custo total de pecas") or k.startswith("pecas"):
            bloco = "pecas"
        if not k or k.startswith(ignorar) or k == "cem por cento":
            continue
        qtd, val = num(ws.cell(r, 2).value), num(ws.cell(r, 3).value)
        total = num(ws.cell(r, 4).value)
        if not total or bloco == "pecas":
            continue
        tipo = (
            "tributo pago"
            if empresa_de(k.split()[0]) or re.search(r"\b(fco|csll|irpj|icms|pis|cofins|iss)\b", k)
            else "despesa"
        )
        seg["despesas"].append(
            {
                "item": str(a).strip(),
                "valor_mensal": round(total, 2),
                "tipo": tipo,
                "qtd": qtd,
                "valor": val,
            }
        )
    return seg


def agrupar_cargos(pessoas, por_empresa):
    grupos = {}
    for p in pessoas:
        k = (p["cargo"], p["empresa"] if por_empresa else "grupo", p["vinculo"])
        grupos.setdefault(k, []).append(p)
    saida = []
    for (cargo, emp, vinc), ps in sorted(
        grupos.items(), key=lambda x: (x[0][0], x[0][1] or "", x[0][2])
    ):
        horas = moda([p["horas_mes"] for p in ps]) or 176
        custos = [p["custo_mensal"] for p in ps]
        saida.append(
            {
                "cargo": cargo,
                "empresa": emp,
                "vinculo": vinc,
                "n": len(ps),
                "salario_base": faixa([p["salario"] for p in ps if p["salario"]]),
                "periculosidade": moda([p["adicionais"].get("periculosidade") for p in ps]),
                "custo_mensal": faixa(custos),
                "horas_mes": horas,
                "custo_hora": faixa([c / horas for c in custos]),
            }
        )
    return saida


def ingerir(caminho, competencia):
    wb = abrir(caminho)
    pessoas, descartadas, segmentos, faturamento = [], [], [], {}
    for ws in wb.worksheets:
        if chave(ws.title) == "faturamento":
            faturamento = ler_faturamento(ws)
            continue
        seg = ler_segmento(ws)
        if seg:
            segmentos.append(seg)
            continue
        p = ler_pessoa(ws)
        if not p:
            continue
        if not p["custo_mensal"] or p["custo_mensal"] <= 0:
            descartadas.append({"motivo": "sem custo", "funcao": p["funcao"]})
            continue
        pessoas.append(p)

    execucao = [
        p
        for p in pessoas
        if p["cargo"] and p["setor"] in SETORES_EXECUCAO and not p["modelo_proposta"]
    ]
    modelos = [p for p in pessoas if p["modelo_proposta"] and p["cargo"]]
    administrativos = [p for p in pessoas if p not in execucao and p not in modelos]

    empresas = {}
    for slug, nome in EMPRESAS.items():
        clt = [p for p in execucao + modelos if p["empresa"] == slug and p["vinculo"] == "clt"]
        adm = [p for p in administrativos if p["empresa"] == slug]
        trib = faturamento.get(slug)
        grupos = {}
        for g in ("grupo_a", "grupo_b", "grupo_c", "grupo_d", "grupo_e"):
            grupos[g] = moda([p["encargos_grupos"].get(g) for p in clt])
        empresas[slug] = {
            "nome": nome,
            "tributos": trib
            or {
                "aliquota": None,
                "pendente": "alíquota não encontrada na planilha; confirmar com a contabilidade",
            },
            "encargos_sociais": {
                "total": moda([p["encargos_pct"] for p in clt]),
                "grupos": grupos,
                "pessoas_base": len(clt),
            },
            "beneficios": {
                "vr_dia": moda([p["vr_dia"] for p in clt]),
                "vt_dia": moda([p["vt_dia"] for p in clt]),
            },
            "administracao_central": {
                "pessoas": len(adm),
                "custo_mensal": round(sum(p["custo_mensal"] for p in adm), 2),
                "nota": "pessoal administrativo, sócios e apoio; rateio entre os contratos da empresa",
            },
        }

    sem_empresa = [p for p in administrativos if not p["empresa"]]
    if sem_empresa:
        empresas["_prestadores_e_sem_empresa"] = {
            "nome": "Prestadores e sem empresa definida",
            "administracao_central": {
                "pessoas": len(sem_empresa),
                "custo_mensal": round(sum(p["custo_mensal"] for p in sem_empresa), 2),
                "nota": "apoio (jurídico, outros) sem empresa do grupo identificada",
            },
        }

    markups, despesas, rotas = [], [], []
    for s in segmentos:
        for i, m in enumerate(s["markups"]):
            alvo = "peças" if i == 1 else "mão de obra e serviço"
            markups.append({"segmento": s["aba"].strip().title(), "aplica_a": alvo, **m})
        for d in s["despesas"]:
            despesas.append({"segmento": s["aba"].strip().title(), **d})
        if s["rota"]:
            rotas.append(s["rota"]["preco_litro"])

    alertas = []
    clt_grupo = [p for p in execucao + modelos if p["vinculo"] == "clt"]
    padrao_grupo = {
        "total": moda([p["encargos_pct"] for p in clt_grupo]),
        "grupos": {
            g: moda([p["encargos_grupos"].get(g) for p in clt_grupo])
            for g in ("grupo_a", "grupo_b", "grupo_c", "grupo_d", "grupo_e")
        },
    }
    for slug, e in empresas.items():
        if slug.startswith("_"):
            continue
        if not e["tributos"].get("aliquota"):
            alertas.append(
                f"{e['nome']}: alíquota de tributos não encontrada; confirmar antes de precificar."
            )
        enc = e["encargos_sociais"]
        if not enc["pessoas_base"]:
            enc.update(
                padrao_grupo, origem="padrão do grupo (empresa sem CLT de execução na planilha)"
            )
            alertas.append(
                f"{e['nome']}: sem CLT de execução na planilha; encargos copiados do padrão do grupo."
            )
        else:
            enc["origem"] = f"{enc['pessoas_base']} composições da empresa"
    grupo_a = {
        e["nome"]: e["encargos_sociais"]["grupos"]["grupo_a"]
        for k, e in empresas.items()
        if not k.startswith("_")
    }
    if len({v for v in grupo_a.values() if v is not None}) > 1:
        alertas.append(
            "Encargos do Grupo A diferem entre empresas ("
            + ", ".join(
                f"{n} {v:.1%}".replace(".", ",") for n, v in grupo_a.items() if v is not None
            )
            + "): reflete o regime tributário de cada uma. Confirmar o regime com a contabilidade."
        )
    for c in agrupar_cargos(execucao, True):
        cm = c["custo_mensal"]
        if c["n"] > 1 and cm["min"] and cm["max"] / cm["min"] > 2:
            nome = EMPRESAS.get(c["empresa"], "prestadores")
            alertas.append(
                f"{c['cargo']} ({nome}): faixa larga, de {brl(cm['min'])} a {brl(cm['max'])}. Use a mediana e confira o caso extremo."
            )
    for d in descartadas:
        alertas.append(f"Aba de pessoa sem custo descartada (função: {d['funcao'] or 'vazia'}).")
    sem_funcao = [p for p in pessoas if not p["funcao"] and p["setor"] in SETORES_EXECUCAO]
    if sem_funcao:
        alertas.append(
            f"{len(sem_funcao)} aba(s) de execução sem função preenchida ficaram fora das faixas."
        )
    sem_cargo = sorted(
        {
            p["funcao"]
            for p in pessoas
            if p["funcao"] and not p["cargo"] and p["setor"] in SETORES_EXECUCAO
        }
    )
    if sem_cargo:
        alertas.append(
            "Funções de execução sem cargo padrão (fora das faixas): " + ", ".join(sem_cargo)
        )
    alertas.append(
        "Custo mensal por pessoa é o custo cheio da planilha (salário, adicionais, encargos, VR, VT e diferenças), sem lucro nem tributo."
    )

    return {
        "versao": VERSAO,
        "competencia": competencia,
        "gerado_em": date.today().isoformat(),
        "fonte": {
            "arquivo": Path(caminho).name,
            "abas_pessoa": len(pessoas),
            "abas_segmento": len(segmentos),
        },
        "parametros": {
            "horas_mes": moda([p["horas_mes"] for p in pessoas]) or 176,
            "dias_uteis_mes": 21,
            "km_por_litro": 10,
            "dias_rota_mes": 22,
            "preco_litro": moda(rotas),
        },
        "empresas": empresas,
        "cargos_por_empresa": agrupar_cargos(execucao, True),
        "cargos_grupo": agrupar_cargos(execucao, False),
        "modelos_proposta": [
            {
                "cargo": p["cargo"],
                "empresa": p["empresa"],
                "salario_base": p["salario"],
                "periculosidade": p["adicionais"].get("periculosidade"),
                "encargos_pct": p["encargos_pct"],
                "custo_mensal": round(p["custo_mensal"], 2),
                "custo_hora": round(p["custo_mensal"] / (p["horas_mes"] or 176), 2),
            }
            for p in modelos
        ],
        "markup_referencia": markups,
        "despesas_mensais_empresa": despesas,
        "alertas": alertas,
    }


# ---------------------------------------------------------------- planilha de leitura

TITULO_BG, SECAO_BG, CAB_BG, SUB_BG = "164E63", "0F766E", "BAE6FD", "F8FAFC"
FONTE = "Aptos"
_fino = Side(style="thin", color="CBD5E1")
BORDA = Border(left=_fino, right=_fino, top=_fino, bottom=_fino)
MOEDA, PCT, NUM = "R$ #,##0.00", "0.00%", "#,##0"


def _aba(wb, nome, titulo, subtitulo, larguras, primeira=False):
    ws = wb.active if primeira else wb.create_sheet(nome)
    ws.title = nome
    ws.sheet_view.showGridLines = False
    for i, w in enumerate(larguras, 1):
        ws.column_dimensions[L(i)].width = w
    for r, (txt, bg, fonte, h) in enumerate(
        [
            (titulo, TITULO_BG, Font(name=FONTE, size=15, bold=True, color="FFFFFF"), 30),
            (subtitulo, SUB_BG, Font(name=FONTE, size=10, color="475569"), 30),
        ],
        1,
    ):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(larguras))
        c = ws.cell(r, 1, txt)
        c.fill, c.font = PatternFill("solid", fgColor=bg), fonte
        c.alignment = Alignment(vertical="center", wrap_text=True, indent=1)
        ws.row_dimensions[r].height = h
    return ws


def _tabela(ws, linha, cabecalho, linhas, formatos):
    for i, n in enumerate(cabecalho, 1):
        c = ws.cell(linha, i, n)
        c.fill, c.border = PatternFill("solid", fgColor=CAB_BG), BORDA
        c.font = Font(name=FONTE, size=10, bold=True, color="1F2937")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[linha].height = 30
    ws.freeze_panes = ws.cell(linha + 1, 1)
    for r, valores in enumerate(linhas, linha + 1):
        for i, v in enumerate(valores, 1):
            c = ws.cell(r, i, v)
            c.border, c.font = BORDA, Font(name=FONTE, size=10, color="1F2937")
            c.alignment = Alignment(vertical="top", wrap_text=True)
            if formatos[i - 1]:
                c.number_format = formatos[i - 1]
    if linhas:
        ws.auto_filter.ref = f"A{linha}:{L(len(cabecalho))}{linha + len(linhas)}"


def _f(d, k):
    return (d or {}).get(k)


def gravar_xlsx(base, destino):
    wb = Workbook()
    emp = {k: v for k, v in base["empresas"].items() if not k.startswith("_")}

    ws = _aba(
        wb,
        "Leia-me",
        "BASE DE CUSTOS DA PRECIFICAÇÃO",
        f"Competência {base['competencia']} · fonte {base['fonte']['arquivo']} · gerada em {base['gerado_em']}. "
        "Arquivo gerado por ingerir_custos.py: não edite à mão, atualize a planilha de origem e rode de novo.",
        [34, 90],
        primeira=True,
    )
    _tabela(
        ws,
        4,
        ["Aba", "O que tem"],
        [
            [
                "Tributos",
                "Alíquota sobre o faturamento e retenção típica de cada empresa (aba Faturamento).",
            ],
            ["Encargos", "Encargos sociais por grupo (A a E) e benefícios por empresa."],
            [
                "Cargos por empresa",
                "Faixa mínima, mediana e máxima de salário, custo mensal e custo-hora por cargo de execução.",
            ],
            [
                "Cargos no grupo",
                "As mesmas faixas juntando as empresas; use quando a empresa não tiver o cargo.",
            ],
            ["Modelos de proposta", "Composições 'A Pagar' usadas como cargo de proposta."],
            [
                "Markup e despesas",
                "Lucro e impostos usados por segmento e despesas mensais fixas da empresa.",
            ],
            ["Alertas", "O que falta ou precisa de confirmação antes de usar a base."],
        ],
        [None, None],
    )

    ws = _aba(
        wb,
        "Tributos",
        "TRIBUTOS SOBRE O FATURAMENTO",
        "Alíquota efetiva mais usada nas notas de cada empresa.",
        [18, 14, 26, 16, 10, 40],
    )
    _tabela(
        ws,
        4,
        [
            "Empresa",
            "Alíquota",
            "Alíquotas vistas",
            "Retenção típica",
            "Notas",
            "Fonte / pendência",
        ],
        [
            [
                e["nome"],
                _f(e["tributos"], "aliquota"),
                ", ".join(f"{x:.2%}" for x in e["tributos"].get("aliquotas_vistas", [])),
                _f(e["tributos"], "retencao_tipica"),
                _f(e["tributos"], "notas"),
                e["tributos"].get("fonte") or e["tributos"].get("pendente"),
            ]
            for e in emp.values()
        ],
        [None, PCT, None, PCT, NUM, None],
    )

    ws = _aba(
        wb,
        "Encargos",
        "ENCARGOS SOCIAIS E BENEFÍCIOS",
        "Percentuais sobre a remuneração (salário + adicionais).",
        [18, 11, 11, 11, 11, 11, 12, 12, 12, 14, 16],
    )
    _tabela(
        ws,
        4,
        [
            "Empresa",
            "Grupo A",
            "Grupo B",
            "Grupo C",
            "Grupo D",
            "Grupo E",
            "Total",
            "VR/dia",
            "VT/dia",
            "Pessoas base",
            "Adm. central R$/mês",
        ],
        [
            [
                e["nome"],
                *(
                    e["encargos_sociais"]["grupos"].get(g)
                    for g in ("grupo_a", "grupo_b", "grupo_c", "grupo_d", "grupo_e")
                ),
                e["encargos_sociais"]["total"],
                e["beneficios"]["vr_dia"],
                e["beneficios"]["vt_dia"],
                e["encargos_sociais"]["pessoas_base"],
                e["administracao_central"]["custo_mensal"],
            ]
            for e in emp.values()
        ],
        [None, PCT, PCT, PCT, PCT, PCT, PCT, MOEDA, MOEDA, NUM, MOEDA],
    )

    cab = [
        "Cargo",
        "Empresa",
        "Vínculo",
        "N",
        "Salário mín",
        "Salário med",
        "Salário máx",
        "Periculosidade",
        "Custo mín",
        "Custo med",
        "Custo máx",
        "Horas/mês",
        "R$/h mín",
        "R$/h med",
        "R$/h máx",
    ]
    fmt = [
        None,
        None,
        None,
        NUM,
        MOEDA,
        MOEDA,
        MOEDA,
        PCT,
        MOEDA,
        MOEDA,
        MOEDA,
        NUM,
        MOEDA,
        MOEDA,
        MOEDA,
    ]
    larg = [24, 14, 11, 6, 13, 13, 13, 13, 13, 13, 13, 10, 11, 11, 11]

    def linhas_cargo(lista):
        out = []
        for c in lista:
            out.append(
                [
                    c["cargo"],
                    EMPRESAS.get(c["empresa"], "Grupo" if c["empresa"] == "grupo" else "—"),
                    c["vinculo"].upper() if c["vinculo"] == "clt" else "Prestador",
                    c["n"],
                    _f(c["salario_base"], "min"),
                    _f(c["salario_base"], "med"),
                    _f(c["salario_base"], "max"),
                    c["periculosidade"],
                    _f(c["custo_mensal"], "min"),
                    _f(c["custo_mensal"], "med"),
                    _f(c["custo_mensal"], "max"),
                    c["horas_mes"],
                    _f(c["custo_hora"], "min"),
                    _f(c["custo_hora"], "med"),
                    _f(c["custo_hora"], "max"),
                ]
            )
        return out

    ws = _aba(
        wb,
        "Cargos por empresa",
        "FAIXAS DE CUSTO POR CARGO E EMPRESA",
        "Custo mensal cheio por pessoa, sem lucro e sem tributo. Base = mediana; conservador = máximo.",
        larg,
    )
    _tabela(ws, 4, cab, linhas_cargo(base["cargos_por_empresa"]), fmt)
    ws = _aba(
        wb,
        "Cargos no grupo",
        "FAIXAS DE CUSTO POR CARGO NO GRUPO",
        "Todas as empresas juntas. Use quando a empresa escolhida não tiver o cargo.",
        larg,
    )
    _tabela(ws, 4, cab, linhas_cargo(base["cargos_grupo"]), fmt)

    ws = _aba(
        wb,
        "Modelos de proposta",
        "COMPOSIÇÕES DE PROPOSTA",
        "Abas 'A Pagar' da planilha: cargos montados para proposta.",
        [24, 14, 14, 14, 14, 14, 14],
    )
    _tabela(
        ws,
        4,
        ["Cargo", "Empresa", "Salário base", "Periculosidade", "Encargos", "Custo mensal", "R$/h"],
        [
            [
                m["cargo"],
                EMPRESAS.get(m["empresa"], "—"),
                m["salario_base"],
                m["periculosidade"],
                m["encargos_pct"],
                m["custo_mensal"],
                m["custo_hora"],
            ]
            for m in base["modelos_proposta"]
        ],
        [None, None, MOEDA, PCT, PCT, MOEDA, MOEDA],
    )

    ws = _aba(
        wb,
        "Markup e despesas",
        "MARKUP E DESPESAS POR SEGMENTO",
        "Preço = custo ÷ (1 − lucro − impostos − adicionais), como nas abas de segmento.",
        [20, 24, 12, 12, 12, 4, 20, 30, 16, 14],
    )
    _tabela(
        ws,
        4,
        ["Segmento", "Aplica a", "Lucro", "Impostos", "Adicionais"],
        [
            [m["segmento"], m["aplica_a"], m["lucro"], m["impostos"], m["adicionais"]]
            for m in base["markup_referencia"]
        ],
        [None, None, PCT, PCT, PCT],
    )
    inicio = 6 + len(base["markup_referencia"])
    _tabela(
        ws,
        inicio,
        ["Segmento", "Item", "Valor mensal", "Tipo"],
        [
            [d["segmento"], d["item"], d["valor_mensal"], d["tipo"]]
            for d in base["despesas_mensais_empresa"]
        ],
        [None, None, MOEDA, None],
    )
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = None

    ws = _aba(
        wb,
        "Alertas",
        "ALERTAS DA INGESTÃO",
        "Resolva ou registre como premissa antes de usar a base numa proposta.",
        [120],
    )
    _tabela(ws, 4, ["Alerta"], [[a] for a in base["alertas"]], [None])

    wb.save(destino)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("planilha")
    ap.add_argument("pasta")
    ap.add_argument(
        "--competencia", help="AAAA-MM da folha (padrão: tenta ler do nome do arquivo)"
    )
    a = ap.parse_args()
    competencia = a.competencia
    if not competencia:
        m = re.search(
            r"(20\d\d)[_ -]*(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)",
            chave(Path(a.planilha).stem).replace(" ", "_"),
        )
        meses = [
            "jan",
            "fev",
            "mar",
            "abr",
            "mai",
            "jun",
            "jul",
            "ago",
            "set",
            "out",
            "nov",
            "dez",
        ]
        competencia = f"{m.group(1)}-{meses.index(m.group(2)) + 1:02d}" if m else "nao-informada"
    base = ingerir(a.planilha, competencia)
    pasta = Path(a.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "base-custos.json").write_text(
        json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    gravar_xlsx(base, pasta / "base-custos.xlsx")
    print(
        f"competência {competencia}: {base['fonte']['abas_pessoa']} pessoas, "
        f"{len(base['cargos_por_empresa'])} faixas por empresa, {len(base['alertas'])} alertas"
    )
    for slug, e in base["empresas"].items():
        if not slug.startswith("_"):
            print(
                f"  {e['nome']}: tributos {e['tributos'].get('aliquota')}, encargos {e['encargos_sociais']['total']}"
            )
    print(f"gravado em {pasta}")


if __name__ == "__main__":
    main()
