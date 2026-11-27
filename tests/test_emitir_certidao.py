"""Testes unitários do script emitir_certidao.py (sem rede e sem dados pessoais)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "plugins/realmak/skills/emitir-certidoes/scripts/emitir_certidao.py"

spec = importlib.util.spec_from_file_location("emitir_certidao", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_limpar_e_formatar_cnpj():
    assert mod.limpar_cnpj("11.222.333/0001-81") == "11222333000181"
    assert mod.formatar_cnpj("11222333000181") == "11.222.333/0001-81"
    with pytest.raises(ValueError):
        mod.limpar_cnpj("12345")


def test_normalizar_data_iso():
    assert mod.normalizar_data_iso("2026-12-24T10:00:00Z") == "2026-12-24"
    assert mod.normalizar_data_iso("24/12/2026") == "2026-12-24"
    assert mod.normalizar_data_iso("") is None


def test_detectar_divergencia_nome_eireli_ltda():
    obs = mod.detectar_divergencia_nome(
        "EMPRESA EXEMPLO SERVICOS LTDA",
        "EMPRESA EXEMPLO SERVICOS EIRELI",
    )
    assert obs is not None
    assert "sem bloqueio" in obs
    assert mod.detectar_divergencia_nome("EMPRESA EXEMPLO LTDA", "EMPRESA EXEMPLO LTDA") is None


def test_classificar_resultado_texto():
    assert mod.classificar_resultado_texto("NADA CONSTA de processos de falência") == "NEGATIVA"
    assert (
        mod.classificar_resultado_texto("Certidão Positiva com Efeitos de Negativa")
        == "POSITIVA_COM_EFEITOS_DE_NEGATIVA"
    )
    assert mod.classificar_resultado_texto("CERTIDAO POSITIVA - POSSUI DEBITO") == "POSITIVA"


def test_emitir_tjdft_reaproveita_vigente_mock(monkeypatch, tmp_path):
    chamadas = []

    def fake_http(url, *, method="GET", data=None, headers=None, timeout=25):
        chamadas.append((method, url))
        if "/pessoas/" in url:
            body = json.dumps(
                {"nome_receita": "EMPRESA EXEMPLO EIRELI", "tipo_pessoa": "JURIDICA"}
            ).encode()
            return 200, {}, body
        if "/solicitacoes" in url:
            body = json.dumps(
                {
                    "certidao_existente": True,
                    "certidao": {
                        "id": "abc-123",
                        "data_emissao": "2026-11-24",
                        "data_validade": "2026-12-24",
                        "status": "finalizada",
                        "url_certidao": "https://exemplo.invalid/certidao.pdf",
                    },
                }
            ).encode()
            return 200, {}, body
        return 200, {"Content-Type": "application/pdf"}, b"%PDF-1.4\nconteudo simulado"

    monkeypatch.setattr(mod, "_http_request", fake_http)
    monkeypatch.setattr(
        mod,
        "extrair_texto_pdf",
        lambda _p: "CNPJ 11.222.333/0001-81 NADA CONSTA VALIDA ATE 24/12/2026",
    )

    saida = tmp_path / "H-11.pdf"
    res = mod.emitir_tjdft(
        cnpj_digitos="11222333000181",
        nome="EMPRESA EXEMPLO LTDA",
        tipo="FALENCIA_CONCORDATA",
        saida=saida,
        recriar=False,
    )
    assert saida.is_file()
    assert res["situacao"] == "ok"
    assert res["reutilizada"] is True
    assert res["validade"] == "2026-12-24"
    assert "sem bloqueio" in res["observacao"]
    assert all("certidao_a_recriar" not in u for _, u in chamadas)


def test_emitir_sefaz_go_mock(monkeypatch, tmp_path):
    def fake_http(url, *, method="GET", data=None, headers=None, timeout=25):
        assert method == "POST"
        assert b"Certidao.ConfirmaNomeContribuinte=Sim" in (data or b"")
        return 200, {"Content-Type": "application/pdf"}, b"%PDF-1.3\nsimulado"

    monkeypatch.setattr(mod, "_http_request", fake_http)
    monkeypatch.setattr(
        mod,
        "extrair_texto_pdf",
        lambda _p: "CERTIDAO NEGATIVA CNPJ 11.222.333/0001-81 EMITIDA EM 27/11/2026 VALIDA ATE 26/01/2027",
    )

    saida = tmp_path / "H-05.pdf"
    res = mod.emitir_sefaz_go(
        cnpj_digitos="11222333000181",
        nome="EMPRESA EXEMPLO LTDA",
        tipo="01",
        saida=saida,
    )
    assert saida.is_file()
    assert res["situacao"] == "ok"
    assert res["resultado"] == "NEGATIVA"
    assert res["validade"] == "2027-01-26"
