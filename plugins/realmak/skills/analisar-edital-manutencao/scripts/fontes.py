"""Transforma citações no HTML em links para o resolvedor do card no CRM."""

import json
import os
import re
import sys
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urlsplit

DOCUMENTOS = {
    "tr": "TR",
    "termo de referência": "TR",
    "edital": "Edital",
    "etp": "ETP",
    "estudo técnico preliminar": "ETP",
}
DOCUMENTO = "|".join(DOCUMENTOS)
NUM = r"\d+(?:\.\d+)*(?!\w|/\d{4}\b|\.\d)"
SEP = r"(?:\s*[,;/–—-]\s*|\s+(?:e|a|até)\s+)"
LISTA = rf"{NUM}(?:{SEP}{NUM})*"
CITACAO = re.compile(
    rf"\b(?:(?P<antes>(?:item|itens)\s+(?P<lista_antes>{LISTA})\s+d[oa]\s+)(?P<doc_final>{DOCUMENTO})\b"
    rf"|(?P<doc>{DOCUMENTO})\b(?:\s*[,;:]?\s+(?:(?:item|itens)\s+)?(?P<lista>{LISTA})(?!\s*(?:h/mês|%)))?)",
    re.I,
)
NUMERO = re.compile(NUM)


def contexto(pasta):
    checklist = Path(pasta).resolve().parent / "checklist.json"
    dados = json.loads(checklist.read_text(encoding="utf-8")) if checklist.is_file() else {}
    lead = dados.get("lead_id") or os.environ.get("REALMAK_LEAD_ID", "")
    if not re.fullmatch(r"[1-9]\d*", str(lead)):
        return ""
    base = os.environ.get("REALMAK_CRM_BASE_URL") or dados.get("crm_base_url", "")
    if base:
        url = urlsplit(base)
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username is not None
            or url.query
            or url.fragment
            or url.path.strip("/")
            or re.search(r"[\s\\]", base)
        ):
            raise ValueError("Origem pública do CRM inválida")
    return f"{base.rstrip('/')}/realmak_licitacao/fonte/{lead}"


def vincular(texto, rota):
    """O texto já está escapado como HTML. Preserve rótulos e separadores."""

    def substituir(m):
        doc = DOCUMENTOS[(m["doc"] or m["doc_final"]).lower()]

        def link(rotulo, item=None):
            params = {"documento": doc}
            if item:
                params["item"] = item
            href = escape(rota + "?" + urlencode(params), quote=True)
            return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{rotulo}</a>'

        grupo = "lista_antes" if m["antes"] else "lista"
        if not m[grupo]:
            return link(m[0])
        ini = m.start(grupo) - m.start()
        fim = m.end(grupo) - m.start()

        def item(n):
            rotulo = n[0]
            if n.start() == 0:
                rotulo = m[0][:ini] + rotulo
            if n.end() == len(m[grupo]):
                rotulo += m[0][fim:]
            return link(rotulo, n[0])

        return NUMERO.sub(item, m[grupo])

    return CITACAO.sub(substituir, texto)


class TextoVisivel(HTMLParser):
    """Substitui somente nós de texto, preservando literalmente o resto do arquivo."""

    def __init__(self, html, rota):
        super().__init__(convert_charrefs=False)
        self.rota = rota
        self.linhas = [0] + [m.end() for m in re.finditer("\n", html)]
        self.ignorar = []
        self.edicoes = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag in ("a", "head", "script", "style", "textarea", "code", "pre"):
            self.ignorar.append(tag)

    def handle_endtag(self, tag):
        if self.ignorar and self.ignorar[-1] == tag:
            self.ignorar.pop()

    def handle_data(self, data):
        if self.ignorar:
            return
        novo = vincular(data, self.rota)
        if novo != data:
            linha, coluna = self.getpos()
            ini = self.linhas[linha - 1] + coluna
            self.edicoes.append((ini, ini + len(data), novo))


def vincular_html(html, rota):
    if not rota:
        return html
    partes = []
    anterior = 0
    for ini, fim, novo in TextoVisivel(html, rota).edicoes:
        partes.extend((html[anterior:ini], novo))
        anterior = fim
    return "".join([*partes, html[anterior:]])


def fontes_do_painel(dados, rota):
    """Fontes disponíveis inclusive ao abrir o painel exportado sem o CRM."""
    if not rota:
        return ""

    def textos(valor):
        if isinstance(valor, dict):
            for v in valor.values():
                yield from textos(v)
        elif isinstance(valor, list):
            for v in valor:
                yield from textos(v)
        elif isinstance(valor, str) and CITACAO.search(valor):
            yield valor

    linhas = [f"<li>{vincular(escape(t), rota)}</li>" for t in dict.fromkeys(textos(dados))]
    if not linhas:
        return ""
    return (
        "<details><summary>Fontes citadas no painel</summary><ul>"
        + "".join(linhas)
        + "</ul></details>"
    )


if __name__ == "__main__":
    arquivo = Path(sys.argv[1])
    rota = contexto(arquivo.parent)
    if rota:
        original = arquivo.read_bytes().decode("utf-8")
        arquivo.write_bytes(vincular_html(original, rota).encode("utf-8"))
