"""Preenche somente entradas do modelo de proposta de manutenção."""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from openpyxl import load_workbook
from openpyxl.workbook.properties import CalcProperties

MODELO = Path(__file__).resolve().parents[1] / "assets/Modelo_Proposta_Comercial_Exequibilidade_Manutencao.xlsx"

PREMISSAS = dict(zip(
    (
        "edital", "contratante", "objeto", "uasg_orgao", "processo", "local", "data_proposta",
        "validade_dias", "vigencia_meses", "teto_mensal", "preco_mensal", "verba_pecas_sob_demanda",
        "tributos", "administracao", "contingencia", "margem_minima", "dias_uteis",
        "horas_jornada", "fator_produtivo", "reserva_horas", "glosa_maxima",
        "capital_giro_meses", "primeiro_ciclo_dias", "limite_desconto", "proponente", "cnpj",
        "contato", "representante_legal", "responsavel_tecnico",
    ),
    range(5, 34), strict=True,
))
CONTEUDO_PROPOSTA = dict(zip(
    ("preco", "pecas", "atendimento", "mobilizacao", "reajuste", "observacoes"),
    range(16, 22), strict=True,
))
OPERACAO = dict(zip(
    (
        "pecas", "cmms", "deslocamentos", "ferramentas", "ensaios", "epis", "garantias",
        "treinamentos", "residuos", "subcontratacao", "comunicacao", "mobilizacao",
        "capital_giro", "outro",
    ),
    range(5, 19), strict=True,
))
TABELAS = {
    "equipamentos": ("Equipamentos", 5, 105, ("A", "B", "C", "D", "F", "G", "J")),
    "mao_de_obra": ("Custos MO", 5, 14, ("A", "B", "C", "D", "E", "G")),
    "pecas": ("Peças Preventiva", 5, 54, ("B", "C", "D", "F", "G", "H")),
    "obrigacoes": ("Obrigações e SLA", 5, 34, ("A", "B", "C", "D", "E", "F", "G")),
    "fontes": ("Fontes", 5, 24, ("A", "B", "C", "D", "E", "F")),
    "pendencias": ("Fontes", 29, 30, ("A", "B", "C", "D", "E", "F")),
}
NUMERICAS = set(range(12, 29))
PERCENTUAIS = {"tributos", "administracao", "contingencia", "margem_minima", "fator_produtivo", "glosa_maxima", "limite_desconto"}


def campos(objeto, aceitos, contexto):
    if not isinstance(objeto, dict):
        raise ValueError(f"{contexto}: esperado um objeto JSON.")
    if desconhecidos := objeto.keys() - aceitos.keys():
        raise ValueError(f"{contexto}: campos desconhecidos: {', '.join(sorted(desconhecidos))}.")
    return objeto


def numero(valor, contexto, *, percentual=False, positivo=False):
    if valor is None:
        return
    if type(valor) not in (int, float) or not math.isfinite(valor) or valor < 0:
        raise ValueError(f"{contexto}: esperado número finito não negativo ou null.")
    if (percentual and valor > 1) or (positivo and valor == 0):
        raise ValueError(f"{contexto}: valor fora da faixa.")


def gravar(aba, endereco, valor):
    if valor is None:
        return
    celula = aba[endereco]
    if celula.data_type == "f":
        raise ValueError(f"{aba.title}!{endereco}: célula de fórmula protegida.")
    if type(valor) not in (str, int, float, date):
        raise ValueError(f"{aba.title}!{endereco}: valor deve ser texto, número ou null.")
    if isinstance(valor, str) and len(valor) > 32767:
        raise ValueError(f"{aba.title}!{endereco}: texto ultrapassa o limite de uma célula.")
    if type(valor) in (int, float):
        numero(valor, f"{aba.title}!{endereco}")
    celula.value = valor
    if isinstance(valor, str):
        celula.data_type = "s"


