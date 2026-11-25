"""Score da recomendação de análise, só com biblioteca padrão.

Uso: python3 skills/score/scripts/score.py <licitacao_id>
     python3 .../score.py --dados <pasta do agente> [--saida <topo.json>]
     python3 .../score.py --exemplo

Três perguntas, em pontos, lidas das saídas da análise (`analise/*.json`, contrato
do plano 2026-11-16-analise-edital-e-cotacao-sob-demanda.md):
  Podemos participar? (triagem)  aderência da empresa mais aderente em habilitacao.json
  Dá para executar? (lote)       conclusão de tecnica.json
  Dá lucro? (margem)             margem e exequibilidade de precificacao.json
Falta de dado vale pontos parciais, nunca zera. Grava só `relatorio/topo.json`.

O parser do AGENTS.md lê apenas os mapas score/precificacao e os escalares de
caminho; não é um parser YAML geral. Campo ausente usa o padrão abaixo, e o
fallback aparece no tooltip.
"""
import argparse
import datetime as _dt
import json
import math
import os
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
PADRAO = {
    "nome_agente": "analisador-edital",
    "pasta_licitacoes": "/data/conlicitacao/licitacoes",
    "dias_minimos_preparo": 3,
    "score": {
        "pontos": {"triagem": 30, "lote": 30, "margem": 40},
        "faixas_nota": {"baixa": 0, "media": 30, "oportunidade": 55, "alta": 75},
    },
    "precificacao": {"tributos_pct": 15, "margem_minima_pct": 10},
}
ROTULOS = {1: "Baixa", 2: "Média", 3: "Inconclusivo", 4: "Oportunidade", 5: "Alta"}


def numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)





def pct(x):
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",") + "%"



def escalar_yaml(texto):
    texto = texto.strip()
    if texto.startswith("{") and texto.endswith("}"):
        return {k.strip(): escalar_yaml(v) for k, v in
                (parte.split(":", 1) for parte in texto[1:-1].split(",") if ":" in parte)}
    if texto.startswith("[") and texto.endswith("]"):
        return [escalar_yaml(x) for x in texto[1:-1].split(",") if x.strip()]
    try:
        return json.loads(texto)
    except (ValueError, TypeError):
        return texto.strip("\"'")



def parametros(raiz):
    try:
        texto = (raiz / "AGENTS.md").read_text(encoding="utf-8")
    except OSError:
        texto = ""
    mapas = {}
    for trecho in re.findall(r"```ya?ml\s*\n(.*?)```", texto, re.S):
        pilha = [(-1, mapas)]
        for linha in trecho.splitlines():
            # Comentários fora de aspas; valores lidos aqui não contêm escapes YAML.
            linha = re.split(r"\s+#", linha, maxsplit=1)[0].rstrip()
            m = re.match(r"^( *)([a-z_]+):\s*(.*)$", linha)
            if not m:
                continue
            indentacao, chave, valor = len(m[1]), m[2], m[3]
            if indentacao == 0 and chave not in PADRAO:
                pilha = [(-1, mapas)]
                continue
            while len(pilha) > 1 and indentacao <= pilha[-1][0]:
                pilha.pop()
            if indentacao and len(pilha) == 1:
                continue
            pai = pilha[-1][1]
            pai[chave] = escalar_yaml(valor) if valor else {}
            if not valor:
                pilha.append((indentacao, pai[chave]))
    faltantes = []

    def mesclar(padrao, lido, prefixo=""):
        saida = {}
        for chave, valor in padrao.items():
            caminho = f"{prefixo}.{chave}" if prefixo else chave
            atual = lido.get(chave) if isinstance(lido, dict) else None
            if isinstance(valor, dict):
                saida[chave] = mesclar(valor, atual, caminho)
            elif ((numero(valor) and numero(atual)) or
                  (isinstance(valor, str) and isinstance(atual, str) and atual) or
                  (isinstance(valor, list) and isinstance(atual, list) and len(atual) == len(valor)
                   and all(numero(x) for x in atual) and atual == sorted(atual))):
                saida[chave] = atual
            else:
                saida[chave] = valor
                faltantes.append(caminho)
        return saida
    return mesclar(PADRAO, mapas), faltantes


ADERENCIA = {"alta": 1.0, "media": 0.75, "baixa": 0.4, "nao_atende": 0.0}
VIAVEL = {"sim": 1.0, "com_ressalvas": 2 / 3, "nao": 0.0}
SESSAO = re.compile(r"sess[aã]o", re.I)


def ler(pasta, nome):
    try:
        valor = json.loads((pasta / "analise" / f"{nome}.json").read_text(encoding="utf-8"))
        return valor if isinstance(valor, dict) else None
    except (OSError, ValueError):
        return None


