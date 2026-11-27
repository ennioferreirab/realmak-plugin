#!/usr/bin/env python3
"""Gera o DOCX das declarações de uma licitação no padrão das empresas do grupo Realmak.

Uso: python3 gerar_declaracoes.py especificacao.json saida.docx

A especificação (JSON) tem:
  empresa: dados do cadastro (razao_social, cnpj, inscricao_estadual, inscricao_rotulo, endereco, cidade, uf, cep,
           representante{nome, cargo, rg, cpf, tratamento}, assinatura, assinatura_inclui_nome, timbre)
           `assinatura` e `timbre` são caminhos de imagem (relativos ao JSON ou absolutos).
  destinatario: {orgao: [linhas], modalidade: "PREGÃO ELETRÔNICO Nº 35/2026", processo: "PROCESSO ADMINISTRATIVO Nº ..."}
  local_data: "Brasília, 27 de novembro de 2026"
  declaracoes: [{titulo, paragrafos: [texto ou {"texto", "recuo": true, "negrito": true}
                 ou {"tabela": {"cabecalho": [...], "linhas": [[...]], "larguras_cm": [...], "direita": [índices de coluna],
                                "negrito_linhas": [índices de linha], "tamanho": 9}}],
                 assinaturas: ["representante"] | ["representante", {nome, linhas: [...]}],  (padrão: representante)
                 rodape: [linhas finais antes da assinatura, opcional]}]
Marcadores no texto: {qualificacao} (empresa + representante), {qualificacao_curta} (empresa sem representante),
{razao_social}, {cnpj}, {representante}, {cpf_representante}, {modalidade}, {local_data}.
"""
import json
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

FONTE, TAMANHO = 'Arial', 11


def qualificacao(e, com_representante=True):
    r = e.get('representante') or {}
    inscricao = f", {e['inscricao_rotulo']} nº {e['inscricao_estadual']}" if e.get('inscricao_estadual') else ''
    sede = f"{e['endereco']}, {e['cidade']}-{e['uf']}" + (f", CEP {e['cep']}" if e.get('cep') else '')
    texto = f"A empresa {e['razao_social']}, inscrita no CNPJ sob o nº {e['cnpj']}{inscricao}, com sede na {sede}"
    if com_representante and r.get('nome'):
        texto += (f", por intermédio de seu representante legal, {r.get('tratamento', 'o(a) Senhor(a)')} {r['nome']}, "
                  f"portador(a) da carteira de identidade nº {r['rg']} e do CPF nº {r['cpf']}")
    return texto


def preencher(texto, e, spec):
    r = e.get('representante') or {}
    return texto.format(qualificacao=qualificacao(e), qualificacao_curta=qualificacao(e, False),
                        razao_social=e['razao_social'], cnpj=e['cnpj'], representante=r.get('nome', ''),
                        cpf_representante=r.get('cpf', ''), modalidade=spec['destinatario']['modalidade'],
                        local_data=spec['local_data'])


def paragrafo(doc, texto='', negrito=False, alinhamento=WD_ALIGN_PARAGRAPH.JUSTIFY, recuo=False, depois=6, tamanho=TAMANHO):
    p = doc.add_paragraph()
    p.alignment = alinhamento
    p.paragraph_format.space_after = Pt(depois)
    p.paragraph_format.line_spacing = 1.15
    if recuo:
        p.paragraph_format.first_line_indent = Cm(1.25)
    run = p.add_run(texto)
    run.bold = negrito
    run.font.name = FONTE
    run.font.size = Pt(tamanho)
    return p


def tabela(doc, spec, e, dados):
    cab, linhas = spec['cabecalho'], spec['linhas']
    tam = spec.get('tamanho', 9)
    t = doc.add_table(rows=1 + len(linhas), cols=len(cab))
    t.style = 'Table Grid'
    t.autofit = False
    direita, negritos = set(spec.get('direita', [])), set(spec.get('negrito_linhas', []))
    for j, largura in enumerate(spec.get('larguras_cm', [])):
        t.columns[j].width = Cm(largura)
    for i, linha in enumerate([cab] + linhas):
        for j, texto in enumerate(linha):
            c = t.cell(i, j)
            if spec.get('larguras_cm'):
                c.width = Cm(spec['larguras_cm'][j])
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if j in direita and i else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(preencher(str(texto), e, dados))
            run.bold = i == 0 or (i - 1) in negritos
            run.font.name, run.font.size = FONTE, Pt(tam)
            if i == 0:
                sombra = OxmlElement('w:shd')
                sombra.set(qn('w:val'), 'clear')
                sombra.set(qn('w:fill'), 'D9D9D9')
                c._tc.get_or_add_tcPr().append(sombra)
    paragrafo(doc, '', depois=4)


