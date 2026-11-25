"""Gera a visão v1 dos agentes a partir das definições versionadas."""
import argparse
import hashlib
import json
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
DESTINOS_VALIDOS = {"proxima", "parar", "humano", "rerodar", "precos"}
DESTINO_PADRAO = {
    "seguir": "proxima",
    "parar": "parar",
    "humano": "humano",
    "rerodar": "rerodar",
    "precos": "precos",
}
EXTENSOES_LEGIVEIS = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".sh",
    ".csv",
    ".html",
    ".css",
    ".js",
    ".toml",
}


def ler_json(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


def textos(dados, campo, origem, minimo=1):
    valores = dados[campo]
    if (
        not isinstance(valores, list)
        or len(valores) < minimo
        or any(not isinstance(valor, str) or not valor.strip() for valor in valores)
    ):
        raise ValueError(f"{origem}: {campo} precisa de textos preenchidos")
    return valores


def texto(dados, campo, origem):
    valor = dados[campo]
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{origem}: preencha {campo}")
    return valor


def conferir_ids(esperados, encontrados, origem):
    if sorted(esperados) != sorted(encontrados):
        raise ValueError(f"{origem}: IDs esperados {list(esperados)}, encontrados {list(encontrados)}")


def listar_arquivos_skill(pasta_skill):
    arquivos = []
    for caminho in sorted(pasta_skill.rglob("*")):
        if not caminho.is_file():
            continue
        rel = caminho.relative_to(pasta_skill)
        if any(parte.startswith(".") or parte == "__pycache__" for parte in rel.parts):
            continue
        if caminho.suffix.lower() not in EXTENSOES_LEGIVEIS:
            continue
        arquivos.append(rel.as_posix())
    return arquivos


def resolver_skill(pasta, skill):
    if skill is None:
        return None, None, None, []
    candidatos = (
        ("agente", pasta / ".agents/skills", RAIZ / "agentes"),
        ("agente", pasta / "skills", RAIZ / "agentes"),
        ("plugin", RAIZ / "plugins/realmak/skills", RAIZ / "plugins/realmak/skills"),
    )
    for origem, raiz, base_rel in candidatos:
        pasta_skill = raiz / skill
        caminho = pasta_skill / "SKILL.md"
        if caminho.is_file():
            partes = caminho.read_text(encoding="utf-8").split("---", 2)
            if len(partes) == 3 and not partes[0].strip():
                metadados = yaml.safe_load(partes[1])
                if metadados["name"] == skill:
                    caminho_rel = caminho.relative_to(base_rel).as_posix()
                    return metadados["name"], origem, caminho_rel, listar_arquivos_skill(pasta_skill)
            raise ValueError(f"{caminho}: frontmatter inválido ou nome diferente de {skill}")
    raise ValueError(f"{pasta.name}: skill inexistente: {skill}")


def gerar_decisao(id_etapa, valor, entrada):
    if isinstance(entrada, dict):
        quando = texto(entrada, "quando", f"{id_etapa}.{valor}")
        destino = texto(entrada, "destino", f"{id_etapa}.{valor}")
    else:
        if not isinstance(entrada, str) or not entrada.strip():
            raise ValueError(f"{id_etapa}: preencha decisoes.{valor}")
        quando = entrada
        destino = DESTINO_PADRAO.get(valor, "")
    if destino not in DESTINOS_VALIDOS:
        raise ValueError(f"{id_etapa}.{valor}: destino inválido: {destino}")
    return {"valor": valor, "quando": quando, "destino": destino}


def gerar_item(pasta, item, nota, modelos):
    id_item = item["id"]
    tier = item["tier"]
    skill_nome, skill_origem, skill_caminho, skill_arquivos = resolver_skill(
        pasta, item.get("skill") or nota.get("skill")
    )
    return {
        "id": id_item,
        "titulo": item["titulo"],
        "skill": skill_nome,
        "skill_origem": skill_origem,
        "skill_caminho": skill_caminho,
        "skill_arquivos": skill_arquivos,
        "tier": tier,
        "modelo": modelos[tier],
        "depende_de": item.get("depende_de", []),
        "entrada": item.get("entrada"),
        "saida": item.get("saida") or nota.get("saida"),
        "objetivo": texto(nota, "objetivo", id_item),
        "criterios": textos(nota, "criterios", id_item, minimo=0),
        "resumo": textos(nota, "resumo", id_item),
        "restricoes": textos(nota, "restricoes", id_item, minimo=0),
        "tolera_falha": item.get("tolera_falha", False),
        "cerebro_apoio": item.get("cerebro_apoio", False),
    }


def gerar_etapas(pasta, fluxo, notas):
    etapas = []
    etapas_fluxo = [etapa["id"] for etapa in fluxo["etapas"] if not etapa.get("portao")]
    portoes_fluxo = [etapa["id"] for etapa in fluxo["etapas"] if etapa.get("portao")]
    itens_fluxo = [item["id"] for etapa in fluxo["etapas"] for item in etapa.get("itens", [])]
    conferir_ids(etapas_fluxo, notas["etapas"], "notas das etapas")
    conferir_ids(portoes_fluxo, notas["portoes"], "notas dos portões")
    conferir_ids(itens_fluxo, notas["itens"], "notas dos itens")

    for etapa in fluxo["etapas"]:
        id_etapa = etapa["id"]
        if etapa.get("portao"):
            nota = notas["portoes"][id_etapa]
            conferir_ids(etapa["decisoes"], nota["decisoes"], id_etapa)
            if not etapas or "portao" in etapas[-1]:
                raise ValueError(f"{id_etapa}: portão sem etapa precedente")
            etapas[-1]["portao"] = {
                "id": id_etapa,
                "titulo": etapa["titulo"],
                "objetivo": texto(nota, "objetivo", id_etapa),
                "criterios": textos(nota, "criterios", id_etapa),
                "decisoes": [
                    gerar_decisao(id_etapa, valor, nota["decisoes"][valor])
                    for valor in etapa["decisoes"]
                ],
            }
            continue

        nota = notas["etapas"][id_etapa]
        itens = {item["id"]: item for item in etapa["itens"]}
        conferir_ids(itens, [id_item for grupo in nota["grupos"] for id_item in grupo["itens"]], id_etapa)
        grupos = []
        for grupo in nota["grupos"]:
            if grupo["tipo"] not in {"paralelo", "sequencia", "leque"} or not grupo["itens"]:
                raise ValueError(f"{id_etapa}: grupo inválido")
            grupos.append({
                "tipo": grupo["tipo"],
                "rotulo": texto(grupo, "rotulo", id_etapa),
                "itens": [
                    gerar_item(pasta, itens[id_item], notas["itens"][id_item], notas["modelos"])
                    for id_item in grupo["itens"]
                ],
            })
        etapas.append({
            "id": id_etapa,
            "titulo": etapa["titulo"],
            "objetivo": texto(nota, "objetivo", id_etapa),
            "criterios": textos(nota, "criterios", id_etapa, minimo=0),
            "descricao": texto(nota, "descricao", id_etapa),
            "grupos": grupos,
        })
    return etapas


def gerar_visao(pasta, versao_plugin):
    agente = ler_json(pasta / "agente.json")
    notas = ler_json(pasta / "visao-notas.json")
    caminho_fluxo = pasta / "fluxo.json"
    if caminho_fluxo.is_file():
        fluxo_bytes = caminho_fluxo.read_bytes()
        fluxo_sha = hashlib.sha256(fluxo_bytes).hexdigest()
        etapas = gerar_etapas(pasta, json.loads(fluxo_bytes), notas)
    else:
        fluxo_sha = None
        etapas = [
            {
                "id": texto(etapa, "id", pasta.name),
                "titulo": texto(etapa, "titulo", pasta.name),
                "objetivo": texto(etapa, "objetivo", pasta.name),
                "criterios": textos(etapa, "criterios", pasta.name, minimo=0),
                "descricao": texto(etapa, "descricao", pasta.name),
                "grupos": [],
            }
            for etapa in notas["etapas_descritivas"]
        ]
    return {
        "versao": 1,
        "agente": agente["acao"],
        "titulo": agente["titulo"],
        "gerado_de": {"plugin_versao": versao_plugin, "fluxo_sha256": fluxo_sha},
        "resumo": texto(notas, "resumo", pasta.name),
        "etapas": etapas,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Confere os arquivos sem escrever")
    args = parser.parse_args()
    plugin = RAIZ / "plugins/realmak/.codex-plugin/plugin.json"
    versao_plugin = ler_json(plugin)["version"]
    pastas = sorted(
        {p.parent for nome in ("fluxo.json", "visao-notas.json", "visao.json") for p in (RAIZ / "agentes").glob(f"*/{nome}")}
    )
    falha = False
    for pasta in pastas:
        try:
            visao = gerar_visao(pasta, versao_plugin)
            esperado = json.dumps(visao, ensure_ascii=False, indent=2) + "\n"
            caminho = pasta / "visao.json"
            if not args.check:
                caminho.write_text(esperado, encoding="utf-8")
            elif not caminho.exists() or caminho.read_text(encoding="utf-8") != esperado:
                raise ValueError("visao.json desatualizado. Rode scripts/gerar_visao_fluxo.py.")
        except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as erro:
            print(f"{pasta.name}: {erro}")
            falha = True
    return int(falha)


if __name__ == "__main__":
    raise SystemExit(main())
