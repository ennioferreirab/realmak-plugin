"""Planilha de análise de manutenção no layout do Modelo de Proposta e Exequibilidade.

build(data, destino): data=None gera o modelo em branco.
"""

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.datavalidation import DataValidation

TITULO_BG, SECAO_BG, CAB_BG = "164E63", "0F766E", "BAE6FD"
SUB_BG, ENTRADA_BG, TXT, TXT2 = "F8FAFC", "FFF2CC", "1F2937", "475569"
VERDE, VERDE_TX, LARANJA, LARANJA_TX, VERM, VERM_TX = (
    "DCFCE7",
    "166534",
    "FFEDD5",
    "9A3412",
    "FEE2E2",
    "991B1B",
)
FONTE = "Aptos"
fino = Side(style="thin", color="CBD5E1")
BORDA = Border(left=fino, right=fino, top=fino, bottom=fino)


def fill(c):
    return PatternFill("solid", fgColor=c)


class Folha:
    def __init__(self, wb, nome, titulo, subtitulo, larguras, primeira=False):
        self.ws = wb.active if primeira else wb.create_sheet(nome)
        self.ws.title = nome
        self.ws.sheet_view.showGridLines = False
        self.ncol = len(larguras)
        for i, w in enumerate(larguras, 1):
            self.ws.column_dimensions[L(i)].width = w
        self.barra(
            1,
            titulo,
            TITULO_BG,
            Font(name=FONTE + " Display", size=15, bold=True, color="FFFFFF"),
            30,
        )
        self.ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=self.ncol)
        c = self.ws.cell(2, 1, subtitulo)
        c.fill, c.font = fill(SUB_BG), Font(name=FONTE, size=10, color=TXT2)
        c.alignment = Alignment(wrap_text=True, vertical="center")
        self.ws.row_dimensions[2].height = 30
        self.r = 4

    def barra(self, r, texto, bg, font, h):
        self.ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=self.ncol)
        c = self.ws.cell(r, 1, texto)
        c.fill, c.font = fill(bg), font
        c.alignment = Alignment(vertical="center", indent=1)
        self.ws.row_dimensions[r].height = h

    def secao(self, texto):
        self.barra(
            self.r, texto, SECAO_BG, Font(name=FONTE, size=10, bold=True, color="FFFFFF"), 24
        )
        self.r += 1

    def cabecalho(self, nomes):
        for i, n in enumerate(nomes, 1):
            c = self.ws.cell(self.r, i, n)
            c.fill, c.border = fill(CAB_BG), BORDA
            c.font = Font(name=FONTE, size=10, bold=True, color=TXT)
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        self.ws.row_dimensions[self.r].height = 28
        self.r += 1

    def linha(
        self,
        valores,
        entrada=None,
        formulas=(),
        formatos=None,
        negrito=False,
        bg=None,
        altura=None,
    ):
        """entrada: colunas (1-based) amarelas. formulas: colunas cinza-claro de resultado."""
        r = self.r
        for i in range(1, self.ncol + 1):
            v = valores[i - 1] if i - 1 < len(valores) else None
            c = self.ws.cell(r, i)
            if v is not None:
                c.value = v
            c.border = BORDA
            c.font = Font(name=FONTE, size=10, bold=negrito, color=TXT)
            c.alignment = Alignment(vertical="top", wrap_text=True)
            if bg:
                c.fill = fill(bg)
            elif entrada and i in entrada:
                c.fill = fill(ENTRADA_BG)
            elif i in formulas:
                c.fill = fill(SUB_BG)
            if formatos and i in formatos:
                c.number_format = formatos[i]
        if altura:
            self.ws.row_dimensions[r].height = altura
        self.r += 1
        return r

    def subsecao(self, texto):
        """Linha de grupo dentro de uma tabela, como 'A. Identificação'."""
        self.ws.merge_cells(start_row=self.r, start_column=1, end_row=self.r, end_column=self.ncol)
        c = self.ws.cell(self.r, 1, texto)
        c.fill, c.font, c.border = (
            fill("E0F2FE"),
            Font(name=FONTE, size=10, bold=True, color=TITULO_BG),
            BORDA,
        )
        self.r += 1

    def texto(self, texto, altura=None, bg=SUB_BG, negrito=False, cor=TXT2):
        self.ws.merge_cells(start_row=self.r, start_column=1, end_row=self.r, end_column=self.ncol)
        c = self.ws.cell(self.r, 1, texto)
        c.fill, c.font = fill(bg), Font(name=FONTE, size=10, bold=negrito, color=cor)
        c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
        if altura:
            self.ws.row_dimensions[self.r].height = altura
        self.r += 1

    def lista(self, coluna, opcoes, r1, r2):
        dv = DataValidation(type="list", formula1='"' + ",".join(opcoes) + '"', allow_blank=True)
        self.ws.add_data_validation(dv)
        dv.add(f"{L(coluna)}{r1}:{L(coluna)}{r2}")

    def risco_cores(self, rng):
        ws = self.ws
        for txt, bg, fg in (
            ("Alto", VERM, VERM_TX),
            ("Médio", LARANJA, LARANJA_TX),
            ("Baixo", VERDE, VERDE_TX),
        ):
            ws.conditional_formatting.add(
                rng,
                FormulaRule(
                    formula=[f'EXACT({rng.split(":")[0]},"{txt}")'],
                    fill=fill(bg),
                    font=Font(color=fg, bold=True),
                ),
            )


