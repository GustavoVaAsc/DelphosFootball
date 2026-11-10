"""Unit tests for the structured scouting report draft schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from delphos_backend.services.report_schema import (
    ReportSection,
    ScoutingReportDraft,
    build_schema_repair_messages,
    ensure_no_raw_numbers,
)


def make_draft(**overrides: object) -> dict[str, object]:
    """A well-formed draft whose every number lives inside a {fact_ref} placeholder."""
    base: dict[str, object] = {
        "dictamen_financiero": {
            "headline": "Infravalorado frente al mercado",
            "body": "El club paga {market_value_eur} por un valor justo de {fair_value_eur}.",
        },
        "rendimiento": {
            "headline": "Titular indiscutible",
            "body": "Acumuló {minutes} minutos con {goals} goles y {assists} asistencias.",
        },
        "alternativas": {
            "headline": "Reposición asequible",
            "body": "Solo {qualifying_count} candidatos superan el filtro de coste.",
            "candidatos": [
                {
                    "nombre": "Jugador de Prueba",
                    "valoracion": (
                        "Cuesta {candidate_market_value_eur} y ahorra {cost_savings_eur}."
                    ),
                }
            ],
        },
    }
    base.update(overrides)
    return base


def test_well_formed_draft_validates() -> None:
    draft = ScoutingReportDraft(**make_draft())

    assert draft.dictamen_financiero.headline == "Infravalorado frente al mercado"
    assert "{fair_value_eur}" in draft.dictamen_financiero.body
    assert draft.rendimiento.headline == "Titular indiscutible"
    assert draft.alternativas.candidatos[0].nombre == "Jugador de Prueba"
    assert "{cost_savings_eur}" in draft.alternativas.candidatos[0].valoracion


def test_body_with_raw_number_rejected() -> None:
    broken = make_draft(
        rendimiento={
            "headline": "Gran temporada",
            "body": "Metió 15 goles y su valor es €25.0M.",
        }
    )

    with pytest.raises(ValidationError, match="placeholder"):
        ScoutingReportDraft(**broken)


def test_headline_with_raw_number_rejected() -> None:
    broken = make_draft(
        dictamen_financiero={
            "headline": "Un 80% por debajo del mercado",
            "body": "El club paga {market_value_eur}.",
        }
    )

    with pytest.raises(ValidationError, match="placeholder"):
        ScoutingReportDraft(**broken)


def test_candidate_valoracion_with_raw_number_rejected() -> None:
    broken = make_draft(
        alternativas={
            "headline": "Reposición asequible",
            "body": "Solo {qualifying_count} candidatos.",
            "candidatos": [
                {"nombre": "Jugador de Prueba", "valoracion": "Cuesta €540K y ahorra €1.0M."}
            ],
        }
    )

    with pytest.raises(ValidationError, match="placeholder"):
        ScoutingReportDraft(**broken)


def test_placeholder_format_is_documented_on_fields() -> None:
    description = ReportSection.model_fields["body"].description

    assert description is not None
    assert "{fact_ref}" in description
    assert "{fair_value_eur}" in description


def test_ensure_no_raw_numbers_validation_helper() -> None:
    assert ensure_no_raw_numbers("Cuesta {fair_value_eur} en el mercado.") == (
        "Cuesta {fair_value_eur} en el mercado."
    )

    with pytest.raises(ValueError, match="placeholder"):
        ensure_no_raw_numbers("Cuesta 25 millones.")


def test_candidate_name_with_raw_number_rejected() -> None:
    """The name binds a candidate to the card, so it follows the same digit rule."""
    broken = make_draft(
        alternativas={
            "headline": "Reposición asequible",
            "body": "Solo {qualifying_count} candidatos.",
            "candidatos": [{"nombre": "Jugador 9", "valoracion": "Ahorra {cost_savings_eur}."}],
        }
    )

    with pytest.raises(ValidationError, match="placeholder"):
        ScoutingReportDraft(**broken)


def test_schema_repair_request_names_the_offending_field() -> None:
    broken = make_draft(
        dictamen_financiero={"headline": "Cuesta 99 millones.", "body": "Sin cifras."}
    )
    with pytest.raises(ValidationError) as failure:
        ScoutingReportDraft(**broken)
    original = [{"role": "system", "content": "instrucciones"}]

    repaired = build_schema_repair_messages(original, failure.value)

    assert repaired[:1] == original
    assert repaired[-1]["role"] == "user"
    assert "«dictamen_financiero.headline»" in repaired[-1]["content"]
