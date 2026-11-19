import hashlib
import json
import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook

SKILL = Path(__file__).resolve().parents[1] / "plugins/realmak/skills/precificar-proposta-exequibilidade"
SCRIPT = SKILL / "scripts/preencher_planilha.py"
MODELO = SKILL / "assets/Modelo_Proposta_Comercial_Exequibilidade_Manutencao.xlsx"


def executar(dados, tmp_path):
    entrada = tmp_path / "dados.json"
    saida = tmp_path / "proposta.xlsx"
    entrada.write_text(json.dumps(dados), encoding="utf-8")
    processo = subprocess.run([sys.executable, str(SCRIPT), str(entrada), str(saida)], capture_output=True, text=True)
    return processo, saida


def test_preenche_modelo_real_e_preserva_formulas(tmp_path):
    original = hashlib.sha256(MODELO.read_bytes()).hexdigest()
    proc, saida = executar({
        "premissas": {"edital": "PE 10/2026", "vigencia_meses": 12, "preco_mensal": 7200,
                      "tributos": {"valor": 0.15, "fonte": "Base fictícia"}},
        "equipamentos": [["Item 1", "Bomba", 10, 90, 45, "Minutos", "Alta"]],
        "mao_de_obra": [["Técnico", 0.5, 4500, 0.65, 650, "Rateio"]],
        "pecas": [["Kit preventivo", 4, 120, "Incluído", 1, "7 dias"]],
        "operacao": {"deslocamentos": {"mensal": 500, "fonte": "Premissa"}},
        "fontes": [["=documento", "Inventário", "p. 3", "Equipamentos", None, None]],
        "proposta": {"pecas": "Kit preventivo incluído"},
    }, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert hashlib.sha256(MODELO.read_bytes()).hexdigest() == original
    modelo, preenchido = load_workbook(MODELO), load_workbook(saida)
    assert preenchido.sheetnames == modelo.sheetnames
    for aba in modelo:
        for linha in aba.iter_rows():
            for celula in linha:
                if celula.data_type == "f":
                    assert preenchido[aba.title][celula.coordinate].value == celula.value
    assert preenchido["Premissas"]["B15"].value == 7200
    assert preenchido["Premissas"]["B17"].value == 0.15
    assert preenchido["Premissas"]["E17"].value == "Base fictícia"
    assert preenchido["Equipamentos"]["B5"].value == "Bomba"
    assert preenchido["Custos MO"]["C5"].value == 4500
    assert preenchido["Custos Operacionais"]["B5"].value == "='Peças Preventiva'!E56"
    assert preenchido["Custos Operacionais"]["B7"].value == 500
    assert preenchido["Proposta Comercial"]["B17"].value == "Kit preventivo incluído"
    assert preenchido["Fontes"]["A5"].value == "=documento"
    assert preenchido["Fontes"]["A5"].data_type == "s"
    assert preenchido.calculation.fullCalcOnLoad


def test_recusa_excedentes_sem_gerar_saida(tmp_path):
    proc, saida = executar({"equipamentos": [None] * 102}, tmp_path)
    assert proc.returncode == 2 and "até 101 linhas" in proc.stderr
    assert not saida.exists()


def test_recusa_dupla_contagem_de_pecas(tmp_path):
    proc, saida = executar({
        "pecas": [["Kit preventivo", 4, 120, "Incluído", 1, "7 dias"]],
        "operacao": {"pecas": {"mensal": 40}},
    }, tmp_path)
    assert proc.returncode == 2 and "custo mensal de peças vem da reserva" in proc.stderr
    assert not saida.exists()
