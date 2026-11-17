"""Base de custos da skill precificar-proposta-exequibilidade: ingestão e consulta.

A planilha usada aqui é sintética, no mesmo layout da planilha de funcionários do grupo.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "plugins/realmak/skills/precificar-proposta-exequibilidade/scripts"
EXEMPLO = SCRIPTS.parent / "assets/base-custos-exemplo.json"


def carregar(nome):
    spec = importlib.util.spec_from_file_location(nome, SCRIPTS / f"{nome}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def aba_pessoa(wb, titulo, nome, empresa, funcao, setor, salario, peric, encargos, custo):
    ws = wb.create_sheet(titulo)
    ws["A2"], ws["B2"], ws["C2"], ws["D2"], ws["E2"] = nome, empresa, funcao, setor, "Mecânica"
    ws["A3"] = "II – Mão-de-obra (VALOR EM MOEDA CORRENTE)"
    ws["A5"], ws["B5"] = "1.1 – Salário/Mês/Ano", salario
    for r, rot, v in [(8, "a) Adicional Gratificação", 0), (9, "b) Adicional de Insalubridade", 0),
                      (10, "c) Adicional de Periculosidade", peric), (11, "d) Adicional de hora Extra", 0)]:
        ws.cell(r, 1, rot)
        ws.cell(r, 2, v)
    ws["A15"] = "1.3 – Subtotal"
    ws["A22"], ws["B22"] = "INSS", 0.09
    ws["A23"], ws["B23"] = "Vale Refeição", 25
    ws["A24"], ws["B24"] = "Vale Transportes", 11
    grupo_a = encargos - 0.2322 - 0.045 - 0.02
    for ini, tot, rot, v in [(32, 42, "3.1 – Grupo “A”", grupo_a), (44, 53, "3.2 – Grupo “B”", 0.2322),
                             (55, 60, "3.3 – Grupo “C”", 0.045), (62, 64, "3.4 – Grupo “D”", 0.02),
                             (66, 68, "3.5 – Grupo “E”", 0)]:
        ws.cell(ini, 1, rot)
        ws.cell(tot, 1, "TOTAL:")
        ws.cell(tot, 2, v)
    ws["A70"], ws["B70"] = "VALOR DOS ENCARGOS SOCIAIS", encargos
    ws["A74"] = "IV. INSUMOS"
    ws["H29"] = custo
    ws["A101"], ws["B101"] = "VII. PREÇO HOMEM/MÊS", custo
    ws["A104"], ws["B104"] = "HORAS DE TRABALHO", 176


def planilha_sintetica(destino: Path) -> Path:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    seg = wb.active
    seg.title = "MECÂNICA"
    for c, v in enumerate(["CEM POR CENTO", "LUCRO", "IMPOSTOS", "ADCIONAIS", "INDICE", None, "COBTVEL",
                           "KM/DIA", "V. LT"], 1):
        seg.cell(1, c, v)
    for c, v in enumerate([1, 0.1, 0.18, 0, 0.72, None, "ROTA1", 30, 6], 1):
        seg.cell(2, c, v)
    seg["A4"], seg["B4"], seg["C4"], seg["D4"] = "DESCRIÇAO", "QUANT", "VALOR", "TOTAL"
    seg["A5"], seg["D5"] = "FUNCIONARIOS", 100000
    seg["A11"], seg["B11"], seg["C11"], seg["D11"] = "COMBUSTIVEL", 1, 5000, 5000
    seg["A12"], seg["B12"], seg["C12"], seg["D12"] = "ESCRITORIO", 1, 4000, 4000
    seg["A13"], seg["B13"], seg["C13"], seg["D13"] = "REALMAK CSLL", 1, 700, 700

    fat = wb.create_sheet("Faturamento")
    for c, v in enumerate(["Empresa", "Vendedor", "Segmento", "Estado", "Cliente", "Valor Bruto",
                           "Impostos Retido", "Imposto"], 1):
        fat.cell(1, c, v)
    for r, (emp, aliq) in enumerate([("Realmak", 0.15), ("Realmak", 0.15), ("Aforça", 0.12),
                                     ("NortFort", 0.06)], 2):
        fat.cell(r, 1, emp)
        fat.cell(r, 6, 10000)
        fat.cell(r, 7, 0.05)
        fat.cell(r, 8, aliq)

    aba_pessoa(wb, "P1", "Pessoa Um", "Realmak", "Técnico", "Execução", 2000, 0.3, 0.40, 5000)
    aba_pessoa(wb, "P2", "Pessoa Dois", "Realmak", "Técnico ", "Execução", 2200, 0.3, 0.40, 5600)
    aba_pessoa(wb, "P3", "Pessoa Três", "Realmak", "Aux Téc", "Execução", 1500, 0.3, 0.40, 3800)
    aba_pessoa(wb, "P4", "Pessoa Quatro", "Aforça", "Técnico", "Execução", 1900, 0.3, 0.70, 6000)
    aba_pessoa(wb, "P5", "Pessoa Cinco", "Prestador de Serviços", "Eng Mecânico", "Engenharia", 0, 0, 0, 2500)
    aba_pessoa(wb, "P6", "Pessoa Seis", "Realmak", "Aux Adm", "Administração", 1800, 0, 0.40, 3500)
    aba_pessoa(wb, "A Pagar Ajudante", "A Pagar Ajudante", "Realmak", "Ajudante Geral", "Proposta",
               1600, 0.3, 0.40, 3400)
    aba_pessoa(wb, "Vazia", "NOME 1", None, None, "Execução", None, 0, 0, 0)
    wb.save(destino)
    return destino


@pytest.fixture
def base(tmp_path):
    pytest.importorskip("openpyxl")  # ingerir_custos importa openpyxl no topo
    ingerir = carregar("ingerir_custos")
    return ingerir.ingerir(planilha_sintetica(tmp_path / "func.xlsx"), "2026-01")


def test_tributos_e_encargos_por_empresa(base):
    emp = base["empresas"]
    assert emp["realmak"]["tributos"]["aliquota"] == 0.15
    assert emp["realmak"]["tributos"]["retencao_tipica"] == 0.05
    assert emp["aforca"]["tributos"]["aliquota"] == 0.12
    assert emp["nortfort"]["tributos"]["aliquota"] == 0.06
    assert emp["una"]["tributos"]["aliquota"] is None
    assert emp["realmak"]["encargos_sociais"]["total"] == 0.4
    assert emp["aforca"]["encargos_sociais"]["total"] == 0.7
    # Nortfort não tem CLT de execução: herda o padrão do grupo e avisa.
    assert "padrão do grupo" in emp["nortfort"]["encargos_sociais"]["origem"]
    assert any("UNA" in a and "alíquota" in a for a in base["alertas"])


def test_faixas_por_cargo_sem_nome(base):
    tec = next(c for c in base["cargos_por_empresa"]
               if c["cargo"] == "Técnico de manutenção" and c["empresa"] == "realmak")
    assert tec["n"] == 2
    assert tec["custo_mensal"]["min"] == 5000
    assert tec["custo_mensal"]["max"] == 5600
    assert tec["custo_mensal"]["med"] == 5300
    assert tec["custo_hora"]["med"] == round(5300 / 176, 2)
    grupo = next(c for c in base["cargos_grupo"] if c["cargo"] == "Técnico de manutenção" and c["vinculo"] == "clt")
    assert grupo["n"] == 3
    texto = json.dumps(base, ensure_ascii=False)
    for nome in ("Pessoa Um", "Pessoa Dois", "Pessoa Quatro", "Pessoa Seis"):
        assert nome not in texto


def test_administrativo_e_modelo_ficam_fora_das_faixas(base):
    cargos = {c["cargo"] for c in base["cargos_grupo"]}
    assert "Ajudante geral" not in cargos  # só existe como modelo de proposta
    assert base["modelos_proposta"][0]["cargo"] == "Ajudante geral"
    assert base["empresas"]["realmak"]["administracao_central"]["pessoas"] == 1
    assert base["empresas"]["realmak"]["administracao_central"]["custo_mensal"] == 3500


def test_markup_e_despesas_do_segmento(base):
    assert base["markup_referencia"][0] == {
        "segmento": "Mecânica", "aplica_a": "mão de obra e serviço", "lucro": 0.1, "impostos": 0.18, "adicionais": 0.0,
    }
    tipos = {d["item"]: d["tipo"] for d in base["despesas_mensais_empresa"]}
    assert tipos == {"COMBUSTIVEL": "despesa", "ESCRITORIO": "despesa", "REALMAK CSLL": "tributo pago"}
    assert base["parametros"]["preco_litro"] == 6


def test_cli_grava_json_e_planilha(tmp_path):
    pytest.importorskip("openpyxl")
    planilha = planilha_sintetica(tmp_path / "TODOS_FUNCIONARIOS_2026_JAN.xlsx")
    saida = tmp_path / "base"
    r = subprocess.run([sys.executable, str(SCRIPTS / "ingerir_custos.py"), str(planilha), str(saida)],
                       capture_output=True, text=True, check=True)
    assert "competência 2026-01" in r.stdout
    base = json.loads((saida / "base-custos.json").read_text(encoding="utf-8"))
    assert base["competencia"] == "2026-01"
    from openpyxl import load_workbook

    wb = load_workbook(saida / "base-custos.xlsx")
    assert wb.sheetnames == ["Leia-me", "Tributos", "Encargos", "Cargos por empresa", "Cargos no grupo",
                             "Modelos de proposta", "Markup e despesas", "Alertas"]


def consultar(*args):
    r = subprocess.run([sys.executable, str(SCRIPTS / "consultar_base.py"), str(EXEMPLO), *args],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def test_exemplo_e_ficticio_e_consultavel():
    base = json.loads(EXEMPLO.read_text(encoding="utf-8"))
    assert base["fonte"]["arquivo"].startswith("EXEMPLO")
    out = consultar("--listar")
    assert "realmak" in out["empresas"]


def test_linha_custos_mo_fecha_no_custo_de_referencia():
    out = consultar("--empresa", "realmak", "--cargo", "tecnico de manutencao")
    mo = out["custos_mo"]
    c, d, e = mo["C_salario_base"], mo["D_encargos_adicionais"], mo["E_beneficios"]
    assert d == out["encargos_sociais"]["total"]
    assert round(c * (1 + d) + e, 2) == pytest.approx(mo["custo_mensal_referencia"], abs=0.02)
    assert mo["origem"].startswith("faixa da Realmak")


def test_cenarios_e_fallback_do_grupo():
    base = consultar("--empresa", "realmak", "--cargo", "Técnico de manutenção")["custos_mo"]
    cons = consultar("--empresa", "realmak", "--cargo", "Técnico de manutenção", "--cenario", "conservador")["custos_mo"]
    assert cons["custo_mensal_referencia"] >= base["custo_mensal_referencia"]
    fora = consultar("--empresa", "aforca", "--cargo", "Auxiliar técnico")["custos_mo"]
    assert "grupo" in fora["origem"]
    assert fora["E_detalhe"]["outros_itens_folha"] == 0
    assert fora["D_encargos_adicionais"] == 0.7


def test_prestador_vai_cheio_em_c():
    mo = consultar("--empresa", "realmak", "--cargo", "Engenheiro mecânico", "--prestador")["custos_mo"]
    assert mo["D_encargos_adicionais"] == 0 and mo["E_beneficios"] == 0
    assert mo["C_salario_base"] == mo["custo_mensal_referencia"]
