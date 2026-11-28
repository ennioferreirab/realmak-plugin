"""Campos da disposição v2 do card: validação determinística, montagem e preservação de depende_lance."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SKILLS = RAIZ / "plugins/realmak/skills"
EXEMPLO = RAIZ / "agentes/analisador-edital/referencias/card/exemplo/analise"


def _carregar(caminho: Path):
    spec = importlib.util.spec_from_file_location(caminho.stem, caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vc = _carregar(SKILLS / "analisar-edital/scripts/validar_card.py")


def edital_base() -> dict:
    return {
        "convocacao": {"modo": "separada", "fonte": "Edital 8.1 e 10.1/10.3"},
        "habilitacao": [{"id": "hab-001", "rotulo": "CAO"}],
        "atencao": [
            {"titulo": "RT assina", "situacao": "aberto", "destino": {"tipo": "exigencia", "ref": "hab-001"}},
            {
                "titulo": "CAO",
                "situacao": "resolvido",
                "resolucao": "Atende: CAO de 1.140 TR",
                "destino": {"tipo": "etapa", "ref": "contrato"},
            },
        ],
        "prazos": [
            {"prazo": "Sessão pública", "data": "2026-11-30T10:00", "grupo": "sessao"},
            {"prazo": "Proposta ajustada", "data": "", "grupo": "sessao", "momento": "quando o pregoeiro pedir"},
        ],
    }


def test_exemplo_do_contrato_passa():
    assert vc.validar_edital(json.loads((EXEMPLO / "edital.json").read_text(encoding="utf-8"))) == []
    assert vc.validar_habilitacao(json.loads((EXEMPLO / "habilitacao.json").read_text(encoding="utf-8"))) == []


def test_analise_antiga_sem_campos_novos_passa():
    antigo = {"atencao": [{"titulo": "x", "ponto": "y", "gravidade": "alta"}], "prazos": [{"prazo": "Sessão", "data": "2026-11-30"}]}
    assert vc.validar_edital(antigo) == []
    assert vc.validar_habilitacao({"empresas": [{"exigencias": [{"exigencia": "Certidão"}]}]}) == []


def test_edital_valido():
    assert vc.validar_edital(edital_base()) == []


@pytest.mark.parametrize(
    ("mutacao", "trecho"),
    [
        (lambda e: e["convocacao"].update(modo="junto"), "convocacao.modo"),
        (lambda e: e["convocacao"].update(fonte=""), "convocacao.fonte"),
        (lambda e: e["atencao"][0].update(situacao="feito"), "situacao"),
        (lambda e: e["atencao"][1].pop("resolucao"), "resolucao obrigatória"),
        (lambda e: e["atencao"][1].pop("destino"), "destino obrigatório"),
        (lambda e: e["atencao"][1].update(resolucao="x" * 161), "160"),
        (lambda e: e["atencao"][0]["destino"].update(tipo="tela"), "destino.tipo"),
        (lambda e: e["atencao"][0]["destino"].update(ref=""), "destino.ref obrigatório"),
        (lambda e: e["atencao"][0]["destino"].update(ref="hab-999"), "não existe"),
        (lambda e: e["atencao"][1]["destino"].update(ref="execucao"), "de etapa"),
        (lambda e: e["prazos"][1].update(prazo="Proposta em até 2 horas"), "micro-prazo"),
        (lambda e: e["prazos"][1].update(data="até 2h após a convocação"), "micro-prazo"),
        (lambda e: e["prazos"][1].update(momento="em 30 minutos"), "micro-prazo"),
    ],
)
def test_edital_invalido(mutacao, trecho):
    edital = copy.deepcopy(edital_base())
    mutacao(edital)
    assert any(trecho in erro for erro in vc.validar_edital(edital))


def test_destino_sem_precificacao_ou_edital_aceita_ref_vazio():
    edital = edital_base()
    edital["atencao"][0]["destino"] = {"tipo": "precificacao", "ref": ""}
    edital["atencao"][1]["destino"] = {"tipo": "edital", "ref": ""}
    assert vc.validar_edital(edital) == []


def test_observacao_pode_citar_prazo_em_horas():
    edital = edital_base()
    edital["prazos"][1]["observacao"] = "Edital 8.1 dá 2 horas depois da convocação"
    assert vc.validar_edital(edital) == []


ROTULOS_LANCE = [
    "Proposta ajustada ao lance final (Anexo II)",
    "Planilha de composição de custos",
    "Proposta de preços",
    "Anexo de preços unitários",
    "Proposta assinada, ajustada ao último lance, com todas as informações do modelo do Anexo II do TR.",
    "Planilha de composição de preços em anexo à proposta, com todos os custos dos serviços do TR.",
]
ROTULOS_SEM_LANCE = [
    "Descrição detalhada dos serviços",
    "Declaração de critérios de sustentabilidade",
    "Comprovante do regime de tributação",
    "Procuração",
    "Especificações detalhadas dos serviços ofertados; repetir o TR sem comprovação pode desclassificar a proposta.",
    "Informar o regime de tributação da empresa na proposta.",
    "Declaração de cumprimento dos critérios de sustentabilidade da cláusula 18 do edital, junto com a proposta ajustada.",
    "Instrumento de mandato com poderes para o ato, só se a proposta for assinada por procurador.",
]


def test_depende_lance_inferido_na_etapa_proposta():
    for rotulo in ROTULOS_LANCE:
        assert vc.depende_do_lance({"exigencia": rotulo, "etapa_envio": "proposta"}), rotulo
        assert not vc.depende_do_lance({"exigencia": rotulo, "etapa_envio": "habilitacao"}), rotulo
    for rotulo in ROTULOS_SEM_LANCE:
        assert not vc.depende_do_lance({"exigencia": rotulo, "etapa_envio": "proposta"}), rotulo


def test_habilitacao_exige_depende_lance_nos_itens_com_preco():
    hab = {
        "empresas": [
            {
                "exigencias": [
                    {"exigencia": "Proposta ajustada ao lance final", "etapa_envio": "proposta"},
                    {"exigencia": "Planilha de composição de custos", "etapa_envio": "proposta", "depende_lance": True},
                    {"exigencia": "Certidão de falência", "etapa_envio": "habilitacao", "depende_lance": "sim"},
                ]
            }
        ]
    }
    erros = vc.validar_habilitacao(hab)
    assert len(erros) == 2
    assert any("marque depende_lance" in e for e in erros) and any("booleano" in e for e in erros)


def test_indice_ok_nao_pode_depender_do_lance():
    indice = {"itens": [{"exigencia": "Proposta ajustada", "etapa_envio": "proposta", "depende_lance": True, "situacao": "OK"}]}
    assert any("não pode estar OK" in e for e in vc.validar_indice(indice))
    indice["itens"][0]["situacao"] = "PENDENTE"
    assert vc.validar_indice(indice) == []


def test_cli_valida_pasta(tmp_path):
    analise = tmp_path / "agents/analisador-edital/analise"
    analise.mkdir(parents=True)
    (analise / "edital.json").write_text(json.dumps(edital_base()), encoding="utf-8")
    montagem = tmp_path / "agents/analisador-edital/../montagem-proposta"
    montagem.mkdir(parents=True)
    script = str(SKILLS / "analisar-edital/scripts/validar_card.py")
    ok = subprocess.run([sys.executable, script, str(analise)], capture_output=True, text=True)
    assert ok.returncode == 0 and "edital.json: OK" in ok.stdout
    ruim = edital_base()
    ruim["convocacao"]["modo"] = "x"
    (analise / "edital.json").write_text(json.dumps(ruim), encoding="utf-8")
    falha = subprocess.run([sys.executable, script, str(analise)], capture_output=True, text=True)
    assert falha.returncode == 1 and "convocacao.modo" in falha.stdout


# ---- montagem do pacote ----

def _montar(tmp_path, itens):
    pytest.importorskip("pypdf")
    mp = _carregar(SKILLS / "montar-documentacao-disputa/scripts/montar_pacote.py")
    indice = tmp_path / "indice.json"
    mp.montar({"saida": str(tmp_path / "saida"), "indice_json": str(indice), "itens": itens})
    return {i["exigencia"]: i for i in json.loads(indice.read_text(encoding="utf-8"))["itens"]}


def test_montagem_preserva_e_infere_depende_lance(tmp_path):
    itens = [
        {"etapa_envio": "proposta", "ordem_edital": 1, "exigencia": "Proposta ajustada ao lance final", "status": "ok"},
        {"etapa_envio": "proposta", "ordem_edital": 2, "exigencia": "Anexo sem rótulo de preço", "depende_lance": True, "status": "ok"},
        {"etapa_envio": "proposta", "ordem_edital": 3, "exigencia": "Descrição detalhada dos serviços", "status": "ok"},
        {"etapa_envio": "habilitacao", "ordem_edital": 1, "exigencia": "Certidão de falência", "status": "ok"},
    ]
    indice = _montar(tmp_path, itens)
    assert indice["Proposta ajustada ao lance final"]["depende_lance"] is True
    assert indice["Anexo sem rótulo de preço"]["depende_lance"] is True
    assert "depende_lance" not in indice["Descrição detalhada dos serviços"]
    assert "depende_lance" not in indice["Certidão de falência"]
    assert indice["Descrição detalhada dos serviços"]["situacao"] == "OK"
    assert indice["Certidão de falência"]["situacao"] == "OK"


def test_depende_lance_so_fica_ok_com_lance_informado(tmp_path):
    base = {"etapa_envio": "proposta", "ordem_edital": 1, "status": "ok"}
    indice = _montar(
        tmp_path,
        [
            {**base, "exigencia": "Proposta ajustada ao lance final"},
            {**base, "ordem_edital": 2, "exigencia": "Planilha de composição de custos", "lance_informado": True},
        ],
    )
    pendente = indice["Proposta ajustada ao lance final"]
    assert pendente["situacao"] == "PENDENTE"
    assert pendente["motivo"] == "Gerada com o preço de referência; refazer com o lance final"
    assert indice["Planilha de composição de custos"]["situacao"] == "OK"
    assert vc.validar_indice({"itens": list(indice.values())}) == []


def test_montagem_e_validador_inferem_igual():
    pytest.importorskip("pypdf")
    mp = _carregar(SKILLS / "montar-documentacao-disputa/scripts/montar_pacote.py")
    for etapa in ("sessao", "proposta", "habilitacao"):
        for rotulo in ROTULOS_LANCE + ROTULOS_SEM_LANCE + ["Proposta inicial (preço de referência)"]:
            assert mp.depende_do_lance({"exigencia": rotulo}, etapa) == vc.depende_do_lance(
                {"exigencia": rotulo, "etapa_envio": etapa}
            ), (etapa, rotulo)


# ---- textos do contrato e das skills ----

def test_contrato_e_skills_citam_os_campos_novos():
    contrato = (RAIZ / "agentes/analisador-edital/referencias/card/CONTRATO.md").read_text(encoding="utf-8")
    for termo in ("convocacao", "depende_lance", "resolucao", "destino", "Contrato e execução", "Sem micro-prazos"):
        assert termo in contrato, termo
    assert "Até 2 h após a convocação" not in contrato
    for skill in ("analisar-edital", "analisar-habilitacao", "montar-documentacao-disputa"):
        texto = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "Até 2 h após a convocação" not in texto, skill
    edital = (SKILLS / "analisar-edital/SKILL.md").read_text(encoding="utf-8")
    assert "convocacao" in edital and "resolucao" in edital and "validar_card.py" in edital
    assert "depende_lance" in (SKILLS / "analisar-habilitacao/SKILL.md").read_text(encoding="utf-8")
    assert "depende_lance" in (SKILLS / "montar-documentacao-disputa/SKILL.md").read_text(encoding="utf-8")
    conferir = (RAIZ / "agentes/analisador-edital/skills/conferir-habilitacao/SKILL.md").read_text(encoding="utf-8")
    assert "depende_lance" in conferir and "validar_card.py" in conferir
    assert "depende_lance" in (RAIZ / "agentes/montagem-proposta/AGENTS.md").read_text(encoding="utf-8")
