#!/usr/bin/env python3
"""Monta o pacote de envio de uma licitação: um PDF por exigência, numerado na ordem do edital, mais o índice.

Uso: python3 montar_pacote.py plano.json

plano.json:
{
  "saida": "pasta onde gravar o pacote",
  "indice_json": "agents/montagem-proposta/indice-envio.json",  # opcional: grava índice estruturado fora de DOCUMENTOS PARA DISPUTA
  "licitacao": "PE 35/2026 – TJMA", "empresa": "REALMAK SERVIÇOS E COMÉRCIO LTDA",
  "limite_mb": 10,                       # tamanho máximo por arquivo do portal, se o edital informar (opcional)
  "itens": [
    {"ordem": "H-01", "nome": "Ato constitutivo – 18ª alteração contratual", "item_edital": "10.6.1 II",
     "fontes": ["/caminho/a.pdf", "/caminho/b.docx"],   # juntadas nesta ordem num só PDF
     "assinaturas": [{"nome": "Fulano", "papel": "Representante", "assinado": true, "forma": "modelo"}],  # opcional
     "status": "ok" | "pendente", "obs": "texto curto (validade, falta assinatura, ...)"}
  ]
}
Itens sem fontes entram só no índice, como pendência. DOC/DOCX/XLSX/ODT/imagens são convertidos com o LibreOffice
(`soffice`). Sai um JSON com os arquivos gerados, páginas, tamanho e avisos.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter

CONVERTE = {'.doc', '.docx', '.odt', '.rtf', '.xls', '.xlsx', '.ods', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.txt'}


def nome_seguro(texto):
    texto = re.sub(r'[\\/:*?"<>|\r\n]+', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()[:150]


def para_pdf(fonte, tmp):
    fonte = Path(fonte)
    if fonte.suffix.lower() == '.pdf':
        return fonte
    if fonte.suffix.lower() not in CONVERTE:
        raise ValueError(f'formato sem conversão: {fonte.name}')
    soffice = shutil.which('soffice') or shutil.which('libreoffice')
    if not soffice:
        raise RuntimeError('LibreOffice (soffice) não encontrado para converter ' + fonte.name)
    destino = Path(tempfile.mkdtemp(dir=tmp))
    subprocess.run([soffice, '--headless', '--convert-to', 'pdf', '--outdir', str(destino), str(fonte)],
                   check=True, capture_output=True, timeout=300, env={'HOME': str(destino), 'PATH': '/usr/bin:/bin'})
    pdf = destino / (fonte.stem + '.pdf')
    if not pdf.exists():
        raise RuntimeError('conversão falhou: ' + fonte.name)
    return pdf


def resumir_assinaturas(assinaturas):
    if not assinaturas:
        return '—'
    feitas, faltam = [], []
    for a in assinaturas:
        nome = a.get('nome') or '?'
        papel = a.get('papel')
        rotulo = f"{nome} ({papel})" if papel else nome
        if a.get('assinado'):
            forma = a.get('forma')
            feitas.append(f"{rotulo} [{forma}]" if forma else rotulo)
        else:
            faltam.append(rotulo)
    partes = []
    if feitas:
        partes.append('Feitas: ' + ', '.join(feitas))
    if faltam:
        partes.append('Faltam: ' + ', '.join(faltam))
    return ' | '.join(partes) or '—'


def indice_pdf(plano, linhas, saida, tmp):
    """Índice em DOCX convertido para PDF; sem LibreOffice, fica o DOCX."""
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    doc.add_heading('ÍNDICE DE ENVIO', level=1)
    doc.add_paragraph(f"{plano.get('licitacao', '')} — {plano.get('empresa', '')}")
    tabela = doc.add_table(rows=1, cols=6)
    tabela.style = 'Table Grid'
    for c, t in zip(
        tabela.rows[0].cells,
        ['Ordem', 'Documento', 'Item do edital', 'Arquivo', 'Assinaturas', 'Situação'],
        strict=True,
    ):
        c.text = t
    for item_linha in linhas:
        cel = tabela.add_row().cells
        cel[0].text, cel[1].text, cel[2].text = item_linha['ordem'], item_linha['nome'], item_linha.get('item_edital', '')
        cel[3].text = item_linha.get('arquivo') or '—'
        cel[4].text = resumir_assinaturas(item_linha.get('assinaturas'))
        cel[5].text = ('OK' if item_linha['status'] == 'ok' else 'PENDENTE') + (
            f" — {item_linha['obs']}" if item_linha.get('obs') else ''
        )
    for linha in tabela.rows:
        for c in linha.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
    docx_path = Path(tmp) / '00 - INDICE DE ENVIO.docx'
    doc.save(docx_path)
    try:
        pdf = para_pdf(docx_path, tmp)
        final = Path(saida) / '00 - INDICE DE ENVIO.pdf'
        shutil.copyfile(pdf, final)
    except (RuntimeError, subprocess.CalledProcessError):
        final = Path(saida) / '00 - INDICE DE ENVIO.docx'
        shutil.copyfile(docx_path, final)
    return final


def montar(plano):
    saida = Path(plano['saida'])
    saida.mkdir(parents=True, exist_ok=True)
    limite = plano.get('limite_mb')
    linhas, avisos = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for item in plano['itens']:
            linha = {k: item.get(k) for k in ('ordem', 'nome', 'item_edital', 'status', 'obs', 'assinaturas')}
            assinaturas = item.get('assinaturas') or []
            faltam_assinar = [a.get('nome') or '?' for a in assinaturas if not a.get('assinado')]
            linha['status'] = item.get('status') or ('ok' if item.get('fontes') else 'pendente')
            if faltam_assinar:
                linha['status'] = 'pendente'
                if not linha.get('obs'):
                    linha['obs'] = 'Aguardando assinatura de ' + ', '.join(faltam_assinar)
            fontes = item.get('fontes') or []
            if fontes:
                escritor = PdfWriter()
                try:
                    for f in fontes:
                        for pagina in PdfReader(str(para_pdf(f, tmp))).pages:
                            escritor.add_page(pagina)
                except Exception as exc:  # fonte ilegível: vira pendência, o resto do pacote segue
                    linha.update(status='pendente', obs=f'não montado: {exc}')
                    avisos.append(f"{item['ordem']}: {exc}")
                else:
                    escritor.compress_identical_objects()
                    destino = saida / f"{item['ordem']} - {nome_seguro(item['nome'])}.pdf"
                    with open(destino, 'wb') as fh:
                        escritor.write(fh)
                    mb = destino.stat().st_size / 1_048_576
                    linha.update(arquivo=destino.name, paginas=len(escritor.pages), mb=round(mb, 2))
                    if limite and mb > limite:
                        avisos.append(f"{destino.name}: {mb:.1f} MB acima do limite de {limite} MB do portal")
            linhas.append(linha)
        indice = indice_pdf(plano, linhas, saida, tmp)
    indice_json_path = plano.get('indice_json')
    if indice_json_path:
        destino_json = Path(indice_json_path)
        destino_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'itens': [
                {
                    'codigo': item_linha['ordem'],
                    'situacao': 'OK' if item_linha['status'] == 'ok' else 'PENDENTE',
                    'motivo': item_linha.get('obs') or '',
                }
                for item_linha in linhas
            ]
        }
        destino_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'indice': indice.name, 'indice_json': str(indice_json_path) if indice_json_path else None,
            'arquivos': linhas, 'avisos': avisos,
            'pendencias': [item_linha for item_linha in linhas if item_linha['status'] != 'ok']}


if __name__ == '__main__':
    print(json.dumps(montar(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))), ensure_ascii=False, indent=1))
