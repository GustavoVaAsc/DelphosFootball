"""Unit tests for the numeric extractor, verifier, and repair request builder.

The allowed set comes from `report_facts.allowed_number_tokens`, the single builder
of the numbers a report may contain: the verifier only canonicalises and compares.
"""

from __future__ import annotations

import pytest
from scouting_fixtures import profile, valuation

from delphos_backend.services.report_facts import allowed_number_tokens, build_fact_card
from delphos_backend.services.report_verify import (
    build_repair_messages,
    extract_number_tokens,
    verify_prose_numbers,
)

CLEAN_PROSE = (
    "Lionel Messi, del Inter Miami, jugó 1,800 minutos con 15 goles y 12 "
    "asistencias y ganó el 75% de los partidos. Su valor de mercado es €25.0M frente "
    "a un valor justo de €45.0M: una diferencia de €20.0M (+80%)."
)


def _allowed() -> set[str]:
    """The numbers the fact card of the fixture player grounds."""
    return allowed_number_tokens(build_fact_card(profile(), valuation(), None))


@pytest.mark.parametrize(
    ("snippet", "expected"),
    [
        ("Su valor es €25.0M hoy.", ["€25.0M"]),
        ("Tasa de victoria del 75% esta temporada.", ["75%"]),
        ("Acumuló 1,800 minutos completos.", ["1,800"]),
        ("Mejora un +32% respecto al año anterior.", ["+32%"]),
        ("Cae un -12% frente a la media.", ["-12%"]),
        ("Se alquila por €540K al año.", ["€540K"]),
        ("Cuesta €250 fijo.", ["€250"]),
        ("Metió 15 goles en la temporada.", ["15"]),
        ("Ratio de 1.8x por jugada.", ["1.8x"]),
        # A magnitude suffix followed by prose punctuation must stay attached to the
        # number. The extractor used to drop the suffix here: the trailing lookahead
        # rejected the comma, so '€9.9M, muy' matched as '€9.9' and the verifier
        # flagged the wrong token.
        ("Su valor en €9.9M, muy por encima.", ["€9.9M"]),
        ("Cotiza en €25.0M; y sube.", ["€25.0M"]),
        ("Ahorra €540K.", ["€540K"]),
        ("Un 75% de victorias, nada menos.", ["75%"]),
        # A comma that CONTINUES the number must still bind to it, not split it.
        ("Acumuló 1,80 y 12,34 unidades.", ["1,80", "12,34"]),
    ],
)
def test_extract_number_formats(snippet: str, expected: list[str]) -> None:
    assert [occurrence.token for occurrence in extract_number_tokens(snippet)] == expected


def test_extractor_keeps_thousands_separator_intact() -> None:
    occurrences = extract_number_tokens("Acumuló 1,800 y 1,000,000 unidades, hoy 18000.")

    tokens = [occurrence.token for occurrence in occurrences]
    assert tokens == ["1,800", "1,000,000", "18000"]


def test_extractor_ignores_placeholder_keys() -> None:
    occurrences = extract_number_tokens("Valor: {fair_value_eur} y {performance_2025}.")

    assert occurrences == []


def test_verify_clean_prose_passes() -> None:
    result = verify_prose_numbers(CLEAN_PROSE, _allowed())

    assert result.passed
    assert result.violations == ()


def test_verify_flags_injected_number_by_name() -> None:
    prose = "El modelo sitúa su valor en €9.9M, muy por encima."

    result = verify_prose_numbers(prose, _allowed())

    assert not result.passed
    assert [violation.token for violation in result.violations] == ["€9.9M"]
    violation = result.violations[0]
    assert violation.start == prose.index("€9.9M")
    assert "€9.9M" in violation.context


def test_verify_allows_number_present_in_card() -> None:
    allowed = _allowed()

    display_form = verify_prose_numbers("Su valor de mercado asciende a €25.0M.", allowed)
    derived_form = verify_prose_numbers("La diferencia con su valor justo es del +80%.", allowed)

    assert display_form.passed
    assert derived_form.passed


def test_repair_request_names_offending_token() -> None:
    original = [
        {"role": "system", "content": "instrucciones"},
        {"role": "user", "content": "datos"},
    ]
    result = verify_prose_numbers("Vale €9.9M en el mercado.", _allowed())

    repaired = build_repair_messages(original, result)

    assert repaired[:2] == original
    assert repaired[-1]["role"] == "user"
    assert "€9.9M" in repaired[-1]["content"]
