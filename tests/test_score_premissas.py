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
    analise.mkdir()
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
