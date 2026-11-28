import json
import runpy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

SCORE = runpy.run_path(str(
    Path(__file__).resolve().parents[1] / "agentes/analisador-edital/skills/score/scripts/score.py"
))
BRT = timezone(timedelta(hours=-3))


def calcular(tmp_path, *, hoje=date(2026, 10, 15), agora=None, **arquivos):
    analise = tmp_path / "analise"
    analise.mkdir(parents=True)
    for nome, dados in arquivos.items():
        (analise / f"{nome}.json").write_text(json.dumps(dados), encoding="utf-8")
    return SCORE["calcular"](tmp_path, SCORE["PADRAO"], hoje=hoje if agora is None else None, agora=agora)


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


def test_score_nao_trava_sessao_aberta_hoje_ou_amanha(tmp_path):
    agora = datetime(2026, 11, 25, 13, 0, tzinfo=BRT)
    base = {
        "habilitacao": {"mais_aderente": "realmak", "empresas": [{"empresa": "realmak", "aderencia": "alta", "exigencias": [{}]}]},
        "tecnica": {"conclusao": {"viavel": "sim"}},
        "precificacao": {"exequivel": "sim", "margem_pct": 12.0},
    }
    amanha = calcular(
        tmp_path / "amanha",
        agora=agora,
        edital={"prazos": [{"prazo": "Sessão pública", "data": "2026-11-26T14:00", "fonte": "Edital 1.1"}]},
        **base,
    )
    assert amanha["trava"] is None and amanha["nota"] == 5

    hoje_aberta = calcular(
        tmp_path / "hoje_aberta",
        agora=agora,
        edital={"prazos": [{"prazo": "Sessão pública", "data": "2026-11-25T16:00", "fonte": "Edital 1.1"}]},
        **base,
    )
    assert hoje_aberta["trava"] is None and hoje_aberta["nota"] == 5

    so_data_hoje = calcular(
        tmp_path / "so_data_hoje",
        agora=agora,
        edital={"prazos": [{"prazo": "Sessão pública", "data": "2026-11-25", "fonte": "Edital 1.1"}]},
        **base,
    )
    assert so_data_hoje["trava"] is None and so_data_hoje["nota"] == 5


def test_score_trava_quando_prazo_ja_encerrado(tmp_path):
    agora = datetime(2026, 11, 25, 13, 0, tzinfo=BRT)
    base = {
        "habilitacao": {"mais_aderente": "realmak", "empresas": [{"empresa": "realmak", "aderencia": "alta", "exigencias": [{}]}]},
        "tecnica": {"conclusao": {"viavel": "sim"}},
        "precificacao": {"exequivel": "sim", "margem_pct": 12.0},
    }
    hoje_passou = calcular(
        tmp_path / "hoje_passou",
        agora=agora,
        edital={"prazos": [{"prazo": "Sessão pública", "data": "2026-11-25T10:00", "fonte": "Edital 1.1"}]},
        **base,
    )
    assert hoje_passou["nota"] == 1 and hoje_passou["score"] <= 20
    assert [t["fonte"] for t in hoje_passou["trava"]] == ["Edital 1.1"]

    ontem = calcular(
        tmp_path / "ontem",
        agora=agora,
        edital={"prazos": [{"prazo": "Envio de propostas", "data": "2026-11-24", "fonte": "Edital 1.2"}]},
        **base,
    )
    assert ontem["nota"] == 1 and ontem["score"] <= 20
    assert [t["fonte"] for t in ontem["trava"]] == ["Edital 1.2"]


# --- motivos_nota e ressalva técnica -------------------------------------------------

def _hab(aderencia="alta"):
    return {"mais_aderente": "realmak", "empresas": [{"empresa": "realmak", "aderencia": aderencia}]}


