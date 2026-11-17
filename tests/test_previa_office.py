"""Contratos HTTP das duas origens. Com fixtures e URL, usa o visualizador real."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import httpx
import pytest
import respx

from mcp_realmak.config import load_settings
from mcp_realmak.licitacao import arquivos, previa
from mcp_realmak.server import build_app

from .test_licitacao import API, BIA, GALEED, ambiente  # noqa: F401


@pytest.mark.usefixtures("ambiente")
@pytest.mark.parametrize("origem", ["odoo", "brain"])
@pytest.mark.parametrize("ext", ["doc", "docx", "xls", "xlsx"])
@pytest.mark.parametrize("real", [False, True], ids=["contrato", "visualizador-real"])
async def test_previa_e_original(monkeypatch, origem, ext, real):
    url = os.environ.get("TESTE_VISUALIZADOR_URL", "").rstrip("/") if real else "http://visualizador.test:8080"
    fixtures = os.environ.get("TESTE_VISUALIZADOR_FIXTURES")
    if real and not (url and fixtures):
        pytest.skip("Defina TESTE_VISUALIZADOR_URL e TESTE_VISUALIZADOR_FIXTURES para testar a imagem.")
    original = (Path(fixtures) / f"arquivo.{ext}").read_bytes() if real else f"arquivo fictício {ext}".encode()
    monkeypatch.setenv("MCP_REALMAK_VISUALIZADOR_URL", url)
    settings = load_settings()
    if origem == "brain":
        dados = {"t": "cerebro", "e": BIA, "m": "realmak", "s": "arquivo"}
        prefixo = "/mcp/arquivos/cerebro/"
        upstream, cabecalho = f"{GALEED}/original", "x-galeed-act-as"
    else:
        dados = {"t": "baixar", "e": BIA, "l": 7, "d": 31}
        prefixo = "/mcp/arquivos/"
        upstream, cabecalho = f"{API}/arquivo/7/31", "x-realmak-act-as"

    pedidos_reais: list[httpx.Request] = []
    if real:
        enviar = httpx.AsyncHTTPTransport.handle_async_request
        endpoint = httpx.URL(f"{url}/pdf")

        async def observar_envio(transport, pedido):
            if pedido.url.copy_with(query=None) == endpoint:
                pedidos_reais.append(pedido)
            return await enviar(transport, pedido)

        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", observar_envio)

    app = build_app()
    async with (
        respx.mock(assert_all_called=False) as mock,
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://mcp.test") as cliente,
    ):
        arquivo = mock.get(upstream).mock(side_effect=[
            httpx.Response(200, content=original, headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f'attachment; filename="arquivo.{ext}"',
            }) for _ in range(2)
        ] + [httpx.Response(403, json={"erro": "sem acesso", "error": "sem acesso"})])
        rota = mock.post(f"{url}/pdf", params={"ext": ext})
        if real:
            rota.pass_through()
        else:
            rota.mock(return_value=httpx.Response(
                200, content=b"%PDF-1.7\nfixture", headers={"Content-Type": "application/pdf"},
            ))

        ver = prefixo + arquivos.assinar(settings, {**dados, "modo": "v", "x": 4_000_000_000})
        baixar = prefixo + arquivos.assinar(settings, {**dados, "modo": "b", "x": 4_000_000_000})
        vencido = prefixo + arquivos.assinar(settings, {**dados, "modo": "v", "x": 0})
        assert (await cliente.get(vencido)).status_code == 404

        download = await cliente.get(baixar)
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/octet-stream"
        assert download.headers["content-disposition"] == f'attachment; filename="arquivo.{ext}"'
        assert hashlib.sha256(download.content).digest() == hashlib.sha256(original).digest()
        assert not pedidos_reais and not rota.called

        pdf = await cliente.get(ver)
        assert pdf.status_code == 200
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.headers["content-disposition"] == 'inline; filename="arquivo.pdf"'
        assert pdf.headers["cache-control"] == "no-store"
        assert pdf.headers["x-content-type-options"] == "nosniff"
        assert pdf.content.startswith(b"%PDF-")
        assert (await cliente.get(ver)).status_code == 403
        assert arquivo.call_count == 3
        # O RESPX pode interceptar pass_through no pool e na conexão.
        pedidos = pedidos_reais if real else [chamada.request for chamada in rota.calls]
        assert len(pedidos) == 1
        pedido = pedidos[0]
        assert pedido.method == "POST" and dict(pedido.url.params) == {"ext": ext}
        assert pedido.headers["content-length"] == str(len(original))
        assert "authorization" not in pedido.headers
        assert cabecalho not in pedido.headers
        assert arquivo.calls.last.request.headers[cabecalho] == BIA


async def test_previa_rejeita_entrada_grande_sem_chamar_visualizador(monkeypatch):
    monkeypatch.setattr(previa, "MAX_ENTRADA", 3)
    async with respx.mock(assert_all_called=False) as mock:
        rota = mock.post("http://visualizador.test:8080/pdf")
        with pytest.raises(previa.ErroPrevia) as erro:
            await previa.converter("http://visualizador.test:8080", ".doc", httpx.Response(200, content=b"1234"))
    assert erro.value.status == 413
    assert not rota.called


@pytest.mark.parametrize("status,tipo,corpo,esperado", [
    (422, "application/json", b"segredo", 422),
    (504, "application/json", b"segredo", 504),
    (200, "text/html", b"segredo", 502),
    (200, "application/pdf", b"segredo", 502),
])
async def test_previa_falha_sem_repassar_corpo_do_visualizador(status, tipo, corpo, esperado):
    async with respx.mock() as mock:
        mock.post("http://visualizador.test:8080/pdf").mock(return_value=httpx.Response(
            status, content=corpo, headers={"Content-Type": tipo},
        ))
        with pytest.raises(previa.ErroPrevia) as erro:
            await previa.converter("http://visualizador.test:8080", ".doc", httpx.Response(200, content=b"123"))
    assert erro.value.status == esperado
    assert "segredo" not in str(erro.value)
