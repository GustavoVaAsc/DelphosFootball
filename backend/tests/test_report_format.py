"""Unit tests for the JS-parity display formatters (formatEurM, toFixed, Math.round).

Expected strings were captured from `node` running the verbatim reference
implementations, so each branch pins the design preview's output byte for byte.
"""

from __future__ import annotations

import math

import pytest

from delphos_backend.services.report_format import (
    format_count,
    format_eur_m,
    format_fixed,
    format_pct,
    format_ratio,
    js_round,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "N/D"),
        (float("nan"), "N/D"),
        (0, "€0"),
        (250, "€250"),
        (999, "€999"),
        (1_000, "€1K"),
        (1_540, "€2K"),
        (540_000, "€540K"),
        (825_000, "€825K"),
        # abs < 1e6 stays in the K branch even when toFixed(0) rounds up to 1000.
        (999_999, "€1000K"),
        (1_000_000, "€1.0M"),
        (1_234_567, "€1.2M"),
        # (2.65).toFixed(1) === "2.6" in JS: the double sits below 2.65.
        (2_650_000, "€2.6M"),
        (25_000_000, "€25.0M"),
        (45_000_000, "€45.0M"),
        # Sign is retained inside the symbol: "€" + (-250).toFixed(0).
        (-250, "€-250"),
        (-540_000, "€-540K"),
        (-25_000_000, "€-25.0M"),
        # toFixed strips the sign before rounding and re-applies it, so a tie rounds
        # AWAY from zero: node gives formatEurM(-1500) === "€-2K".
        (-1_500, "€-2K"),
        (-999, "€-999"),
    ],
)
def test_format_eur_m_matches_design_preview(value: float | None, expected: str) -> None:
    assert format_eur_m(value) == expected


@pytest.mark.parametrize(
    ("value", "digits", "expected"),
    [
        (2.65, 1, "2.6"),
        (1.25, 1, "1.3"),
        (1.005, 2, "1.00"),
        # The 0.255 double sits ABOVE 0.255, so node gives (0.255).toFixed(2) === "0.26".
        (0.255, 2, "0.26"),
        (999.999, 0, "1000"),
    ],
)
def test_format_fixed_matches_js_tofixed(value: float, digits: int, expected: str) -> None:
    assert format_fixed(value, digits) == expected


@pytest.mark.parametrize(
    ("value", "digits", "expected"),
    [
        # ECMA-262 toFixed strips the sign, rounds the magnitude picking the larger n
        # on a tie, and re-applies the sign: the tie rounds AWAY FROM ZERO. Node:
        # (-1.5).toFixed(0) === "-2", (-0.5).toFixed(0) === "-1",
        # (-2.5).toFixed(0) === "-3", (-999.5).toFixed(0) === "-1000".
        (-1.5, 0, "-2"),
        (-0.5, 0, "-1"),
        (-2.5, 0, "-3"),
        (-999.5, 0, "-1000"),
        (-0.4, 0, "-0"),
        (-1.25, 1, "-1.3"),
    ],
)
def test_format_fixed_rounds_negative_ties_away_from_zero(
    value: float, digits: int, expected: str
) -> None:
    assert format_fixed(value, digits) == expected


def test_js_round_rounds_half_up_toward_infinity() -> None:
    assert js_round((1 - 0.68) * 100) == 32
    assert js_round(-20.5) == -20
    assert js_round(20.5) == 21
    assert js_round((45_000_000 - 25_000_000) / 25_000_000 * 100) == 80


def test_format_count_and_pct_follow_tofixed() -> None:
    assert format_count(1800.0) == "1800"
    assert format_count(0.75 * 100) == "75"
    assert format_count(None) == "N/D"
    assert format_count(math.nan) == "N/D"
    assert format_pct(0.75) == "75%"
    assert format_pct(0.3) == "30%"
    assert format_pct(0.82) == "82%"
    assert format_pct(1.0) == "100%"
    assert format_pct(None) == "N/D"
    assert format_ratio(1.8) == "1.8x"
    assert format_ratio(0.68) == "0.7x"
    assert format_ratio(None) == "N/D"
