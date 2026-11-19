"""The two citation scopes of the report prompt: which key each part of a draft may cite.

Input: the fact card. Output: the player scope (the citable keys of the three top-level
sections) and the candidate scope (the citable keys of one candidate's assessment).
Responsibility: hold the ONE definition of both scopes, so the message the model reads
and the resolver that substitutes the placeholders cannot disagree about which key is
citable where.

The player scope is the card's facts MINUS the model's own diagnostics
(`MODEL_INTERNAL_KEYS`): a regression residual and a classifier probability are the
model's internal state, not a scouting fact, and a verdict that quotes one states
something about the model rather than about the player. The candidate scope is that
candidate's own cells; the candidates are checked to share one key set, because the
request names one candidate key list for all of them and a list that silently covered
only the first candidate would invite a wrong citation.

This module owns the scopes, not the message: `report_prompt_scope` renders them into
the request and `draft_render` resolves against them.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "MODEL_INTERNAL_KEYS",
    "InconsistentCandidateScope",
    "candidate_names",
    "candidate_scope_keys",
    "player_scope",
    "player_scope_keys",
]

MODEL_INTERNAL_KEYS: tuple[str, ...] = (
    "residual_log10",
    "rf_undervalued_pred",
    "rf_undervalued_prob",
    "dt_undervalued_pred",
)
"""The card's model-internal keys: diagnostics, not scouting facts, never citable."""


class InconsistentCandidateScope(ValueError):
    """The card's candidates do not share one key set."""


def player_scope(card: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The cells the three top-level sections may cite, in the card's own order."""
    facts: dict[str, dict[str, Any]] = card["facts"]
    return {key: fact for key, fact in facts.items() if key not in MODEL_INTERNAL_KEYS}


def player_scope_keys(card: dict[str, Any]) -> list[str]:
    """The keys the three top-level sections may cite."""
    return list(player_scope(card))


def candidate_scope_keys(card: dict[str, Any]) -> list[str]:
    """The keys one candidate's assessment may cite; empty when the card has none.

    The union over every candidate, with the assumption checked rather than
    assumed: the candidates are built by one constructor, so a disagreement means the
    card is malformed, and a request that names one key list for all of them would
    be wrong.
    """
    replacements = card.get("replacements") or []
    if not replacements:
        return []
    key_sets = {frozenset(candidate) for candidate in replacements}
    if len(key_sets) > 1:
        raise InconsistentCandidateScope(
            "the card's candidates do not share the same key set: "
            f"{[sorted(keys) for keys in sorted(key_sets, key=len)]}"
        )
    union: dict[str, None] = {}
    for candidate in replacements:
        union.update(dict.fromkeys(candidate))
    return list(union)


def candidate_names(card: dict[str, Any]) -> list[str]:
    """The names the draft must repeat verbatim, one per candidate."""
    return [
        str(candidate["candidate_name"]["display"]) for candidate in card.get("replacements") or []
    ]
