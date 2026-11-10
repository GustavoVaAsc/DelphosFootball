"""The numbers a report may contain (LLM_PLAN §8.2 L2).

Input: the fact card. Output: the set of literals report prose may contain.
Responsibility: build the single allowed set of the fact card's numbers, so the
verifier and the renderer cannot disagree about what is grounded.

Per fact: the raw value (and its int spelling when an integral float) plus the
formatted display; derived from the valuation pair: the raw difference, its
display and the percentage points. The renderer writes the discount with a
leading minus (`/ -16%`), so `cost_discount_pct` also contributes its signed
spelling. `report_verify.verify_prose_numbers` canonicalizes both sides, so raw
and formatted spellings of one amount collapse to a single canonical number.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any


def iter_facts(fact_card: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield `(key, fact)` for the card's facts, then for each replacement candidate."""
    yield from fact_card["facts"].items()
    for candidate in fact_card["replacements"]:
        yield from candidate.items()


def allowed_number_tokens(fact_card: dict[str, Any]) -> set[str]:
    """Every literal that may legitimately appear as a number in report prose."""
    allowed: set[str] = set()
    for key, fact in iter_facts(fact_card):
        allowed |= _fact_tokens(fact)
        if key == "cost_discount_pct" and re.search(r"\d", fact["display"]):
            allowed.add(f"-{fact['display']}")
    return allowed


def _fact_tokens(fact: dict[str, Any]) -> set[str]:
    value, display = fact["value"], fact["display"]
    if value is None or isinstance(value, bool):
        return set()
    tokens: set[str] = set()
    raw = str(value)
    if re.search(r"\d", raw):
        tokens.add(raw)
        if isinstance(value, float) and value.is_integer():
            tokens.add(str(int(value)))
    if re.search(r"\d", display):
        tokens.add(display)
    return tokens
