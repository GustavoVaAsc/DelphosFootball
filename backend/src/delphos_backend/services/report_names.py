"""The database names the report request can carry (LLM_PLAN §7.3).

Input: the fact card. Output: the check that every name in it is representable.
Responsibility: refuse a name the report request cannot represent, so a name that
reads as an instruction never reaches the model.

Several character classes are refused, not only the C0 controls. A control
character (a newline, a carriage return, a tab) would end the line the name is
written on inside the request, so whatever follows it would read as part of the
instructions. A **format** character (a bidi override such as U+202E, a zero-width
joiner) is invisible in the request and reverses or hides what is around it in the
published HTML. A **line** or **paragraph** separator (U+2028, U+2029) ends a line
without being a C0 control, and JSON encoding leaves it raw. A **surrogate** is not
a character at all. The comma would make the name ambiguous when the model must
copy it verbatim out of a listing.

A name is database text, so none of these can be ruled out by the schema that
stores it: the request renders every name as a JSON string, which keeps a name from
starting a token, and the listing joins the names with " | ", which keeps a comma
from being a separator — but a name that carries an instruction is still an
instruction the model may follow, so the data itself is refused.

The refusal is a data problem, not a report problem: the publish stage rejects the
CANDIDATE row before it reaches the database (see
`ml/src/delphos_ml/pipeline/_publish_names.py`), and the card builder refuses the
target player's own name and the club names here, so a report about a player whose
name cannot be represented falls back to the deterministic renderer instead of
carrying the name into the model or into the published HTML.
"""

from __future__ import annotations

import unicodedata
from typing import Any

__all__ = [
    "UnrepresentableCandidateNameError",
    "assert_representable_candidate_names",
    "assert_representable_player_names",
    "unrepresentable_reason",
]

_REFUSED_CATEGORIES = ("Cc", "Cf", "Zl", "Zp", "Cs")
"""The Unicode categories a name may not contain: controls, formats, separators."""


class UnrepresentableCandidateNameError(ValueError):
    """A name cannot be represented in the report request."""


def assert_representable_candidate_names(card: dict[str, Any]) -> None:
    """Raise `UnrepresentableCandidateNameError` naming the first offending name."""
    for candidate in card.get("replacements") or []:
        name = str(candidate["candidate_name"]["display"])
        reason = unrepresentable_reason(name)
        if reason is not None:
            raise UnrepresentableCandidateNameError(
                f"the candidate name {name!r} cannot be represented in the report request: {reason}"
            )


def assert_representable_player_names(card: dict[str, Any]) -> None:
    """Raise when the TARGET player's own names cannot be represented.

    The target's name and the club names reach the model like any other card value
    (the report may cite `{player_name}`), and they reach the published HTML. A
    name carrying a bidi override or a line separator must not travel either way.
    """
    facts = card.get("facts") or {}
    for key in ("player_name", "club_name"):
        cell = facts.get(key)
        if not isinstance(cell, dict):
            continue
        name = str(cell.get("display", ""))
        reason = unrepresentable_reason(name)
        if reason is not None:
            raise UnrepresentableCandidateNameError(
                f"the {key} {name!r} cannot be represented in the report request: {reason}"
            )


def unrepresentable_reason(name: str) -> str | None:
    """Why the name cannot be represented, or None when it can."""
    for character in name:
        category = unicodedata.category(character)
        if category in _REFUSED_CATEGORIES:
            return f"it contains a {category} character ({character!r})"
    if "," in name:
        return "it contains a comma, which makes the name ambiguous in a listing"
    return None