def data_sessao(edital):
    for p in (edital or {}).get("prazos") or []:
        if isinstance(p, dict) and SESSAO.search(str(p.get("prazo") or "")):
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(p.get("data") or ""))
            if m:
                return _dt.date(int(m[1]), int(m[2]), int(m[3])), p.get("fonte") or "edital"
    return None, None


def termo_participar(hab, maximo):
    empresas = [e for e in (hab or {}).get("empresas") or [] if isinstance(e, dict)]
    if not empresas:
        return round(maximo / 2), "Habilitação não analisada"
    escolhida = next((e for e in empresas if e.get("empresa") == hab.get("mais_aderente")), empresas[0])
    fator = ADERENCIA.get(escolhida.get("aderencia"))
    if fator is None:
        return round(maximo / 2), "Aderência não informada"
    return round(maximo * fator), f"{escolhida.get('empresa')}: aderência {escolhida.get('aderencia')}"


def termo_executar(tec, maximo):
    if (tec or {}).get("premissa_decisiva") is True:
        return round(maximo / 3), "Capacidade depende de premissa sem confirmação"
    conclusao = (tec or {}).get("conclusao") or {}
    fator = VIAVEL.get(conclusao.get("viavel"))
    if fator is None:
        return round(maximo / 3), "Análise técnica sem conclusão"
    return round(maximo * fator), {"sim": "Atende", "com_ressalvas": "Atende com condições", "nao": "Não atende"}[conclusao["viavel"]]


def percentual_valido(valor):
    return numero(valor) and 0 <= valor <= 100


def tributos_da_precificacao(prec):
    aliquota = prec.get("tributos_pct")
    if percentual_valido(aliquota):
        return aliquota
    preco = prec.get("preco_mensal")
    if not numero(preco) or preco <= 0:
        return None
    componentes = prec.get("componentes")
    valores = [
        c.get("valor_mensal") for c in componentes
        if isinstance(c, dict) and c.get("componente") == "tributos"
    ] if isinstance(componentes, list) else []
    if len(valores) == 1 and numero(valores[0]) and 0 <= valores[0] <= preco:
        return 100 * valores[0] / preco
    return None


def margem_minima(prec, params):
    minima = prec.get("margem_minima_pct")
    return minima if percentual_valido(minima) else params["precificacao"]["margem_minima_pct"]


def resumo_precificacao(prec, params):
    tributos = tributos_da_precificacao(prec)
    minimo = margem_minima(prec, params)
    sufixo_tributos = " (alíquota pendente)" if prec.get("tributos_pendente") is True else ""
    partes = [
        (f"tributos {pct(tributos)}" if tributos is not None
         else f"hipótese: tributos {pct(params['precificacao']['tributos_pct'])}") + sufixo_tributos,
        f"margem mínima {pct(minimo)}" if percentual_valido(prec.get("margem_minima_pct"))
        else f"hipótese: margem mínima {pct(minimo)}",
    ]
    margem = prec.get("margem_pct")
    if numero(margem):
        rotulo = "margem calculada"
        if prec.get("premissa_decisiva") is True:
            rotulo = "margem condicionada"
        partes.append(f"{rotulo} {pct(margem)}")
    return ", ".join(partes)


def termo_lucro(prec, params, maximo):
    if not prec:
        return round(maximo / 4), None, "Sem precificação"
    if prec.get("premissa_decisiva") is True:
        return round(maximo / 4), None, "Margem depende de premissa sem confirmação"
    margem = prec.get("margem_pct")
    minima = margem_minima(prec, params)
    if prec.get("exequivel") == "nao":
        return 0, margem if numero(margem) else None, "Inexequível no valor estimado"
    if not numero(margem):
        return round(maximo / 4), None, "Margem não calculada"
    if margem >= minima:
        return maximo, margem, f"Margem {pct(margem)} (mínima {pct(minima)})"
    if margem >= 0:
        return round(maximo / 2), margem, f"Margem {pct(margem)}, abaixo da mínima de {pct(minima)}"
    return 0, margem, f"Margem negativa ({pct(margem)})"


def nota_de(score, config):
    f = config["faixas_nota"]
    return 5 if score >= f["alta"] else 4 if score >= f["oportunidade"] else 2 if score >= f["media"] else 1


