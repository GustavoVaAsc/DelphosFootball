"""Unit tests for the Spanish scouting report prompt and its version string."""

from __future__ import annotations

import re

from scouting_fixtures import profile, replacements, valuation

from delphos_backend.core.config import Settings
from delphos_backend.services.draft_render import UnknownPlaceholderError, substitute_placeholders
from delphos_backend.services.report_facts import build_fact_card
from delphos_backend.services.report_prompt import (
    PLACEHOLDER_RE,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_prompt_version,
)
from delphos_backend.services.report_prompt_scope import build_user_message, scope_block

_SYNTAX_TOKEN = "fact_ref"
"""The name the prompt gives to the placeholder syntax; it is not a card key."""


def _card() -> dict:
    """The card of the shared fixture player, with its two replacement candidates."""
    return build_fact_card(profile(), valuation(), replacements())


def _placeholders(text: str) -> list[str]:
    """The keys the text names between braces, without the braces."""
    return [match[1:-1] for match in PLACEHOLDER_RE.findall(text)]


def _map_entries(text: str) -> list[tuple[str, list[str]]]:
    """The `- parte: {clave}, ...` lines of the text, as (label, keys) pairs.

    A line whose label is long is a sentence that happens to mention a key, not an
    entry of the map, so it is left out of the per-part assignment.
    """
    entries: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- ") or "{" not in stripped:
            continue
        label, _, rest = stripped[2:].partition(":")
        keys = _placeholders(rest)
        if keys and len(label) <= 60:
            entries.append((label, keys))
    return entries


def test_prompt_names_the_three_sections() -> None:
    for section_id in ("dictamen_financiero", "rendimiento", "alternativas"):
        assert section_id in SYSTEM_PROMPT


def test_prompt_states_placeholder_syntax() -> None:
    assert "{fact_ref}" in SYSTEM_PROMPT
    assert "{fair_value_eur}" in SYSTEM_PROMPT
    assert PLACEHOLDER_RE.search("{fair_value_eur}") is not None


def test_prompt_states_prohibitions() -> None:
    for stem in ("lesion", "contrato", "salario", "agente", "disciplin"):
        assert stem in SYSTEM_PROMPT
    assert "comparaciones poblacionales" in SYSTEM_PROMPT


def test_prompt_states_register_scope_and_language() -> None:
    for phrase in ("columnas", "API", "depuración", "este jugador", "español", "tal cual"):
        assert phrase in SYSTEM_PROMPT


def test_prompt_states_the_two_citation_scopes_and_the_figures() -> None:
    """The prompt says which scope a key belongs to and which figures the report carries."""
    for phrase in ("Ámbitos de cita", "lista del JUGADOR", "lista del CANDIDATO"):
        assert phrase in SYSTEM_PROMPT
    for key in (
        "{market_value_eur}",
        "{fair_value_eur}",
        "{value_gap_pct}",
        "{minutes}",
        "{apps}",
        "{goals}",
        "{assists}",
        "{cost_savings_eur}",
        "{similarity_score}",
    ):
        assert key in SYSTEM_PROMPT


def test_prompt_version_has_expected_shape() -> None:
    assert re.fullmatch(r"v\d+-t[\d.]+-p[\d.]+-k\d+", PROMPT_VERSION)
    assert PROMPT_VERSION == "v2-t0.7-p0.8-k20"
    assert build_prompt_version(Settings()) == PROMPT_VERSION


def test_the_prompt_revision_default_is_the_shipped_one() -> None:
    """The shipped revision is v2: the prompt names the keys the draft may cite."""
    assert Settings().llm_report_prompt_version == "v2-t0.7-p0.8-k20"
    assert build_prompt_version(Settings()).startswith("v2-")


def test_prompt_version_changes_with_sampling_parameters() -> None:
    hotter = build_prompt_version(Settings(llm_temperature=0.2, llm_top_p=0.9, llm_top_k=40))

    assert hotter == "v2-t0.2-p0.9-k40"
    assert hotter != PROMPT_VERSION
    assert build_prompt_version(Settings(llm_temperature=0.9)) != PROMPT_VERSION


def test_prompt_version_takes_text_revision_from_settings() -> None:
    version = build_prompt_version(Settings(llm_report_prompt_version="v9-t0.5-p0.5-k5"))

    assert version == "v9-t0.7-p0.8-k20"


def test_every_key_the_prompt_names_resolves_in_one_of_the_scopes() -> None:
    """A key the prompt or the request names must exist in the card.

    The prompt's key map and its list of the figures the report must carry are
    written by hand; this test is what keeps them from drifting away from the
    card: rename a fact in `report_facts` and the test fails here, instead of the
    reports failing at run time.
    """
    card = _card()
    candidate_scope = card["replacements"][0]

    for text in (SYSTEM_PROMPT, scope_block(card)):
        for key in _placeholders(text):
            if key == _SYNTAX_TOKEN:
                continue  # the syntax of the placeholder, not a key of the card
            assert _resolves_in_a_scope(key, card, candidate_scope), f"{key} is in no scope"


def test_every_key_of_the_map_resolves_in_the_scope_the_map_assigns_it() -> None:
    """The map says which scope each key belongs to; the resolver must agree."""
    card = _card()
    candidate_scope = card["replacements"][0]
    entries = _map_entries(SYSTEM_PROMPT) + _map_entries(scope_block(card))

    assert entries  # the map is not empty, so the assertions below are not vacuous
    for label, keys in entries:
        for key in keys:
            if "candidato" in label:
                assert substitute_placeholders("{" + key + "}", card, candidate_scope)
            else:
                assert substitute_placeholders("{" + key + "}", card)


def test_the_request_names_no_key_the_card_does_not_hold() -> None:
    """The request's key lists are the card's own scopes, key by key."""
    card = _card()
    message = build_user_message(card)

    for key in _placeholders(message):
        if key == _SYNTAX_TOKEN:
            continue
        assert _resolves_in_a_scope(key, card, card["replacements"][0]), f"{key} is in no scope"


def _resolves_in_a_scope(key: str, card: dict, candidate_scope: dict) -> bool:
    """Whether the key resolves in the player scope or in the candidate scope."""
    for scope in (None, candidate_scope):
        try:
            substitute_placeholders("{" + key + "}", card, scope)
        except UnknownPlaceholderError:
            continue
        return True
    return False