def assinatura(doc, base, e, quem):
    if quem == 'representante':
        r = e['representante']
        img = e.get('assinatura')
        if img:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(18)
            p.add_run().add_picture(str((base / img) if not Path(img).is_absolute() else img), width=Cm(6.5))
        else:
            paragrafo(doc, '_' * 45, alinhamento=WD_ALIGN_PARAGRAPH.CENTER, depois=0)
        if not img or not e.get('assinatura_inclui_nome'):
            paragrafo(doc, r['nome'].upper(), negrito=True, alinhamento=WD_ALIGN_PARAGRAPH.CENTER, depois=0)
            paragrafo(doc, f"{r.get('cargo') or 'Representante legal'} – CPF nº {r['cpf']}", alinhamento=WD_ALIGN_PARAGRAPH.CENTER, depois=0)
        paragrafo(doc, e['razao_social'], alinhamento=WD_ALIGN_PARAGRAPH.CENTER, depois=0, tamanho=10)
    else:  # signatário sem imagem: linha para assinatura manual ou digital
        p = paragrafo(doc, '_' * 45, alinhamento=WD_ALIGN_PARAGRAPH.CENTER, depois=0)
        p.paragraph_format.space_before = Pt(36)
        paragrafo(doc, quem['nome'].upper(), negrito=True, alinhamento=WD_ALIGN_PARAGRAPH.CENTER, depois=0)
        for linha in quem.get('linhas', []):
            paragrafo(doc, linha, alinhamento=WD_ALIGN_PARAGRAPH.CENTER, depois=0)


def gerar(spec_path, saida):
    spec_path = Path(spec_path)
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    base, e, dest = spec_path.parent, spec['empresa'], spec['destinatario']
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21)
    sec.left_margin = sec.right_margin = Cm(2)
    sec.top_margin, sec.bottom_margin, sec.header_distance = Cm(2), Cm(2), Cm(0.8)
    if e.get('timbre'):
        cab = sec.header.paragraphs[0]
        cab.alignment = WD_ALIGN_PARAGRAPH.CENTER
        timbre = (base / e['timbre']) if not Path(e['timbre']).is_absolute() else Path(e['timbre'])
        cab.add_run().add_picture(str(timbre), width=Cm(17))
    for i, d in enumerate(spec['declaracoes']):
        if i:
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        paragrafo(doc, spec['local_data'], alinhamento=WD_ALIGN_PARAGRAPH.RIGHT, depois=12)
        paragrafo(doc, 'AO', negrito=True, alinhamento=WD_ALIGN_PARAGRAPH.LEFT, depois=0)
        for linha in dest['orgao']:
            paragrafo(doc, linha, negrito=True, alinhamento=WD_ALIGN_PARAGRAPH.LEFT, depois=0)
        paragrafo(doc, dest['modalidade'], negrito=True, alinhamento=WD_ALIGN_PARAGRAPH.LEFT, depois=0)
        if dest.get('processo'):
            paragrafo(doc, dest['processo'], negrito=True, alinhamento=WD_ALIGN_PARAGRAPH.LEFT, depois=0)
        p = paragrafo(doc, d['titulo'], negrito=True, alinhamento=WD_ALIGN_PARAGRAPH.CENTER, depois=12)
        p.paragraph_format.space_before = Pt(18)
        for item in d['paragrafos']:
            item = {'texto': item} if isinstance(item, str) else item
            if 'tabela' in item:
                tabela(doc, item['tabela'], e, spec)
                continue
            paragrafo(doc, preencher(item['texto'], e, spec), negrito=item.get('negrito', False),
                      recuo=item.get('recuo', True), tamanho=item.get('tamanho', TAMANHO))
        for linha in d.get('rodape', []):
            paragrafo(doc, preencher(linha, e, spec), alinhamento=WD_ALIGN_PARAGRAPH.LEFT, depois=0)
        for quem in d.get('assinaturas', ['representante']):
            assinatura(doc, base, e, quem)
    doc.save(saida)


if __name__ == '__main__':
    gerar(sys.argv[1], sys.argv[2])
