"""Confere a definição distribuída e as saídas que o card consome."""

import json
import os
import re
import subprocess
import sys
from datetime import date
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
    assert locais == {
        "pasta-licitacao",
        "guia-leitura-edital",
        "analise-tecnica",
        "conferir-habilitacao",
        "cotacao-fornecedor",
        "score",
    }
    assert not (ANALISADOR / ".agents/skills").exists()
    assert not (ANALISADOR / "skills-plugin.json").exists()
    assert locais.isdisjoint(p.parent.name for p in SKILLS.glob("*/SKILL.md"))
    for p in [*SKILLS.glob("*/SKILL.md"), *(p for p in AGENTES.rglob("SKILL.md") if p.parent.name != "templates")]:
        meta = yaml.safe_load(p.read_text(encoding="utf-8").split("---", 2)[1])
        assert meta["name"] == p.parent.name, p
        assert isinstance(meta["description"], str) and meta["description"].strip(), p


def test_fluxo_e_referencias():
    fluxo = ler_json(ANALISADOR / "fluxo.json")
    assert fluxo["versao"] == 6
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
            if item.get("tolera_falha"):
                assert item.get("depende_de"), f"{item['id']}: tolera_falha exige depende_de"
            if "saida" in item:
                saida = item["saida"]
                assert not Path(saida).is_absolute() and ".." not in Path(saida).parts
                assert saida not in saidas
                saidas[saida] = item["id"]
            if item["modo"] == "skill":
                nome = item["skill"]
                assert item["tier"] in ("T1", "T2") and item["saida"]
                assert any((base / nome / "SKILL.md").is_file() for base in (ANALISADOR / "skills", SKILLS)), nome
            elif item["modo"] == "baixar":
                assert item["tier"] == "T0" and item["empresa"] in EMPRESAS
                assert "cmd" not in item and "skill" not in item
            else:
                assert (item["modo"], item["tier"], item["cmd"][0]) == ("script", "T0", "python3")
                cmd = item["cmd"]
                assert all(set(re.findall(r"\{[^}]+\}", p)) <= {
                    "{licitacao_id}", "{pasta_agente}", "{pasta_agente_def}", "{pasta_licitacao}",
                } for p in cmd)
                assert Path(cmd[1].replace("{pasta_agente_def}", str(ANALISADOR))).is_file()
    assert set(saidas) >= {f"analise/{p.name}" for p in EXEMPLO.glob("*.json")}
    e0 = {i["id"]: i for i in etapas["E0"]["itens"]}
    assert set(e0) == {"resumo", "mapa"}
    e1 = {i["id"]: i for i in etapas["E1"]["itens"]}
    assert set(e1) == {"edital", "triagem-cerebro"}
    triagem = e1["triagem-cerebro"]
    assert (triagem["skill"], triagem["tier"]) == ("cerebro", "T2")
    assert triagem["depende_de"] == ["edital"] and triagem["saida"] == "fontes/triagem_cerebro.json"
    e2 = {i["id"]: i for i in etapas["E2"]["itens"]}
    assert "cerebro" not in e2
    parciais = {f"habilitacao-{empresa}" for empresa in EMPRESAS}
    for empresa in EMPRESAS:
        pesquisa = e2[f"pesquisa-habilitacao-{empresa}"]
        assert (pesquisa["skill"], pesquisa["tier"], pesquisa["empresa"]) == ("analisar-habilitacao", "T1", empresa)
        assert empresa in pesquisa["passos"] and not pesquisa.get("depende_de")
        assert not pesquisa.get("tolera_falha")
        assert pesquisa["saida"] == f"fontes/habilitacao/{empresa}/candidatos.json"
        baixar = e2[f"baixar-habilitacao-{empresa}"]
        assert (baixar["modo"], baixar["tier"], baixar["empresa"]) == ("baixar", "T0", empresa)
        assert baixar["depende_de"] == [pesquisa["id"]]
        assert baixar["entrada"] == pesquisa["saida"]
        assert baixar["saida"] == f"fontes/habilitacao/{empresa}/downloads.json"
        item = e2[f"habilitacao-{empresa}"]
        assert (item["skill"], item["tier"], item["empresa"]) == ("analisar-habilitacao", "T2", empresa)
        assert empresa in item["passos"] and item["depende_de"] == [baixar["id"]]
        assert item["tolera_falha"] is True
        assert item["saida"] == f"analise/habilitacao/{empresa}.json"
    final = e2["habilitacao"]
    assert set(final["depende_de"]) == parciais and final["tolera_falha"] is True
    assert final["saida"] == "analise/habilitacao.json" and final["tier"] == "T2"
    tecnica = e2["tecnica"]
    assert tecnica["depende_de"] == ["habilitacao"] and tecnica["tier"] == "T2"
    assert "rerodar" in etapas["G2"]["decisoes"]
    assert {nome for nome, etapa in e2.items() if etapa.get("cerebro_apoio")} == {"pecas", "tecnica"}
    pecas = e2["pecas"]
    assert pecas["tier"] == "T1" and pecas["skill"] == "cotar-pecas-materiais-licitacoes"
    assert not pecas.get("depende_de") and pecas["saida"] == "fontes/pecas.json"
    e3 = {i["id"]: i for i in etapas["E3"]["itens"]}
    assert set(e3) == {"precificacao", "score"}
    assert pecas["saida"] in e3["precificacao"]["passos"]
    assert e3["score"]["depende_de"] == ["precificacao"]


