import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1] / "plugins/realmak/skills/precificar-proposta-exequibilidade"
SCRIPT = SKILL / "scripts/aplicar_pedido.py"

sys.path.insert(0, str(SKILL / "scripts"))
import aplicar_pedido as ap  # noqa: E402


def atual():
    # Dados fictícios: estimado 169.000/mês em 60 meses; custo 100.000; tributos 15%.
    return {
        "versao": 1, "empresa_precificada": "realmak", "valor_estimado": 10_140_000.0,
        "custo_mensal": 100_000.0, "preco_mensal": 130_000.0, "preco_global": 7_800_000.0, "bdi_pct": 30.0,
        "margem_pct": 0.0, "tributos_pct": 15.0, "margem_minima_pct": 10.0, "exequivel": "sim", "resumo": "antigo",
        "vigencia_precificacao": {"meses_iniciais": 60, "recomendacao": "Vale para 60 meses iniciais."},
        "cenarios": [{"nome": "Base", "preco_global": 7_800_000.0, "margem_pct": 0.0, "exequivel": "sim"}],
        "componentes": [
            {"componente": "mao_de_obra", "valor_mensal": 60_000.0, "fonte": "base"},
            {"componente": "operacao", "valor_mensal": 20_000.0, "fonte": "base"},
            {"componente": "pecas", "valor_mensal": 20_000.0, "fonte": "base"},
            {"componente": "tributos", "valor_mensal": 19_500.0, "fonte": "15%"},
            {"componente": "margem", "valor_mensal": -8_500.0, "fonte": ""},
        ],
    }


def pedido(**extra):
    return {"atualizar_planilha": False, "gerar_proposta": False, "buscar_cotacoes": False,
            "pedido_por": 7, "pedido_em": "2026-11-28T10:00:00", **extra}


def margem(preco, custo, trib):
    return (preco * (1 - trib) - custo) / preco * 100


def cenario(res, origem):
    return next(c for c in res["cenarios"] if c.get("origem") == origem)


def test_desconto_sobre_valor_estimado():
    res = ap.calcular(atual(), pedido(modo="desconto", desconto_pct=8))
    assert res["preco_global"] == pytest.approx(9_328_800.0)  # 169.000 x 0,92 x 60
    assert res["preco_mensal"] == pytest.approx(155_480.0)
    assert res["margem_pct"] == pytest.approx(margem(155_480, 100_000, 0.15), abs=0.01)
    assert res["exequivel"] == "sim"
    assert cenario(res, "pedido")["preco_global"] == pytest.approx(9_328_800.0)


def test_preco_informado_e_preco_anterior_vira_cenario():
    base = atual()
    base["valor_estimado"] = 9_000_000.0  # 75% = 6,75 mi: o preço do pedido fica acima do limite
    res = ap.calcular(base, pedido(modo="preco", preco_mensal=120_000))
    assert res["preco_mensal"] == 120_000 and res["preco_global"] == 7_200_000
    assert res["margem_pct"] == pytest.approx(margem(120_000, 100_000, 0.15), abs=0.01)  # 2%
    ant = cenario(res, "anterior")
    assert ant["nome"] == "Preço-alvo anterior" and ant["preco_mensal"] == 130_000
    assert res["preco_anterior"]["preco_global"] == 7_800_000
    assert res["pedido"]["modo"] == "preco"
    assert res["exequivel"] == "no_limite"  # margem 2% < mínima 10%
    assert any("abaixo da mínima" in a for a in res["avisos_pedido"])


def test_margem_fecha_a_formula_da_margem():
    res = ap.calcular(atual(), pedido(modo="margem", margem_pct=20))
    assert res["preco_mensal"] == pytest.approx(100_000 / (1 - 0.15 - 0.20), abs=0.01)
    assert res["margem_pct"] == pytest.approx(20.0, abs=0.01)
    assert res["exequivel"] == "sim"
    comp = {c["componente"]: c["valor_mensal"] for c in res["componentes"]}
    assert comp["tributos"] == pytest.approx(res["preco_mensal"] * 0.15, abs=0.01)
    assert comp["margem"] == pytest.approx(res["preco_mensal"] * 0.85 - 100_000, abs=0.01)


