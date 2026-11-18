"""Confere trilha documental local, integridade das cópias e vínculos por cláusula."""

import argparse
import json
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from controle_validacao import NOME
from fila_documental import TERMOS
from guardar_original import sha256

CLASSES = {"candidato", "exigido", "descartado"}
ETAPAS = ("download", "leitura", "validacao")
ESTADOS = {"ok", "falhou", "nao_executada"}
DECISOES = {"atende", "nao_atende", "descartado"}


def texto(valor):
    return isinstance(valor, str) and bool(valor.strip())


def conferir(raiz, dossie):
    erros = []
    acervo = raiz / "documentos_empresa"
    requisitos = set()
    for requisito in dossie["requisitos"]:
        chave = (requisito["empresa"], requisito["clausula"])
        if chave in requisitos or not all(texto(requisito.get(k)) for k in ("empresa", "clausula", "situacao", "detalhe")):
            erros.append("requisito duplicado ou sem empresa, cláusula, situação e detalhe")
        requisitos.add(chave)
    ids = set()
    copias = set()
    for doc in dossie["documentos"]:
        chave = (doc["empresa"], doc["id"])
        rotulo = "/".join(chave)

        def exigir(condicao, mensagem, rotulo=rotulo):
            if not condicao:
                erros.append(f"{rotulo}: {mensagem}")

        exigir(all(texto(x) for x in chave) and chave not in ids, "ID ausente ou duplicado")
        ids.add(chave)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", chave[0]):
            exigir(False, "empresa inválida")
            continue
        classe = doc.get("classe")
        exigir(classe in CLASSES, "classificação inválida")
        if classe == "descartado":
            exigir(texto(doc.get("motivo_descarte")), "descarte sem motivo")
        vinculos = doc.get("vinculos", [])
        if classe == "exigido":
            exigir(vinculos, "documento exigido sem cláusula")
        for vinculo in vinculos:
            exigir((chave[0], vinculo.get("clausula")) in requisitos, "cláusula ausente na matriz")

        etapas = doc.get("etapas", {})
        for etapa in ETAPAS:
            estado = etapas.get(etapa, {})
            exigir(estado.get("estado") in ESTADOS and texto(estado.get("detalhe")),
                   f"{etapa} sem estado e detalhe observável")

        download = etapas.get("download", {}).get("estado")
        leitura = etapas.get("leitura", {}).get("estado")
        validacao = etapas.get("validacao", {}).get("estado")
        exigir(leitura != "ok" or download == "ok", "leitura sem cópia confirmada")
        exigir(validacao != "ok" or leitura == "ok", "validação sem leitura confirmada")
        if validacao == "ok":
            exigir(vinculos, "validação sem evidência por cláusula")

        tentativas = doc.get("tentativas", [])
        for tentativa in tentativas:
            exigir(all(texto(tentativa.get(k)) for k in ("via", "estado", "resultado"))
                   and tentativa.get("estado") in ESTADOS, "tentativa sem via, estado ou resultado")
        if classe != "descartado" and download != "ok":
            vias = {t.get("via") for t in tentativas}
            exigir({"buscar_identificador", "renovar_link"} <= vias,
                   "faltam registros de busca por identificador ou renovação")
        if download != "ok":
            exigir(not doc.get("arquivo"), "etapa de download contradiz o caminho informado")
            continue

        relativo = Path(doc.get("arquivo") or "")
        caminho = raiz / relativo
        pasta_empresa = acervo / chave[0]
        local_valido = (
            not relativo.is_absolute()
            and not caminho.is_symlink()
            and not pasta_empresa.is_symlink()
            and not acervo.is_symlink()
            and caminho.resolve().is_relative_to(pasta_empresa.resolve())
        )
        exigir(local_valido and caminho.is_file(), "cópia ausente ou fora da pasta da empresa")
        if local_valido and caminho.is_file():
            copias.add(caminho.resolve())
            exigir(sha256(caminho) == doc.get("sha256"), "SHA-256 não corresponde à cópia")
        exigir(vinculos or (classe == "descartado" and texto(doc.get("motivo_descarte"))),
               "cópia sem vínculo à matriz nem descarte justificado")
        for vinculo in vinculos:
            pagina = vinculo.get("pagina")
            secao = vinculo.get("secao")
            if leitura == "ok":
                exigir((type(pagina) is int and pagina > 0 or texto(secao)) and texto(vinculo.get("trecho")),
                       "vínculo lido sem página/seção específica e trecho observado")

        if leitura == "ok":
            conferidas = doc.get("paginas_conferidas_visualmente", [])
            relevantes = {v.get("pagina") for v in vinculos} & set(doc.get("paginas_visuais", []))
            exigir(relevantes.issubset(conferidas), "página vinculada com imagem sem conferência visual")

        if doc.get("digitalizado") and leitura == "ok":
            exigir(doc.get("metodo_leitura") in {"visual", "ocr_conferido"}, "digitalizado sem leitura visual ou OCR conferido")
            paginas = doc.get("paginas_lidas", [])
            exigir(paginas and all(type(n) is int and n > 0 for n in paginas), "digitalizado sem páginas lidas")
            for vinculo in vinculos:
                exigir(vinculo.get("pagina") in paginas, "página vinculada não consta como lida")

    if acervo.exists():
        for caminho in sorted(acervo.rglob("*")):
            controle = caminho.parent == acervo and caminho.name in {
                NOME, NOME + "-journal", NOME + "-wal", NOME + "-shm",
            }
            if not controle and caminho.is_file() and caminho.resolve() not in copias:
                erros.append(f"{caminho.relative_to(raiz)}: cópia sem registro reconciliado")
    return erros



