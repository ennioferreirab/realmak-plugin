"""Fila SQLite por empresa, cláusula e ID. Recebe resultados sanitizados pelo stdin."""

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

from controle_validacao import sincronizar_fila
from guardar_original import sha256

TERMOS = {"salvo", "descartado", "tentativas_esgotadas", "reconciliado"}


def texto(valor):
    return isinstance(valor, str) and bool(valor.strip())


def literal(valor):
    return "'" + valor.replace("'", "''") + "'"


def consulta_versoes(dados):
    emissor = dados.get("emissor_id")
    contrato = dados.get("contrato_numero", "")
    numeros = re.findall(r"(?<!\d)(\d+)\s*[/.-]\s*(\d{4})(?!\d)", contrato)
    if not texto(emissor) or len(numeros) != 1:
        raise ValueError("recupere o ID do emissor e um número de contrato inequívoco no esquema")
    numero, ano = numeros[0]
    padrao = rf"(^|[^0-9])0*{int(numero)}[[:space:]]*[/.-][[:space:]]*{ano}([^0-9]|$)"
    # A minuta e o emitido podem ter títulos e formatação do número diferentes.
    cursor = dados.get("apos")
    filtro = f" AND a.atestado_id > {literal(cursor)}" if cursor else ""
    beneficiario = dados.get("beneficiario_id")
    if beneficiario:
        filtro += f" AND a.beneficiario_id = {literal(beneficiario)}"
    return (
        "SELECT a.atestado_id, a.emissor_id, a.beneficiario_id, a.contrato_numero, "
        "a.situacao_documento, a.data_emissao FROM atestados a "
        f"WHERE a.emissor_id = {literal(emissor)} AND a.contrato_numero ~ {literal(padrao)}"
        f"{filtro} ORDER BY a.atestado_id LIMIT 50"
    )


CAMPOS_TRIAGEM = ("objeto", "servicos", "area", "emissor", "beneficiario", "beneficiario_id",
                  "contrato_numero", "situacao_documento")


def normalizar(valor):
    sem_acentos = "".join(c for c in unicodedata.normalize("NFKD", valor.casefold())
                         if not unicodedata.combining(c))
    return " ".join(sem_acentos.split())


def termos_triagem(triagem, chave):
    termos = triagem[chave]
    if not isinstance(termos, list) or not all(texto(t) for t in termos):
        raise ValueError(f"triagem exige uma lista de termos em {chave}")
    return {normalizar(t) for t in termos}


def avaliar_triagem(ident, triagem):
    registro = triagem["registro"]
    if registro.get("atestado_id", registro.get("id")) != ident or not texto(triagem.get("fonte")):
        raise ValueError("triagem exige a linha bruta do mesmo ID e referência à fonte")
    campos = {k: normalizar(registro[k]) for k in CAMPOS_TRIAGEM if texto(registro.get(k))}
    servico = termos_triagem(triagem, "termos_servico")
    ambiente = termos_triagem(triagem, "termos_ambiente")
    emissores = termos_triagem(triagem, "emissores_compativeis")
    if not servico or not (ambiente or emissores):
        raise ValueError("informe serviços e ambientes ou emissores aplicáveis à cláusula")
    escopo = " ".join(campos.get(k, "") for k in ("objeto", "servicos", "area"))
    sinal_servico = sorted(t for t in servico if t in escopo)
    sinal_ambiente = sorted(t for t in ambiente if t in escopo)
    emissor = registro.get("emissor_id") or ""
    emissor_compativel = normalizar(emissor) in emissores
    return {"fonte": triagem["fonte"], "campos": campos, "servico": sinal_servico,
            "ambiente": sinal_ambiente, "emissor_compativel": emissor_compativel,
            "exige_abertura": bool(sinal_servico and (sinal_ambiente or emissor_compativel))}


def descarte_tecnico(dados, resultado):
    triagem = dados.get("triagem")
    evidencia = resultado.get("evidencia")
    campos = ("campo", "trecho", "clausula_trecho", "comparacao")
    if not triagem or not isinstance(evidencia, dict) or not all(texto(evidencia.get(k)) for k in campos):
        raise ValueError("descarte de atestado exige fonte bruta, trecho da linha, cláusula e comparação individual")
    if normalizar(evidencia["trecho"]) not in triagem["campos"].get(evidencia["campo"], ""):
        raise ValueError("trecho de descarte não consta no campo da linha bruta")
    return {**{k: evidencia[k] for k in campos}, "fonte": triagem["fonte"]}


