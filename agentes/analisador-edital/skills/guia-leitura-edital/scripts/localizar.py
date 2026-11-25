"""Mapa de leitura da licitação: onde está cada informação, por documento e página.

Uso:
  python3 localizar.py <licitacao_id>   # grava agents/<nome_agente>/fontes/mapa_leitura.json e imprime o resumo
  python3 localizar.py --guia           # regera referencias/ONDE-ESTA.md a partir do catálogo e da medição

Tipo de cada documento, nesta ordem:
  1. manifesto  -> extraidos[].tipo_documento (quando o CRM gravar)
  2. CRM        -> realmak_app.modelos_decisores.julgamentos (só SELECT; transitório)
  3. nome       -> heurística pelo nome do arquivo
Nunca trava: documento ilegível vira aviso.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REF = AQUI.parent / "referencias"
# O daemon passa PASTA_LICITACOES e NOME_AGENTE; o padrão é o caminho do acervo no container.
PASTA_LICITACOES = Path(os.environ.get("PASTA_LICITACOES", "/data/conlicitacao/licitacoes"))
NOME_AGENTE = os.environ.get("NOME_AGENTE", "analisador-edital")
CRM_DB_CONTAINER = "realmak-crm-postgres-1"                                         # AGENTS.md: crm_resumo.container
CHAVE_SEGURA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
PAGINA = re.compile(r"^--- Página (\d+) ---$")


def chave_segura(valor):
    return bool(CHAVE_SEGURA.fullmatch(str(valor or ""))) and ".." not in str(valor or "")
TR_EMBUTIDO = re.compile(r"^\s*(ANEXO\s+[IVXLC0-9]+\s*[-–—:.]?\s*)?(DO EDITAL\s*[-–—:]?\s*)?TERMO DE REFER[EÊ]NCIA\b", re.I)
NOME = [("edital", r"edital|aviso de (licita|contrata)"),
        ("termo_referencia", r"termo[ _-]*de[ _-]*refer|\bTR\b|caderno[ _-]*de[ _-]*especifica|projeto[ _-]*b[aá]sico"),
        ("estudo_tecnico_preliminar", r"\bETP|estudo[ _-]*t[eé]cnico"),
        ("minuta_contrato", r"minuta|contrato"),
        ("planilha_precos", r"planilha|or[cç]amento|composi[cç]|\.xlsx?$|\.ods$|\.csv$")]


def catalogo():
    return json.loads((REF / "catalogo.json").read_text(encoding="utf-8"))


def tipos_crm(lid):
    if not str(lid).isdigit():
        return {}
    sql = ("select distinct on (caminho_documento) caminho_documento, resultado::jsonb->>'tipo_documento', "
           "resultado::jsonb->'resposta'->>'confidence' from modelos_decisores.julgamentos "
           f"where licitacao_id = '{int(lid)}' order by caminho_documento, criado_em desc")
    cmd = ["docker", "exec", CRM_DB_CONTAINER, "sh", "-c",
           'psql -U "${POSTGRES_USER:-odoo}" -d realmak_app -At -F "|" -v ON_ERROR_STOP=1 -c "$0"', sql]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if out.returncode != 0:
        return {}
    res = {}
    for linha in out.stdout.splitlines():
        partes = linha.split("|")
        if len(partes) == 3:
            res[partes[0]] = (partes[1], float(partes[2]) if partes[2] else None)
    return res


def tipo_por_nome(caminho):
    nome = Path(caminho).name
    for tipo, rx in NOME:
        if re.search(rx, nome, re.I):
            return tipo
    return "outros"


def paginas(texto):
    """[(pagina, linha)] a partir dos marcadores do CRM; sem marcador, tudo é página 1."""
    pag, res = 1, []
    for linha in texto.splitlines():
        m = PAGINA.match(linha.strip())
        if m:
            pag = int(m.group(1))
            continue
        res.append((pag, linha))
    return res


def _entradas_disco(base):
    """Fallback para cards fora do ConLicitação (PNCP, Compras, link) cujo manifesto não lista anexos[]."""
    raiz_extraidos = base / "extraidos"
    entradas, vistos, avisos = [], set(), []
    if raiz_extraidos.is_dir():
        for txt_path in sorted(raiz_extraidos.rglob("*.txt")):
            if not txt_path.is_file():
                continue
            rel_txt = txt_path.relative_to(raiz_extraidos).as_posix()
            cam = rel_txt[:-4] if rel_txt.endswith(".txt") else rel_txt
            entradas.append({"caminho_documento": cam, "caminho": rel_txt})
            vistos.add(cam)
    raiz_anexos = base / "anexos"
    if raiz_anexos.is_dir():
        for orig in sorted(raiz_anexos.rglob("*")):
            if not orig.is_file():
                continue
            rel_orig = orig.relative_to(base).as_posix()
            if rel_orig not in vistos:
                avisos.append(f"{orig.name}: sem texto extraído")
    return entradas, avisos


def mapa(lid):
    cat = catalogo()
    base = PASTA_LICITACOES / str(lid)
    man = json.loads((base / "manifesto.json").read_text(encoding="utf-8"))
    crm = tipos_crm(lid)
    docs, avisos = [], []
    entradas = [
        e for anexo in man.get("anexos", []) for e in (anexo.get("extraidos") or [])
    ]
    if not entradas:
        entradas, avisos_disco = _entradas_disco(base)
        avisos.extend(avisos_disco)
    for e in entradas:
        cam, txt = e.get("caminho_documento"), e.get("caminho")
        if not cam or not txt:
            continue
        txt_rel = txt[len("extraidos/"):] if txt.startswith("extraidos/") else txt
        txt_path = base / "extraidos" / txt_rel
        if e.get("tipo_documento"):
            tipo, conf, origem = e["tipo_documento"], e.get("tipo_confianca"), "manifesto"
        elif cam in crm:
            (tipo, conf), origem = crm[cam], "crm"
        else:
            tipo, conf, origem = tipo_por_nome(cam), None, "nome do arquivo"
        try:
            linhas = paginas(txt_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception as err:
            avisos.append(f"{Path(cam).name}: texto ilegível ({err})")
            linhas = []
        embutidos = []
        if tipo == "edital":
            for pag, linha in linhas:
                if pag >= 3 and TR_EMBUTIDO.match(linha):
                    embutidos.append({"tipo": "termo_referencia", "pagina": pag})
                    break
        n_paginas = e.get("paginas")
        if n_paginas is None and linhas:
            n_paginas = max(p for p, _ in linhas)
        docs.append({"arquivo": Path(cam).name, "tipo": tipo, "confianca": conf, "origem_tipo": origem,
                     "original": str(base / cam), "texto": str(txt_path),
                     "paginas": n_paginas, "paginas_nao_extraidas": e.get("paginas_nao_extraidas") or [],
                     "embutidos": embutidos, "_linhas": linhas})
    infos = {}
    for inf in cat["informacoes"]:
        rx = re.compile(inf["termos"], re.I)
        ordem = inf["ordem"]
        def prioridade(d, ordem=ordem):
            t = d["tipo"]
            if t == "edital" and d["embutidos"] and ordem and ordem[0] == "termo_referencia":
                return 0.5  # TR embutido no edital
            return ordem.index(t) if t in ordem else len(ordem) + 1
        achados = []
        for d in sorted(docs, key=prioridade):
            n = 0
            for pag, linha in d["_linhas"]:
                if rx.search(linha):
                    achados.append({"arquivo": d["arquivo"], "tipo": d["tipo"], "pagina": pag,
                                    "trecho": re.sub(r"\s+", " ", linha).strip()[:200]})
                    n += 1
                    if n == 2:
                        break
            if len(achados) >= 4:
                break
        infos[inf["chave"]] = {"rotulo": inf["rotulo"], "secoes": inf["secoes"], "ordem": ordem,
                               "achados": achados[:4], "nao_achado": not achados, "nota": inf.get("nota", "")}
    for d in docs:
        d.pop("_linhas")
    return {"licitacao_id": str(lid), "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "documentos": docs, "informacoes": infos, "avisos": avisos}


def guia():
    cat = catalogo()
    med = json.loads((REF / "medicao-2026-10-15.json").read_text(encoding="utf-8"))
    nomes = cat["tipos"]
    sig = {"edital": "Edital", "termo_referencia": "TR", "estudo_tecnico_preliminar": "ETP",
           "minuta_contrato": "Minuta", "planilha_precos": "Planilha", "outros": "Outros"}
    linhas = ["# Onde está cada informação", "",
              f"Gerado de [catalogo.json](catalogo.json) (fonte única) e da medição de 2026-10-15 em {med['n_licitacoes']} licitações do CRM. "
              "**Ordem** = onde procurar primeiro. **Medição** = em quantas licitações com aquele tipo de documento o termo aparece (presença) "
              "e quanto das ocorrências cai em cada tipo (participação). Regerar: `python3 scripts/localizar.py --guia`.", "",
              "| Informação | Seções | Ordem de leitura | Medição (presença / participação) | Atenção |", "|---|---|---|---|---|"]
    por_rotulo = med.get("info", {})
    for inf in cat["informacoes"]:
        m = por_rotulo.get(inf.get("medicao", ""))
        medida = ""
        if m:
            top = sorted(m["participacao"].items(), key=lambda kv: -kv[1])[:2]
            medida = " · ".join(f"{sig[t]} {100 * m['presenca'][t]:.0f}% / {100 * p:.0f}%" for t, p in top if p > 0)
        ordem = " → ".join(sig[t] for t in inf["ordem"])
        linhas.append(f"| {inf['rotulo']} | {', '.join(inf['secoes'])} | {ordem} | {medida or '—'} | {inf.get('nota', '')} |")
    linhas += ["", "Tipos: " + " · ".join(f"**{sig[k]}** = {v}" for k, v in nomes.items()) + "."]
    (REF / "ONDE-ESTA.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("ONDE-ESTA.md regerado")


def main(argv):
    if "--guia" in argv:
        guia()
        return 0
    if len(argv) < 2 or not chave_segura(argv[1]):
        print(__doc__)
        return 1
    lid = argv[1]
    res = mapa(lid)
    saida = PASTA_LICITACOES / lid / "agents" / NOME_AGENTE / "fontes" / "mapa_leitura.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for lixo in saida.parent.glob("._*"):
        lixo.unlink(missing_ok=True)
    print(f"mapa: {saida}")
    for d in res["documentos"]:
        emb = f" · TR embutido a partir da p. {d['embutidos'][0]['pagina']}" if d["embutidos"] else ""
        print(f"  [{d['tipo']} · {d['origem_tipo']}] {d['arquivo']} ({d['paginas']} p.){emb}")
    faltam = [v["rotulo"] for v in res["informacoes"].values() if v["nao_achado"]]
    print(f"  informações localizadas: {len(res['informacoes']) - len(faltam)}/{len(res['informacoes'])}")
    if faltam:
        print("  sem ocorrência: " + "; ".join(faltam))
    for a in res["avisos"]:
        print("  ⚠️", a)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
