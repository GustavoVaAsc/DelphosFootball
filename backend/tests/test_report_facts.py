"""Unit tests for the fact-card builder and its allowed-number set (LLM_PLAN §8.1/§8.2)."""

from __future__ import annotations

import json

from scouting_fixtures import profile, replacements, valuation

from delphos_backend.services.report_facts import (
    allowed_number_tokens,
    build_fact_card,
    iter_facts,
)


def _card():
    return build_fact_card(profile(), valuation(), replacements())


def test_every_fact_has_flat_key_raw_value_and_display() -> None:
    card = _card()

    assert set(card) == {"facts", "replacements"}
    for key, fact in iter_facts(card):
        assert "." not in key, f"fact key must be flat: {key}"
        assert set(fact) == {"value", "display"}
        assert isinstance(fact["display"], str)
        assert fact["display"] != ""

    # The names LLM_PLAN §8.1 calls out, flat as specified.
    for key in ("fair_value_eur", "market_value_eur", "goals", "win_rate"):
        assert key in card["facts"]
    for key in ("rank", "candidate_name", "cost_savings_eur", "cost_ratio"):
        assert key in card["replacements"][0]


def test_missing_values_render_not_available() -> None:
    card = build_fact_card(
        {
            "player_id": 1,
            "name": "Sin Datos",
            "position": None,
            "sub_position": None,
            "club_name": None,
            "cluster_id": None,
            "active_season": {},
        },
        {
            "season": 2025,
            "market_value_eur": None,
            "fair_value_eur": None,
            "residual_log10": None,
            "valuation_status": None,
            "is_undervalued": None,
            "rf_undervalued_prob": None,
            "rf_undervalued_pred": None,
            "dt_undervalued_pred": None,
        },
        None,
    )
    facts = card["facts"]
    for key in (
        "club_name",
        "position",
        "sub_position",
        "cluster_id",
        "league_id",
        "minutes",
        "market_value_eur",
        "fair_value_eur",
        "value_gap_eur",
        "value_gap_pct",
        "valuation_status",
        "rf_undervalued_prob",
        "is_undervalued",
    ):
        assert facts[key]["display"] == "N/D", key
    assert card["replacements"] == []


def test_spanish_labels_replace_raw_english() -> None:
    card = _card()
    facts = card["facts"]

    # The position vocabulary mirrors POS_LABELS in the design preview
    # (frontend/design-preview/index.html:1494-1498).
    assert facts["position"] == {"value": "Attack", "display": "Ataque"}
    assert facts["sub_position"] == {"value": "Right Winger", "display": "Extremo Derecho"}
    assert facts["league_id"] == {"value": "ES1", "display": "LaLiga"}
    assert facts["valuation_status"] == {"value": "undervalued", "display": "Infravalorado"}
    assert facts["cluster_id"] == {"value": 0, "display": "Creador Ofensivo"}
    candidates = card["replacements"]
    assert candidates[0]["candidate_valuation_status"]["display"] == "Infravalorado"
    assert candidates[1]["candidate_valuation_status"]["display"] == "Valor Justo"


def test_card_exposes_the_resolved_role() -> None:
    """The role the report prints is a card fact, resolved like the preview."""
    card = _card()

    assert card["facts"]["role"]["display"] == "Extremo Derecho"

    unknown = build_fact_card(
        profile(position="Goalkeeper", sub_position=None),
        valuation(),
        None,
    )
    assert unknown["facts"]["role"]["display"] == "Posición Desconocida"


def test_role_resolves_from_the_sub_position_when_position_is_null() -> None:
    """A NULL position must not hide the role the sub-position names."""
    card = build_fact_card(
        profile(position=None, sub_position="Right Winger"),
        valuation(),
        None,
    )

    assert card["facts"]["role"]["display"] == "Extremo Derecho"
    # The position cell itself is still absent, and says so.
    assert card["facts"]["position"]["display"] == "N/D"


def test_unknown_codes_fall_back_to_the_raw_value() -> None:
    card = build_fact_card(
        profile(position="Wingback", active_season={"league_id": "ZZ9", "minutes": 90.0}),
        valuation(valuation_status="mystery"),
        None,
    )
    facts = card["facts"]

    # A position the vocabulary does not manage falls back to a neutral Spanish
    # form: the model must never read unmanaged English in the card.
    assert facts["position"]["display"] == "Posición Desconocida"
    assert facts["league_id"]["display"] == "ZZ9"
    assert facts["valuation_status"]["display"] == "mystery"


def test_card_contains_no_per90_figure() -> None:
    card = _card()
    keys = [key for key, _fact in iter_facts(card)]

    for needle in ("per90", "per_90", "per-90", "per 90", "por90"):
        assert not any(needle in key.lower() for key in keys), f"per-90 key: {needle}"
    blob = json.dumps(card, default=str).lower()
    for needle in ("per90", "per_90", "per-90", "por90"):
        assert needle not in blob, f"per-90 value: {needle}"


def test_allowed_numbers_covers_raw_formatted_and_derived_variants() -> None:
    allowed = allowed_number_tokens(_card())

    # Raw and formatted variants of a known fact.
    assert "25000000.0" in allowed
    assert "25000000" in allowed
    assert "€25.0M" in allowed
    # The derived difference and percentage (fair - market = €20M = +80%).
    assert "20000000.0" in allowed
    assert "€20.0M" in allowed
    assert "80" in allowed
    assert "80%" in allowed
    # Percent facts keep both spellings; booleans ground no numbers.
    assert "0.75" in allowed
    assert "75%" in allowed
    assert "Sí" not in allowed
    assert "True" not in allowed
    # The renderer writes the discount with a leading minus: "/ -16%".
    assert "-16%" in allowed
    # Qualifying count 0 grounds the "(0 pares cualificados)" sentence.
    assert "0" in allowed
