"""Mascara segredos em logs e mensagens de erro (inspirado no mask_sensitive do CRM)."""

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # URLs: descarta a query string, onde ficam as assinaturas
    (re.compile(r"(https?://[^\s\"'>?]+)\?[^\s\"'>]*"), r"\1"),
    (re.compile(r"(x-auth-token['\"]?\s*[:=]\s*['\"]?)[^'\"\s,}]+", re.I), r"\1***"),
    (re.compile(r"(Authorization['\"]?\s*[:=]\s*['\"]?)(Bearer|Basic)\s+[^'\"\s,}]+", re.I), r"\1\2 ***"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", re.I), r"\1***"),
    (re.compile(r"gld_live_[A-Za-z0-9]+"), "gld_live_***"),
    (re.compile(r"(_boletim_web_session|cnl-[\w-]+|licitacao)=[^;\s,]+", re.I), r"\1=***"),
    (re.compile(r"(auth=)[A-Za-z0-9_\-\.]{12,}"), r"\1***"),
]


def mask_sensitive(text: object) -> str:
    """Remove tokens, cookies e assinaturas de um texto."""
    value = str(text)
    for pattern, repl in _PATTERNS:
        value = pattern.sub(repl, value)
    return value
