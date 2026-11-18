"""Reconcilia originais por empresa, ID exato e SHA-256 sem ler links assinados."""

import argparse
import json
import re
import sys
from pathlib import Path

from guardar_original import sha256

TAMANHO = 50
SHA = re.compile(r"[a-f0-9]{64}")


def hash_valido(valor):
    return isinstance(valor, str) and SHA.fullmatch(valor) is not None


def consulta(ident, apos=None):
    if not isinstance(ident, str) or not ident.strip():
        raise ValueError("informe um ID exato de registro")
    if apos is not None and not hash_valido(apos):
        raise ValueError("cursor precisa ser o último SHA-256 da página")
    ident = ident.replace("'", "''")
    cursor = f" AND rd.sha > '{apos}'" if apos else ""
    return (
        "SELECT rd.sha, MAX(rd.versao) AS versao, MAX(d.caminho_relativo) AS caminho "
        "FROM registro_documentos rd LEFT JOIN documentos d ON d.sha = rd.sha "
        f"WHERE rd.registro_id = '{ident}'{cursor} GROUP BY rd.sha ORDER BY rd.sha LIMIT {TAMANHO}"
    )


def pendente(motivo, **detalhe):
    return {"estado": "pendente", "motivo": motivo, **detalhe}


def reconciliar(dados):
    empresa, ident = dados["empresa"], dados["id"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", empresa):
        raise ValueError("use o alias da empresa")
    consulta(ident)
    registrados = {}
    apos = None
    incompleta = True
    for pagina in dados.get("paginas", []):
        if not incompleta or pagina["empresa"] != empresa or pagina["id"] != ident or pagina.get("apos") != apos:
            raise ValueError("página fora da empresa, ID ou sequência consultados")
        linhas = pagina["linhas"]
        chaves = [linha["sha"] for linha in linhas]
        if (any(not hash_valido(k) for k in chaves) or chaves != sorted(set(chaves))
                or (apos and chaves and chaves[0] <= apos)):
            raise ValueError("página sem SHA-256 em ordem estável")
        for linha in linhas:
            registrados[linha["sha"]] = linha.get("caminho")
        incompleta = len(linhas) >= TAMANHO or pagina.get("truncado", False)
        if incompleta and not chaves:
            raise ValueError("resultado truncado sem cursor")
        if chaves:
            apos = chaves[-1]
    alvo = dados.get("sha256_esperado")
    if alvo is not None and not hash_valido(alvo):
        raise ValueError("SHA-256 esperado inválido")
    if incompleta:
        return pendente("pagine registro_documentos antes de selecionar a versão", proxima_sql=consulta(ident, apos))
    if alvo and registrados and alvo not in registrados and not incompleta:
        return pendente("hash esperado diverge do vínculo estruturado", hashes=sorted(registrados))
    if not alvo:
        if len(registrados) != 1:
            return pendente("sem vínculo único; confira versão ou hash esperado", hashes=sorted(registrados))
        alvo = next(iter(registrados))

    for origem in ("provas", "busca"):
        for indice, resultado in enumerate(dados.get(origem, [])):
            if (resultado.get("empresa") == empresa and resultado.get("sha256") == alvo
                    and resultado.get("tem_link_baixar") is True):
                return {"estado": "selecionado", "origem": origem, "indice": indice,
                        "sha256": alvo}
    caminho = registrados.get(alvo)
    if caminho:
        nome = caminho.replace("\\", "/").rsplit("/", 1)[-1]
        return pendente("busque o original pelo nome e confira o SHA-256", nome=nome, sha256=alvo)
    return pendente("nenhum link utilizável para o SHA-256", sha256=alvo)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="acao", required=True)
    sql = subs.add_parser("consulta")
    sql.add_argument("id")
    sql.add_argument("--apos")
    subs.add_parser("resolver")
    conferir = subs.add_parser("conferir")
    conferir.add_argument("arquivo", type=Path)
    conferir.add_argument("sha256")
    args = parser.parse_args()
    try:
        if args.acao == "consulta":
            print(consulta(args.id, args.apos))
        elif args.acao == "resolver":
            resultado = reconciliar(json.load(sys.stdin))
            print(json.dumps(resultado, ensure_ascii=False))
            return 0 if resultado["estado"] == "selecionado" else 2
        else:
            if not hash_valido(args.sha256) or not args.arquivo.is_file() or not args.arquivo.stat().st_size:
                raise ValueError("informe arquivo não vazio e SHA-256 esperado")
            if sha256(args.arquivo) != args.sha256:
                raise ValueError("bytes baixados divergem do SHA-256 de origem")
            print("SHA-256 de origem confirmado")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(f"Recuperação pendente: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
