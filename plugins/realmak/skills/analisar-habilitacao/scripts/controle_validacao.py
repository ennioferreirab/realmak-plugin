"""Controle retomável de leitura delegada. O coordenador chama o executor autorizado."""

import argparse
import json
import os
import sqlite3
import sys
import time
import uuid
from contextlib import closing
from pathlib import Path

from guardar_original import sha256

NOME = "controle_validacao.sqlite"
RESERVA_SEGUNDOS = 3600


def conectar(raiz):
    acervo = raiz / "documentos_empresa"
    banco = acervo / NOME
    if acervo.is_symlink() or banco.is_symlink():
        raise ValueError("controle de validação não aceita links simbólicos")
    acervo.mkdir(mode=0o700, exist_ok=True)
    db = sqlite3.connect(banco)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS tarefas (
        numero INTEGER PRIMARY KEY, empresa TEXT, sha256 TEXT, clausula TEXT, arquivo TEXT,
        estado TEXT DEFAULT 'pendente', reserva TEXT, vence INTEGER, executor TEXT,
        modelo TEXT, chamada TEXT, resultado TEXT, UNIQUE(empresa, sha256, clausula))""")
    db.execute("""CREATE TABLE IF NOT EXISTS eventos (
        instante INTEGER, numero INTEGER, evento TEXT, dados TEXT)""")
    return db


def evento(db, n, nome, dados):
    db.execute("INSERT INTO eventos VALUES (?, ?, ?, ?)",
               (int(time.time()), n, nome, json.dumps(dados, ensure_ascii=False)))


def inserir(db, raiz, empresa, digest, clausula, arquivo):
    rel = Path(arquivo)
    if (rel.is_absolute() or rel.parts[:3] != ("documentos_empresa", empresa, digest)
            or len(rel.parts) != 4 or not clausula):
        raise ValueError("controle exige original arquivado por empresa e hash")
    destino = raiz / rel
    if not destino.resolve().is_relative_to(raiz.resolve() / "documentos_empresa" / empresa / digest):
        raise ValueError("original fora da pasta do hash")
    db.execute("INSERT OR IGNORE INTO tarefas(empresa,sha256,clausula,arquivo) VALUES (?,?,?,?)",
               (empresa, digest, clausula, arquivo))


def sincronizar_fila(raiz, fila):
    if not fila.is_file():
        return
    with closing(sqlite3.connect(fila.resolve().as_uri() + "?mode=ro", uri=True)) as origem:
        linhas = origem.execute("SELECT empresa,clausula,dados FROM fila "
                                "WHERE tipo='original' AND estado='salvo'").fetchall()
    if linhas:
        with closing(conectar(raiz)) as db, db:
            for empresa, clausula, dados in linhas:
                original = json.loads(dados)
                inserir(db, raiz, empresa, original["sha256"], clausula, original["arquivo"])


def conciliar(db, raiz, dossie):
    for doc in dossie["documentos"]:
        if doc["etapas"]["download"]["estado"] == "ok":
            arquivo = raiz / doc["arquivo"]
            if not arquivo.is_file() or sha256(arquivo) != doc["sha256"]:
                raise ValueError(f"cópia anterior sem bytes confirmados para {doc['id']}")
            for vinculo in doc.get("vinculos", []):
                inserir(db, raiz, doc["empresa"], doc["sha256"], vinculo["clausula"], doc["arquivo"])


def reservar(db, limite):
    db.execute("BEGIN IMMEDIATE")
    agora = int(time.time())
    expiradas = db.execute("SELECT numero,executor,modelo,chamada FROM tarefas WHERE estado='em_leitura' "
                           "AND chamada IS NULL AND vence<=?", (agora,)).fetchall()
    for item in expiradas:
        evento(db, item["numero"], "reserva_expirada", dict(item))
        db.execute("UPDATE tarefas SET estado='pendente', reserva=NULL, vence=NULL, executor=NULL, "
                   "modelo=NULL, chamada=NULL WHERE numero=?", (item["numero"],))
    linhas = db.execute("SELECT * FROM tarefas WHERE estado='pendente' ORDER BY numero LIMIT ?",
                        (limite,)).fetchall()
    lote = []
    for linha in linhas:
        reserva = uuid.uuid4().hex
        db.execute("UPDATE tarefas SET estado='em_leitura', reserva=?, vence=? WHERE numero=?",
                   (reserva, agora + RESERVA_SEGUNDOS, linha["numero"]))
        evento(db, linha["numero"], "reservada", {})
        lote.append({**dict(linha), "estado": "em_leitura", "reserva": reserva,
                     "vence": agora + RESERVA_SEGUNDOS})
    return lote


def exigir_textos(dados, chaves):
    if not all(isinstance(dados.get(k), str) and dados[k].strip() for k in chaves):
        raise ValueError("campos textuais obrigatórios: " + ", ".join(chaves))


def atualizar(db, acao, dados):
    db.execute("BEGIN IMMEDIATE")
    item = db.execute("SELECT * FROM tarefas WHERE numero=?", (dados["numero"],)).fetchone()
    if item is None or not item["reserva"] or item["reserva"] != dados.get("reserva"):
        raise ValueError("reserva inexistente ou substituída")
    registro = json.dumps(dados, sort_keys=True, ensure_ascii=False)
    if acao == "receber" and item["resultado"] == registro:
        return
    if acao == "revisar":
        if item["estado"] != "revisao":
            raise ValueError("item sem revisão pendente")
        exigir_textos(dados, ("revisor", "localizacao", "trecho", "confronto"))
        if dados.get("decisao") not in {"atende", "nao_atende", "descartado"}:
            raise ValueError("registre a decisão de revisão ou mantenha o impedimento")
        db.execute("UPDATE tarefas SET estado='revisada', resultado=? WHERE numero=?",
                   (registro, item["numero"]))
        evento(db, item["numero"], acao, dados)
        return
    if item["estado"] != "em_leitura":
        raise ValueError("a reserva já terminou")
    if acao == "despacho":
        exigir_textos(dados, ("executor", "modelo", "chamada"))
        identidade = tuple(dados[k] for k in ("executor", "modelo", "chamada"))
        anterior = tuple(item[k] for k in ("executor", "modelo", "chamada"))
        if identidade == anterior:
            return
        if item["chamada"]:
            raise ValueError("item já despachado; retome a chamada registrada")
        db.execute("UPDATE tarefas SET executor=?, modelo=?, chamada=? WHERE numero=?",
                   (*identidade, item["numero"]))
    else:
        if acao == "receber":
            if not item["chamada"] or item["chamada"] != dados.get("chamada"):
                raise ValueError("resultado sem chamada real registrada para a reserva")
            if any(item[k] != dados.get(k) for k in ("empresa", "sha256", "clausula")):
                raise ValueError("resultado de outra cópia ou cláusula")
            estado = dados.get("estado")
            if estado == "lido":
                exigir_textos(dados, ("localizacao", "trecho", "confronto"))
                if dados.get("decisao") not in {"atende", "nao_atende", "descartado"}:
                    raise ValueError("leitura exige decisão explícita ou revisão")
            elif estado == "revisao":
                exigir_textos(dados, ("impedimento",))
            else:
                raise ValueError("use lido ou revisao")
        else:
            exigir_textos(dados, ("impedimento",))
            if item["chamada"] and dados.get("chamada_encerrada") is not True:
                raise ValueError("confirme o encerramento da chamada antes de redistribuir")
            estado = "bloqueado" if acao == "bloqueio" else "pendente"
        db.execute("UPDATE tarefas SET estado=?, resultado=?, reserva=?, vence=NULL, "
                   "executor=?, modelo=?, chamada=? WHERE numero=?",
                   (estado, registro, None if estado == "pendente" else item["reserva"],
                    None if estado == "pendente" else item["executor"],
                    None if estado == "pendente" else item["modelo"],
                    None if estado == "pendente" else item["chamada"], item["numero"]))
    evento(db, item["numero"], acao, dados)


def cobertura(db):
    itens = [dict(r) for r in db.execute("SELECT * FROM tarefas ORDER BY numero")]
    estados = {}
    for item in itens:
        estado = item["estado"]
        estados[estado] = estados.get(estado, 0) + 1
    return {"total": len(itens), "estados": estados, "itens": itens}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raiz", type=Path)
    parser.add_argument("acao", choices=("conciliar", "reservar", "despacho", "receber", "devolver",
                                        "bloqueio", "retomar_bloqueados", "revisar", "cobertura"))
    parser.add_argument("--fila", type=Path)
    parser.add_argument("--dossie", type=Path)
    parser.add_argument("--limite", type=int, choices=range(1, 6), default=2)
    args = parser.parse_args()
    try:
        sincronizar_fila(args.raiz, args.fila or args.raiz / "fila.sqlite")
        with closing(conectar(args.raiz)) as db, db:
            if args.acao == "conciliar":
                if not args.dossie:
                    raise ValueError("informe --dossie")
                conciliar(db, args.raiz, json.loads(args.dossie.read_text(encoding="utf-8")))
            elif args.acao == "reservar":
                print(json.dumps(reservar(db, args.limite), ensure_ascii=False))
                return 0
            elif args.acao == "retomar_bloqueados":
                for item in db.execute("SELECT numero FROM tarefas WHERE estado='bloqueado'").fetchall():
                    evento(db, item["numero"], "retomar_bloqueados", {})
                db.execute("UPDATE tarefas SET estado='pendente', reserva=NULL, vence=NULL, "
                           "executor=NULL, modelo=NULL, chamada=NULL, resultado=NULL WHERE estado='bloqueado'")
            elif args.acao != "cobertura":
                atualizar(db, args.acao, json.load(sys.stdin))
            print(json.dumps(cobertura(db), ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as erro:
        print(f"Controle de validação: {erro}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
