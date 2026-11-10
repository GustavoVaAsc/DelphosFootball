"""Display formatters ported from the design preview's JavaScript (LLM_PLAN §7.4).

Input: raw numeric values from the analytics data. Output: pre-formatted display
strings (`€25.0M`, `1800`, `75%`, `1.8x`). Responsibility: be the single backend
source of the product's number formatting, so the fact card, the deterministic
renderer and the LLM prompt cannot disagree with the UI.

The JS semantics are reproduced deliberately rather than approximated with Python's
`round()`: `toFixed` rounds the *exact* binary value and resolves ties by picking the
larger integer, so `(1.25).toFixed(1)` is `"1.3"` while `(2.65).toFixed(1)` is
`"2.6"` (the double sits below 2.65) — which rules out `value * 10**digits` rounding
and half-even. The spec strips the sign before rounding and re-applies it, so a tie
rounds *away from zero*: `(-1.5).toFixed(0)` is `"-2"`. `Math.round` is a different
rule (half up toward +infinity, `Math.round(-20.5) == -20`) and `js_round` implements
that one. The branch thresholds compare `Math.abs(value)` before formatting, so
`999999` stays in the K branch and renders `€1000K`, and the sign is kept inside the
symbol (`€-250`). All formatters map `None` and `NaN` to `"N/D"`: the JS reference
crashes on `null` counts and prints `"NaN"`, but this module feeds the fallback
renderer, which must never fail.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal


def js_round(value: float) -> int:
    """JS `Math.round`: nearest integer, ties toward +infinity."""
    return math.floor(value + 0.5)


def format_fixed(value: float | None, digits: int) -> str:
    """JS `Number.prototype.toFixed(digits)`, or `"N/D"` for missing values.

    Rounds the exact `Decimal` of the double with ties *away from zero*, matching the
    spec's "pick the larger n" rule on the magnitude (the sign is stripped before
    rounding and re-applied afterwards): so `(2.65).toFixed(1)` stays `"2.6"`,
    `(1.25).toFixed(1)` becomes `"1.3"` and `(-1.5).toFixed(0)` becomes `"-2"`.
    """
    if _is_missing(value):
        return "N/D"
    quantum = Decimal(1).scaleb(-digits)
    quantized = Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)
    return f"{quantized:.{digits}f}"


def format_eur_m(value: float | None) -> str:
    """JS `formatEurM` (index.html:1553): `€25.0M` / `€540K` / `€250`, `"N/D"` for null."""
    if _is_missing(value):
        return "N/D"
    if abs(value) >= 1e6:
        return f"€{format_fixed(value / 1e6, 1)}M"
    if abs(value) >= 1e3:
        return f"€{format_fixed(value / 1e3, 0)}K"
    return f"€{format_fixed(value, 0)}"


def format_count(value: float | None) -> str:
    """`toFixed(0)` for counts: minutes, apps, starts, goals, assists, age."""
    if _is_missing(value):
        return "N/D"
    return str(js_round(value))


def format_pct(value: float | None) -> str:
    """`(ratio * 100).toFixed(0) + '%'` for rates: win rate, probabilities, similarity."""
    if _is_missing(value):
        return "N/D"
    return f"{js_round(value * 100)}%"


def format_ratio(value: float | None) -> str:
    """`toFixed(1) + 'x'` for cost ratios (`1.8x`)."""
    if _is_missing(value):
        return "N/D"
    return f"{format_fixed(value, 1)}x"


def _is_missing(value: float | None) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))
