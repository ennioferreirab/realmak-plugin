"""Testes dos links curtos (/a/<codigo>), persistência SQLite, acessos, limpeza e compatibilidade."""

from __future__ import annotations

import sqlite3
import time
from urllib.parse import urlsplit

import httpx
import pytest
import respx

from mcp_realmak.config import load_settings
from mcp_realmak.licitacao import arquivos, links_curtos
from mcp_realmak.server import build_app

from .test_licitacao import API, BIA, GALEED, PUBLIC, ambiente  # noqa: F401


@pytest.mark.usefixtures("ambiente")
async def test_link_curto_pagina_visualizacao_download_acessos_e_reuso_apos_reinicio():
    settings = load_settings()
    emitido = arquivos.link_curto(
        settings,
        {"t": "cerebro", "e": BIA, "m": "realmak", "s": "atestado-ar"},
        nome="Atestado AR.doc",
    )
    codigo = urlsplit(emitido["link"]).path.rsplit("/", 1)[-1]
    assert urlsplit(emitido["link"]).path == f"/a/{codigo}"
    assert 8 <= len(codigo) <= 10 and codigo.isalnum()
    assert BIA not in emitido["link"]

    # Novo build_app() simula reinício do servidor lendo o mesmo SQLite em disco.
    app = build_app()
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GALEED}/original").mock(side_effect=[
            httpx.Response(200, content=b"%PDF-1.7 preview", headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": 'attachment; filename="Atestado AR.pdf"',
            }),
            httpx.Response(200, content=b"\xd0\xcf\x11\xe0 word", headers={
                "Content-Type": "application/msword",
                "Content-Disposition": 'attachment; filename="Atestado AR.doc"',
            }),
        ])
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC) as c,
        ):
            # 1) Navegador recebe página de visualização com botão Baixar (?b=1) e iframe (?v=1).
            pagina = await c.get(f"/a/{codigo}", headers={"Accept": "text/html,application/xhtml+xml"})
            assert pagina.status_code == 200
            assert "text/html" in pagina.headers["content-type"]
            assert f'/a/{codigo}?b=1' in pagina.text
            assert f'/a/{codigo}?v=1' in pagina.text
            assert "Atestado AR.doc" in pagina.text
            assert BIA not in pagina.text

            # 2) Iframe (?v=1) entrega inline.
            ver = await c.get(
                f"/a/{codigo}?v=1",
                headers={"Accept": "text/html", "X-Forwarded-For": "203.0.113.10, 10.0.0.1", "User-Agent": "TestBrowser/1.0"},
            )
            assert ver.status_code == 200
            assert ver.headers["content-disposition"] == 'inline; filename="Atestado AR.pdf"'
            assert ver.content == b"%PDF-1.7 preview"

            # 3) Download (?b=1) entrega attachment original.
            baixar = await c.get(
                f"/a/{codigo}?b=1",
                headers={"X-Forwarded-For": "203.0.113.10", "User-Agent": "curl/8.0"},
            )
            assert baixar.status_code == 200
            assert baixar.headers["content-disposition"] == 'attachment; filename="Atestado AR.doc"'
            assert baixar.content == b"\xd0\xcf\x11\xe0 word"

    with sqlite3.connect(links_curtos.caminho_banco(settings)) as conn:
        acessos = conn.execute(
            "SELECT codigo, tipo, email, modo, ip, user_agent, status FROM acessos_links ORDER BY id"
        ).fetchall()
    assert acessos == [
        (codigo, "cerebro", BIA, "v", "203.0.113.10", "TestBrowser/1.0", 200),
        (codigo, "cerebro", BIA, "b", "203.0.113.10", "curl/8.0", 200),
    ]


