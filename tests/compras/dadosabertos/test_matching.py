"""Tests for free-text matching against catalog names."""

from mcp_realmak.compras.dadosabertos.matching import is_exact, rank_by_text, tokenize

NOMES = [
    "CADEIRA ESCRITÓRIO",
    "CADEIRA ESCRITÓRIO GIRATÓRIA COM BRAÇOS",
    "APARELHO RAIOS X USO MÉDICO",
    "APARELHO DETECTOR DE ARMA / EXPLOSIVO POR RAIO X",
    "MESA ESCRITÓRIO",
]


def _rank(texto: str) -> tuple[list[str], bool]:
    return rank_by_text(texto, NOMES, key=lambda n: n)


class TestTokenize:
    def test_strips_accents_case_and_stopwords(self) -> None:
        assert tokenize("Cadeira DE Escritório") == ["cadeira", "escritorio"]

    def test_keeps_single_letter_tokens(self) -> None:
        assert tokenize("raio x") == ["raio", "x"]

    def test_splits_punctuation(self) -> None:
        assert tokenize("FIXO-FIXO STFC/LOCAL") == ["fixo", "fixo", "stfc", "local"]


class TestRankByText:
    def test_complete_match_prefers_closest_name(self) -> None:
        matches, completo = _rank("cadeira escritório")
        assert completo is True
        assert matches[0] == "CADEIRA ESCRITÓRIO"
        assert len(matches) == 2

    def test_prefix_matches_plural(self) -> None:
        matches, completo = _rank("raio x")
        assert completo is True
        assert "APARELHO RAIOS X USO MÉDICO" in matches
        assert "APARELHO DETECTOR DE ARMA / EXPLOSIVO POR RAIO X" in matches

    def test_short_token_requires_exact_match(self) -> None:
        # "x" matches only the whole token, never as a prefix of other words
        matches, completo = _rank("x")
        assert completo is True
        assert set(matches) == {
            "APARELHO RAIOS X USO MÉDICO",
            "APARELHO DETECTOR DE ARMA / EXPLOSIVO POR RAIO X",
        }

    def test_partial_match_flagged_incomplete(self) -> None:
        matches, completo = _rank("scanner raio x")
        assert completo is False
        assert matches  # closest ones, sharing "raio" and "x"

    def test_no_match(self) -> None:
        assert _rank("xyzzy") == ([], False)

    def test_empty_query(self) -> None:
        assert _rank("de da") == ([], False)

    def test_limit(self) -> None:
        matches, _ = rank_by_text("cadeira", NOMES, key=lambda n: n, limite=1)
        assert len(matches) == 1


class TestIsExact:
    def test_same_tokens_any_order_and_accent(self) -> None:
        assert is_exact("escritorio cadeira", "CADEIRA ESCRITÓRIO") is True

    def test_extra_words_not_exact(self) -> None:
        assert is_exact("cadeira escritório", "CADEIRA ESCRITÓRIO GIRATÓRIA") is False

    def test_empty_query_never_exact(self) -> None:
        assert is_exact("de", "de") is False
