import json
import runpy
from datetime import date
from pathlib import Path

import pytest

SCORE = runpy.run_path(str(
    Path(__file__).resolve().parents[1] / "agentes/analisador-edital/skills/score/scripts/score.py"
))


def calcular(tmp_path, **arquivos):
    analise = tmp_path / "analise"
    analise.mkdir(parents=True)
    for nome, dados in arquivos.items():
        (analise / f"{nome}.json").write_text(json.dumps(dados), encoding="utf-8")
    return SCORE["calcular"](tmp_path, SCORE["PADRAO"], hoje=date(2026, 10, 15))


@pytest.mark.parametrize(("tecnica", "preco"), [(True, False), (False, True), (True, True)])
def test_premissa_decisiva_nao_e_trava(tmp_path, tecnica, preco):
    result = calcular(
        tmp_path,
        tecnica={"conclusao": {"viavel": "nao" if tecnica else "sim"}, "premissa_decisiva": tecnica},
        precificacao={"exequivel": "nao" if preco else "sim", "margem_pct": -16.1 if preco else 3.6,
                      "premissa_decisiva": preco},
    )
    assert result["trava"] is None and result["nota"] != 1
    assert any("premissa decisiva" in aviso for aviso in result["avisos"])


def test_preco_inexequivel_documentado_mantem_trava(tmp_path):
    result = calcular(
        tmp_path, tecnica={"conclusao": {"viavel": "sim"}, "premissa_decisiva": True},
        precificacao={"exequivel": "nao", "margem_pct": -16.1},
    )
    assert result["nota"] == 1
    assert [t["fonte"] for t in result["trava"]] == ["precificacao.json"]


def test_cenario_alternativo_nao_substitui_base(tmp_path):
    result = calcular(tmp_path, precificacao={
        "exequivel": "no_limite", "margem_pct": 3.6, "premissa_decisiva": False,
        "cenarios": [{"nome": "Alternativo (P)", "exequivel": "nao", "margem_pct": -16.1}],
    })
    assert result["trava"] is None and result["nota"] != 1
    assert "3,6" in result["termos"][-1]["motivo"]


def test_score_exibe_percentuais_usados_e_aplica_minima_da_precificacao(tmp_path):
    result = calcular(tmp_path, precificacao={
        "tributos_pct": 19.29, "margem_pct": 4.82, "margem_minima_pct": 4.0,
    })
    assert result["termos"][-1]["pontos"] == 40
    assert result["hipotese_precificacao"] == "tributos 19,29%, margem mínima 4%, margem calculada 4,82%"


def test_saida_antiga_deriva_tributos_do_componente_mensal(tmp_path):
    result = calcular(tmp_path, precificacao={
        "preco_mensal": 38633.33, "margem_pct": 4.82,
        "componentes": [{"componente": "tributos", "valor_mensal": 7452.37}],
    })
    assert result["hipotese_precificacao"] == "tributos 19,29%, hipótese: margem mínima 10%, margem calculada 4,82%"


def test_score_preserva_aliquota_zero_e_coloca_fallback_como_hipotese(tmp_path):
    result = calcular(tmp_path, precificacao={"tributos_pct": 0, "margem_minima_pct": True})
    assert result["hipotese_precificacao"] == "tributos 0%, hipótese: margem mínima 10%"


def test_score_sinaliza_tributos_pendente_com_motivo_e_padrao(tmp_path):
    com_motivo = calcular(tmp_path / "m1", precificacao={
        "tributos_pct": 12.68,
        "margem_pct": 8.5,
        "tributos_pendente": True,
        "tributos_pendente_motivo": "Alíquota da AForça baseada em apenas 1 NF; confirmar com contabilidade",
    })
    assert "Alíquota da AForça baseada em apenas 1 NF; confirmar com contabilidade" in com_motivo["avisos"]
    assert "alíquota pendente" in com_motivo["hipotese_precificacao"]

    sem_motivo = calcular(tmp_path / "m2", precificacao={
        "margem_pct": 8.5,
        "tributos_pendente": True,
    })
    assert "Alíquota tributária pendente de confirmação contábil" in sem_motivo["avisos"]
    assert "alíquota pendente" in sem_motivo["hipotese_precificacao"]


def test_score_nao_sinaliza_tributos_pendente_quando_falso_ou_ausente(tmp_path):
    falso = calcular(tmp_path / "f1", precificacao={
        "tributos_pct": 19.29,
        "margem_pct": 12.0,
        "tributos_pendente": False,
    })
    assert not any("pendente" in a.lower() for a in falso["avisos"])
    assert "alíquota pendente" not in falso["hipotese_precificacao"]

    ausente = calcular(tmp_path / "f2", precificacao={
        "tributos_pct": 19.29,
        "margem_pct": 12.0,
    })
    assert not any("pendente" in a.lower() for a in ausente["avisos"])
    assert "alíquota pendente" not in ausente["hipotese_precificacao"]
