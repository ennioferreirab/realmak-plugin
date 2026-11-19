"""Confere a definição distribuída e as saídas que o card consome."""

import json
import re
from graphlib import TopologicalSorter
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
AGENTES = RAIZ / "agentes"
ANALISADOR = AGENTES / "analisador-edital"
SKILLS = RAIZ / "plugins/realmak/skills"
EXEMPLO = ANALISADOR / "referencias/card/exemplo/analise"
EMPRESAS = ("aforca", "realmak", "una", "nortfort")


def ler_json(arquivo):
    return json.loads(arquivo.read_text(encoding="utf-8"))


def test_manifestos_e_contexto():
    for chave, titulo in (("analisador-edital", "Analisador de Edital"), ("garimpo", "Garimpo")):
        pasta = AGENTES / chave
        manifesto = ler_json(pasta / "agente.json")
        assert manifesto["acao"] == chave
        assert manifesto["titulo"] == titulo
        assert type(manifesto["chat"]) is bool
        assert type(manifesto["funil"]) is bool
        assert isinstance(manifesto["depende_de"], list)
        assert all(isinstance(f, str) for f in manifesto["ferramentas"])
        assert (pasta / "AGENTS.md").is_file()
    analisador = ler_json(ANALISADOR / "agente.json")
    assert (analisador["tipo"], analisador["tier"]) == ("gestor", "T2")
    assert "buscar_web" in analisador["ferramentas"]
    assert {f"cerebro_{acao}" for acao in ("empresas", "buscar", "fatos", "esquema", "consulta", "provas")} <= set(
        analisador["ferramentas"]
    )
    assert (ANALISADOR / "GESTOR.md").stat().st_size
    contexto = AGENTES / "contexto"
    assert set(EMPRESAS) <= ler_json(contexto / "empresas.json")["cerebros"].keys()
    for arquivo in ("prompt_empresa.md", "prompt_sistema.md"):
        assert (contexto / arquivo).stat().st_size


def test_skills_unicas_e_frontmatter():
    locais = {p.parent.name for p in (ANALISADOR / "skills").glob("*/SKILL.md")}
    assert locais == {"pasta-licitacao", "guia-leitura-edital", "analise-tecnica", "cotacao-fornecedor", "score"}
    assert not (ANALISADOR / ".agents/skills").exists()
    assert not (ANALISADOR / "skills-plugin.json").exists()
    assert locais.isdisjoint(p.parent.name for p in SKILLS.glob("*/SKILL.md"))
    for p in [*SKILLS.glob("*/SKILL.md"), *(p for p in AGENTES.rglob("SKILL.md") if p.parent.name != "templates")]:
        meta = yaml.safe_load(p.read_text(encoding="utf-8").split("---", 2)[1])
        assert meta["name"] == p.parent.name, p
        assert isinstance(meta["description"], str) and meta["description"].strip(), p