def conferir_fila(arquivo, dossie):
    if not arquivo.is_file():
        return ["fila documental não encontrada"]
    with sqlite3.connect(arquivo.resolve().as_uri() + "?mode=ro", uri=True) as db:
        linhas = db.execute("SELECT empresa,clausula,ident,tipo,estado,dados FROM fila").fetchall()
    erros = [f"{e}/{c}/{i}: {t} em {s} na fila" for e, c, i, t, s, _ in linhas if s not in TERMOS]
    originais = {(e, c, i): (s, json.loads(d)) for e, c, i, t, s, d in linhas if t == "original"}
    documentos = {
        (doc["empresa"], vinculo["clausula"], doc["id"]): doc
        for doc in dossie["documentos"] for vinculo in doc.get("vinculos", [])
    }
    for chave, (estado, dados) in originais.items():
        if (estado == "descartado" and (chave[2].startswith("at_") or "triagem" in dados)
                and (dados.get("material", True) or not dados.get("evidencia_descarte"))):
            erros.append(f"{'/'.join(chave)}: descarte técnico sem triagem e evidência individual")
        if estado != "salvo":
            continue
        doc = documentos.get(chave, {})
        download = doc.get("etapas", {}).get("download", {}).get("estado")
        if download != "ok" or any(dados.get(k) != doc.get(k) for k in ("arquivo", "sha256")):
            erros.append(f"{'/'.join(chave)}: original salvo sem cópia e hash correspondentes no dossiê")
        if dados.get("material", True) and doc.get("classe") == "descartado":
            leitura = doc.get("etapas", {}).get("leitura", {}).get("estado")
            if leitura != "ok":
                erros.append(f"{'/'.join(chave)}: candidato material descartado sem leitura comprovada")
    for doc in dossie["documentos"]:
        if (doc["id"].startswith("at_") and doc["classe"] == "descartado"
                and doc["etapas"]["download"]["estado"] != "ok"):
            chaves = [(doc["empresa"], v["clausula"], doc["id"]) for v in doc.get("vinculos", [])]
            if not chaves or any(originais.get(chave, (None,))[0] != "descartado" for chave in chaves):
                erros.append(f"{doc['empresa']}/{doc['id']}: descarte sem decisão correspondente na fila")
        if doc["classe"] != "exigido":
            continue
        estado = doc.get("etapas", {}).get("download", {}).get("estado")
        esperado = "salvo" if estado == "ok" else "tentativas_esgotadas"
        for vinculo in doc.get("vinculos", []):
            chave = (doc["empresa"], vinculo["clausula"], doc["id"])
            if estado == "nao_executada" or originais.get(chave, (None,))[0] != esperado:
                erros.append(f"{'/'.join(chave)}: documento exigido sem tentativa reconciliada na fila")
    return erros

