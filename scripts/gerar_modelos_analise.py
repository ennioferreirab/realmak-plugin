"""Gera as planilhas-modelo das skills de análise de edital.

Uso (a partir da raiz do repositório):

    uv run --with openpyxl python scripts/gerar_modelos_analise.py

Grava:
    plugins/realmak/skills/analisar-edital-manutencao/assets/modelo-analise-manutencao.xlsx
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


# --------------------------------------------------------------------------- manutenção


def manutencao(destino: Path):
    wb = Workbook()
    instrucoes(
        wb,
        [
            "Análise de edital de manutenção: modelo de planilha",
            "",
            "Células amarelas são entradas. Células cinza são fórmulas: não sobrescreva.",
            "Preencha na ordem das abas: Documentos, Requisitos, Divergências, Escopo, Peças e materiais, "
            "Dimensionamento, Pendências e, por último, Conclusão.",
            "IDs: D-01 para documentos, R-01 para requisitos, P-01 para pendências. Use os IDs sempre que uma aba citar outra.",
            "Aba Requisitos: só o que afeta a execução do serviço e a qualificação técnica. "
            "Prazos do certame e habilitação jurídica, fiscal e econômica ficam na análise geral do edital.",
            "Aba Escopo: cada atividade recebe um Tipo de carga (Programada, Não programada ou Indireta). "
            "O Dimensionamento soma as horas por esse tipo.",
            "Aba Checks: todas as linhas devem estar em OK antes da entrega.",
            "Os arquivos analise-manutencao.md e analise-manutencao.html repetem os números calculados aqui. "
            "Se houver diferença, vale esta planilha.",
        ],
    )

    ws = wb.create_sheet("Conclusão")
    ws.column_dimensions["A"].width = 40
    for col, largura in zip("BCD", (50, 45, 45), strict=True):
        ws.column_dimensions[col].width = largura
    titulo(ws, 1, "Identificação")
    campos = [
        "Órgão / unidade",
        "Edital e processo",
        "Objeto",
        "Vigência",
        "Valor estimado",
        "Data desta análise",
    ]
    for linha, nome in enumerate(campos, 2):
        rotulo(ws, linha, nome)
        entrada(ws, linha, linha, 2, 2)
    titulo(ws, 9, "1. Conclusão de exequibilidade operacional")
    rotulo(ws, 10, "Conclusão")
    entrada(ws, 10, 10, 2, 2)
    lista(ws, "B10", ["Atende", "Atende com condições", "Não atende"])
    rotulo(ws, 11, "Justificativa (até cinco linhas)")
    entrada(ws, 11, 11, 2, 2)
    ws.row_dimensions[11].height = 90
    rotulo(ws, 12, "Horas requeridas por mês")
    formula(ws, 12, 2, "=Dimensionamento!B35", "#,##0.0")
    rotulo(ws, 13, "Horas disponíveis por mês")
    formula(ws, 13, 2, "=Dimensionamento!B36", "#,##0.0")
    rotulo(ws, 14, "Cobertura da equipe")
    formula(ws, 14, 2, "=Dimensionamento!B37", "0%")
    rotulo(ws, 15, "Folga (horas por mês)")
    formula(ws, 15, 2, "=Dimensionamento!B38", "#,##0.0")
    titulo(ws, 17, "Condições para atender")
    cabecalho(ws, 18, ["Condição"])
    entrada(ws, 19, 23, 1, 1)
    titulo(ws, 25, "Gargalos de capacidade")
    cabecalho(ws, 26, ["Gargalo", "Onde está demonstrado"])
    entrada(ws, 27, 31, 1, 2)
    titulo(ws, 33, "Obrigações de maior risco")
    cabecalho(ws, 34, ["Obrigação", "Requisito (ID)", "Por que é risco", "Como reduzir"])
    entrada(ws, 35, 44, 1, 4)
    titulo(ws, 46, "Pontos para a analista decidir")
    cabecalho(ws, 47, ["Ponto", "Prazo"])
    entrada(ws, 48, 52, 1, 2)

    aba_documentos(wb)

    ws = wb.create_sheet("Requisitos")
    cabecalho(
        ws,
        1,
        [
            "ID",
            "Grupo",
            "Requisito",
            "Documento (ID)",
            "Seção / item / página / aba",
            "Quantidade",
            "Unidade de medição",
            "Periodicidade",
            "Custo afetado",
            "Risco",
            "Pendência (ID)",
        ],
        [8, 22, 60, 14, 24, 12, 16, 16, 24, 10, 14],
    )
    entrada(ws, 2, 500, 1, 11)
    lista(
        ws,
        "B2:B500",
        ["Execução", "SLA e penalidades", "Peças e materiais", "Qualificação técnica"],
    )
    lista(ws, "J2:J500", ["Alto", "Médio", "Baixo"])
    ws.freeze_panes = "D2"

    ws = wb.create_sheet("Divergências")
    cabecalho(
        ws,
        1,
        ["Item", "Contagem A", "Fonte A", "Contagem B", "Fonte B", "Adotada", "Motivo"],
        [40, 14, 24, 14, 24, 10, 50],
    )
    entrada(ws, 2, 60, 1, 7)
    lista(ws, "F2:F60", ["A", "B"])
    ws.freeze_panes = "A2"

    ws = wb.create_sheet("Escopo")
    cabecalho(
        ws,
        1,
        [
            "Bloco",
            "Tipo de carga",
            "Atividade",
            "Requisito (ID)",
            "Frequência anual",
            "Volume",
            "Unidade do volume",
            "Tempo por execução (h)",
            "Horas por ano",
            "Profissional",
            "Recurso necessário",
        ],
        [24, 18, 50, 14, 12, 10, 16, 14, 14, 24, 34],
    )
    entrada(ws, 2, 201, 1, 8)
    entrada(ws, 2, 201, 10, 11)
    for linha in range(2, 202):
        formula(
            ws,
            linha,
            9,
            f"=IF(COUNT(E{linha},F{linha},H{linha})=3,E{linha}*F{linha}*H{linha},0)",
            "#,##0.0",
            negrito=False,
        )
    lista(
        ws,
        "A2:A201",
        [
            "Preventiva",
            "Corretiva",
            "Documentação",
            "Sistema de gestão",
            "Treinamento e suporte",
            "Logística",
            "Responsabilidade técnica",
            "Mobilização",
        ],
    )
    lista(ws, "B2:B201", ["Programada", "Não programada", "Indireta"])
    ws.freeze_panes = "D2"
    rotulo(ws, 203, "Blocos sem aplicação neste certame (e motivo)")
    entrada(ws, 204, 204, 1, 11)

    ws = wb.create_sheet("Peças e materiais")
    cabecalho(
        ws,
        1,
        [
            "Item",
            "Tipo",
            "Requisito (ID)",
            "Como é pago",
            "Quantidade estimada por ano",
            "Unidade",
            "Base da estimativa",
            "Regra do edital (autorização, teto, estoque mínimo)",
            "Observação",
        ],
        [44, 16, 14, 22, 16, 12, 34, 44, 34],
    )
    entrada(ws, 2, 300, 1, 9)
    lista(ws, "B2:B300", ["Peça", "Insumo", "Material", "Kit preventivo"])
    lista(
        ws,
        "D2:D300",
        ["Incluído no preço", "Cobrado à parte", "Fornecido pelo órgão", "Edital não diz"],
    )
    ws.freeze_panes = "B2"

    ws = wb.create_sheet("Dimensionamento")
    for col, largura in zip("ABCDEF", (42, 22, 26, 32, 24, 44), strict=True):
        ws.column_dimensions[col].width = largura
    titulo(ws, 1, "5.1 Premissas")
    cabecalho(ws, 2, ["Premissa", "Valor", "Tipo", "O que muda se estiver errada"])
    entrada(ws, 3, 12, 1, 4)
    lista(ws, "C3:C12", ["(D) dado do documento", "(C) cálculo", "(P) premissa"])
    titulo(ws, 14, "5.2 Carga de trabalho")
    cabecalho(ws, 15, ["Bloco de carga", "Horas por ano", "Horas por mês", "Base do cálculo"])
    for linha, nome in zip(
        (16, 17, 18), ("Programada", "Não programada", "Indireta"), strict=True
    ):
        ws.cell(linha, 1, nome).border = BORDA
        formula(ws, linha, 2, f"=SUMIF(Escopo!$B$2:$B$201,A{linha},Escopo!$I$2:$I$201)", "#,##0.0")
        formula(ws, linha, 3, f"=B{linha}/12", "#,##0.0")
        entrada(ws, linha, linha, 4, 4)
    rotulo(ws, 19, "Total requerido")
    formula(ws, 19, 2, "=SUM(B16:B18)", "#,##0.0")
    formula(ws, 19, 3, "=SUM(C16:C18)", "#,##0.0")
    titulo(ws, 21, "5.3 Capacidade da equipe")
    cabecalho(
        ws,
        22,
        [
            "Profissional",
            "Quantidade",
            "Horas brutas por mês (por pessoa)",
            "Descontos por mês (h, por pessoa)",
            "Horas produtivas por mês",
            "Descontos considerados",
        ],
    )
    for linha in range(23, 31):
        entrada(ws, linha, linha, 1, 4)
        entrada(ws, linha, linha, 6, 6)
        formula(
            ws,
            linha,
            5,
            f"=IF(COUNT(B{linha},C{linha})=2,B{linha}*(C{linha}-N(D{linha})),0)",
            "#,##0.0",
        )
    rotulo(ws, 31, "Total disponível")
    formula(ws, 31, 5, "=SUM(E23:E30)", "#,##0.0")
    titulo(ws, 33, "5.4 Resultado")
    cabecalho(ws, 34, ["Indicador", "Valor"])
    resultado = [
        ("Horas requeridas por mês", "=C19", "#,##0.0"),
        ("Horas disponíveis por mês", "=E31", "#,##0.0"),
        ("Cobertura (disponíveis ÷ requeridas)", '=IF(B35>0,B36/B35,"")', "0%"),
        ("Folga (disponíveis − requeridas)", "=B36-B35", "#,##0.0"),
    ]
    for linha, (nome, expr, fmt) in zip(range(35, 39), resultado, strict=True):
        ws.cell(linha, 1, nome).border = BORDA
        formula(ws, linha, 2, expr, fmt)
    titulo(ws, 40, "5.5 Testes")
    cabecalho(
        ws,
        41,
        [
            "Teste",
            "Exigência (com ID do requisito)",
            "Carga",
            "Capacidade",
            "Resultado",
            "Observação",
        ],
    )
    ws.cell(42, 1, "Primeiro ciclo (horas)").border = BORDA
    entrada(ws, 42, 42, 2, 4)
    entrada(ws, 42, 42, 6, 6)
    formula(ws, 42, 5, '=IF(COUNT(C42,D42)=2,IF(D42>=C42,"Atende","Não atende"),"")')
    ws.cell(43, 1, "Pior SLA").border = BORDA
    entrada(ws, 43, 43, 2, 6)
    lista(ws, "E43", ["Atende", "Não atende"])
    titulo(ws, 45, "5.6 Conclusão sobre a equipe")
    for linha, nome in zip(
        (46, 47, 48),
        (
            "Mínimo exigido na qualificação técnica (com ID do requisito)",
            "Equipe necessária pelo cálculo de carga",
            "Explicação da diferença, se houver",
        ),
        strict=True,
    ):
        rotulo(ws, linha, nome)
        entrada(ws, linha, linha, 2, 4)

    aba_pendencias(wb, ["Divergência", "Dado ausente", "Esclarecimento", "Levar à análise geral"])

    aba_checks(
        wb,
        [
            ("Requisitos sem grupo", '=COUNTIFS(Requisitos!C2:C500,"<>",Requisitos!B2:B500,"")'),
            (
                "Requisitos sem documento de origem",
                '=COUNTIFS(Requisitos!C2:C500,"<>",Requisitos!D2:D500,"")',
            ),
            (
                "Requisitos sem seção, item, página ou aba",
                '=COUNTIFS(Requisitos!C2:C500,"<>",Requisitos!E2:E500,"")',
            ),
            (
                "Requisitos sem classificação de risco",
                '=COUNTIFS(Requisitos!C2:C500,"<>",Requisitos!J2:J500,"")',
            ),
            (
                "Atividades do escopo sem tipo de carga",
                '=COUNTIFS(Escopo!C2:C201,"<>",Escopo!B2:B201,"")',
            ),
            (
                "Atividades do escopo com zero hora por ano",
                '=COUNTIFS(Escopo!C2:C201,"<>",Escopo!I2:I201,0)',
            ),
            (
                "Atividades do escopo sem requisito de origem",
                '=COUNTIFS(Escopo!C2:C201,"<>",Escopo!D2:D201,"")',
            ),
            (
                "Peças e materiais sem forma de pagamento",
                "=COUNTIFS('Peças e materiais'!A2:A300,\"<>\",'Peças e materiais'!D2:D300,\"\")",
            ),
            ("Carga requerida não calculada (1 = falta)", "=IF(Dimensionamento!C19>0,0,1)"),
            ("Capacidade da equipe não informada (1 = falta)", "=IF(Dimensionamento!E31>0,0,1)"),
            ("Teste de pior SLA sem resultado (1 = falta)", '=IF(Dimensionamento!E43="",1,0)'),
            (
                "Pendências sem ação sugerida",
                '=COUNTIFS(Pendências!C2:C100,"<>",Pendências!F2:F100,"")',
            ),
            ("Conclusão não preenchida (1 = falta)", '=IF(Conclusão!B10="",1,0)'),
        ],
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)


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


if __name__ == "__main__":
    manutencao(SKILLS / "analisar-edital-manutencao/assets/modelo-analise-manutencao.xlsx")
    fornecimento(SKILLS / "analisar-edital-fornecimento/assets/modelo-analise-fornecimento.xlsx")
    print("modelos gerados")