def preencher_tabela(planilha, dados, chave, especificacao):
    aba, inicio, fim, colunas = especificacao
    linhas = dados.get(chave, [])
    if not isinstance(linhas, list) or len(linhas) > fim - inicio + 1:
        raise ValueError(f"{chave}: esperado até {fim - inicio + 1} linhas.")
    for n, linha in enumerate(linhas, inicio):
        if not isinstance(linha, list) or len(linha) != len(colunas):
            raise ValueError(f"{chave}: linha {n - inicio + 1} precisa ter {len(colunas)} valores.")
        if chave == "equipamentos":
            for i in (2, 3, 4):
                numero(linha[i], chave, positivo=i == 3)
            if linha[5] not in (None, "Minutos", "Horas"):
                raise ValueError("equipamentos: unidade de tempo deve ser Minutos ou Horas.")
        elif chave == "mao_de_obra":
            for i in (1, 2, 3, 4):
                numero(linha[i], chave)
        elif chave == "pecas":
            for i in (1, 2, 4):
                numero(linha[i], chave)
        for col, valor in zip(colunas, linha, strict=True):
            gravar(planilha[aba], f"{col}{n}", valor)


def preencher(dados, saida: Path):
    campos(dados, {**TABELAS, "premissas": None, "proposta": None, "operacao": None}, "dados")
    if saida.resolve() == MODELO or saida.suffix.lower() != ".xlsx":
        raise ValueError("Informe um destino .xlsx diferente do modelo.")
    planilha = load_workbook(MODELO)
    premissas = campos(dados.get("premissas", {}), PREMISSAS, "premissas")
    for chave, entrada in premissas.items():
        valor = entrada
        if isinstance(entrada, dict):
            campos(entrada, {"valor": None, "fonte": None}, f"premissas.{chave}")
            valor = entrada.get("valor")
            gravar(planilha["Premissas"], f"E{PREMISSAS[chave]}", entrada.get("fonte"))
        linha = PREMISSAS[chave]
        if linha in NUMERICAS:
            numero(valor, chave, percentual=chave in PERCENTUAIS, positivo=chave == "vigencia_meses")
        if chave == "data_proposta" and valor is not None:
            valor = date.fromisoformat(valor)
        gravar(planilha["Premissas"], f"B{linha}", valor)

    for chave, valor in campos(dados.get("proposta", {}), CONTEUDO_PROPOSTA, "proposta").items():
        gravar(planilha["Proposta Comercial"], f"B{CONTEUDO_PROPOSTA[chave]}", valor)
    for chave, valores in campos(dados.get("operacao", {}), OPERACAO, "operacao").items():
        campos(valores, {"mensal": None, "fonte": None}, f"operacao.{chave}")
        mensal = valores.get("mensal")
        numero(mensal, chave)
        if chave == "pecas" and dados.get("pecas") and mensal is not None:
            raise ValueError("Com peças detalhadas, o custo mensal de peças vem da reserva da planilha.")
        linha = OPERACAO[chave]
        gravar(planilha["Custos Operacionais"], f"B{linha}", mensal)
        gravar(planilha["Custos Operacionais"], f"E{linha}", valores.get("fonte"))
    for chave, especificacao in TABELAS.items():
        preencher_tabela(planilha, dados, chave, especificacao)
    if dados.get("pecas"):
        planilha["Custos Operacionais"]["B5"] = "='Peças Preventiva'!E56"
    if planilha.calculation is None:
        planilha.calculation = CalcProperties()
    planilha.calculation.fullCalcOnLoad = True

    with NamedTemporaryFile(dir=saida.parent, suffix=".xlsx", delete=False) as temporario:
        tmp = Path(temporario.name)
    try:
        planilha.save(tmp)
        tmp.replace(saida)
    finally:
        tmp.unlink(missing_ok=True)
        planilha.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dados", type=Path)
    parser.add_argument("saida", type=Path)
    args = parser.parse_args()
    try:
        preencher(json.loads(args.dados.read_text(encoding="utf-8")), args.saida)
    except (OSError, TypeError, ValueError) as exc:
        parser.exit(2, f"Erro ao preencher planilha: {exc}\n")


if __name__ == "__main__":
    main()
