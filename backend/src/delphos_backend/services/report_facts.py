"""Fact-card assembly for the scouting report pipeline (LLM_PLAN §8.1).

Input: the raw player profile, valuation and replacement-payload dicts that
`llm_reports.generate_report` reads (same sources, same values).
Output: a JSON-serializable fact card `{"facts": {key: {"value", "display"}},
"replacements": [...]}`, plus `allowed_number_tokens(card)` — every number report
prose may contain (LLM_PLAN §8.2 L2). Responsibility: assemble the card, give each
citable fact a flat short key, its raw value and a pre-formatted display string, and
resolve English vocabulary to Spanish through `delphos_domain`; publish no per-90
figure (§9.3).

The card's parts live in two modules so this one stays near the 130-line cap of
backend/AGENTS.md §4: `report_card_facts` reads the player's facts and
`report_card_cells` builds the cells of one candidate. The allowed-number set lives
in `report_allowed` and is re-exported here, its public home.

A candidate name the report request cannot represent is refused here, at card-build
time: the card is what the request is built from, so a name that carries an
instruction must never reach it. The deterministic renderer reads the card too and
escapes every value, so it gets `build_deterministic_card` — the same card without
that refusal, for the fallback that must answer even when the data is unusable.
"""

from __future__ import annotations

from typing import Any

from delphos_backend.services.report_allowed import allowed_number_tokens, iter_facts
from delphos_backend.services.report_card_cells import replacement_entry
from delphos_backend.services.report_card_facts import player_facts
from delphos_backend.services.report_names import (
    assert_representable_candidate_names,
    assert_representable_player_names,
)

__all__ = [
    "allowed_number_tokens",
    "build_deterministic_card",
    "build_fact_card",
    "iter_facts",
]


def build_fact_card(
    profile: dict[str, Any],
    valuation: dict[str, Any],
    replacements: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the fact card from the raw dicts the scouting context reads.

    Raises `UnrepresentableCandidateNameError` when a candidate name cannot be
    represented in the report request.
    """
    card = _build_card(profile, valuation, replacements)
    assert_representable_candidate_names(card)
    assert_representable_player_names(card)
    return card


def build_deterministic_card(
    profile: dict[str, Any],
    valuation: dict[str, Any],
    replacements: dict[str, Any] | None,
) -> dict[str, Any]:
    """The card the deterministic renderer reads, without the request's name rule.

    The renderer escapes every value for an HTML text context and never sends the
    card to a model, so a name the request cannot represent is rendered rather than
    refused: the endpoint still answers with a report.
    """
    return _build_card(profile, valuation, replacements)


def _build_card(
    profile: dict[str, Any],
    valuation: dict[str, Any],
    replacements: dict[str, Any] | None,
) -> dict[str, Any]:
    """The card itself: the player's facts and the cells of every candidate."""
    payload = replacements or {}
    items = payload.get("replacements") or []
    return {
        "facts": player_facts(profile, valuation, payload),
        "replacements": [replacement_entry(item) for item in items],
    }