def test_visao_fluxo_contrato_canvas():
    visao = ler_json(ANALISADOR / "visao.json")
    assert visao["versao"] == 1
    assert visao["gerado_de"]["plugin_versao"] == "0.16.8"
    destinos_validos = {"proxima", "parar", "humano", "rerodar", "precos"}
    itens_por_id = {}
    for etapa in visao["etapas"]:
        assert isinstance(etapa["objetivo"], str) and etapa["objetivo"].strip()
        assert isinstance(etapa["criterios"], list) and etapa["criterios"]
        if "portao" in etapa:
            portao = etapa["portao"]
            assert isinstance(portao["objetivo"], str) and portao["objetivo"].strip()
            for decisao in portao["decisoes"]:
                assert decisao["destino"] in destinos_validos
        for grupo in etapa["grupos"]:
            for item in grupo["itens"]:
                itens_por_id[item["id"]] = item
                assert isinstance(item["objetivo"], str) and item["objetivo"].strip()
                assert isinstance(item["criterios"], list)
                assert item["skill_origem"] in {"agente", "plugin", None}
                if item["skill"] is not None:
                    assert item["skill_origem"] in {"agente", "plugin"}
                    assert isinstance(item["skill_caminho"], str) and item["skill_caminho"].endswith("/SKILL.md")
                    assert "SKILL.md" in item["skill_arquivos"]
                else:
                    assert item["skill_origem"] is None and item["skill_caminho"] is None
                    assert item["skill_arquivos"] == []
    assert itens_por_id["tecnica"]["skill_origem"] == "agente"
    assert itens_por_id["tecnica"]["skill_caminho"] == "analisador-edital/skills/analise-tecnica/SKILL.md"
    assert itens_por_id["habilitacao"]["skill_origem"] == "plugin"
    assert itens_por_id["habilitacao"]["skill_caminho"] == "analisar-habilitacao/SKILL.md"


