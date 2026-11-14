"""Word-prefix market search builder for player name, club, and country.

Input: free-text search query from GET /players?name=... or chat search_players.
Output: a parameterized PostgreSQL WHERE fragment and its bind parameters, or None.
Responsibility: build an accent-folded, word-prefix SQL predicate matching every
whitespace-separated token against player name fields, club name, and citizenship
country (in both dataset English and Spanish country labels). Kept separate from
players.py to preserve the 130-line module budget.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from delphos_backend.repositories.country_search_map import COUNTRY_ES_TO_EN

_ACCENT_SRC = "áàäâãéèëêíìïîóòöôõúùüûñçğşćčđłńřśźżžı"
_ACCENT_DST = "aaaaaeeeeiiiiooooouuuuncgsccdlnrszzzi"
assert len(_ACCENT_SRC) == len(_ACCENT_DST)

_STOPWORDS = frozenset({"de", "del", "el", "la", "las", "los", "y"})
_HAYSTACK_SQL = (
    f"translate(lower(concat_ws(' ', p.name, p.first_name, p.last_name, "
    f"c.name, p.country_of_citizenship)), '{_ACCENT_SRC}', '{_ACCENT_DST}')"
)


def _fold_text(text: str) -> str:
    """Lowercase and strip accents to align Python tokens with SQL translate()."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("ı", "i").replace("ł", "l").replace("đ", "d")


def _escape_like(token: str) -> str:
    return token.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def _matching_token_countries(token: str) -> list[str]:
    """Return English country keys whose Spanish name has a word starting with token."""
    matches: set[str] = set()
    for es_name, en_names in COUNTRY_ES_TO_EN.items():
        words = [w for w in re.split(r"[\s-]+", es_name) if w and w not in _STOPWORDS]
        if es_name.startswith(token) or any(word.startswith(token) for word in words):
            matches.update(en_names)
    return sorted(matches)


def _matching_phrase_countries(phrase: str) -> list[str]:
    """Return English country keys whose Spanish name begins with a multi-word phrase."""
    matches: set[str] = set()
    for es_name, en_names in COUNTRY_ES_TO_EN.items():
        if es_name.startswith(phrase):
            matches.update(en_names)
    return sorted(matches)


def build_search_clause(query: str | None) -> tuple[str, list[Any]] | None:
    """Build a parameterized word-prefix SQL clause for player, club, or country search."""
    if not query:
        return None
    tokens = [tok for tok in _fold_text(query).split() if tok]
    if not tokens:
        return None

    token_clauses: list[str] = []
    params: list[Any] = []
    for token in tokens:
        escaped = _escape_like(token)
        patterns = [f"{escaped}%", f"% {escaped}%", f"%-{escaped}%", f"%'{escaped}%"]
        or_parts = [f"{_HAYSTACK_SQL} LIKE %s ESCAPE '!'"] * len(patterns)
        params.extend(patterns)
        if es_countries := _matching_token_countries(token):
            or_parts.append("p.country_of_citizenship = ANY(%s)")
            params.append(es_countries)
        token_clauses.append("(" + " OR ".join(or_parts) + ")")

    combined = " AND ".join(token_clauses)
    if len(tokens) > 1 and (phrase_countries := _matching_phrase_countries(" ".join(tokens))):
        return f"(({combined}) OR p.country_of_citizenship = ANY(%s))", [
            *params,
            phrase_countries,
        ]
    return f"({combined})", params