def analise_documental(dossie, itens_fila):
    pendencias = []
    total = 0
    completos = 0
    for doc in dossie["documentos"]:
        etapas = doc["etapas"]
        salvo = etapas["download"]["estado"] == "ok"
        for vinculo in doc.get("vinculos", []):
            chave = (doc["empresa"], vinculo["clausula"], doc["id"])
            material = itens_fila.get(chave, {}).get("material", True)
            if doc["classe"] != "exigido" and not (salvo and material):
                continue
            total += 1
            etapa = next((e for e in ETAPAS if etapas[e]["estado"] != "ok"), None)
            if etapa:
                motivo = vinculo.get("impedimento") or etapas[etapa]["detalhe"]
            elif vinculo.get("decisao") not in DECISOES or not texto(vinculo.get("resultado")):
                motivo = "falta decisão fundamentada para este vínculo"
            else:
                completos += 1
                continue
            pendencias.append({"empresa": chave[0], "clausula": chave[1], "id": chave[2],
                               "etapa": etapa or "validacao", "detalhe": motivo})
    return {"total": total, "decididos": completos, "pendencias": pendencias}


def ler_material(arquivo):
    if not arquivo or not arquivo.is_file():
        return {}
    with sqlite3.connect(arquivo.resolve().as_uri() + "?mode=ro", uri=True) as db:
        linhas = db.execute("SELECT empresa,clausula,ident,dados FROM fila WHERE tipo='original'")
        return {(e, c, i): json.loads(d) for e, c, i, d in linhas}


def conferir_controle(raiz, dossie):
    esperados = {(d["empresa"], d["sha256"], v["clausula"]) for d in dossie["documentos"]
                 if d["etapas"]["download"]["estado"] == "ok" for v in d.get("vinculos", [])}
    arquivo = raiz / "documentos_empresa" / NOME
    if not arquivo.is_file():
        return {"estado": "ausente", "total": 0, "estados": {}, "faltantes": sorted(esperados)}
    with closing(sqlite3.connect(arquivo.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        estados = dict(db.execute("SELECT estado, COUNT(*) FROM tarefas GROUP BY estado"))
        presentes = set(db.execute("SELECT empresa,sha256,clausula FROM tarefas"))
    total = sum(estados.values())
    faltantes = sorted(esperados - presentes)
    completa = bool(total) and not faltantes and total == estados.get("lido", 0) + estados.get("revisada", 0)
    return {"estado": "concluida" if completa else "incompleta", "total": total,
            "estados": estados, "faltantes": faltantes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pasta", type=Path)
    parser.add_argument("dossie", type=Path)
    parser.add_argument("--fila", type=Path, help="verifica a cobertura operacional antes do fechamento")
    parser.add_argument("--exigir-validacao", action="store_true",
                        help="retorna 3 se a trilha estiver íntegra e a análise não estiver completa")
    parser.add_argument("--json", action="store_true", help="emite estados e pendências em JSON")
    args = parser.parse_args()
    try:
        dados = json.loads(args.dossie.read_text(encoding="utf-8"))
        erros = conferir(args.pasta.resolve(), dados)
        erros_fila = conferir_fila(args.fila, dados) if args.fila else []
        analise = analise_documental(dados, ler_material(args.fila))
        delegacao = conferir_controle(args.pasta.resolve(), dados)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error) as exc:
        print(f"Dossiê inválido: {exc}", file=sys.stderr)
        return 2
    aquisicao = "com_pendencias" if erros_fila else "reconciliada" if args.fila else "fila_nao_conferida"
    integridade = "com_inconsistencias" if erros else "conferida"
    erros.extend(erros_fila)
    completa = not erros and analise["total"] > 0 and not analise["pendencias"]
    analise["estado"] = "completa" if completa else "incompleta"
    if args.json:
        print(json.dumps({"aquisicao": aquisicao, "integridade": integridade, "analise_documental": analise,
                          "leitura_delegada": delegacao, "erros_trilha": erros}, ensure_ascii=False))
    else:
        for erro in erros:
            print(erro, file=sys.stderr)
        print(f"Aquisição operacional: {aquisicao}")
        print(f"Integridade da trilha: {integridade}")
        print(f"Leitura delegada: {delegacao['estado']} ({delegacao['total']} vínculos)")
        print(f"Análise documental: {analise['estado']} "
              f"({analise['decididos']}/{analise['total']} vínculos decididos)")
        for item in analise["pendencias"]:
            print(f"{item['empresa']}/{item['clausula']}/{item['id']}: "
                  f"{item['etapa']}: {item['detalhe']}")
    if erros:
        return 2
    if args.exigir_validacao and not completa:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