def adicionar(db, dado):
    tipo = dado["tipo"]
    chave = [dado[k] for k in ("empresa", "clausula", "id")]
    if not all(texto(k) for k in chave) or tipo not in {"original", "versoes"}:
        raise ValueError("informe empresa, cláusula, ID e tipo original ou versoes")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", chave[0]):
        raise ValueError("use empresa como alias minúsculo ou CNPJ sem pontuação")
    metadados = {}
    if tipo == "original":
        material = dado.get("material", True)
        if type(material) is not bool:
            raise ValueError("material precisa ser booleano")
        if "triagem" in dado:
            metadados["triagem"] = avaliar_triagem(chave[2], dado["triagem"])
            material = material or metadados["triagem"]["exige_abertura"]
        metadados["material"] = material
    else:
        metadados = {k: dado[k] for k in ("emissor_id", "contrato_numero")}
        if dado.get("beneficiario_id"):
            metadados["beneficiario_id"] = dado["beneficiario_id"]
        consulta_versoes(metadados)
    if tipo == "original":
        existente = db.execute(
            "SELECT numero, dados, estado FROM fila WHERE empresa=? AND clausula=? AND ident=? AND tipo=?",
            (*chave, tipo),
        ).fetchone()
        if existente:
            dados = json.loads(existente["dados"])
            if "triagem" in metadados:
                dados["triagem"] = metadados["triagem"]
            dados["material"] = dados.get("material", True) or material
            estado = existente["estado"]
            descarte_sem_rastro = chave[2].startswith("at_") and not dados.get("evidencia_descarte")
            if estado == "descartado" and (dados["material"] or descarte_sem_rastro):
                estado = "pendente"
            db.execute("UPDATE fila SET dados=?, estado=? WHERE numero=?",
                       (json.dumps(dados), estado, existente["numero"]))
            return
    db.execute(
        "INSERT OR IGNORE INTO fila(empresa,clausula,ident,tipo,dados) VALUES (?,?,?,?,?)",
        (*chave, tipo, json.dumps(metadados)),
    )


def confirmar_copia(pasta, empresa, resultado):
    arquivo, digest = resultado.get("arquivo"), resultado.get("sha256")
    if not texto(arquivo) or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("salvo exige arquivo relativo e SHA-256 confirmado")
    relativo = Path(arquivo)
    acervo = pasta / "documentos_empresa"
    destino = acervo / empresa / digest
    copia = pasta / relativo
    if (relativo.is_absolute() or relativo.parts[:3] != ("documentos_empresa", empresa, digest)
            or len(relativo.parts) != 4 or any(p.is_symlink() for p in (acervo, destino.parent, destino, copia))
            or not copia.is_file() or copia.stat().st_size == 0):
        raise ValueError("cópia ausente ou fora do diretório de originais da empresa e SHA-256")
    esperado = resultado.get("sha256_origem")
    if esperado is not None and esperado != digest:
        raise ValueError("SHA-256 confirmado diverge do SHA-256 de origem")
    if sha256(copia) != digest:
        raise ValueError("SHA-256 não corresponde à cópia no disco")
    return {"arquivo": relativo.as_posix(), "sha256": digest}