def calcular(pasta, params, fallbacks=(), hoje=None):
    edital, hab, tec, prec = (ler(pasta, n) for n in ("edital", "habilitacao", "tecnica", "precificacao"))
    config = params["score"]
    maximos = config["pontos"]
    pt, mt = termo_participar(hab, maximos["triagem"])
    pl, ml = termo_executar(tec, maximos["lote"])
    pm, margem, mm = termo_lucro(prec, params, maximos["margem"])
    score = pt + pl + pm

    travas, avisos = [], []
    hoje = hoje or _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=-3))).date()
    sessao, fonte = data_sessao(edital)
    if sessao is None:
        avisos.append("Data da sessão não encontrada em edital.json")
    elif 0 <= (sessao - hoje).days < params["dias_minimos_preparo"]:
        travas.append({"motivo": f"Sessão em menos de {params['dias_minimos_preparo']} dias", "escopo": "global", "fonte": fonte})
    avaliadas = [e for e in (hab or {}).get("empresas") or [] if isinstance(e, dict) and e.get("exigencias")]
    if avaliadas and all(e.get("aderencia") == "nao_atende" for e in avaliadas):
        travas.append({"motivo": "Nenhuma empresa do grupo atende à habilitação", "escopo": "global", "fonte": "habilitacao.json"})
    tecnica_condicionada = (tec or {}).get("premissa_decisiva") is True
    preco_condicionado = (prec or {}).get("premissa_decisiva") is True
    if not tecnica_condicionada and ((tec or {}).get("conclusao") or {}).get("viavel") == "nao":
        travas.append({"motivo": "Análise técnica: não atende", "escopo": "global", "fonte": "tecnica.json"})
    if not preco_condicionado and (prec or {}).get("exequivel") == "nao":
        travas.append({"motivo": "Preço inexequível no valor estimado", "escopo": "global", "fonte": "precificacao.json"})
    depende_premissa = tecnica_condicionada or preco_condicionado
    if depende_premissa:
        avisos.append("Equipe ou preço depende de premissa decisiva ainda sem confirmação")
    if (prec or {}).get("tributos_pendente") is True:
        motivo_trib = (prec.get("tributos_pendente_motivo") or "").strip() if isinstance(prec.get("tributos_pendente_motivo"), str) else ""
        avisos.append(motivo_trib or "Alíquota tributária pendente de confirmação contábil")
    if travas:
        score = min(score, 20)
        nota = 1
    elif margem is None and pl > 0:
        nota = 3
    else:
        nota = nota_de(score, config)
        if nota == 1 and depende_premissa:
            nota = 3

    termos = [{"rotulo": "Podemos participar?", "pontos": pt, "maximo": maximos["triagem"], "motivo": mt},
              {"rotulo": "Dá para executar?", "pontos": pl, "maximo": maximos["lote"], "motivo": ml},
              {"rotulo": "Dá lucro?", "pontos": pm, "maximo": maximos["margem"], "motivo": mm}]
    hipotese = resumo_precificacao(prec or {}, params)
    tip = [f"{t['rotulo']} {t['pontos']}/{t['maximo']}: {t['motivo']}" for t in termos]
    if travas:
        tip.append("Trava, score até 20: " + "; ".join(f"{t['motivo']} ({t['fonte']})" for t in travas))
    elif nota == 3:
        tip.append("Nota 3: premissa decisiva sem confirmação" if depende_premissa else "Nota 3: margem não calculada")
    tip.append(hipotese)
    if fallbacks:
        tip.append("Parâmetros padrão: " + ", ".join(fallbacks))
    if travas:
        sintese = "A análise indica um impedimento para disputar. Confira o motivo antes de decidir."
    elif nota <= 3 or depende_premissa:
        sintese = "Confirme as pendências de habilitação, execução ou preço antes de decidir."
    else:
        sintese = "Vale avaliar a disputa, considerando as condições de habilitação e preço."
    return {"score": score, "nota": nota, "rotulo": ROTULOS[nota], "termos": termos, "sintese": sintese,
            "trava": travas or None, "avisos": avisos, "hipotese_precificacao": hipotese,
            "tip_score": "\n".join(tip)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("licitacao_id", nargs="?")
    parser.add_argument("--dados", type=Path, help="pasta do agente na licitação (com analise/)")
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--exemplo", action="store_true")
    args = parser.parse_args()
    params, fallbacks = parametros(RAIZ)
    if args.exemplo:
        pasta = RAIZ / "referencias" / "card" / "exemplo"
    elif args.dados:
        pasta = args.dados
    elif args.licitacao_id and args.licitacao_id.isdigit():
        raiz = Path(os.environ.get("PASTA_LICITACOES", params["pasta_licitacoes"]))
        nome = os.environ.get("NOME_AGENTE", params["nome_agente"])
        pasta = raiz / args.licitacao_id / "agents" / nome
    else:
        parser.error("informe licitacao_id, --dados ou --exemplo")
    topo = calcular(pasta, params, fallbacks)
    if args.exemplo and not args.saida:
        print(json.dumps(topo, ensure_ascii=False, indent=2))
        return
    saida = args.saida or pasta / "relatorio" / "topo.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(topo, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"saida": str(saida), "score": topo["score"], "nota": topo["nota"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