def test_fluxo_e_referencias():
    fluxo = ler_json(ANALISADOR / "fluxo.json")
    assert fluxo["versao"] >= 4
    ids = set()
    saidas = {}
    etapas = {}
    for etapa in fluxo["etapas"]:
        assert etapa["id"] not in ids and etapa["id"] != "documento"
        assert etapa["titulo"].strip()
        ids.add(etapa["id"])
        etapas[etapa["id"]] = etapa
        if etapa.get("portao"):
            decisoes = etapa["decisoes"]
            assert "seguir" in decisoes
            assert set(decisoes) <= {"seguir", "parar", "humano", "rerodar", "precos"}
            continue
        itens = etapa["itens"]
        deps = {i["id"]: set(i.get("depende_de", [])) for i in itens}
        assert all(d <= deps.keys() for d in deps.values())
        assert len(list(TopologicalSorter(deps).static_order())) == len(itens)
        for item in itens:
            assert item["id"] not in ids and item["id"] != "documento"
            ids.add(item["id"])
            assert 0 < len(item["titulo"]) <= 120
            assert len(item.get("passos", "")) <= 200
            if "saida" in item:
                saida = item["saida"]
                assert not Path(saida).is_absolute() and ".." not in Path(saida).parts
                assert saida not in saidas
                saidas[saida] = item["id"]
            if item["modo"] == "skill":
                nome = item["skill"]
                assert item["tier"] in ("T1", "T2") and item["saida"]
                assert any((base / nome / "SKILL.md").is_file() for base in (ANALISADOR / "skills", SKILLS)), nome
            else:
                assert (item["modo"], item["tier"], item["cmd"][0]) == ("script", "T0", "python3")
                cmd = item["cmd"]
                assert all(set(re.findall(r"\{[^}]+\}", p)) <= {
                    "{licitacao_id}", "{pasta_agente}", "{pasta_agente_def}", "{pasta_licitacao}",
                } for p in cmd)
                assert Path(cmd[1].replace("{pasta_agente_def}", str(ANALISADOR))).is_file()
    assert set(saidas) >= {f"analise/{p.name}" for p in EXEMPLO.glob("*.json")}
    e2 = {i["id"]: i for i in etapas["E2"]["itens"]}
    parciais = {f"habilitacao-{empresa}" for empresa in EMPRESAS}
    for empresa in EMPRESAS:
        item = e2[f"habilitacao-{empresa}"]
        assert (item["skill"], item["tier"]) == ("analisar-habilitacao", "T1")
        assert empresa in item["passos"] and not item.get("depende_de")
        assert item["saida"] == f"analise/habilitacao/{empresa}.json"
    final = e2["habilitacao"]
    assert set(final["depende_de"]) == parciais and final["tolera_falha"] is True
    assert final["saida"] == "analise/habilitacao.json" and final["tier"] == "T2"
    assert "rerodar" in etapas["G2"]["decisoes"]
    pecas = e2["pecas"]
    assert pecas["tier"] == "T1" and pecas["skill"] == "cotar-pecas-materiais-licitacoes"
    assert not pecas.get("depende_de") and pecas["saida"] == "fontes/pecas.json"
    assert pecas["saida"] in etapas["E3"]["itens"][0]["passos"]


@pytest.mark.parametrize(("arquivo", "objetos", "listas"), [
    ("edital", ("cabecalho",), ("atencao", "prazos", "habilitacao", "declaracoes", "proposta", "impugnacao",
                                "perguntas_tecnico", "avisos", "nao_lido", "documentos")),
    ("habilitacao", (), ("empresas", "cobertura", "emitiveis", "perguntas_tecnico")),
    ("tecnica", ("conclusao",), ("itens", "cotacoes_online", "escopo", "equipe", "sla", "arquivos")),
    ("precificacao", (), ("cenarios", "componentes", "cotacoes_online", "arquivos")),
])
def test_contrato_do_card(arquivo, objetos, listas):
    exemplo = ler_json(EXEMPLO / f"{arquivo}.json")
    assert exemplo["versao"] == 1 and isinstance(exemplo["gerado_em"], str)
    for campo in objetos:
        assert isinstance(exemplo[campo], dict)
    for campo in listas:
        assert isinstance(exemplo[campo], list)
    if arquivo == "habilitacao":
        assert exemplo["mais_aderente"] in (*EMPRESAS, None)
        assert {e["empresa"] for e in exemplo["empresas"]} == set(EMPRESAS)
        linhas = {(c["empresa"], c["exigencia"], c["fonte"]): c for c in exemplo["cobertura"]}
        for empresa in exemplo["empresas"]:
            assert empresa["aderencia"] in {"alta", "media", "baixa", "nao_atende"}
            for exigencia in empresa["exigencias"]:
                assert exigencia["situacao"] in {"atende", "parcial", "nao_atende", "verificar"}
                assert {"exigencia", "fonte", "situacao", "prova", "validade"} <= exigencia.keys()
                registro = linhas[empresa["empresa"], exigencia["exigencia"], exigencia["fonte"]]
                assert type(registro["eliminatoria"]) is bool
                assert registro["estado"] in {"prova_lida", "vias_esgotadas", "falha", "pendente"}
                assert all({"via", "consulta", "resultado"} <= t.keys() for t in registro["tentativas"])