def test_scripts_aceitam_chave_externa_e_rejeitam_caminho_inseguro(tmp_path):
    chave = "pncp-02292266000180-1-000164-2026"
    pasta = tmp_path / chave
    (pasta / "anexos/h1/envios/u1").mkdir(parents=True)
    (pasta / "anexos/h2/envios/u2").mkdir(parents=True)
    (pasta / "extraidos/anexos/h1/envios/u1").mkdir(parents=True)
    (pasta / "manifesto.json").write_text(json.dumps({"versao": 1, "chave": chave, "licitacao_id": None}), encoding="utf-8")
    (pasta / "anexos/h1/envios/u1/2-edital-no-47-2026.pdf").write_bytes(b"%PDF-1.4")
    (pasta / "anexos/h2/envios/u2/1-edital.pdf").write_bytes(b"%PDF-1.4")
    (pasta / "extraidos/anexos/h1/envios/u1/2-edital-no-47-2026.pdf.txt").write_text(
        "--- Página 1 ---\nEdital nº 47/2026\n--- Página 2 ---\nQualificação técnica e atestado de capacidade\n",
        encoding="utf-8",
    )
    env = {**os.environ, "PASTA_LICITACOES": str(tmp_path), "NOME_AGENTE": "analisador-edital"}

    resumo_py = str(ANALISADOR / "skills/pasta-licitacao/scripts/resumo_conlicitacao.py")
    localizar_py = str(ANALISADOR / "skills/guia-leitura-edital/scripts/localizar.py")
    score_py = str(ANALISADOR / "skills/score/scripts/score.py")

    r_resumo = subprocess.run([sys.executable, resumo_py, chave], env=env, capture_output=True, text=True, check=True)
    dados_resumo = json.loads(r_resumo.stdout)
    assert dados_resumo["situacao"] == "sem_resumo"
    assert dados_resumo["licitacao_id"] == chave
    assert "pendencia" not in dados_resumo

    r_mapa = subprocess.run([sys.executable, localizar_py, chave], env=env, capture_output=True, text=True, check=True)
    assert "mapa:" in r_mapa.stdout
    mapa_json = ler_json(pasta / "agents/analisador-edital/fontes/mapa_leitura.json")
    assert mapa_json["licitacao_id"] == chave
    assert len(mapa_json["documentos"]) == 1
    assert mapa_json["documentos"][0]["arquivo"] == "2-edital-no-47-2026.pdf"
    assert mapa_json["documentos"][0]["paginas"] == 2
    assert any("1-edital.pdf" in a for a in mapa_json["avisos"])

    r_score = subprocess.run([sys.executable, score_py, chave], env=env, capture_output=True, text=True, check=True)
    assert json.loads(r_score.stdout)["nota"] >= 1
    assert (pasta / "agents/analisador-edital/relatorio/topo.json").is_file()

    for invalida in ("../etc", "a/b", "..", ""):
        for script in (resumo_py, localizar_py, score_py):
            proc = subprocess.run([sys.executable, script, invalida], env=env, capture_output=True, text=True)
            assert proc.returncode != 0, f"{script} aceitou chave insegura {invalida!r}"


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
    if arquivo == "edital":
        assert "portal_sessao" in exemplo["cabecalho"]
        _validar_portal_sessao(exemplo["cabecalho"]["portal_sessao"])
        assert "vigencia" in exemplo
        _validar_vigencia(exemplo["vigencia"])
    if arquivo == "precificacao":
        assert "vigencia_precificacao" in exemplo
        _validar_vigencia_precificacao(exemplo["vigencia_precificacao"])
    if arquivo == "habilitacao":
        assert exemplo["mais_aderente"] in (*EMPRESAS, None)
        assert {e["empresa"] for e in exemplo["empresas"]} == set(EMPRESAS)
        linhas = {(c["empresa"], c["exigencia"], c["fonte"]): c for c in exemplo["cobertura"]}
        grupos = {linha["fonte"]: linha["grupo"] for linha in ler_json(EXEMPLO / "edital.json")["habilitacao"]}
        for empresa in exemplo["empresas"]:
            assert empresa["aderencia"] in {"alta", "media", "baixa", "nao_atende"}
            for exigencia in empresa["exigencias"]:
                assert exigencia["situacao"] in {"atende", "parcial", "nao_atende", "verificar"}
                assert {"exigencia", "fonte", "situacao", "prova", "validade"} <= exigencia.keys()
                registro = linhas[empresa["empresa"], exigencia["exigencia"], exigencia["fonte"]]
                assert type(registro["eliminatoria"]) is bool
                assert registro["estado"] in {"prova_lida", "vias_esgotadas", "falha", "pendente"}
                assert all({"via", "consulta", "resultado"} <= t.keys() for t in registro["tentativas"])

                if "grupo" in exigencia:
                    assert exigencia["grupo"] == grupos[exigencia["fonte"]]
                if "motivo" in exigencia:
                    assert exigencia["situacao"] != "atende" and 0 < len(exigencia["motivo"]) <= 120
                if "acao" in exigencia:
                    acao = exigencia["acao"]
                    assert acao["o_que"] and acao["quem"]
                    assert acao["ate"] == "" or date.fromisoformat(acao["ate"]).isoformat() == acao["ate"]
        if "pesquisa_incompleta" in exemplo:
            assert isinstance(exemplo["pesquisa_incompleta"], list)
            aliases = set()
            for alerta in exemplo["pesquisa_incompleta"]:
                assert alerta["empresa"] in EMPRESAS and alerta["empresa"] not in aliases
                aliases.add(alerta["empresa"])
                assert alerta["motivo"]
            assert {linha["empresa"] for linha in linhas.values() if linha["estado"] == "falha"} <= aliases


