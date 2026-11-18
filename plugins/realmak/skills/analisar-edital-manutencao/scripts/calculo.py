"""Contas da análise de manutenção.

O relatório e o painel usam estes valores.
"""


def _n(x):
    return x if isinstance(x, (int, float)) else 0


def inventarios(D):
    tabelas = []
    limites = D.get("limites", {})
    for campo, chave, titulo in (
        ("nobreaks", "nobreak", "Nobreaks"),
        ("geradores", "gerador", "Grupos geradores"),
    ):
        linhas = [list(linha[:5]) for linha in D.get(campo, [])]
        if not linhas:
            continue
        tabela = {
            "titulo": titulo,
            "cols": [["Qtd", "num"], ["Potência (kVA)", "num"], ["Fabricante", "filtro"],
                     ["Localização", "filtro"], ["Faixa", "chip"]],
            "linhas": linhas,
            "soma": [0],
            "total": sum(_n(linha[0]) for linha in linhas),
            "resumo": "",
        }
        limite = limites.get(chave)
        if isinstance(limite, (int, float)):
            quantidade = sum(_n(q) for q, potencia, *_ in linhas
                             if isinstance(potencia, (int, float)) and potencia >= limite)
            tabela["destaque"] = {"col": 1, "min": limite, "rotulo": f"≥ {limite} kVA (exigência do item)"}
            tabela["resumo"] = f"{quantidade} com {limite} kVA ou mais"
        tabelas.append(tabela)

    for grupo in D.get("inventario", []):
        if not grupo["linhas"]:
            continue
        tabelas.append({
            "titulo": grupo["categoria"],
            "cols": [["Qtd", "num"], ["Equipamento", "texto"], ["Especificação", "texto"],
                     ["Localização", "filtro"], ["Onde consta", "texto"]],
            "linhas": grupo["linhas"],
            "soma": [0],
            "total": sum(_n(linha[0]) for linha in grupo["linhas"]),
            "resumo": "",
        })
    return tabelas


def calcular(D):
    limites = D.get("limites", {})
    horas = []
    for e in D["escopo"]:
        fq, vol, t = (e[4], e[5], e[7])
        horas.append(fq * vol * t if all(isinstance(x, (int, float)) for x in (fq, vol, t)) else 0)
    carga = {}
    for tipo in ("Programada", "Não programada", "Indireta"):
        ano = sum(h for h, e in zip(horas, D["escopo"], strict=False) if e[1] == tipo)
        carga[tipo] = [ano, ano / 12]
    total = sum(v[0] for v in carga.values())
    carga["Total requerido"] = [total, total / 12]
    disp = sum(_n(q[1]) * (_n(q[2]) - _n(q[3])) for q in D["equipe"])
    req = total / 12
    ciclo = D["testes"]["ciclo"]
    res_ciclo = "Atende" if _n(ciclo[2]) >= _n(ciclo[1]) and ciclo[1] is not None else "Não atende"
    nb, gr = D.get("nobreaks", []), D.get("geradores", [])
    checks = [
        ("Requisitos sem grupo", sum(1 for r in D["requisitos"] if r[2] and not r[1])),
        ("Requisitos sem fonte", sum(1 for r in D["requisitos"] if r[2] and not r[3])),
        ("Requisitos sem risco", sum(1 for r in D["requisitos"] if r[2] and not r[8])),
        ("Atividades sem tipo de carga", sum(1 for e in D["escopo"] if e[2] and not e[1])),
        (
            "Atividades com zero hora por ano",
            sum(1 for h, e in zip(horas, D["escopo"], strict=False) if e[2] and h == 0),
        ),
        ("Atividades sem requisito de origem", sum(1 for e in D["escopo"] if e[2] and not e[3])),
        (
            "Peças e materiais sem forma de pagamento",
            sum(1 for p in D["pecas"] if p[0] and not p[3]),
        ),
        (
            "Equipamentos sem faixa de atendimento",
            sum(1 for x in nb + gr if _n(x[0]) > 0 and not x[4]),
        ),
        ("Carga requerida não calculada (1 = falta)", 0 if total > 0 else 1),
        ("Capacidade da equipe não informada (1 = falta)", 0 if disp > 0 else 1),
        ("Teste de pior SLA sem resultado (1 = falta)", 0 if D["testes"]["sla"][3] else 1),
        ("Pontos de atenção sem providência", sum(1 for p in D["pontos"] if p[2] and not p[5])),
        ("Conclusão não preenchida (1 = falta)", 0 if D.get("conclusao") else 1),
    ]
    return {
        "horas": horas,
        "carga": carga,
        "num": {"req": req, "disp": disp, "cob": (disp / req) if req else 0, "folga": disp - req},
        "ciclo": res_ciclo,
        "checks": [(n, v, "OK" if v == 0 else "ALERTA") for n, v in checks],
        "nNb": sum(_n(x[0]) for x in nb),
        "nGr": sum(_n(x[0]) for x in gr),
        "nb_ok": sum(_n(x[0]) for x in nb if "nobreak" in limites and isinstance(x[1], (int, float)) and x[1] >= limites["nobreak"]),
        "gr_ok": sum(_n(x[0]) for x in gr if "gerador" in limites and isinstance(x[1], (int, float)) and x[1] >= limites["gerador"]),
        "limites": limites,
        "inventarios": inventarios(D),
    }