def test_motivos_nota_forma_e_estado_atual(tmp_path):
    result = calcular(
        tmp_path, habilitacao=_hab(),
        tecnica={"conclusao": {"viavel": "com_ressalvas", "ressalvas": [
            "Dimensionamento de carga e SLA pendentes: anexos I a XIII do TR fora do acervo"]}},
        precificacao={"exequivel": "no_limite", "margem_pct": 15, "margem_minima_pct": 10, "tributos_pendente": True},
    )
    motivos = result["motivos_nota"]
    assert SCORE["validar_motivos_nota"](motivos) == []
    assert 3 <= len(motivos) <= 5
    assert motivos[0] == {"sinal": "+", "texto": "Realmak atende bem à habilitação"}
    assert any(m["sinal"] == "-" and "Dimensionamento" in m["texto"] for m in motivos)
    assert any("margem de 15%" in m["texto"] for m in motivos)
    assert any("tributária" in m["texto"] for m in motivos)


def test_motivos_nota_sem_dados_continuam_validos(tmp_path):
    result = calcular(tmp_path)
    assert SCORE["validar_motivos_nota"](result["motivos_nota"]) == []
    assert len(result["motivos_nota"]) == 3


def test_motivos_nota_ressalva_com_codigo_ou_bastidor_nao_vira_motivo(tmp_path):
    result = calcular(tmp_path, tecnica={"conclusao": {"viavel": "com_ressalvas", "ressalvas": [
        "Rodada limitada à herança da habilitação (empresa_avaliada = realmak)", "Veja hab-016 em tecnica.json"]}})
    textos = " ".join(m["texto"] for m in result["motivos_nota"])
    assert "empresa_avaliada" not in textos and "hab-016" not in textos and "tecnica.json" not in textos
    assert SCORE["validar_motivos_nota"](result["motivos_nota"]) == []


def test_motivos_nota_trava_entra_na_lista(tmp_path):
    result = calcular(tmp_path, precificacao={"exequivel": "nao", "margem_pct": -16.1})
    assert any("inexequível" in m["texto"] for m in result["motivos_nota"])
    assert len(result["motivos_nota"]) <= 5


@pytest.mark.parametrize("motivos", [
    None, [], [{"sinal": "+", "texto": "a"}] * 2, [{"sinal": "+", "texto": "a"}] * 6,
    [{"sinal": "*", "texto": "a"}] * 3, [{"sinal": "+", "texto": ""}] * 3,
    [{"sinal": "+", "texto": "x" * 91}] * 3,
    [{"sinal": "-", "texto": "Falta hab-016 no edital"}] * 3,
    [{"sinal": "-", "texto": "Risco H-18 aberto"}] * 3,
    [{"sinal": "-", "texto": "Decidido no G1"}] * 3,
    [{"sinal": "-", "texto": "Ver habilitacao.json"}] * 3,
])
def test_validar_motivos_nota_rejeita(motivos):
    assert SCORE["validar_motivos_nota"](motivos)


def test_validar_ressalva_tecnica():
    validar = SCORE["validar_ressalva_tecnica"]
    assert validar({"conclusao": {"resumo": "Atende", "ressalvas": [
        "Dimensionamento de carga e SLA pendentes: anexos I a XIII do TR fora do acervo"]}}) == []
    assert validar({"conclusao": {"ressalvas": ["Rodada limitada à herança da habilitação (empresa_avaliada = una)"]}})
    assert validar({"conclusao": {"resumo": "Análise na rodada de G2"}})
    assert validar({"conclusao": {"ressalvas": ["x" * 201]}})
    assert validar(None) == []


def test_cli_validar(tmp_path, capsys):
    import subprocess, sys
    (tmp_path / "relatorio").mkdir()
    (tmp_path / "analise").mkdir()
    topo = {"motivos_nota": [{"sinal": "+", "texto": "Ok"}, {"sinal": "-", "texto": "Pendente"},
                             {"sinal": "-", "texto": "Outro"}]}
    (tmp_path / "relatorio" / "topo.json").write_text(json.dumps(topo), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "agentes/analisador-edital/skills/score/scripts/score.py"
    ok = subprocess.run([sys.executable, str(script), "--dados", str(tmp_path), "--validar"], capture_output=True, text=True)
    assert ok.returncode == 0
    (tmp_path / "analise" / "tecnica.json").write_text(
        json.dumps({"conclusao": {"ressalvas": ["rodada limitada"]}}), encoding="utf-8")
    ruim = subprocess.run([sys.executable, str(script), "--dados", str(tmp_path), "--validar"], capture_output=True, text=True)
    assert ruim.returncode == 1
