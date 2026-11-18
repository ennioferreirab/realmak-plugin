"""Agenda e prepara a leitura das cópias arquivadas, sem decidir seu mérito."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from guardar_original import sha256

LIMITE_BYTES = 50 * 1024 * 1024
LIMITE_UNIDADES = 2000


def agenda(dossie):
    for doc in dossie["documentos"]:
        etapas = doc["etapas"]
        if etapas["download"]["estado"] != "ok" or not doc.get("vinculos"):
            continue
        if etapas["leitura"]["estado"] != "ok" or etapas["validacao"]["estado"] != "ok":
            yield {k: doc[k] for k in ("empresa", "id", "arquivo", "sha256", "vinculos")}


def pdf(copia, saida):
    import pymupdf

    with pymupdf.open(copia) as original:
        if original.needs_pass:
            raise ValueError("PDF exige senha para leitura")
        for pagina in original:
            numero = pagina.number + 1
            texto = pagina.get_text().strip()
            registro = {"pagina": numero, "texto": texto}
            if not texto or pagina.get_image_info():
                imagem = saida / f"pagina-{numero}.png"
                escala = min(2, 1800 / max(pagina.rect.width, pagina.rect.height))
                pagina.get_pixmap(matrix=pymupdf.Matrix(escala, escala)).save(imagem)
                registro["imagem"] = imagem.name
            yield registro


def docx(copia):
    from docx import Document
    from docx.table import Table

    for numero, bloco in enumerate(Document(copia).iter_inner_content(), 1):
        if isinstance(bloco, Table):
            for linha, itens in enumerate(bloco.rows, 1):
                yield {"secao": f"Tabela no bloco {numero}, linha {linha}",
                       "texto": " | ".join(c.text for c in itens.cells)}
        else:
            yield {"secao": f"Parágrafo no bloco {numero}", "texto": bloco.text}


def doc(copia):
    javascript = """
    const WordExtractor = require('word-extractor');
    new WordExtractor().extract(process.argv[1]).then(d => {
      process.stdout.write(JSON.stringify([
        ['Corpo', d.getBody()], ['Cabeçalho e rodapé', d.getHeaders()],
        ['Notas de rodapé', d.getFootnotes()], ['Notas finais', d.getEndnotes()],
        ['Caixas de texto', d.getTextboxes()]
      ]));
    }).catch(() => { process.exitCode = 1; });
    """
    resposta = subprocess.run(["node", "-e", javascript, str(copia)], capture_output=True,
                              text=True, timeout=40, check=False)
    if resposta.returncode:
        raise ValueError("Word binário ilegível ou módulo Node word-extractor indisponível")
    for secao, texto in json.loads(resposta.stdout):
        for numero, linha in enumerate(texto.splitlines(), 1):
            if linha.strip():
                yield {"secao": f"{secao}, linha extraída {numero}", "texto": linha}


def xlsx(copia):
    from openpyxl import load_workbook

    pasta = load_workbook(copia, read_only=True, data_only=True)
    try:
        for aba in pasta:
            for numero, linha in enumerate(aba.values, 1):
                if any(valor is not None for valor in linha):
                    yield {"secao": f"Aba {aba.title}, linha {numero}",
                           "texto": " | ".join("" if valor is None else str(valor) for valor in linha)}
    finally:
        pasta.close()


def extrair(raiz, doc_item, pasta):
    relativo = Path(doc_item["arquivo"])
    copia = raiz / relativo
    acervo = raiz.resolve() / "documentos_empresa"
    empresa = acervo / doc_item["empresa"]
    if (relativo.is_absolute() or empresa.parent != acervo
            or not copia.resolve().is_relative_to(empresa)
            or not copia.is_file() or sha256(copia) != doc_item["sha256"]):
        raise ValueError("cópia arquivada ausente, fora da empresa ou com hash divergente")
    if copia.stat().st_size > LIMITE_BYTES:
        raise ValueError("cópia excede 50 MiB; continue com leitor manual")
    if pasta.resolve().is_relative_to((raiz / "documentos_empresa").resolve()):
        raise ValueError("grave derivados fora de documentos_empresa")
    formato = copia.suffix.lower()
    leitores = {".doc": doc, ".docx": docx, ".xlsx": xlsx}
    if formato != ".pdf" and formato not in leitores:
        raise ValueError(f"formato {formato or 'sem extensão'} sem leitor; confira manualmente")
    pasta.mkdir(mode=0o700)
    partes = pdf(copia, pasta) if formato == ".pdf" else leitores[formato](copia)
    arquivo = pasta / "leitura.jsonl"
    total = 0
    paginas_visuais = []
    with arquivo.open("x", encoding="utf-8") as stream:
        for numero, parte in enumerate(partes, 1):
            if numero > LIMITE_UNIDADES:
                raise ValueError("extração parcial após 2000 unidades; continue com leitor manual")
            if parte.get("imagem"):
                paginas_visuais.append(parte["pagina"])
            if parte["texto"].strip() or parte.get("imagem"):
                stream.write(json.dumps(parte, ensure_ascii=False) + "\n")
                total += 1
    if not total:
        raise ValueError("nenhum texto ou imagem recuperado; abra no leitor nativo")
    return {"estado": "preparado", "unidades": total, "indice": str(arquivo),
            "paginas_visuais": paginas_visuais, "sha256": doc_item["sha256"]}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raiz", type=Path)
    parser.add_argument("dossie", type=Path)
    comandos = parser.add_subparsers(dest="acao", required=True)
    comandos.add_parser("agenda")
    extracao = comandos.add_parser("extrair")
    extracao.add_argument("empresa")
    extracao.add_argument("id")
    extracao.add_argument("saida", type=Path)
    args = parser.parse_args()
    try:
        itens = list(agenda(json.loads(args.dossie.read_text(encoding="utf-8"))))
        if args.acao == "agenda":
            resultado = itens
        else:
            item = next((d for d in itens if (d["empresa"], d["id"]) == (args.empresa, args.id)), None)
            if item is None:
                raise ValueError("empresa e ID ausentes da agenda de leitura")
            resultado = extrair(args.raiz, item, args.saida)
    except Exception as erro:
        detalhe = str(erro) if isinstance(erro, (ValueError, ImportError, TimeoutError)) else type(erro).__name__
        print(json.dumps({"estado": "falhou", "detalhe": detalhe}, ensure_ascii=False))
        return 2
    print(json.dumps(resultado, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
