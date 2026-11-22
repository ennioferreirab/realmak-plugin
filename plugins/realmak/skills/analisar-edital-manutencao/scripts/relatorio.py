"""Relatório de análise de manutenção para impressão (HTML que vira PDF) e Markdown para as outras skills.

Layout inspirado na análise da equipe: leitura rápida, quadro de condições com caixas de
seleção, tabelas numeradas com coluna "Onde consta" e grupos A, B, C...
"""

import html
import re


def esc(s):
    s = html.escape(str(s if s is not None else ""))
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"==(.+?)==", r"<mark>\1</mark>", s)
    return s


def md_inline(s):
    return (
        re.sub(r"==(.+?)==", r"**\1**", str(s if s is not None else ""))
        .replace("|", "/")
        .replace("\n", " ")
    )


def fmt_num(x, casas=1):
    if isinstance(x, (int, float)):
        t = f"{x:,.{casas}f}"
        return t.replace(",", "X").replace(".", ",").replace("X", ".")
    return "" if x is None else str(x)


def br_money(x):
    return "R$ " + fmt_num(x, 2)


class Doc:
    def __init__(self):
        self.blocks = []

    def add(self, *b):
        self.blocks.append(b)

    # ------------------------------------------------------------------ HTML
    def html(self, titulo_pagina, rodape):
        out = []
        for b in self.blocks:
            k = b[0]
            if k == "capa":
                _, t1, t2, t3, aviso = b
                out.append(
                    f'<header class="capa"><h1>{esc(t1)}</h1><p class="l2">{esc(t2)}</p><p class="l3">{esc(t3)}</p><p class="aviso">{esc(aviso)}</p></header>'
                )
            elif k == "h2":
                out.append(f"<h2>{esc(b[1])}</h2>")
            elif k == "h3":
                out.append(f"<h3>{esc(b[1])}</h3>")
            elif k == "p":
                out.append(f'<p class="nota">{esc(b[1])}</p>')
            elif k == "conclusao":
                cls = {"Atende": "ok", "Atende com condições": "cond", "Não atende": "nao"}.get(
                    b[1], "cond"
                )
                out.append(
                    f'<div class="conclusao {cls}"><span>Conclusão</span><b>{esc(b[1])}</b></div>'
                )
            elif k == "bullets":
                out.append(
                    '<ul class="rapida">'
                    + "".join(f"<li><b>{esc(a)}:</b> {esc(t)}</li>" for a, t in b[1])
                    + "</ul>"
                )
            elif k == "cards":
                out.append(
                    '<div class="cards">'
                    + "".join(
                        f'<div class="card"><b>{esc(v)}</b><span>{esc(r)}</span></div>'
                        for r, v in b[1]
                    )
                    + "</div>"
                )
            elif k == "table":
                _, cab, linhas, opt = b
                larg = opt.get("larguras")
                t = ["<table>"]
                if larg:
                    t.append(
                        "<colgroup>"
                        + "".join(f'<col style="width:{w}%">' for w in larg)
                        + "</colgroup>"
                    )
                t.append(
                    "<thead><tr>"
                    + "".join(f"<th>{esc(h)}</th>" for h in cab)
                    + "</tr></thead>"
                )
                # Não separe o título do grupo da primeira linha, nem o total
                # da última linha de dados. O restante da tabela pode paginar.
                rodape_tabela = opt.get("rodape")
                vinculos = {i for i, ln in enumerate(linhas[:-1]) if isinstance(ln, str)}
                if len(linhas) > 1 and opt.get("total"):
                    vinculos.add(len(linhas) - 2)
                if linhas and rodape_tabela:
                    vinculos.add(len(linhas) - 1)
                for n, ln in enumerate(linhas):
                    if n - 1 not in vinculos:
                        t.append('<tbody class="linhas-juntas">' if n in vinculos else "<tbody>")
                    if isinstance(ln, str):
                        t.append(f'<tr class="grupo"><td colspan="{len(cab)}">{esc(ln)}</td></tr>')
                        if n not in vinculos:
                            t.append("</tbody>")
                        continue
                    cls = ' class="total"' if opt.get("total") and n == len(linhas) - 1 else ""
                    tds = []
                    for i, c in enumerate(ln):
                        klass = ""
                        if opt.get("check") and i == 0:
                            klass = ' class="chk"'
                        elif c in ("Alto", "Médio", "Baixo") and opt.get("risco") == i:
                            klass = f' class="r-{ {"Alto": "a", "Médio": "m", "Baixo": "b"}[c] }"'
                        elif opt.get("num") and i in opt["num"]:
                            klass = ' class="num"'
                        tds.append(f"<td{klass}>{esc(c)}</td>")
                    t.append(f"<tr{cls}>" + "".join(tds) + "</tr>")
                    if n not in vinculos:
                        t.append("</tbody>")
                if rodape_tabela:
                    if not linhas:
                        t.append("<tbody>")
                    t.append(f'<tr class="total"><td colspan="{len(cab)}">{esc(rodape_tabela)}</td></tr></tbody>')
                t.append("</table>")
                out.append("".join(t))
            elif k == "passos":
                out.append(
                    '<ul class="passos">' + "".join(f"<li>{esc(t)}</li>" for t in b[1]) + "</ul>"
                )
        return (
            HTML.replace("{{TITULO}}", esc(titulo_pagina))
            .replace("{{RODAPE}}", rodape.replace('"', "'"))
            .replace("{{CORPO}}", "\n".join(out))
        )

    # -------------------------------------------------------------- Markdown
    def md(self):
        out = []
        for b in self.blocks:
            k = b[0]
            if k == "capa":
                out += [f"# {b[1]}", "", f"**{b[2]}**", "", b[3], "", f"_{b[4]}_", ""]
            elif k == "h2":
                out += [f"## {b[1]}", ""]
            elif k == "h3":
                out += [f"### {b[1]}", ""]
            elif k == "p":
                out += [md_inline(b[1]), ""]
            elif k == "conclusao":
                out += [f"**Conclusão: {b[1].upper()}**", ""]
            elif k == "bullets":
                out += [f"- **{a}:** {md_inline(t)}" for a, t in b[1]] + [""]
            elif k == "cards":
                out += (
                    ["| Indicador | Valor |", "| --- | --- |"]
                    + [f"| {r} | {v} |" for r, v in b[1]]
                    + [""]
                )
            elif k == "table":
                _, cab, linhas, opt = b
                out.append("| " + " | ".join(cab) + " |")
                out.append("| " + " | ".join("---" for _ in cab) + " |")
                for ln in linhas:
                    if isinstance(ln, str):
                        out.append("| **" + md_inline(ln) + "** |" + " |" * (len(cab) - 1))
                    else:
                        out.append("| " + " | ".join(md_inline(c) for c in ln) + " |")
                out.append("")
                if opt.get("rodape"):
                    out += [md_inline(opt["rodape"]), ""]
            elif k == "passos":
                out += [f"- {md_inline(t)}" for t in b[1]] + [""]
        return "\n".join(out)


HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITULO}}</title>
<style>
  :root{--azul:#1f3864;--azul2:#2e5c8a;--grupo:#dce6f1;--linha:#c9d3e0;--tx:#1f2937;--tx2:#4b5563;--marca:#fff3a3}
  *{box-sizing:border-box}
  html{background:#eef1f5}
  body{margin:0;color:var(--tx);font:10pt/1.4 Arial,"Helvetica Neue",Helvetica,sans-serif}
  .pagina{max-width:1080px;margin:20px auto;background:#fff;padding:32px 40px;box-shadow:0 1px 4px rgba(0,0,0,.12)}
  .capa{text-align:center;margin-bottom:14px}
  .capa h1{font-size:13pt;margin:0;color:var(--azul);letter-spacing:.2px}
  .capa .l2{font-size:11.5pt;font-weight:700;color:var(--azul);margin:2px 0}
  .capa .l3{margin:2px 0}
  .capa .aviso{color:#c00000;margin:4px 0 0}
  h2{font-size:10.5pt;color:var(--azul);text-transform:uppercase;margin:22px 0 6px;padding-bottom:3px;border-bottom:2px solid var(--azul)}
  h3{font-size:10pt;color:var(--azul2);margin:14px 0 5px}
  mark{background:var(--marca);padding:0 1px}
  ul.rapida{margin:6px 0 10px;padding-left:18px}
  ul.rapida li{margin:3px 0}
  .conclusao{display:flex;align-items:center;gap:10px;margin:8px 0;border:1px solid var(--linha)}
  .conclusao span{background:var(--azul);color:#fff;font-weight:700;padding:6px 10px}
  .conclusao b{padding:6px 4px;font-size:11pt}
  .conclusao.ok b{color:#166534}.conclusao.cond b{color:#9a3412}.conclusao.nao b{color:#991b1b}
  .cards{display:flex;gap:8px;margin:8px 0 4px}
  .card{flex:1;border:1px solid var(--linha);text-align:center;padding:6px 4px}
  .card b{display:block;font-size:13pt;color:var(--azul)}
  .card span{font-size:8.5pt;color:var(--tx2)}
  table{width:100%;border-collapse:collapse;margin:4px 0 6px;font-size:9pt;table-layout:fixed}
  th,td{border:1px solid var(--linha);padding:4px 6px;vertical-align:top;text-align:left;word-wrap:break-word}
  th{background:var(--azul);color:#fff;font-weight:700;text-align:center}
  tr.grupo td{background:var(--grupo);font-weight:700;color:var(--azul)}
  tr.total td{font-weight:700;background:#f3f6fa}
  td.chk{text-align:center;font-size:11pt;width:34px}
  td.num{text-align:right;white-space:nowrap}
  td.r-a{color:#991b1b;font-weight:700}td.r-m{color:#9a3412;font-weight:700}td.r-b{color:#166534;font-weight:700}
  p.nota{margin:4px 0 6px;color:var(--tx2)}
  ul.passos{padding-left:18px}ul.passos li{margin:3px 0}
  @page{size:A4 landscape;margin:12mm 12mm 14mm;
    @bottom-center{content:"{{RODAPE}} | Página " counter(page) " de " counter(pages);font:8pt Arial,sans-serif;color:#4b5563}}
  @media print{html{background:#fff}.pagina{box-shadow:none;margin:0;padding:0;max-width:none}
    h2,h3,thead{break-after:avoid}tr,.linhas-juntas{break-inside:avoid}thead{display:table-header-group}mark{-webkit-print-color-adjust:exact;print-color-adjust:exact}
    th,tr.grupo td,.conclusao span{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
</style>
</head>
<body><div class="pagina">
{{CORPO}}
</div></body></html>
"""


def _fmt_campos(texto, calc):
    n = calc["num"]
    campos = {
        "req": fmt_num(n["req"]),
        "disp": fmt_num(n["disp"]),
        "cob": fmt_num(n["cob"] * 100) + "%",
        "folga": fmt_num(n["folga"]),
        "nb_ok": calc["nb_ok"],
        "gr_ok": calc["gr_ok"],
        "n_nobreaks": calc["nNb"],
        "n_geradores": calc["nGr"],
        "lim_nobreak": calc["limites"].get("nobreak", "não informado"),
        "lim_gerador": calc["limites"].get("gerador", "não informado"),
    }
    try:
        return str(texto).format_map(campos)
    except (KeyError, ValueError):
        return str(texto)


def build(D, calc, destino_html, destino_md, *, rota=""):
    from fontes import vincular_html

    n, carga = calc["num"], calc["carga"]

    def F(t):
        return _fmt_campos(t, calc)

    cp = D["capa"]
    d = Doc()
    d.add(
        "capa",
        cp["titulo"],
        cp["linha2"],
        cp["linha3"],
        cp.get(
            "aviso",
            "Este documento é um resumo de apoio. Confira o texto oficial antes de decidir e de montar a proposta.",
        ),
    )
    d.add("h2", "Leitura rápida para decisão")
    d.add("conclusao", D["conclusao"])
    d.add("bullets", [(a, F(t)) for a, t in D["leitura_rapida"]])
    d.add(
        "cards",
        [
            ("Horas requeridas/mês", fmt_num(n["req"])),
            ("Horas disponíveis/mês", fmt_num(n["disp"])),
            ("Cobertura da equipe", fmt_num(n["cob"] * 100) + "%"),
            ("Folga (h/mês)", fmt_num(n["folga"])),
        ],
    )
    d.add("h3", "Quadro de condições para executar")
    d.add(
        "table",
        ["OK", "Condição", "Referência"],
        [("☐", c, r) for c, r in D["condicoes"]],
        {"check": True, "larguras": [5, 72, 23]},
    )
    d.add("h3", "Prazos de execução")
    d.add("table", ["Prazo", "Evento", "Onde consta"], D["prazos"], {"larguras": [16, 64, 20]})

    d.add("h2", "Tabela 1 - Dados do serviço")
    d.add(
        "table",
        ["Campo", "Informação", "Onde consta"],
        [x if isinstance(x, str) else tuple(x) for x in D["dados_servico"]],
        {"larguras": [18, 60, 22]},
    )

    if calc["inventarios"]:
        d.add("h2", "Tabela 2 - Equipamentos cobertos")
    for tabela in calc["inventarios"]:
        d.add("h3", tabela["titulo"])
        resumo = f"TOTAL: {tabela['total']}."
        if tabela["resumo"]:
            resumo += f" {tabela['resumo']}."
        d.add("table", [nome for nome, _ in tabela["cols"]], tabela["linhas"], {
            "num": [i for i, (_, tipo) in enumerate(tabela["cols"]) if tipo == "num"],
            "rodape": resumo,
        })

    d.add("h2", "Tabela 3 - Escopo e carga de trabalho")
    rows = []
    for e, h in zip(D["escopo"], calc["horas"], strict=False):
        rows.append(
            (
                e[2],
                e[1],
                e[3],
                fmt_num(e[4], 0),
                f"{fmt_num(e[5], 0)} {e[6]}",
                fmt_num(e[7]),
                fmt_num(h),
                e[8] if len(e) > 8 else "",
            )
        )
    rows.append(("Total", "", "", "", "", "", fmt_num(carga["Total requerido"][0]), ""))
    d.add(
        "table",
        [
            "Atividade",
            "Tipo de carga",
            "Requisito",
            "Freq./ano",
            "Volume",
            "Tempo (h)",
            "Horas/ano",
            "Profissional",
        ],
        rows,
        {"num": [3, 5, 6], "total": True, "larguras": [36, 11, 8, 7, 11, 7, 8, 12]},
    )
    if D.get("escopo_na"):
        d.add("p", "Fora do escopo neste certame: " + D["escopo_na"])

    d.add("h2", "Tabela 4 - Dimensionamento")
    d.add("h3", "Tabela 4A - Premissas")
    d.add(
        "table",
        ["Premissa", "Valor", "Tipo", "O que muda se estiver errada"],
        [tuple(p) for p in D["premissas"]],
        {"larguras": [38, 14, 14, 34]},
    )
    d.add("h3", "Tabela 4B - Carga e capacidade")
    eqp = "; ".join(f"{q[1]} × {fmt_num(q[2] - q[3], 0)} h ({q[0]})" for q in D["equipe"])
    d.add(
        "table",
        ["Indicador", "Por ano", "Por mês", "Base"],
        [
            (
                "Carga programada",
                fmt_num(carga["Programada"][0]),
                fmt_num(carga["Programada"][1]),
                D["base_carga"].get("Programada", ""),
            ),
            (
                "Carga não programada",
                fmt_num(carga["Não programada"][0]),
                fmt_num(carga["Não programada"][1]),
                D["base_carga"].get("Não programada", ""),
            ),
            (
                "Carga indireta",
                fmt_num(carga["Indireta"][0]),
                fmt_num(carga["Indireta"][1]),
                D["base_carga"].get("Indireta", ""),
            ),
            (
                "Total requerido",
                fmt_num(carga["Total requerido"][0]),
                fmt_num(carga["Total requerido"][1]),
                "",
            ),
            ("Horas disponíveis", "", fmt_num(n["disp"]), eqp),
            (
                "Cobertura e folga",
                "",
                f"{fmt_num(n['cob'] * 100)}% · {fmt_num(n['folga'])} h",
                "Disponíveis ÷ requeridas; disponíveis − requeridas",
            ),
        ],
        {"num": [1, 2], "larguras": [30, 12, 16, 42]},
    )
    t = D["testes"]
    d.add("h3", "Tabela 4C - Testes")
    d.add(
        "table",
        ["Teste", "Exigência", "Carga", "Capacidade", "Resultado"],
        [
            (
                "Primeiro ciclo",
                t["ciclo"][0],
                f"{fmt_num(t['ciclo'][1])} h",
                f"{fmt_num(t['ciclo'][2])} h",
                calc["ciclo"],
            ),
            ("Pior SLA", t["sla"][0], t["sla"][1], t["sla"][2], f"{t['sla'][3]}: {t['sla'][4]}"),
        ],
        {"larguras": [12, 40, 14, 14, 20]},
    )
    ce = D["conclusao_equipe"]
    d.add(
        "p",
        f"Equipe: mínimo exigido na habilitação — {ce[0]}. Necessária pelo cálculo — {ce[1]}. {ce[2]}",
    )

    d.add("h2", "Tabela 5 - Peças, insumos e materiais")
    d.add(
        "table",
        ["Item", "Tipo", "Como é pago", "Regra do edital", "Observação"],
        [(p[0], p[1], p[3], p[7], p[8]) for p in D["pecas"]],
        {"larguras": [28, 8, 13, 33, 18]},
    )

    d.add("h2", "Tabela 6 - Requisitos de execução")
    grupos = ["Execução", "SLA e penalidades", "Peças e materiais", "Qualificação técnica"]
    linhas = []
    for gi, g in enumerate(grupos):
        sel = [(r[0], r[2], r[3], r[8], r[9]) for r in D["requisitos"] if r[1] == g]
        if sel:
            linhas.append(f"{chr(65 + gi)}. {g}")
            linhas += sel
    d.add(
        "table",
        ["ID", "Requisito", "Onde consta", "Risco", "Pendência"],
        linhas,
        {"risco": 3, "larguras": [6, 55, 19, 8, 12]},
    )

    d.add("h2", "Tabela 7 - Pontos de atenção e divergências")
    d.add(
        "table",
        ["Nº", "Ponto de atenção / divergência", "Onde consta", "Providência sugerida"],
        [(p[0], p[2], p[3], p[5]) for p in D["pontos"]],
        {"larguras": [6, 50, 19, 25]},
    )

    if D.get("proximos_passos"):
        d.add("h2", "Próximos passos sugeridos")
        d.add("passos", D["proximos_passos"])
    d.add("h2", "Documentos analisados")
    d.add(
        "table",
        ["ID", "Documento", "Origem", "Data"],
        [(x[0], x[1], x[3], x[4]) for x in D["documentos"]],
        {"larguras": [7, 45, 33, 15]},
    )

    with open(destino_html, "w", encoding="utf-8") as arq:
        html = d.html(D.get("titulo_pagina", cp["titulo"]), D.get("rodape", cp["titulo"]))
        arq.write(vincular_html(html, rota))
    with open(destino_md, "w", encoding="utf-8") as arq:
        arq.write(d.md())
