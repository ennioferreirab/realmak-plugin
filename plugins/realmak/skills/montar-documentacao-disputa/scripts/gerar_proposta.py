#!/usr/bin/env python3
"""Etapa "Proposta" do pacote: proposta no modelo do edital (DOCX + PDF) e planilha de composição de custos (PDF).

Uso:
  python3 gerar_proposta.py calcular entrada.json
  python3 gerar_proposta.py proposta entrada.json saida.docx
  python3 gerar_proposta.py planilha modelo.xlsx saida_dir --preco-mensal 159351.29 [--data AAAA-MM-DD] [--validade 90]
                            [--nome "Planilha de composição de custos"]

entrada.json (proposta):
  empresa, destinatario, local_data: como em redigir-declaracoes/scripts/gerar_declaracoes.py. A empresa traz também
      telefone, email, banco, agencia, conta (de dados_empresa) e `regime_tributario` (da precificação ou do Cérebro).
  proposta: {
    titulo: "ANEXO II – PROPOSTA DE PREÇOS", objeto, preco_mensal, meses (60), teto_mensal,
    item1: {codigo, descricao, unidade},
    itens_fixos: [{codigo, descricao, anual}]   # item fixado pela Administração, fora da disputa (pode ser vazio)
    validade_dias, validade_minima_dias, clausula_validade,
    limite_exequibilidade_pct (75), clausula_exequibilidade,
    regime_tributario, clausula_regime,
    desconto_sob_demanda: {clausula}            # ativa a fórmula D = [1 – (VP/VE)] × 100
    anexos: [textos]
  }
`calcular` e `proposta` imprimem JSON com valores, desconto D e alertas; alerta de nível "erro" não gera arquivo (exit 2).
`planilha` recalcula o modelo da skill precificar-proposta-exequibilidade com o preço informado e gera o PDF só com
as abas de composição (sem fontes, observações internas, margem-alvo, checks nem memória de exequibilidade).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

CENT = Decimal("0.01")
ABAS_COMPOSICAO = ("Custos MO", "Custos Operacionais", "BDI e Preço")
COLUNAS_INTERNAS = {"Custos MO": "G", "Custos Operacionais": "E"}

_UNID = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze",
         "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
_DEZ = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
_CEN = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos",
        "novecentos"]


def dinheiro(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP)


def brl(v) -> str:
    return "R$ " + f"{dinheiro(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v) -> str:
    return f"{Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP):,.2f}".replace(".", ",") + "%"


def _centenas(n: int) -> str:
    if n == 100:
        return "cem"
    c, resto = divmod(n, 100)
    partes = [_CEN[c]] if c else []
    if resto:
        partes.append(_UNID[resto] if resto < 20 else _DEZ[resto // 10] + (f" e {_UNID[resto % 10]}" if resto % 10 else ""))
    return " e ".join(partes)


def extenso(valor) -> str:
    """Valor em reais por extenso (pt-BR): 9561077.40 → 'nove milhões, quinhentos e sessenta e um mil e setenta e sete reais e quarenta centavos'."""
    centavos_total = int(dinheiro(valor) * 100)
    inteiro, centavos = divmod(centavos_total, 100)
    grupos = []
    for nome_s, nome_p, base in (("bilhão", "bilhões", 10**9), ("milhão", "milhões", 10**6), ("mil", "mil", 1000)):
        q, inteiro_resto = divmod(inteiro, base)
        inteiro = inteiro_resto
        if q:
            grupos.append((q, "mil" if base == 1000 else (nome_s if q == 1 else nome_p), base))
    resto = inteiro
    textos = [(f"{_centenas(q)} {n}" if not (base == 1000 and q == 1) else "mil") for q, n, base in grupos]
    if resto:
        textos.append(_centenas(resto))
    if not textos:
        reais = ""
    elif len(textos) == 1:
        reais = textos[0]
    else:
        ultimo = resto if resto else grupos[-1][0]
        ligacao = " e " if ultimo < 100 or ultimo % 100 == 0 else ", "
        reais = ", ".join(textos[:-1]) + ligacao + textos[-1]
    total_int = centavos_total // 100
    partes = []
    if total_int:
        sufixo = "real" if total_int == 1 else ("de reais" if total_int % 10**6 == 0 else "reais")
        partes.append(f"{reais} {sufixo}")
    if centavos:
        partes.append(f"{_centenas(centavos)} {'centavo' if centavos == 1 else 'centavos'}")
    return " e ".join(partes) or "zero real"


def calcular(entrada: dict) -> dict:
    p = entrada["proposta"]
    e = entrada.get("empresa", {})
    meses = int(p.get("meses", 60))
    mensal = dinheiro(p["preco_mensal"])
    anual = mensal * 12
    total1 = mensal * meses
    fixos = [{**i, "anual": dinheiro(i["anual"]), "total": dinheiro(i["anual"]) * meses / 12} for i in p.get("itens_fixos", [])]
    fixos_anual = sum((i["anual"] for i in fixos), Decimal(0))
    fixos_total = dinheiro(sum((i["total"] for i in fixos), Decimal(0)))
    total = total1 + fixos_total
    teto = dinheiro(p["teto_mensal"]) if p.get("teto_mensal") else None
    d = (1 - mensal / teto) * 100 if teto else None
    limite_pct = Decimal(str(p.get("limite_exequibilidade_pct", 75)))
    piso = dinheiro(teto * limite_pct / 100) if teto else None
    alertas = []

    def erro(texto):
        alertas.append({"nivel": "erro", "texto": texto})

    if mensal <= 0:
        erro("Preço mensal não informado: a proposta só pode usar o valor da precificação aprovada ou de instrução humana.")
    if teto and mensal > teto:
        erro(f"Preço mensal {brl(mensal)} acima do máximo do edital ({brl(teto)}).")
    if piso and mensal < piso:
        erro(f"Preço mensal {brl(mensal)} abaixo de {limite_pct}% do valor orçado ({brl(piso)}): inexequível "
             f"({p.get('clausula_exequibilidade', 'edital')}).")
    minima = int(p.get("validade_minima_dias", 0) or 0)
    if int(p.get("validade_dias", 0)) < minima:
        erro(f"Validade de {p.get('validade_dias')} dias menor que o mínimo do edital ({minima} dias).")
    if not (p.get("regime_tributario") or e.get("regime_tributario")):
        erro("Regime de tributação ausente: use o regime da precificação ou do Cérebro; sem fonte, deixe pendente.")
    faltam_banco = [c for c in ("banco", "agencia", "conta") if not e.get(c)]
    if faltam_banco:
        alertas.append({"nivel": "aviso", "texto": "Dados bancários faltando no cadastro: " + ", ".join(faltam_banco) + "."})
    return {
        "meses": meses,
        "preco_mensal": mensal,
        "preco_anual": anual,
        "subtotal1": total1,
        "itens_fixos": fixos,
        "subtotal2_anual": fixos_anual,
        "subtotal2": fixos_total,
        "total": total,
        "total_extenso": extenso(total),
        "teto_mensal": teto,
        "total_orcado": dinheiro(teto * meses + fixos_total) if teto else None,
        "desconto_d": d,
        "piso_exequivel_mensal": piso,
        "alertas": alertas,
        "ok": not any(a["nivel"] == "erro" for a in alertas),
    }


def _json(obj):
    def padrao(o):
        if isinstance(o, Decimal):
            return float(o)
        raise TypeError(type(o))

    return json.dumps(obj, ensure_ascii=False, indent=1, default=padrao)


def montar_spec(entrada: dict, c: dict) -> dict:
    p, e = entrada["proposta"], entrada["empresa"]
    meses = c["meses"]
    i1 = p.get("item1", {})
    regime = p.get("regime_tributario") or e.get("regime_tributario")
    linhas_empresa = [
        f"Razão Social da Empresa: {e['razao_social']}",
        f"CNPJ: {e['cnpj']}" + (f"   –   {e['inscricao_rotulo']} nº {e['inscricao_estadual']}" if e.get("inscricao_estadual") else ""),
        f"End.: {e['endereco']}, {e['cidade']}-{e['uf']}" + (f", CEP {e['cep']}" if e.get("cep") else ""),
        f"Tel.: {e.get('telefone', '—')}   e-mail: {e.get('email', '—')}",
    ]
    if all(e.get(k) for k in ("banco", "agencia", "conta")):
        linhas_empresa.append(f"Banco: {e['banco']}   Nº da Agência: {e['agencia']}   Nº da Conta Corrente: {e['conta']}")
    r = e.get("representante") or {}
    linhas_empresa.append(f"Nome do Responsável da Empresa: {r.get('nome', '')} – {r.get('cargo', '')}")
    linhas_empresa.append(f"Regime de tributação da empresa ({p.get('clausula_regime', 'edital')}): {regime}")

    parag = [
        {"texto": "Declaro que nos preços propostos estão computados todos os custos necessários para o atendimento do "
                  "objeto desta licitação, bem como impostos, encargos trabalhistas, previdenciários, fiscais, comerciais, "
                  "taxas, seguros, garantia, lucro da empresa e quaisquer outros que incidam ou venham a incidir sobre o "
                  "objeto licitado, constante da proposta."}
    ]
    parag += [{"texto": t, "recuo": False} for t in linhas_empresa]
    parag.append({"texto": "1 – SERVIÇOS PRESTADOS MENSALMENTE", "negrito": True, "recuo": False})
    parag.append({"tabela": {
        "cabecalho": ["Item", "Descrição", "Un.", "Quant.", "Valor total mensal", "Valor total anual",
                      f"Valor total ({meses} meses)"],
        "linhas": [
            [i1.get("codigo", "1.1"), i1.get("descricao", p.get("objeto", "")), i1.get("unidade", "Mês"), str(meses),
             brl(c["preco_mensal"]), brl(c["preco_anual"]), brl(c["subtotal1"])],
            ["", "SUBTOTAL 1", "", "", brl(c["preco_mensal"]), brl(c["preco_anual"]), brl(c["subtotal1"])],
        ],
        "larguras_cm": [1.1, 5.6, 1.1, 1.3, 2.5, 2.6, 2.8], "direita": [4, 5, 6], "negrito_linhas": [1], "tamanho": 8,
    }})
    if c["itens_fixos"]:
        parag.append({"texto": "2 – SERVIÇOS SOB DEMANDA E FORNECIMENTO DE PEÇAS (valor fixado pela Administração, "
                               "não disputado e não alterado pela licitante)", "negrito": True, "recuo": False})
        linhas = [[i.get("codigo", ""), i["descricao"], brl(i["anual"]), brl(i["total"])] for i in c["itens_fixos"]]
        linhas.append(["", "SUBTOTAL 2", brl(c["subtotal2_anual"]), brl(c["subtotal2"])])
        parag.append({"tabela": {
            "cabecalho": ["Item", "Descrição", "Valor total anual", f"Valor total ({meses} meses)"],
            "linhas": linhas, "larguras_cm": [1.5, 8.5, 3.5, 3.5], "direita": [2, 3],
            "negrito_linhas": [len(linhas) - 1], "tamanho": 9,
        }})
        composicao = (f" Composição: SUBTOTAL 1 ({meses} × {brl(c['preco_mensal'])} = {brl(c['subtotal1'])}) + "
                      f"SUBTOTAL 2 (valor fixo da Administração, {brl(c['subtotal2'])} em {meses} meses).")
    else:
        composicao = ""
    parag.append({"texto": f"Preço Total da Proposta para {meses} meses (algarismo e por extenso): {brl(c['total'])} "
                           f"({c['total_extenso']}).", "negrito": True, "recuo": False})
    if composicao:
        parag.append({"texto": composicao.strip(), "recuo": False})
    ds = p.get("desconto_sob_demanda")
    if ds and c["desconto_d"] is not None:
        parag.append({"texto": f"Desconto aplicável aos serviços sob demanda ({ds.get('clausula', 'edital')}): "
                               f"D = [1 – (VP/VE)] × 100 = [1 – ({brl(c['preco_mensal'])} / {brl(c['teto_mensal'])})] × 100 = "
                               f"{pct(c['desconto_d'])}, sendo VP o valor ofertado para o item 1 e VE o valor estimado "
                               f"pela Administração para o item 1.", "recuo": False})
    validade = int(p["validade_dias"])
    parag.append({"texto": f"Validade da Proposta: {validade} dias, a contar da apresentação"
                           + (f" ({p['clausula_validade']})." if p.get("clausula_validade") else "."), "recuo": False})
    if p.get("anexos"):
        parag.append({"texto": "Anexos desta proposta: " + "; ".join(p["anexos"]) + ".", "recuo": False})
    parag.append({"texto": "{local_data}.", "recuo": False})
    return {
        "empresa": e,
        "destinatario": entrada["destinatario"],
        "local_data": entrada["local_data"],
        "declaracoes": [{"titulo": p.get("titulo", "PROPOSTA DE PREÇOS"), "paragrafos": parag}],
    }


def _soffice(args: list[str], tmp: Path):
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        raise RuntimeError("LibreOffice (soffice) não encontrado")
    perfil = tmp / f"lo-{uuid.uuid4().hex[:8]}"
    (perfil / "user").mkdir(parents=True)
    # números e datas no padrão brasileiro nas planilhas convertidas
    (perfil / "user" / "registrymodifications.xcu").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<oor:items xmlns:oor="http://openoffice.org/2001/registry" '
        'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
        '<item oor:path="/org.openoffice.Setup/L10N"><prop oor:name="ooSetupSystemLocale" oor:op="fuse">'
        '<value>pt-BR</value></prop></item>\n</oor:items>\n',
        encoding="utf-8",
    )
    subprocess.run([exe, f"-env:UserInstallation=file://{perfil}", "--headless", *args], check=True, capture_output=True,
                   timeout=300, env={"HOME": str(tmp), "PATH": "/usr/bin:/bin"})


def para_pdf(arquivo: Path, destino: Path, tmp: Path) -> Path:
    _soffice(["--convert-to", "pdf", "--outdir", str(destino), str(arquivo)], tmp)
    pdf = destino / (arquivo.stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError("conversão para PDF falhou: " + arquivo.name)
    return pdf


def cmd_proposta(entrada_path: Path, saida: Path) -> int:
    entrada = json.loads(entrada_path.read_text(encoding="utf-8"))
    c = calcular(entrada)
    if not c["ok"]:
        print(_json(c))
        return 2
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "redigir-declaracoes" / "scripts"))
    from gerar_declaracoes import gerar

    spec = montar_spec(entrada, c)
    spec_path = entrada_path.parent / f".spec-{uuid.uuid4().hex[:8]}.json"
    try:
        spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        saida.parent.mkdir(parents=True, exist_ok=True)
        gerar(spec_path, str(saida))
    finally:
        spec_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        c["pdf"] = str(para_pdf(saida, saida.parent, Path(tmp)))
    c["docx"] = str(saida)
    print(_json(c))
    return 0


def cmd_planilha(modelo: Path, saida_dir: Path, preco: str, data: str | None, validade: int | None, nome: str) -> int:
    import openpyxl
    from openpyxl.worksheet.properties import PageSetupProperties

    saida_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        wb = openpyxl.load_workbook(modelo)
        prem = wb["Premissas"]
        original = prem["B15"].value
        prem["B15"] = float(dinheiro(preco))
        if data:
            prem["B11"] = datetime.strptime(data, "%Y-%m-%d")
        if validade:
            prem["B12"] = validade
        base = tmp / "base.xlsx"
        wb.save(base)

        recalc = tmp / "recalc"
        _soffice(["--convert-to", "xlsx", "--outdir", str(recalc), str(base)], tmp)
        v = openpyxl.load_workbook(recalc / "base.xlsx", data_only=True)
        bdi = v["BDI e Preço"]
        resumo = {
            "preco_mensal": bdi["C13"].value,
            "preco_mensal_modelo": original,
            "custos_diretos": bdi["C7"].value,
            "custo_antes_tributos_e_lucro": bdi["C10"].value,
            "tributos": bdi["C11"].value,
            "lucro": bdi["C12"].value,
            "lucro_pct": bdi["D12"].value,
            "checks_pendentes_ou_falhos": [
                f"{v['Checks'][f'A{r}'].value}: {v['Checks'][f'D{r}'].value}"
                for r in range(6, 12)
                if v["Checks"][f"D{r}"].value not in ("PASSA", None)
            ],
        }

        cabecalho = f"{prem['B29'].value} – CNPJ {prem['B30'].value} – {prem['B5'].value} – {prem['B6'].value}"
        for ws in wb.worksheets:
            if ws.title in ABAS_COMPOSICAO:
                ws["A2"] = cabecalho
                col = COLUNAS_INTERNAS.get(ws.title)
                if col:
                    ws.column_dimensions[col].hidden = True
                ws.column_dimensions["A"].width = max(ws.column_dimensions["A"].width or 0, 52)
                ws.page_setup.orientation = "landscape"
                ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
                ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
            else:
                ws.sheet_state = "hidden"
        wb["BDI e Preço"]["D16"] = None
        for nome_aba in reversed(ABAS_COMPOSICAO):  # o LibreOffice imprime a primeira aba mesmo oculta
            wb.move_sheet(nome_aba, offset=-wb.sheetnames.index(nome_aba))
        for ws in wb.worksheets:
            ws.sheet_view.tabSelected = ws.title == ABAS_COMPOSICAO[0]
        wb.active = 0
        pdf_xlsx = tmp / f"{nome}.xlsx"
        wb.save(pdf_xlsx)
        pdf = para_pdf(pdf_xlsx, saida_dir, tmp)
    resumo["pdf"] = str(pdf)
    print(_json(resumo))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("calcular")
    s.add_argument("entrada", type=Path)
    s = sub.add_parser("proposta")
    s.add_argument("entrada", type=Path)
    s.add_argument("saida", type=Path)
    s = sub.add_parser("planilha")
    s.add_argument("modelo", type=Path)
    s.add_argument("saida_dir", type=Path)
    s.add_argument("--preco-mensal", required=True)
    s.add_argument("--data")
    s.add_argument("--validade", type=int)
    s.add_argument("--nome", default="Planilha de composição de custos")
    a = ap.parse_args(argv)
    if a.cmd == "calcular":
        c = calcular(json.loads(a.entrada.read_text(encoding="utf-8")))
        print(_json(c))
        return 0 if c["ok"] else 2
    if a.cmd == "proposta":
        return cmd_proposta(a.entrada, a.saida)
    return cmd_planilha(a.modelo, a.saida_dir, a.preco_mensal, a.data, a.validade, a.nome)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