def _validar_portal_sessao(portal_sessao):
    if portal_sessao is None:
        return
    assert isinstance(portal_sessao, dict)
    assert set(portal_sessao) == {"nome", "url", "id_no_portal", "fonte"}
    assert isinstance(portal_sessao["nome"], str) and portal_sessao["nome"].strip()
    url = portal_sessao["url"]
    assert url is None or (isinstance(url, str) and url.startswith(("http://", "https://")))
    id_no_portal = portal_sessao["id_no_portal"]
    assert id_no_portal is None or (isinstance(id_no_portal, str) and id_no_portal.strip())
    assert isinstance(portal_sessao["fonte"], str) and portal_sessao["fonte"].strip()


def test_contrato_portal_sessao_edital():
    skill = (SKILLS / "analisar-edital/SKILL.md").read_text(encoding="utf-8")
    for termo in (
        "portal_sessao",
        "Compras.gov.br",
        "SISLOG",
        "BLL",
        "Licitações-e",
        "usuarioNome",
        "numeroCompra",
    ):
        assert termo in skill
    assert "acompanhamento-compra?compra=" not in skill

    card_6623_sislog = {
        "nome": "SISLOG",
        "url": "https://sislog.go.gov.br/",
        "id_no_portal": "124137",
        "fonte": "Edital 2.3; Aviso PNCP/DJE",
    }
    _validar_portal_sessao(card_6623_sislog)

    # Edital sem portal no texto: resolvido pelos metadados do PNCP (usuarioNome + numeroCompra)
    pncp_sem_portal_no_edital = {
        "nome": "SISLOG",
        "url": "https://sislog.go.gov.br/",
        "id_no_portal": "124137",
        "fonte": "PNCP",
    }
    _validar_portal_sessao(pncp_sem_portal_no_edital)

    pncp_url_nula = {
        "nome": "Compras.gov.br",
        "url": None,
        "id_no_portal": "90012/2026",
        "fonte": "PNCP",
    }
    _validar_portal_sessao(pncp_url_nula)
    _validar_portal_sessao(None)

    with pytest.raises(AssertionError):
        _validar_portal_sessao({
            "nome": "SISLOG",
            "url": "javascript:alert(1)",
            "id_no_portal": "124137",
            "fonte": "Edital 2.3",
        })


def _validar_vigencia(vigencia):
    if vigencia is None:
        return
    assert isinstance(vigencia, dict)
    obrigatorios = {"tipo", "meses", "prorrogavel_ate_meses", "conta_a_partir_de", "texto", "fonte"}
    opcionais = {"mecanismo_correcao", "indice", "data_base_orcamento"}
    assert obrigatorios <= set(vigencia) <= (obrigatorios | opcionais)
    assert vigencia["tipo"] in {"contrato", "ata"}
    for campo_int in ("meses", "prorrogavel_ate_meses"):
        valor = vigencia[campo_int]
        assert valor is None or (type(valor) is int and valor > 0)
    conta = vigencia["conta_a_partir_de"]
    assert conta is None or isinstance(conta, str)
    assert isinstance(vigencia["texto"], str) and vigencia["texto"].strip()
    assert isinstance(vigencia["fonte"], str) and vigencia["fonte"].strip()
    if "mecanismo_correcao" in vigencia:
        assert vigencia["mecanismo_correcao"] in {"reajuste_indice", "repactuacao", "ambos", "omisso", "vedado", None}
    for campo_texto_opt in ("indice", "data_base_orcamento"):
        if campo_texto_opt in vigencia:
            valor = vigencia[campo_texto_opt]
            assert valor is None or (isinstance(valor, str) and valor.strip())


