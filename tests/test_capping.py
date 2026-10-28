from __future__ import annotations

from mcp_realmak.capping import cap_text, dumps
from mcp_realmak.sanitize import mask_sensitive


def test_texto_curto_passa_inteiro():
    assert cap_text("abc", 10) == "abc"


def test_texto_longo_e_cortado_com_aviso_em_portugues():
    r = cap_text("x" * 500, 100)
    assert r.startswith("x" * 100) and "cortado em 100" in r and "paginação" in r
    assert len(r) < 300


def test_dumps_mantem_acentos():
    assert "licitação" in dumps({"a": "licitação"})


def test_mask_sensitive():
    texto = (
        "x-auth-token: 'abc123def' Authorization: Bearer gld_live_zzfake99 "
        "https://h.test/download?auth=eyJabcdefghijklmnop&x=1 _boletim_web_session=zzz"
    )
    r = mask_sensitive(texto)
    for segredo in ("abc123def", "zzfake99", "eyJabcdefghijklmnop", "zzz", "x=1"):
        assert segredo not in r