@pytest.mark.usefixtures("ambiente")
async def test_link_curto_recusa_vencido_limpa_expirados_e_preserva_rotas_legadas():
    settings = load_settings()
    agora = int(time.time())
    token_expirado = arquivos.assinar(settings, {"t": "baixar", "e": BIA, "l": 7, "d": 1, "x": agora - 5})
    cod_vencido = links_curtos.criar(
        settings, tipo="baixar", token=token_expirado, email=BIA, expira_em=agora - 5, agora=agora - 10,
    )

    app = build_app()
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{API}/arquivo/7/31").mock(return_value=httpx.Response(
            200, content=b"%PDF-1.7 legado", headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": 'attachment; filename="edital.pdf"',
            },
        ))
        mock.get(f"{GALEED}/original").mock(return_value=httpx.Response(
            200, content=b"%PDF-1.7 brain-legado", headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": 'attachment; filename="cat.pdf"',
            },
        ))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC) as c,
        ):
            # Link vencido responde 404 e é removido do banco.
            assert (await c.get(f"/a/{cod_vencido}")).status_code == 404
            assert (await c.get("/a/invalido!")).status_code == 404

            # Novo link dispara limpeza de eventuais vencidos e acessos antigos.
            cod_antigo = links_curtos.criar(
                settings, tipo="baixar", token=token_expirado, email=BIA, expira_em=agora - 1, agora=agora - 10,
            )
            links_curtos.registrar_acesso(
                settings, codigo=cod_antigo, tipo="baixar", email=BIA, modo="b",
                ip="127.0.0.1", user_agent="ua", status=200,
                agora=agora - links_curtos.RETENCAO_ACESSOS_S - 5,
            )
            novo = arquivos.link_curto(settings, {"t": "baixar", "e": BIA, "l": 7, "d": 31})
            cod_novo = urlsplit(novo["link"]).path.rsplit("/", 1)[-1]

            with sqlite3.connect(links_curtos.caminho_banco(settings)) as conn:
                codigos = [r[0] for r in conn.execute("SELECT codigo FROM links_curtos").fetchall()]
                acessos_restantes = conn.execute("SELECT count(*) FROM acessos_links").fetchone()[0]
            assert codigos == [cod_novo]
            assert acessos_restantes == 0

            # Rotas legadas continuam funcionando.
            leg_lic = arquivos.links_download(settings, "", {"t": "baixar", "e": BIA, "l": 7, "d": 31})
            leg_brain = arquivos.links_download(settings, "cerebro/", {"t": "cerebro", "e": BIA, "m": "realmak", "s": "cat"})
            assert (await c.get(urlsplit(leg_lic["link_baixar"]).path)).status_code == 200
            assert (await c.get(urlsplit(leg_brain["link_visualizar"]).path)).status_code == 200


@pytest.mark.usefixtures("ambiente")
async def test_link_curto_word_usa_previa_pdf_na_visualizacao_e_original_no_download(monkeypatch):
    monkeypatch.setenv("MCP_REALMAK_VISUALIZADOR_URL", "http://visualizador.test:8080")
    settings = load_settings()
    emitido = arquivos.link_curto(
        settings,
        {"t": "cerebro", "e": BIA, "m": "realmak", "s": "atestado-word"},
        nome="Atestado.docx",
    )
    caminho = urlsplit(emitido["link"]).path

    app = build_app()
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GALEED}/original").mock(side_effect=[
            httpx.Response(200, content=b"PK\x03\x04 docx", headers={
                "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "Content-Disposition": 'attachment; filename="Atestado.docx"',
            }) for _ in range(2)
        ])
        previa = mock.post("http://visualizador.test:8080/pdf", params={"ext": "docx"}).mock(
            return_value=httpx.Response(200, content=b"%PDF-1.7 convertido", headers={"Content-Type": "application/pdf"})
        )
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC) as c,
        ):
            ver = await c.get(f"{caminho}?v=1")
            assert ver.status_code == 200
            assert ver.headers["content-type"] == "application/pdf"
            assert ver.headers["content-disposition"] == 'inline; filename="Atestado.pdf"'
            assert ver.content.startswith(b"%PDF-")

            baixar = await c.get(f"{caminho}?b=1")
            assert baixar.status_code == 200
            assert baixar.headers["content-disposition"] == 'attachment; filename="Atestado.docx"'
            assert baixar.content == b"PK\x03\x04 docx"
            assert previa.call_count == 1