def test_premissas_recalcula_custo_e_acha_preco_pela_margem():
    res = ap.calcular(atual(), pedido(modo="premissas", premissas={
        "folha_pct": 10, "pecas_fator": 1.5, "tributos_pct": 12, "margem_pct": 15}))
    custo = 100_000 + 6_000 + 10_000
    assert res["custo_mensal"] == pytest.approx(custo)
    assert res["preco_mensal"] == pytest.approx(custo / (1 - 0.12 - 0.15), abs=0.01)
    assert res["margem_pct"] == pytest.approx(15.0, abs=0.01)
    assert res["tributos_pct"] == 12.0
    comp = {c["componente"]: c["valor_mensal"] for c in res["componentes"]}
    assert comp["mao_de_obra"] == 66_000 and comp["pecas"] == 30_000
    # o preço anterior é reavaliado com o custo e os tributos novos
    ant = cenario(res, "anterior")
    assert ant["margem_pct"] == pytest.approx(margem(130_000, custo, 0.12), abs=0.01)


def test_premissas_parciais_mantem_o_resto():
    res = ap.calcular(atual(), pedido(modo="premissas", premissas={"tributos_pct": 10}))
    assert res["custo_mensal"] == 100_000
    # sem margem informada, mantém a margem atual (0%)
    assert res["preco_mensal"] == pytest.approx(100_000 / 0.90, abs=0.01)


def test_inexequivel_nao_e_escondido_pelo_limite_de_75_por_cento():
    # 8,4 milhões em 60 meses ainda fecha margem positiva, mas está abaixo de 75% de 10,14 milhões (7,605 mi)
    res = ap.calcular(atual(), pedido(modo="preco", preco_mensal=120_000))
    assert res["preco_global"] < 10_140_000 * 0.75
    assert res["exequivel"] == "nao"
    assert any("75%" in a for a in res["avisos_pedido"])
    neg = ap.calcular(atual(), pedido(modo="preco", preco_mensal=100_000))
    assert neg["margem_pct"] < 0 and neg["exequivel"] == "nao"


def test_cenarios_sensibilidade_e_resumo_sao_refeitos():
    res = ap.calcular(atual(), pedido(modo="desconto", desconto_pct=8, recado="priorizar margem"))
    nomes = [c["nome"] for c in res["cenarios"]]
    assert nomes[0].startswith("Pedido:") and "Preço-alvo anterior" in nomes and "Base" not in nomes
    rot = {s["rotulo"]: s["margem_pct"] for s in res["sensibilidade"]}
    assert rot["Mão de obra +10%"] == pytest.approx(margem(155_480, 106_000, 0.15), abs=0.01)
    assert rot["Tributos +1 p.p."] == pytest.approx(margem(155_480, 100_000, 0.16), abs=0.01)
    assert res["piso_sugerido"] == pytest.approx(100_000 / (1 - 0.15 - 0.10), abs=0.01)
    assert "priorizar margem" in res["resumo"] and "60 meses" in res["resumo"]
    assert res["bdi_pct"] == pytest.approx((155_480 / 100_000 - 1) * 100, abs=0.01)


def test_entrada_original_nao_e_alterada():
    a = atual()
    ap.calcular(a, pedido(modo="margem", margem_pct=20))
    assert a == atual()


@pytest.mark.parametrize("ped", [
    {"modo": "desconto"}, {"modo": "desconto", "desconto_pct": 100}, {"modo": "preco", "preco_mensal": 0},
    {"modo": "margem", "margem_pct": 90}, {"modo": "premissas", "premissas": {}}, {"modo": "outro"},
    {"modo": "premissas", "premissas": {"folha_pct": -100}},
])
def test_pedido_invalido_e_recusado(ped):
    with pytest.raises(ap.PedidoInvalido):
        ap.calcular(atual(), pedido(**ped))


