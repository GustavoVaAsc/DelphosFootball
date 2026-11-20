"""The `{fact_ref}` substitution of a scouting-report draft.

Input: prose with `{fact_ref}` placeholders, the fact card and, optionally, the
candidate whose own cells the prose may cite. Output: the prose with every
placeholder replaced by the fact's formatted display string.
Responsibility: resolve a placeholder against exactly one scope and refuse a key
outside it, so the report falls back to the deterministic renderer instead of
publishing a broken sentence (LLM_PLAN §8.2).

A placeholder resolves against exactly one scope. The three top-level sections
resolve against the card's player scope (its facts minus the model's own
diagnostics), and a candidate's prose resolves against that candidate's own cells
only. The card's candidates share key names with the target's facts, so a candidate
scope that fell back to the top-level facts would let a candidate's sentence quote
the TARGET player's figures — a wrong number about a real person, published as if the
model had written it. An unknown key is therefore an error, not a fallback, and so is
a key the player scope excludes: a residual or a classifier probability is the
model's own state, not a scouting fact.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from delphos_backend.services.report_bindings import UnknownPlaceholderError
from delphos_backend.services.report_prompt import PLACEHOLDER_RE
from delphos_backend.services.report_scope import player_scope

__all__ = ["UnknownPlaceholderError", "substitute_placeholders"]


def substitute_placeholders(
    text: str,
    card: Mapping[str, Any],
    candidate: Mapping[str, dict[str, Any]] | None = None,
) -> str:
    """Replace each `{fact_ref}` with its display string; unknown keys raise.

    `candidate` scopes the lookup to that candidate's own cells; without it the
    lookup is the card's player scope. The two scopes never mix.
    """

    def replace(match: re.Match[str]) -> str:
        key = match.group(0)[1:-1]
        scope = candidate if candidate is not None else player_scope(card)
        fact = scope.get(key)
        if fact is None:
            raise UnknownPlaceholderError(key)
        return str(fact["display"])

    return PLACEHOLDER_RE.sub(replace, text)