def test_contrato_vigencia_edital():
    skill = (SKILLS / "analisar-edital/SKILL.md").read_text(encoding="utf-8")
    for termo in (
        "vigencia",
        "prorrogavel_ate_meses",
        "conta_a_partir_de",
        "minuta de contrato",
        "mecanismo_correcao",
        "indice",
        "data_base_orcamento",
    ):
        assert termo in skill

    _validar_vigencia({
        "tipo": "contrato",
        "meses": 12,
        "prorrogavel_ate_meses": 60,
        "conta_a_partir_de": "assinatura",
        "texto": "Vigência de 12 meses contados da assinatura, prorrogável até 60 meses.",
        "fonte": "TR 5.1 (p. 14)",
        "mecanismo_correcao": "reajuste_indice",
        "indice": "IPCA",
        "data_base_orcamento": "2026-10-15",
    })
    _validar_vigencia({
        "tipo": "ata",
        "meses": 12,
        "prorrogavel_ate_meses": 24,
        "conta_a_partir_de": "publicação do extrato",
        "texto": "Ata válida por 1 ano, prorrogável por igual período.",
        "fonte": "Edital 12.1 (p. 19)",
        "mecanismo_correcao": "omisso",
        "indice": None,
        "data_base_orcamento": None,
    })
    _validar_vigencia({
        "tipo": "contrato",
        "meses": None,
        "prorrogavel_ate_meses": None,
        "conta_a_partir_de": "ordem de serviço",
        "texto": "Prazo de execução e vigência de 150 dias corridos a partir da ordem de serviço.",
        "fonte": "Minuta de Contrato 3.1 (p. 42)",
    })
    _validar_vigencia(None)

    with pytest.raises(AssertionError):
        _validar_vigencia({
            "tipo": "outro",
            "meses": 12,
            "prorrogavel_ate_meses": None,
            "conta_a_partir_de": "assinatura",
            "texto": "12 meses",
            "fonte": "TR 5.1",
        })
    with pytest.raises(AssertionError):
        _validar_vigencia({
            "tipo": "contrato",
            "meses": "12",
            "prorrogavel_ate_meses": None,
            "conta_a_partir_de": "assinatura",
            "texto": "12 meses",
            "fonte": "TR 5.1",
        })
    with pytest.raises(AssertionError):
        _validar_vigencia({
            "tipo": "contrato",
            "meses": 12,
            "prorrogavel_ate_meses": None,
            "conta_a_partir_de": "assinatura",
            "texto": "12 meses",
            "fonte": "TR 5.1",
            "mecanismo_correcao": "livre",
        })


def _validar_vigencia_precificacao(vp):
    if vp is None:
        return
    assert isinstance(vp, dict)
    chaves = {
        "meses_iniciais",
        "prorrogavel_ate_meses",
        "mecanismo",
        "indice_ou_cct",
        "data_base",
        "clausula",
        "defasagem_reais",
        "defasagem_pp",
        "base_fechamento",
        "recomendacao",
    }
    assert set(vp) == chaves
    for campo_int in ("meses_iniciais", "prorrogavel_ate_meses"):
        valor = vp[campo_int]
        assert valor is None or (type(valor) is int and valor > 0)
    assert vp["mecanismo"] in {"reajuste_indice", "repactuacao", "ambos", "omisso", "vedado", None}
    for campo_num in ("defasagem_reais", "defasagem_pp"):
        valor = vp[campo_num]
        assert valor is None or (isinstance(valor, (int, float)) and type(valor) is not bool)
    for campo_str in ("indice_ou_cct", "data_base", "clausula", "base_fechamento", "recomendacao"):
        valor = vp[campo_str]
        assert valor is None or isinstance(valor, str)


def test_contrato_vigencia_precificacao():
    skill = (SKILLS / "precificar-proposta-exequibilidade/SKILL.md").read_text(encoding="utf-8")
    for termo in (
        "vigencia_precificacao",
        "art. 107",
        "art. 106",
        "art. 135",
        "art. 84",
        "Decreto 11.462/2023",
        "premissas.vigencia_meses",
        "proposta.reajuste",
    ):
        assert termo in skill

    _validar_vigencia_precificacao({
        "meses_iniciais": 30,
        "prorrogavel_ate_meses": 60,
        "mecanismo": "repactuacao",
        "indice_ou_cct": "CCT + IPCA",
        "data_base": "2026-05-01",
        "clausula": "Minuta 7.2 (p. 38)",
        "defasagem_reais": 4200.5,
        "defasagem_pp": 1.35,
        "base_fechamento": "vigência inicial de 30 meses",
        "recomendacao": "Incluir defasagem na vigência inicial; não embutir prorrogação.",
    })
    _validar_vigencia_precificacao(None)

    with pytest.raises(AssertionError):
        _validar_vigencia_precificacao({
            "meses_iniciais": 12,
            "prorrogavel_ate_meses": 60,
            "mecanismo": "invalido",
            "indice_ou_cct": "IPCA",
            "data_base": "2026-10-15",
            "clausula": "TR 5.1",
            "defasagem_reais": 0.0,
            "defasagem_pp": 0.0,
            "base_fechamento": "12 meses",
            "recomendacao": "ok",
        })
