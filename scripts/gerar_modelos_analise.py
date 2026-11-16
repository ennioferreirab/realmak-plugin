"""Gera as planilhas-modelo das skills de análise de edital.

Uso (a partir da raiz do repositório):

    uv run --with openpyxl python scripts/gerar_modelos_analise.py

Grava:
    plugins/realmak/skills/analisar-edital-manutencao/assets/modelo-analise-manutencao.xlsx (via scripts da skill)
    plugins/realmak/skills/analisar-edital-fornecimento/assets/modelo-analise-fornecimento.xlsx

Convenção das planilhas: célula amarela é entrada, célula cinza é fórmula.
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

SKILLS = Path(__file__).resolve().parents[1] / "plugins/realmak/skills"

AMARELO = PatternFill("solid", fgColor="FFF2CC")
CINZA = PatternFill("solid", fgColor="E7E6E6")
AZUL = PatternFill("solid", fgColor="1F3864")
BRANCO_NEGRITO = Font(bold=True, color="FFFFFF")
NEGRITO = Font(bold=True)
TITULO = Font(bold=True, size=13)
BORDA = Border(*[Side(style="thin", color="BFBFBF")] * 4)
QUEBRA = Alignment(wrap_text=True, vertical="top")


def cabecalho(ws, linha, colunas, larguras=None):
    for i, nome in enumerate(colunas, 1):
        c = ws.cell(linha, i, nome)
        c.fill, c.font, c.border = AZUL, BRANCO_NEGRITO, BORDA
        c.alignment = Alignment(wrap_text=True, vertical="center")
    if larguras:
        for i, largura in enumerate(larguras, 1):
            ws.column_dimensions[get_column_letter(i)].width = largura


def entrada(ws, l1, l2, c1, c2):
    for linha in range(l1, l2 + 1):
        for col in range(c1, c2 + 1):
            c = ws.cell(linha, col)
            c.fill, c.border, c.alignment = AMARELO, BORDA, QUEBRA


def formula(ws, linha, col, expr, formato=None, negrito=True):
    c = ws.cell(linha, col, expr)
    c.fill, c.border = CINZA, BORDA
    c.font = NEGRITO if negrito else Font()
    if formato:
        c.number_format = formato
    return c


def lista(ws, intervalo, itens):
    dv = DataValidation(type="list", formula1='"' + ",".join(itens) + '"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(intervalo)


def titulo(ws, linha, texto):
    ws.cell(linha, 1, texto).font = TITULO


def rotulo(ws, linha, texto):
    c = ws.cell(linha, 1, texto)
    c.font, c.alignment = NEGRITO, QUEBRA


def instrucoes(wb, linhas):
    ws = wb.active
    ws.title = "Instruções"
    ws.column_dimensions["A"].width = 115
    for i, texto in enumerate(linhas, 1):
        ws.cell(i, 1, texto).alignment = QUEBRA
    ws["A1"].font = TITULO
    base = len(linhas) + 2
    c = ws.cell(base, 1, "Entrada")
    c.fill, c.border = AMARELO, BORDA
    c = ws.cell(base + 1, 1, "Fórmula")
    c.fill, c.border = CINZA, BORDA


def aba_checks(wb, checks):
    ws = wb.create_sheet("Checks")
    cabecalho(ws, 1, ["Verificação", "Ocorrências", "Situação"], [70, 14, 12])
    for linha, (nome, expr) in enumerate(checks, 2):
        ws.cell(linha, 1, nome).border = BORDA
        formula(ws, linha, 2, expr)
        formula(ws, linha, 3, f'=IF(B{linha}=0,"OK","ALERTA")')
    fim = len(checks) + 1
    rotulo(ws, fim + 2, "Total de alertas")
    formula(ws, fim + 2, 2, f'=COUNTIF(C2:C{fim},"ALERTA")')


def aba_documentos(wb):
    ws = wb.create_sheet("Documentos")
    cabecalho(ws, 1, ["ID", "Arquivo", "Tipo de documento", "Versão ou data"], [8, 55, 30, 20])
    entrada(ws, 2, 60, 1, 4)
    ws.freeze_panes = "A2"


def aba_pendencias(wb, tipos):
    ws = wb.create_sheet("Pendências")
    cabecalho(
        ws,
        1,
        ["ID", "Tipo", "Descrição", "Fonte", "Impacto", "Ação sugerida", "Prazo"],
        [8, 24, 55, 24, 34, 34, 14],
    )
    entrada(ws, 2, 100, 1, 7)
    lista(ws, "B2:B100", tipos)
    ws.freeze_panes = "A2"


# ------------------------------------------------------------------------- fornecimento


def fornecimento(destino: Path):
    wb = Workbook()
    instrucoes(
        wb,
        [
            "Análise de edital de fornecimento: modelo de planilha",
            "",
            "Células amarelas são entradas. Células cinza são fórmulas: não sobrescreva.",
            "Preencha na ordem das abas: Documentos, Itens, Exigências técnicas, Entrega, Condições comerciais, "
            "Pendências e, por último, Resumo.",
            "IDs: D-01 para documentos, E-01 para exigências técnicas, P-01 para pendências. "
            "Itens usam o número do lote e do item do edital.",
            "Aba Itens: uma linha por item do edital, com a descrição como consta no termo de referência. "
            "A coluna Atendemos? fica em A confirmar até a equipe responder.",
            "Prazos do certame e habilitação jurídica, fiscal e econômica ficam na análise geral do edital.",
            "Aba Checks: todas as linhas devem estar em OK antes da entrega.",
            "O arquivo analise-fornecimento.html repete os números calculados aqui. Se houver diferença, vale esta planilha.",
        ],
    )

    ws = wb.create_sheet("Resumo")
    ws.column_dimensions["A"].width = 40
    for col, largura in zip("BCD", (50, 45, 45), strict=True):
        ws.column_dimensions[col].width = largura
    titulo(ws, 1, "Identificação")
    campos = [
        "Órgão / unidade",
        "Edital e processo",
        "Objeto",
        "Critério de julgamento",
        "Registro de preços",
        "Data desta análise",
    ]
    for linha, nome in enumerate(campos, 2):
        rotulo(ws, linha, nome)
        entrada(ws, linha, linha, 2, 2)
    lista(ws, "B5", ["Por item", "Por lote", "Global"])
    lista(ws, "B6", ["Sim", "Não"])
    titulo(ws, 9, "1. Conclusão de atendimento ao objeto")
    rotulo(ws, 10, "Conclusão")
    entrada(ws, 10, 10, 2, 2)
    lista(ws, "B10", ["Atende", "Atende com condições", "Não atende"])
    rotulo(ws, 11, "Justificativa (até cinco linhas)")
    entrada(ws, 11, 11, 2, 2)
    ws.row_dimensions[11].height = 90
    indicadores = [
        ("Itens do edital", "=COUNTA(Itens!C2:C1001)", "0"),
        ("Itens que atendemos", '=COUNTIF(Itens!L2:L1001,"Sim")', "0"),
        ("Itens que não atendemos", '=COUNTIF(Itens!L2:L1001,"Não")', "0"),
        ("Itens a confirmar", '=COUNTIF(Itens!L2:L1001,"A confirmar")', "0"),
        ("Valor estimado total (R$)", "=SUM(Itens!I2:I1001)", "#,##0.00"),
        (
            "Valor estimado dos itens que atendemos (R$)",
            '=SUMIF(Itens!L2:L1001,"Sim",Itens!I2:I1001)',
            "#,##0.00",
        ),
    ]
    for linha, (nome, expr, fmt) in zip(range(12, 18), indicadores, strict=True):
        rotulo(ws, linha, nome)
        formula(ws, linha, 2, expr, fmt)
    titulo(ws, 19, "Condições para atender")
    cabecalho(ws, 20, ["Condição"])
    entrada(ws, 21, 25, 1, 1)
    titulo(ws, 27, "Pontos de maior risco")
    cabecalho(ws, 28, ["Ponto", "Exigência ou item", "Por que é risco", "Como reduzir"])
    entrada(ws, 29, 38, 1, 4)
    titulo(ws, 40, "Pontos para a analista decidir")
    cabecalho(ws, 41, ["Ponto", "Prazo"])
    entrada(ws, 42, 46, 1, 2)

    aba_documentos(wb)

    ws = wb.create_sheet("Itens")
    cabecalho(
        ws,
        1,
        [
            "Lote",
            "Item",
            "Descrição (como no edital)",
            "Especificação que restringe",
            "Marca ou modelo de referência",
            "Unidade",
            "Quantidade",
            "Valor unitário estimado (R$)",
            "Valor total estimado (R$)",
            "Código CATMAT",
            "Fonte (documento e item)",
            "Atendemos?",
            "Marca e modelo que seriam ofertados",
            "Observação",
        ],
        [8, 8, 55, 40, 26, 10, 12, 16, 16, 14, 22, 14, 30, 34],
    )
    entrada(ws, 2, 1001, 1, 8)
    entrada(ws, 2, 1001, 10, 14)
    for linha in range(2, 1002):
        formula(
            ws,
            linha,
            9,
            f"=IF(COUNT(G{linha},H{linha})=2,G{linha}*H{linha},0)",
            "#,##0.00",
            negrito=False,
        )
    lista(ws, "L2:L1001", ["Sim", "Não", "A confirmar"])
    ws.freeze_panes = "D2"

    ws = wb.create_sheet("Exigências técnicas")
    cabecalho(
        ws,
        1,
        [
            "ID",
            "Tipo",
            "Exigência",
            "Itens ou lotes abrangidos",
            "Documento (ID)",
            "Seção / item / página",
            "Quando é exigida",
            "Prazo",
            "Risco",
            "Pendência (ID)",
        ],
        [8, 26, 60, 22, 14, 22, 24, 16, 10, 14],
    )
    entrada(ws, 2, 300, 1, 10)
    lista(
        ws,
        "B2:B300",
        [
            "Amostra ou prova de conceito",
            "Catálogo ou ficha técnica",
            "Certificação ou registro",
            "Carta do fabricante",
            "Garantia",
            "Assistência técnica",
            "Validade mínima",
            "Atestado de fornecimento",
            "Outra",
        ],
    )
    lista(
        ws,
        "G2:G300",
        ["Na proposta", "Na habilitação", "Após convocação", "Na entrega", "Na assinatura"],
    )
    lista(ws, "I2:I300", ["Alto", "Médio", "Baixo"])
    ws.freeze_panes = "D2"

    ws = wb.create_sheet("Entrega")
    cabecalho(
        ws,
        1,
        [
            "Local de entrega",
            "Cidade / UF",
            "Itens ou lotes",
            "Prazo de entrega (dias)",
            "Prazo conta a partir de",
            "Entrega parcelada?",
            "Frete e descarga por conta de",
            "Instalação, montagem ou treinamento",
            "Recebimento (provisório e definitivo)",
            "Fonte (documento e item)",
        ],
        [40, 18, 18, 14, 26, 16, 22, 34, 34, 22],
    )
    entrada(ws, 2, 100, 1, 10)
    lista(ws, "F2:F100", ["Sim", "Não", "Edital não diz"])
    lista(ws, "G2:G100", ["Contratada", "Órgão", "Edital não diz"])
    ws.freeze_panes = "A2"

    ws = wb.create_sheet("Condições comerciais")
    cabecalho(
        ws,
        1,
        ["Condição", "O que o edital diz", "Fonte (documento e item)", "Risco"],
        [44, 70, 26, 10],
    )
    condicoes = [
        "Vigência da ata ou do contrato",
        "Quantidade mínima por pedido",
        "Adesão de outros órgãos (carona)",
        "Cota reservada ou exclusividade para ME/EPP",
        "Margem de preferência",
        "Prazo de pagamento",
        "Reajuste",
        "Garantia contratual",
        "Multa por atraso na entrega",
        "Outras penalidades",
        "Troca de marca ou modelo durante a execução",
        "Subcontratação",
    ]
    for linha, nome in enumerate(condicoes, 2):
        ws.cell(linha, 1, nome).border = BORDA
        entrada(ws, linha, linha, 2, 4)
    entrada(ws, len(condicoes) + 2, len(condicoes) + 11, 1, 4)
    lista(ws, f"D2:D{len(condicoes) + 11}", ["Alto", "Médio", "Baixo"])
    ws.freeze_panes = "A2"

    aba_pendencias(
        wb,
        [
            "Divergência",
            "Dado ausente",
            "Esclarecimento",
            "Levar à análise geral",
            "Confirmar com a equipe",
        ],
    )

    ex = "'Exigências técnicas'"
    aba_checks(
        wb,
        [
            ("Nenhum item lançado (1 = falta)", "=IF(COUNTA(Itens!C2:C1001)>0,0,1)"),
            ("Itens sem quantidade", '=COUNTIFS(Itens!C2:C1001,"<>",Itens!G2:G1001,"")'),
            ("Itens sem unidade", '=COUNTIFS(Itens!C2:C1001,"<>",Itens!F2:F1001,"")'),
            ("Itens sem fonte", '=COUNTIFS(Itens!C2:C1001,"<>",Itens!K2:K1001,"")'),
            (
                "Itens sem resposta em Atendemos?",
                '=COUNTIFS(Itens!C2:C1001,"<>",Itens!L2:L1001,"")',
            ),
            ("Exigências técnicas sem tipo", f'=COUNTIFS({ex}!C2:C300,"<>",{ex}!B2:B300,"")'),
            (
                "Exigências técnicas sem documento de origem",
                f'=COUNTIFS({ex}!C2:C300,"<>",{ex}!E2:E300,"")',
            ),
            (
                "Exigências técnicas sem classificação de risco",
                f'=COUNTIFS({ex}!C2:C300,"<>",{ex}!I2:I300,"")',
            ),
            ("Locais de entrega sem prazo", '=COUNTIFS(Entrega!A2:A100,"<>",Entrega!D2:D100,"")'),
            ("Nenhum local de entrega lançado (1 = falta)", "=IF(COUNTA(Entrega!A2:A100)>0,0,1)"),
            (
                "Pendências sem ação sugerida",
                '=COUNTIFS(Pendências!C2:C100,"<>",Pendências!F2:F100,"")',
            ),
            ("Conclusão não preenchida (1 = falta)", '=IF(Resumo!B10="",1,0)'),
        ],
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)


def manutencao_v2(destino: Path):
    """A planilha de manutenção é gerada pelo script da própria skill (layout do modelo de exequibilidade)."""
    import sys

    sys.path.insert(0, str(SKILLS / "analisar-edital-manutencao/scripts"))
    import planilha

    planilha.build(None, destino)


if __name__ == "__main__":
    manutencao_v2(SKILLS / "analisar-edital-manutencao/assets/modelo-analise-manutencao.xlsx")
    fornecimento(SKILLS / "analisar-edital-fornecimento/assets/modelo-analise-fornecimento.xlsx")
    print("modelos gerados")
