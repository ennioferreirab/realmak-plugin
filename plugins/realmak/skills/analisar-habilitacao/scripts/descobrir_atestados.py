"""Gera consultas de descoberta e reúne os IDs das páginas preservadas."""

import argparse
import json
import sys

RECORTES = ("composto", "amplo", "equipamento", "servico")
AMBIENTE = "concat_ws(' ', e.nome, e.ramo, e.superior_nome, a.objeto, a.area)"
OBJETO = "concat_ws(' ', a.objeto, a.area)"
SERVICO = "concat_ws(' ', s.descricao, s.trecho)"


def literal(texto):
    return "'" + texto.replace("'", "''") + "'"


def termos_do_plano(plano):
    termos = {}
    for recorte in RECORTES:
        lista = plano["termos"][recorte]
        if not isinstance(lista, list) or not lista:
            raise ValueError(f"informe termos para {recorte}")
        termos[recorte] = list(dict.fromkeys(" ".join(t.lower().split()) for t in lista))
        if "" in termos[recorte]:
            raise ValueError(f"termo vazio em {recorte}")
    if not set(termos["amplo"]).difference(termos["composto"]):
        raise ValueError("informe ao menos um termo amplo distinto da expressão composta")
    return termos


def contem(campo, termos):
    return "(" + " OR ".join(f"strpos(lower({campo}), {literal(t)}) > 0" for t in termos) + ")"


def consulta(recorte, termos, apos, limite):
    if recorte in ("composto", "amplo"):
        filtro = (
            f"{contem(AMBIENTE, termos)} OR EXISTS (SELECT 1 FROM unnest(e.nomes) AS n(nome) "
            f"WHERE {contem('n.nome', termos)})"
        )
        emissor = " LEFT JOIN entidades e ON e.entidade_id = a.emissor_id"
    else:
        filtro = (
            f"{contem(OBJETO, termos)} "
            "OR EXISTS (SELECT 1 FROM atestado_servicos s "
            f"WHERE s.atestado_id = a.atestado_id AND {contem(SERVICO, termos)})"
        )
        emissor = ""
    cursor = f" AND a.atestado_id > {literal(apos)}" if apos is not None else ""
    return (
        "SELECT a.atestado_id, a.emissor_id, a.beneficiario_id, a.contrato_numero, "
        f"a.objeto, a.situacao_documento FROM atestados a{emissor} "
        f"WHERE ({filtro}){cursor} ORDER BY a.atestado_id LIMIT {limite}"
    )


def unir(plano, limite):
    cursores = dict.fromkeys(RECORTES)
    completos = set()
    candidatos = {}
    for pagina in plano.get("paginas", []):
        recorte = pagina["recorte"]
        if (pagina["empresa"] != plano["empresa"] or recorte not in RECORTES
                or recorte in completos or pagina["apos"] != cursores[recorte]):
            raise ValueError("página fora da empresa, recorte ou sequência")
        ids = [linha["atestado_id"] for linha in pagina["linhas"]]
        if (any(not isinstance(i, str) or not i for i in ids)
                or ids != sorted(set(ids)) or len(ids) > limite):
            raise ValueError("página sem IDs únicos e ordenados ou acima do limite")
        if ids and cursores[recorte] is not None and ids[0] <= cursores[recorte]:
            raise ValueError("página sem avanço de cursor")
        for ident in ids:
            candidatos.setdefault(ident, []).append(recorte)
        if len(ids) < limite and not pagina["truncado"]:
            completos.add(recorte)
        elif ids:
            cursores[recorte] = ids[-1]
        else:
            raise ValueError("página truncada sem cursor; reduza o limite ou divida o recorte")
    return {
        "empresa": plano["empresa"],
        "candidatos": {ident: sorted(candidatos[ident]) for ident in sorted(candidatos)},
        "pendentes": {r: cursores[r] for r in RECORTES if r not in completos},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("acao", choices=("consulta", "unir"))
    parser.add_argument("--recorte", choices=RECORTES)
    parser.add_argument("--apos")
    parser.add_argument("--limite", type=int, choices=range(1, 501), metavar="1..500", default=50)
    args = parser.parse_args()
    try:
        plano = json.load(sys.stdin)
        termos = termos_do_plano(plano)
        if args.acao == "consulta":
            if args.recorte is None:
                raise ValueError("informe --recorte")
            print(consulta(args.recorte, termos[args.recorte], args.apos, args.limite))
        else:
            resultado = unir(plano, args.limite)
            print(json.dumps(resultado, ensure_ascii=False))
            return 1 if resultado["pendentes"] else 0
    except (ValueError, KeyError, TypeError, AttributeError) as erro:
        print(erro, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
