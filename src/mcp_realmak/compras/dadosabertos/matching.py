"""Free-text matching against catalog names (CATMAT PDM / CATSER).

The Compras.gov.br API has no working text filter on its catalogs, so the
catalogs are downloaded once and searched locally. Pure logic, no HTTP.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")

_STOPWORDS = frozenset({"de", "da", "do", "das", "dos", "para", "com", "e", "a", "o", "em"})
_MIN_PREFIX_LEN = 3


def tokenize(text: str) -> list[str]:
    """Lowercase, strip accents and split into alphanumeric tokens (stopwords dropped)."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    tokens = re.findall(r"[a-z0-9]+", ascii_text.lower())
    return [t for t in tokens if t not in _STOPWORDS]


def _token_matches(query_token: str, candidate_tokens: Sequence[str]) -> bool:
    """Short tokens (e.g. "x") must match exactly; longer ones also by prefix (raio ~ raios)."""
    if len(query_token) < _MIN_PREFIX_LEN:
        return query_token in candidate_tokens
    return any(
        ct.startswith(query_token) or (len(ct) >= _MIN_PREFIX_LEN and query_token.startswith(ct))
        for ct in candidate_tokens
    )


def is_exact(texto: str, nome: str) -> bool:
    """True when the query and the catalog name have the same set of tokens."""
    return set(tokenize(texto)) == set(tokenize(nome)) and bool(tokenize(texto))


def rank_by_text(
    texto: str,
    itens: Sequence[T],
    key: Callable[[T], str | None],
    limite: int = 10,
) -> tuple[list[T], bool]:
    """Rank catalog entries by how many query tokens their name contains.

    Returns:
        (matches, complete). ``complete`` is True when every returned entry
        contains all query tokens; False means only a partial match was found
        (the entries share the highest number of tokens). Empty when nothing matches.
    """
    query = tokenize(texto)
    if not query:
        return [], False

    scored: list[tuple[int, int, str, T]] = []
    for item in itens:
        nome = key(item) or ""
        candidate_tokens = tokenize(nome)
        matched = sum(1 for q in query if _token_matches(q, candidate_tokens))
        if matched:
            scored.append((matched, len(candidate_tokens), nome, item))
    if not scored:
        return [], False

    best = max(s[0] for s in scored)
    top = [s for s in scored if s[0] == best]
    # Most matched tokens first, then fewer extra words (closer to the query), then name.
    top.sort(key=lambda s: (s[1], s[2]))
    return [s[3] for s in top[:limite]], best == len(query)
