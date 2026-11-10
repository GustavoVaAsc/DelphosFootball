"""Unit tests for the Spanish scouting report prompt and its version string."""

from __future__ import annotations

import re

from delphos_backend.core.config import Settings
from delphos_backend.services.report_prompt import (
    PLACEHOLDER_RE,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_prompt_version,
)


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


def test_prompt_version_has_expected_shape() -> None:
    assert re.fullmatch(r"v\d+-t[\d.]+-p[\d.]+-k\d+", PROMPT_VERSION)
    assert PROMPT_VERSION == "v1-t0.7-p0.8-k20"
    assert build_prompt_version(Settings()) == PROMPT_VERSION


def test_prompt_version_changes_with_sampling_parameters() -> None:
    hotter = build_prompt_version(Settings(llm_temperature=0.2, llm_top_p=0.9, llm_top_k=40))

    assert hotter == "v1-t0.2-p0.9-k40"
    assert hotter != PROMPT_VERSION
    assert build_prompt_version(Settings(llm_temperature=0.9)) != PROMPT_VERSION


def test_prompt_version_takes_text_revision_from_settings() -> None:
    version = build_prompt_version(Settings(llm_report_prompt_version="v2-t0.5-p0.5-k5"))

    assert version == "v2-t0.7-p0.8-k20"