def cartao(f, linha, col, titulo, formula, formato):
    ws = f.ws
    ws.merge_cells(start_row=linha, start_column=col, end_row=linha, end_column=col + 1)
    c = ws.cell(linha, col, titulo)
    c.fill, c.font = fill(CAB_BG), Font(name=FONTE, size=10, bold=True, color=TXT)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells(start_row=linha + 1, start_column=col, end_row=linha + 2, end_column=col + 1)
    v = ws.cell(linha + 1, col, formula)
    v.fill, v.font, v.number_format = (
        fill(SUB_BG),
        Font(name=FONTE, size=14, bold=True, color=TXT),
        formato,
    )
    v.alignment = Alignment(horizontal="center", vertical="center")
    for rr in range(linha, linha + 3):
        for cc in (col, col + 1):
            ws.cell(rr, cc).border = BORDA


def pad(lst, n, vazio):
    lst = list(lst or [])
    return lst + [vazio] * max(0, n - len(lst))


def build(D, destino):
    wb = Workbook()
    wb.remove(wb.active)
    v = D or {}
    ident = v.get("ident", {})
    N = {
        k: max(len(v.get(k, [])) + 3, m)
        for k, m in (
            ("requisitos", 40),
            ("escopo", 25),
            ("pecas", 20),
            ("pontos", 20),
            ("nobreaks", 40),
            ("geradores", 15),
            ("premissas", 12),
            ("documentos", 10),
            ("equipe", 5),
            ("condicoes", 6),
            ("riscos", 6),
            ("decisoes", 4),
            ("dados", 0),
        )
    }

    # ------------------------------------------------------------- abas de dados primeiro (refs)
    # Equipamentos
    eq = Folha(
        wb,
        "Equipamentos",
        "PARQUE DE EQUIPAMENTOS COBERTOS",
        "Transcreva o inventário do TR, uma linha por grupo de equipamentos iguais. A faixa define o prazo de atendimento.",
        [8, 12, 26, 52, 14, 18],
    )
    eq.secao("NOBREAKS")
    eq.cabecalho(["Qtd", "Potência (kVA)", "Fabricante", "Localização", "Faixa", "Fonte"])
    nb1 = eq.r
    for row in pad(v.get("nobreaks"), N["nobreaks"], ()):
        eq.linha(list(row), entrada=range(1, 7), formatos={2: "0.0#"})
    nb2 = eq.r - 1
    tot_nb = eq.linha(["Total", None, "Com 60 kVA ou mais:", None], negrito=True, bg=SUB_BG)
    eq.ws.cell(tot_nb, 2, f"=SUM(A{nb1}:A{nb2})")
    eq.ws.cell(tot_nb, 4, f'=SUMIFS(A{nb1}:A{nb2},B{nb1}:B{nb2},">=60")')
    eq.r += 1
    eq.secao("GRUPOS GERADORES")
    eq.cabecalho(["Qtd", "Potência (kVA)", "Fabricante", "Localização", "Faixa", "Fonte"])
    gr1 = eq.r
    for row in pad(v.get("geradores"), N["geradores"], ()):
        eq.linha(list(row), entrada=range(1, 7))
    gr2 = eq.r - 1
    tot_gr = eq.linha(["Total", None, "Com 150 kVA ou mais:", None], negrito=True, bg=SUB_BG)
    eq.ws.cell(tot_gr, 2, f"=SUM(A{gr1}:A{gr2})")
    eq.ws.cell(tot_gr, 4, f'=SUMIFS(A{gr1}:A{gr2},B{gr1}:B{gr2},">=150")')
    eq.lista(5, ["Faixa 1 · 4 h", "Faixa 2 · 8 h", "Faixa 3 · 24 h", "Sem faixa"], nb1, gr2)

    # Escopo e carga
    es = Folha(
        wb,
        "Escopo e Carga",
        "ESCOPO, ATIVIDADES E CARGA DE TRABALHO",
        "Cada obrigação do TR vira uma atividade com frequência, volume e tempo. As horas por ano são calculadas; o tipo de carga alimenta o Dimensionamento.",
        [20, 16, 48, 11, 11, 9, 12, 11, 12, 22, 30],
    )
    es.cabecalho(
        [
            "Bloco",
            "Tipo de carga",
            "Atividade",
            "Requisito",
            "Frequência anual",
            "Volume",
            "Unidade",
            "Tempo por execução (h)",
            "Horas por ano",
            "Profissional",
            "Recurso necessário",
        ]
    )
    e1 = es.r
    for row in pad(v.get("escopo"), N["escopo"], ()):
        row = list(row) + [None] * 11
        r = es.linha(
            row[:8] + [None] + row[8:10],
            entrada=[1, 2, 3, 4, 5, 6, 7, 8, 10, 11],
            formulas=[9],
            formatos={9: "#,##0.0", 8: "0.0"},
        )
        es.ws.cell(r, 9, f"=IF(COUNT(E{r},F{r},H{r})=3,E{r}*F{r}*H{r},0)")
    e2 = es.r - 1
    tot_es = es.linha(
        ["Total", None, None, None, None, None, None, None],
        negrito=True,
        bg=SUB_BG,
        formatos={9: "#,##0.0"},
    )
    es.ws.cell(tot_es, 9, f"=SUM(I{e1}:I{e2})")
    es.lista(
        1,
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
        e1,
        e2,
    )
    es.lista(2, ["Programada", "Não programada", "Indireta"], e1, e2)
    es.r += 1
    es.secao("BLOCOS SEM APLICAÇÃO NESTE CERTAME")
    es.texto(v.get("escopo_na", ""), altura=36, bg=ENTRADA_BG, cor=TXT)

    # Dimensionamento
    dm = Folha(
        wb,
        "Dimensionamento",
        "DIMENSIONAMENTO DA EQUIPE",
        "Compare a carga requerida com as horas produtivas reais. Premissas em amarelo; resultados calculados.",
        [44, 18, 22, 30, 20, 40],
    )
    dm.secao("PREMISSAS")
    dm.cabecalho(["Premissa", "Valor", "Tipo", "O que muda se estiver errada", None, None])
    p1 = dm.r
    for row in pad(v.get("premissas"), N["premissas"], ()):
        dm.linha(list(row), entrada=[1, 2, 3, 4])
    dm.lista(3, ["(D) dado do documento", "(C) cálculo", "(P) premissa"], p1, dm.r - 1)
    dm.r += 1
    dm.secao("CARGA DE TRABALHO")
    dm.cabecalho(
        ["Tipo de carga", "Horas por ano", "Horas por mês", "Base do cálculo", None, None]
    )
    cg = {}
    for t in ("Programada", "Não programada", "Indireta"):
        r = dm.linha(
            [t, None, None, v.get("base_carga", {}).get(t)],
            entrada=[4],
            formulas=[2, 3],
            formatos={2: "#,##0.0", 3: "#,##0.0"},
        )
        dm.ws.cell(
            r, 2, f"=SUMIF('Escopo e Carga'!$B${e1}:$B${e2},A{r},'Escopo e Carga'!$I${e1}:$I${e2})"
        )
        dm.ws.cell(r, 3, f"=B{r}/12")
        cg[t] = r
    rt = dm.linha(
        ["Total requerido"], negrito=True, bg=SUB_BG, formatos={2: "#,##0.0", 3: "#,##0.0"}
    )
    dm.ws.cell(rt, 2, f"=SUM(B{cg['Programada']}:B{cg['Indireta']})")
    dm.ws.cell(rt, 3, f"=SUM(C{cg['Programada']}:C{cg['Indireta']})")
    dm.r += 1
    dm.secao("CAPACIDADE DA EQUIPE")
    dm.cabecalho(
        [
            "Profissional",
            "Quantidade",
            "Horas brutas por mês (por pessoa)",
            "Descontos por mês (h, por pessoa)",
            "Horas produtivas por mês",
            "Descontos considerados",
        ]
    )
    q1 = dm.r
    for row in pad(v.get("equipe"), N["equipe"], ()):
        row = list(row) + [None] * 6
        r = dm.linha(
            row[:4] + [None, row[4]],
            entrada=[1, 2, 3, 4, 6],
            formulas=[5],
            formatos={5: "#,##0.0"},
        )
        dm.ws.cell(r, 5, f"=IF(COUNT(B{r},C{r})=2,B{r}*(C{r}-N(D{r})),0)")
    q2 = dm.r - 1
    rd = dm.linha(["Total disponível"], negrito=True, bg=SUB_BG, formatos={5: "#,##0.0"})
    dm.ws.cell(rd, 5, f"=SUM(E{q1}:E{q2})")
    dm.r += 1
    dm.secao("RESULTADO")
    dm.cabecalho(["Indicador", "Valor", None, None, None, None])
    R = {}
    for k, nome, f, fmt in (
        ("req", "Horas requeridas por mês", f"=C{rt}", "#,##0.0"),
        ("disp", "Horas disponíveis por mês", f"=E{rd}", "#,##0.0"),
        ("cob", "Cobertura (disponíveis ÷ requeridas)", None, "0.0%"),
        ("folga", "Folga (disponíveis − requeridas)", None, "#,##0.0"),
    ):
        R[k] = dm.linha([nome, f], formulas=[2], formatos={2: fmt})
    dm.ws.cell(R["cob"], 2, f'=IF(B{R["req"]}>0,B{R["disp"]}/B{R["req"]},"")')
    dm.ws.cell(R["folga"], 2, f"=B{R['disp']}-B{R['req']}")
    dm.r += 1
    dm.secao("TESTES")
    dm.cabecalho(
        [
            "Teste",
            "Exigência (com ID do requisito)",
            "Carga",
            "Capacidade",
            "Resultado",
            "Observação",
        ]
    )
    t = v.get("testes", {})
    tc = t.get("ciclo", [None] * 5)
    rc = dm.linha(
        ["Primeiro ciclo (horas)", tc[0], tc[1], tc[2], None, tc[4] if len(tc) > 4 else None],
        entrada=[2, 3, 4, 6],
        formulas=[5],
        formatos={3: "#,##0.0", 4: "#,##0.0"},
    )
    dm.ws.cell(rc, 5, f'=IF(COUNT(C{rc},D{rc})=2,IF(D{rc}>=C{rc},"Atende","Não atende"),"")')
    ts = t.get("sla", [None] * 5)
    rs = dm.linha(["Pior SLA"] + list(ts), entrada=[2, 3, 4, 5, 6])
    dm.lista(5, ["Atende", "Não atende"], rs, rs)
    dm.r += 1
    dm.secao("CONCLUSÃO SOBRE A EQUIPE")
    ce = v.get("conclusao_equipe", [None] * 3)
    ce_r = []
    for nome, val in zip(
        (
            "Mínimo exigido na qualificação técnica",
            "Equipe necessária pelo cálculo de carga",
            "Explicação da diferença",
        ),
        ce,
        strict=False,
    ):
        r = dm.linha([nome, val], entrada=[2], altura=32)
        dm.ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        ce_r.append(r)

    # Peças e materiais
    pc = Folha(
        wb,
        "Peças e Materiais",
        "PEÇAS, INSUMOS E MATERIAIS EXIGIDOS",
        "O que o serviço exige e como cada item é pago. Preço e cotação ficam para a precificação.",
        [42, 12, 11, 20, 12, 12, 32, 46, 30],
    )
    pc.cabecalho(
        [
            "Item",
            "Tipo",
            "Requisito",
            "Como é pago",
            "Quantidade estimada por ano",
            "Unidade",
            "Base da estimativa",
            "Regra do edital",
            "Observação",
        ]
    )
    c1 = pc.r
    for row in pad(v.get("pecas"), N["pecas"], ()):
        pc.linha(list(row), entrada=range(1, 10))
    c2 = pc.r - 1
    pc.lista(2, ["Peça", "Insumo", "Material", "Kit preventivo"], c1, c2)
    pc.lista(
        4,
        ["Incluído no preço", "Cobrado à parte", "Fornecido pelo órgão", "Edital não diz"],
        c1,
        c2,
    )

    # Requisitos
    rq = Folha(
        wb,
        "Requisitos",
        "MATRIZ DE REQUISITOS DE EXECUÇÃO",
        "Cada exigência do serviço ligada à fonte. Prazos do certame e habilitação jurídica, fiscal e econômica ficam na análise geral do edital.",
        [8, 18, 54, 26, 11, 14, 14, 22, 10, 11],
    )
    rq.cabecalho(
        [
            "ID",
            "Grupo",
            "Requisito",
            "Fonte",
            "Quantidade",
            "Unidade",
            "Periodicidade",
            "Custo afetado",
            "Risco",
            "Pendência",
        ]
    )
    q_1 = rq.r
    for row in pad(v.get("requisitos"), N["requisitos"], ()):
        rq.linha(list(row), entrada=range(1, 11))
    q_2 = rq.r - 1
    rq.lista(
        2, ["Execução", "SLA e penalidades", "Peças e materiais", "Qualificação técnica"], q_1, q_2
    )
    rq.lista(9, ["Alto", "Médio", "Baixo"], q_1, q_2)
    rq.risco_cores(f"I{q_1}:I{q_2}")
    rq.ws.freeze_panes = f"C{q_1}"

    # Pontos de atenção
    pa = Folha(
        wb,
        "Pontos de Atenção",
        "PONTOS DE ATENÇÃO, DIVERGÊNCIAS E PENDÊNCIAS",
        "Divergências entre documentos, dados ausentes e o que levar à análise geral. Cada ponto tem providência e prazo.",
        [8, 20, 56, 26, 30, 40, 16],
    )
    pa.cabecalho(
        [
            "Nº",
            "Tipo",
            "Ponto de atenção",
            "Onde consta",
            "Impacto",
            "Providência sugerida",
            "Prazo",
        ]
    )
    a1 = pa.r
    for row in pad(v.get("pontos"), N["pontos"], ()):
        pa.linha(list(row), entrada=range(1, 8))
    a2 = pa.r - 1
    pa.lista(2, ["Divergência", "Dado ausente", "Esclarecimento", "Levar à análise geral"], a1, a2)

    # Documentos
    dc = Folha(
        wb,
        "Documentos",
        "DOCUMENTOS ANALISADOS E FONTES",
        "Todos os arquivos lidos, com a origem de cada um (anexo, plataforma, PNCP ou portal de origem).",
        [8, 50, 22, 30, 16],
    )
    dc.cabecalho(["ID", "Documento", "Tipo", "Origem", "Versão ou data"])
    for row in pad(v.get("documentos"), N["documentos"], ()):
        dc.linha(list(row), entrada=range(1, 6))

    # ------------------------------------------------------------- Resumo (primeira aba)
    rs_ = Folha(
        wb,
        "Resumo Executivo",
        "ANÁLISE DE MANUTENÇÃO — EXEQUIBILIDADE OPERACIONAL",
        v.get(
            "subtitulo",
            "Preencha as abas na ordem do fluxo de uso. Amarelo é entrada; os indicadores são calculados.",
        ),
        [20, 26, 16, 28, 16, 28, 16, 28],
    )
    wb.move_sheet("Resumo Executivo", offset=-(len(wb.sheetnames) - 1))
    ws = rs_.ws
    rs_.secao("IDENTIFICAÇÃO")
    for nome in (
        "Órgão / unidade",
        "Edital e processo",
        "Objeto",
        "Vigência",
        "Valor estimado",
        "Sessão pública",
        "Data desta análise",
    ):
        r = rs_.r
        c = ws.cell(r, 1, nome)
        c.font, c.border, c.fill = (
            Font(name=FONTE, size=10, bold=True, color=TXT),
            BORDA,
            fill(SUB_BG),
        )
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        x = ws.cell(r, 2, ident.get(nome))
        x.font, x.alignment, x.fill = (
            Font(name=FONTE, size=10, color=TXT),
            Alignment(wrap_text=True, vertical="top"),
            fill(ENTRADA_BG),
        )
        for cc in range(2, 9):
            ws.cell(r, cc).border = BORDA
        ws.row_dimensions[r].height = 15 * (1 + len(str(ident.get(nome) or "")) // 150)
        rs_.r += 1
    rs_.r += 1
    k = rs_.r
    cartao(rs_, k, 1, "HORAS REQUERIDAS / MÊS", f"=Dimensionamento!B{R['req']}", "#,##0.0")
    cartao(rs_, k, 3, "HORAS DISPONÍVEIS / MÊS", f"=Dimensionamento!B{R['disp']}", "#,##0.0")
    cartao(rs_, k, 5, "COBERTURA DA EQUIPE", f"=Dimensionamento!B{R['cob']}", "0.0%")
    cartao(rs_, k, 7, "FOLGA (H/MÊS)", f"=Dimensionamento!B{R['folga']}", "#,##0.0")
    cartao(rs_, k + 4, 1, "NOBREAKS", f"=Equipamentos!B{tot_nb}", "0")
    cartao(rs_, k + 4, 3, "GERADORES", f"=Equipamentos!B{tot_gr}", "0")
    cartao(rs_, k + 4, 5, "ATIVIDADES NO ESCOPO", f"=COUNTA('Escopo e Carga'!C{e1}:C{e2})", "0")
    cartao(rs_, k + 4, 7, "PONTOS DE ATENÇÃO", f"=COUNTA('Pontos de Atenção'!C{a1}:C{a2})", "0")
    rs_.r = k + 8
    rs_.secao("CONCLUSÃO DE EXEQUIBILIDADE OPERACIONAL")
    r = rs_.r
    c = ws.cell(r, 1, "Conclusão")
    c.font, c.fill, c.border = Font(name=FONTE, size=10, bold=True, color=TXT), fill(SUB_BG), BORDA
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    x = ws.cell(r, 2, v.get("conclusao"))
    x.font, x.fill, x.border = (
        Font(name=FONTE, size=12, bold=True, color=TXT),
        fill(ENTRADA_BG),
        BORDA,
    )
    rs_.lista(2, ["Atende", "Atende com condições", "Não atende"], r, r)
    concl_cell = f"B{r}"
    for txt, bg, fg in (
        ("Atende", VERDE, VERDE_TX),
        ("Atende com condições", LARANJA, LARANJA_TX),
        ("Não atende", VERM, VERM_TX),
    ):
        ws.conditional_formatting.add(
            f"B{r}:D{r}",
            FormulaRule(
                formula=[f'EXACT($B${r},"{txt}")'],
                fill=fill(bg),
                font=Font(color=fg, bold=True, size=12),
            ),
        )
    ws.row_dimensions[r].height = 24
    rs_.r += 1
    rs_.texto(v.get("justificativa", ""), altura=78, bg=ENTRADA_BG, cor=TXT)
    rs_.r += 1

    def tabela_resumo(titulo, cab, linhas, n, merges):
        rs_.secao(titulo)
        rr = rs_.r
        col = 1
        for nome, span in zip(cab, merges, strict=False):
            ws.merge_cells(start_row=rr, start_column=col, end_row=rr, end_column=col + span - 1)
            c = ws.cell(rr, col, nome)
            c.fill, c.font, c.alignment = (
                fill(CAB_BG),
                Font(name=FONTE, size=10, bold=True, color=TXT),
                Alignment(horizontal="center", vertical="center", wrap_text=True),
            )
            for cc in range(col, col + span):
                ws.cell(rr, cc).border = BORDA
            col += span
        rs_.r += 1
        for row in pad(linhas, n, ()):
            rr = rs_.r
            col = 1
            row = list(row) + [None] * len(cab)
            altura = 18
            for val, span in zip(row, merges, strict=False):
                ws.merge_cells(
                    start_row=rr, start_column=col, end_row=rr, end_column=col + span - 1
                )
                c = ws.cell(rr, col, val)
                c.font, c.alignment, c.fill = (
                    Font(name=FONTE, size=10, color=TXT),
                    Alignment(wrap_text=True, vertical="top"),
                    fill(ENTRADA_BG),
                )
                for cc in range(col, col + span):
                    ws.cell(rr, cc).border = BORDA
                largura = sum(ws.column_dimensions[L(cc)].width for cc in range(col, col + span))
                altura = max(altura, 15 * (1 + len(str(val or "")) // max(1, int(largura * 1.1))))
                col += span
            ws.row_dimensions[rr].height = altura
            rs_.r += 1
        rs_.r += 1

    tabela_resumo(
        "CONDIÇÕES PARA ATENDER",
        ["OK", "Condição", "Referência"],
        [("☐",) + tuple(x) for x in v.get("condicoes", [])],
        len(v.get("condicoes", [])) or N["condicoes"],
        [1, 5, 2],
    )
    tabela_resumo(
        "OBRIGAÇÕES DE MAIOR RISCO",
        ["Obrigação", "Requisito", "Por que é risco", "Como reduzir"],
        v.get("riscos", []),
        len(v.get("riscos", [])) or N["riscos"],
        [2, 1, 3, 2],
    )
    tabela_resumo(
        "PONTOS PARA A ANALISTA DECIDIR",
        ["Ponto", "Prazo"],
        v.get("decisoes", []),
        len(v.get("decisoes", [])) or N["decisoes"],
        [6, 2],
    )
    rs_.secao("FLUXO DE USO")
    for i, t_ in enumerate(
        [
            "Identificação e Documentos",
            "Equipamentos e Requisitos",
            "Escopo e Carga, Peças e Materiais",
            "Dimensionamento e Pontos de Atenção",
            "Conclusão no Resumo Executivo e conferência dos Checks",
        ],
        1,
    ):
        rr = rs_.r
        c = ws.cell(rr, 1, i)
        c.fill, c.font, c.alignment = (
            fill(SECAO_BG),
            Font(name=FONTE, size=10, bold=True, color="FFFFFF"),
            Alignment(horizontal="center"),
        )
        ws.merge_cells(start_row=rr, start_column=2, end_row=rr, end_column=8)
        x = ws.cell(rr, 2, t_)
        x.font = Font(name=FONTE, size=10, color=TXT)
        for cc in range(1, 9):
            ws.cell(rr, cc).border = BORDA
        rs_.r += 1
    rs_.r += 1
    rs_.secao("LEGENDA")
    rs_.texto(
        "Amarelo = entrada editável | Azul = título/resultado | Verde = condição favorável | Laranja/vermelho = atenção. Marcação nos textos: (D) dado do documento, (C) cálculo, (P) premissa, (R) recomendação.",
        altura=30,
    )

    # ------------------------------------------------------------- Checks
    ck = Folha(
        wb,
        "Checks",
        "CONTROLES DE INTEGRIDADE",
        "Todas as linhas devem estar em OK antes da entrega. Um ALERTA que não dá para resolver vira ponto de atenção.",
        [64, 14, 14],
    )
    st = ck.r
    ck.linha(["Situação geral"], negrito=True, bg=SUB_BG)
    ck.r += 1
    ck.cabecalho(["Verificação", "Ocorrências", "Situação"])
    checks = [
        (
            "Requisitos sem grupo",
            f'=COUNTIFS(Requisitos!C{q_1}:C{q_2},"<>",Requisitos!B{q_1}:B{q_2},"")',
        ),
        (
            "Requisitos sem fonte",
            f'=COUNTIFS(Requisitos!C{q_1}:C{q_2},"<>",Requisitos!D{q_1}:D{q_2},"")',
        ),
        (
            "Requisitos sem risco",
            f'=COUNTIFS(Requisitos!C{q_1}:C{q_2},"<>",Requisitos!I{q_1}:I{q_2},"")',
        ),
        (
            "Atividades sem tipo de carga",
            f"=COUNTIFS('Escopo e Carga'!C{e1}:C{e2},\"<>\",'Escopo e Carga'!B{e1}:B{e2},\"\")",
        ),
        (
            "Atividades com zero hora por ano",
            f"=COUNTIFS('Escopo e Carga'!C{e1}:C{e2},\"<>\",'Escopo e Carga'!I{e1}:I{e2},0)",
        ),
        (
            "Atividades sem requisito de origem",
            f"=COUNTIFS('Escopo e Carga'!C{e1}:C{e2},\"<>\",'Escopo e Carga'!D{e1}:D{e2},\"\")",
        ),
        (
            "Peças e materiais sem forma de pagamento",
            f"=COUNTIFS('Peças e Materiais'!A{c1}:A{c2},\"<>\",'Peças e Materiais'!D{c1}:D{c2},\"\")",
        ),
        (
            "Equipamentos sem faixa de atendimento",
            f'=COUNTIFS(Equipamentos!A{nb1}:A{gr2},">0",Equipamentos!E{nb1}:E{gr2},"")',
        ),
        ("Carga requerida não calculada (1 = falta)", f"=IF(Dimensionamento!C{rt}>0,0,1)"),
        ("Capacidade da equipe não informada (1 = falta)", f"=IF(Dimensionamento!E{rd}>0,0,1)"),
        ("Teste de pior SLA sem resultado (1 = falta)", f'=IF(Dimensionamento!E{rs}="",1,0)'),
        (
            "Pontos de atenção sem providência",
            f"=COUNTIFS('Pontos de Atenção'!C{a1}:C{a2},\"<>\",'Pontos de Atenção'!F{a1}:F{a2},\"\")",
        ),
        ("Conclusão não preenchida (1 = falta)", f"=IF('Resumo Executivo'!{concl_cell}=\"\",1,0)"),
    ]
    k1 = ck.r
    for nome, f in checks:
        r = ck.linha([nome, f], formulas=[2, 3])
        ck.ws.cell(r, 3, f'=IF(B{r}=0,"OK","ALERTA")')
    k2 = ck.r - 1
    ck.ws.cell(st, 2, f'=IF(COUNTIF(C{k1}:C{k2},"ALERTA")>0,"ALERTA","OK")')
    for rng in (f"C{k1}:C{k2}", f"B{st}"):
        ck.ws.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="equal",
                formula=['"OK"'],
                fill=fill(VERDE),
                font=Font(color=VERDE_TX, bold=True),
            ),
        )
        ck.ws.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="equal",
                formula=['"ALERTA"'],
                fill=fill(LARANJA),
                font=Font(color=LARANJA_TX, bold=True),
            ),
        )

    # ordem das abas
    ordem = [
        "Resumo Executivo",
        "Documentos",
        "Equipamentos",
        "Requisitos",
        "Escopo e Carga",
        "Peças e Materiais",
        "Dimensionamento",
        "Pontos de Atenção",
        "Checks",
    ]
    wb._sheets = [wb[n] for n in ordem]
    for ws_ in wb.worksheets:
        ws_.page_setup.orientation = "landscape"
        ws_.page_setup.fitToWidth = 1
        ws_.page_setup.fitToHeight = 0
        ws_.sheet_properties.pageSetUpPr.fitToPage = True
        ws_.print_options.horizontalCentered = True
    wb.active = 0
    wb.calculation.fullCalcOnLoad = True
    wb.save(destino)
    return {"R": R, "rt": rt, "tot_nb": tot_nb, "tot_gr": tot_gr}