def registrar(db, numero, resultado, pasta):
    item = db.execute("SELECT * FROM fila WHERE numero = ?", (numero,)).fetchone()
    if item is None or item["estado"] in TERMOS:
        raise ValueError("item ausente ou já encerrado")
    estado = resultado["estado"]
    detalhe = resultado.get("detalhe")
    if not texto(detalhe) or "http://" in detalhe.lower() or "https://" in detalhe.lower():
        raise ValueError("registre resultado concreto, sem URL")
    tentativas = resultado.get("tentativas", [])
    for tentativa in tentativas:
        if not all(texto(tentativa.get(k)) for k in ("via", "resultado")):
            raise ValueError("tentativa sem via e resultado observável")
        if tentativa.get("estado") not in {"ok", "falhou", "nao_executada"}:
            raise ValueError("informe estado observável de cada tentativa")
        if re.search(r"https?://", tentativa["resultado"], re.I):
            raise ValueError("registre tentativas sem URL")
    if item["tipo"] == "original":
        minuta = resultado.get("minuta")
        if minuta:
            adicionar(db, {**minuta, "empresa": item["empresa"], "clausula": item["clausula"],
                           "id": item["ident"], "tipo": "versoes"})
        if estado not in {"salvo", "descartado", "tentativas_esgotadas", "transitorio"}:
            raise ValueError("estado inválido para original")
        if estado != "descartado" and not any(t["estado"] in {"ok", "falhou"} for t in tentativas):
            raise ValueError("informe tentativa observada para o original")
        dados = json.loads(item["dados"])
        if estado == "descartado":
            if dados.get("material", True):
                raise ValueError("candidato material requer recuperação e leitura antes da decisão de mérito")
            if resultado.get("fundamento") not in {"duplicata", "clausula_inaplicavel", "incompatibilidade_objetiva"}:
                raise ValueError("descarte em triagem exige fundamento objetivo individual")
            if item["ident"].startswith("at_") or "triagem" in dados:
                dados["evidencia_descarte"] = descarte_tecnico(dados, resultado)
                db.execute("UPDATE fila SET dados=? WHERE numero=?", (json.dumps(dados), numero))

        if estado == "salvo":
            dados.update(confirmar_copia(pasta, item["empresa"], resultado))
            db.execute("UPDATE fila SET dados=? WHERE numero=?", (json.dumps(dados), numero))
        if estado == "tentativas_esgotadas":
            vias = {t["via"] for t in tentativas}
            if not {"buscar_identificador", "renovar_link"} <= vias:
                raise ValueError("registre resultado ou bloqueio específico da busca por ID e da renovação")
    elif estado == "reconciliado":
        linhas = resultado["linhas"]
        dados = json.loads(item["dados"])
        ids = [linha["atestado_id"] for linha in linhas]
        if ids != sorted(set(ids)) or (dados.get("apos") and ids and ids[0] <= dados["apos"]):
            raise ValueError("a página de IDs não avançou em ordem estável")
        tentativas.append({"via": "cerebro_consulta", "estado": "ok", "resultado": f"IDs retornados: {', '.join(ids) or 'nenhum'}"})
        for linha in linhas:
            if linha.get("situacao_documento") != "minuta":
                adicionar(db, {"empresa": item["empresa"], "clausula": item["clausula"],
                               "id": linha["atestado_id"], "tipo": "original"})
        if len(ids) >= 50 or resultado.get("truncado"):
            if not ids:
                raise ValueError("resultado truncado sem IDs; reduza o recorte antes de fechar")
            dados["apos"] = ids[-1]
            db.execute("UPDATE fila SET dados = ? WHERE numero = ?", (json.dumps(dados), numero))
            estado = "em_andamento"
    elif estado != "transitorio":
        raise ValueError("consulta de versões só encerra com resultado estruturado")
    db.execute("INSERT INTO historico VALUES (?, ?, ?, ?)",
               (numero, estado, detalhe, json.dumps(tentativas, ensure_ascii=False)))
    db.execute("UPDATE fila SET estado = ? WHERE numero = ?", (estado, numero))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fila")
    parser.add_argument("acao", choices=("adicionar", "proximo", "registrar", "fechar"))
    parser.add_argument("--numero", type=int)
    args = parser.parse_args()
    try:
        with sqlite3.connect(args.fila) as db:
            db.row_factory = sqlite3.Row
            db.execute("CREATE TABLE IF NOT EXISTS fila(numero INTEGER PRIMARY KEY, empresa TEXT, "
                       "clausula TEXT, ident TEXT, tipo TEXT, dados TEXT, estado TEXT DEFAULT 'pendente', "
                       "UNIQUE(empresa, clausula, ident, tipo))")
            db.execute("CREATE TABLE IF NOT EXISTS historico(numero INTEGER, estado TEXT, detalhe TEXT, tentativas TEXT)")
            if args.acao == "adicionar":
                for dado in json.load(sys.stdin):
                    adicionar(db, dado)
            elif args.acao == "registrar":
                resultado = json.load(sys.stdin)
                fila = Path(args.fila).resolve()
                registrar(db, args.numero, resultado, fila.parent)
                if resultado["estado"] == "salvo":
                    db.commit()
                    sincronizar_fila(fila.parent, fila)
            else:
                abertos = list(db.execute(
                    "SELECT * FROM fila WHERE estado IN ('pendente','transitorio','em_andamento') "
                    "ORDER BY CASE estado WHEN 'transitorio' THEN 1 ELSE 0 END, "
                    "CASE tipo WHEN 'versoes' THEN 0 ELSE 1 END, numero"
                ))
                if args.acao == "fechar":
                    saida = {"abertos": [dict(i) for i in abertos],
                             "itens": [dict(i) for i in db.execute("SELECT * FROM fila")],
                             "historico": [dict(i) for i in db.execute("SELECT * FROM historico")]}
                    encerrada = not abertos and bool(saida["itens"])
                    saida["encerramento_operacional"] = encerrada
                    saida["lacunas_documentais"] = [i for i in saida["itens"]
                                                    if i["estado"] == "tentativas_esgotadas"]
                    saida["aceite_cobertura"] = "requer_revisao"
                    print(json.dumps(saida, ensure_ascii=False))
                    return 0 if encerrada else 2
                item = dict(abertos[0]) if abertos else None
                if item and item["tipo"] == "versoes":
                    item["sql"] = consulta_versoes(json.loads(item["dados"]))
                print(json.dumps(item, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        print(f"Fila documental: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
