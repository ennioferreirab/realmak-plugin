"""Testes do gerar_proposta.py (etapa "proposta"): valores, extenso, desconto D, alertas e ordem das etapas."""

from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "plugins/realmak/skills/montar-documentacao-disputa/scripts"


def _carregar(nome: str):
    spec = importlib.util.spec_from_file_location(nome, PASTA / f"{nome}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gp = _carregar("gerar_proposta")


def entrada(**proposta):
    base = {
        "preco_mensal": 159351.29,
        "meses": 60,
        "teto_mensal": 169000,
        "itens_fixos": [{"descricao": "Sob demanda", "anual": 100000}, {"descricao": "Peças", "anual": 200000}],
        "validade_dias": 90,
        "validade_minima_dias": 90,
        "regime_tributario": "Simples Nacional",
    }
    base.update(proposta)
    return {"empresa": {"banco": "BB", "agencia": "1", "conta": "2"}, "proposta": base}


@pytest.mark.parametrize(
    ("valor", "texto"),
    [
        (11061077.40, "onze milhões, sessenta e um mil e setenta e sete reais e quarenta centavos"),
        (1500000, "um milhão e quinhentos mil reais"),
        (2000000, "dois milhões de reais"),
        (1001, "mil e um reais"),
        (0.5, "cinquenta centavos"),
    ],
)
def test_extenso(valor, texto):
    assert gp.extenso(valor) == texto


def test_totais_e_desconto_d():
    c = gp.calcular(entrada())
    assert c["ok"] and not c["alertas"]
    assert c["subtotal1"] == Decimal("9561077.40")
    assert c["subtotal2"] == Decimal("1500000.00")
    assert c["total"] == Decimal("11061077.40")
    assert c["total_orcado"] == Decimal("11640000.00")
    assert round(c["desconto_d"], 2) == Decimal("5.71")
    assert gp.brl(c["total"]) == "R$ 11.061.077,40"


@pytest.mark.parametrize(
    ("ajuste", "trecho"),
    [
        ({"preco_mensal": 170000}, "acima do máximo"),
        ({"preco_mensal": 126000}, "inexequível"),
        ({"validade_dias": 60}, "Validade"),
        ({"regime_tributario": ""}, "Regime de tributação"),
    ],
)
def test_alertas_de_erro_bloqueiam(ajuste, trecho):
    c = gp.calcular(entrada(**ajuste))
    assert not c["ok"]
    assert any(trecho in a["texto"] for a in c["alertas"] if a["nivel"] == "erro")


def test_ordem_das_etapas_no_pacote():
    pytest.importorskip("pypdf")
    mp = _carregar("montar_pacote")
    assert mp.ETAPAS_VALIDAS == ("sessao", "proposta", "habilitacao")
    assert mp._normalizar_etapa("proposta") == "proposta"
    assert mp._normalizar_etapa("outra") == "habilitacao"


@pytest.mark.parametrize("etapa", ["sessao", "proposta", "habilitacao"])
def test_passo_manual_no_portal_nao_vira_item(tmp_path, etapa):
    pytest.importorskip("pypdf")
    mp = _carregar("montar_pacote")
    passos = [
        "Declarações no sistema (Compras.gov.br)",
        "Marcar as declarações do sistema ao cadastrar a proposta inicial",
        "Cadastro da proposta inicial no portal",
        'Enviar anexo pelo botão "Enviar anexo"',
    ]
    itens = [{"etapa_envio": etapa, "exigencia": p, "status": "pendente"} for p in passos]
    itens.append({"etapa_envio": etapa, "exigencia": "Declaração de critérios de sustentabilidade", "status": "pendente"})
    indice = tmp_path / "indice.json"
    resultado = mp.montar({"saida": str(tmp_path / "saida"), "indice_json": str(indice), "itens": itens})
    import json

    exigencias = [i["exigencia"] for i in json.loads(indice.read_text())["itens"]]
    assert exigencias == ["Declaração de critérios de sustentabilidade"]
    assert not any("sistema" in a.lower() for a in resultado.get("avisos", []))