def test_precificacao_sem_base_e_recusada():
    sem = atual()
    sem["custo_mensal"] = None
    with pytest.raises(ap.PedidoInvalido):
        ap.calcular(sem, pedido(modo="margem", margem_pct=20))
    sem = atual()
    sem["valor_estimado"] = None
    with pytest.raises(ap.PedidoInvalido):
        ap.calcular(sem, pedido(modo="desconto", desconto_pct=5))


def test_dados_da_planilha_acompanham_o_pedido():
    ped = pedido(modo="premissas", premissas={"folha_pct": 10, "pecas_fator": 2, "tributos_pct": 12, "margem_pct": 15})
    res = ap.calcular(atual(), ped)
    dados = {"premissas": {"vigencia_meses": 60, "tributos": {"valor": 0.15, "fonte": "x"}},
             "mao_de_obra": [["Técnico", 1, 4000, 0.65, 500, "obs"]],
             "pecas": [["Kit", 4, 100, "Incluído", 1, "7 dias"]], "operacao": {"pecas": {"mensal": 1000, "fonte": "p"}}}
    novo = ap.ajustar_dados_planilha(dados, ped, res)
    assert novo["premissas"]["preco_mensal"]["valor"] == res["preco_mensal"]
    assert novo["premissas"]["tributos"]["valor"] == 0.12
    assert novo["mao_de_obra"][0][2] == 4400 and novo["mao_de_obra"][0][4] == 550 and novo["mao_de_obra"][0][3] == 0.65
    assert novo["pecas"][0][2] == 200 and novo["operacao"]["pecas"]["mensal"] == 2000
    assert dados["mao_de_obra"][0][2] == 4000


def test_linha_de_comando(tmp_path):
    (tmp_path / "p.json").write_text(json.dumps(atual()), encoding="utf-8")
    (tmp_path / "ped.json").write_text(json.dumps(pedido(modo="desconto", desconto_pct=8)), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "p.json"), str(tmp_path / "ped.json"),
                           str(tmp_path / "s.json")], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    saida = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert saida["preco_global"] == pytest.approx(9_328_800.0)
    (tmp_path / "ruim.json").write_text(json.dumps({"modo": "x"}), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "p.json"), str(tmp_path / "ruim.json"),
                           str(tmp_path / "n.json")], capture_output=True, text=True)
    assert proc.returncode == 2 and "modo" in proc.stderr and not (tmp_path / "n.json").exists()


def test_skill_agente_e_contrato_citam_o_pedido():
    raiz = SKILL.parents[3]
    assert "fontes/pedido_precificacao.json" in (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "scripts/aplicar_pedido.py" in (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "pedido_precificacao.json" in (raiz / "agentes/analisador-edital/AGENTS.md").read_text(encoding="utf-8")
    contrato = (raiz / "agentes/analisador-edital/referencias/card/CONTRATO.md").read_text(encoding="utf-8")
    assert "### Pedido de precificação" in contrato and '"anterior"' in contrato


def test_cenarios_de_risco_anteriores_sao_reavaliados_no_preco_do_pedido():
    base = atual()
    custo_risco = 123_500.0  # conservador: custo de hoje + 23,5%
    base["cenarios"] = [
        {"nome": "Base, preço-alvo", "preco_global": 7_800_000.0, "margem_pct": margem(130_000, 100_000, 0.15), "exequivel": "sim"},
        {"nome": "Conservador, no preço-alvo", "preco_global": 7_800_000.0, "margem_pct": margem(130_000, custo_risco, 0.15), "exequivel": "nao"},
        {"nome": "Conservador, no teto", "preco_global": 10_140_000.0, "margem_pct": margem(169_000, custo_risco, 0.15), "exequivel": "nao"},
    ]
    res = ap.calcular(base, pedido(modo="desconto", desconto_pct=8))
    risco = [c for c in res["cenarios"] if c["nome"] == "Conservador, no preço do pedido"]
    assert len(risco) == 1  # o duplicado e o de custo igual ao de hoje não entram
    assert risco[0]["margem_pct"] == pytest.approx(margem(155_480, custo_risco, 0.15), abs=0.01)
    assert risco[0]["origem"] == "ia"
    assert all(c["nome"] != "Base, preço-alvo" for c in res["cenarios"])
