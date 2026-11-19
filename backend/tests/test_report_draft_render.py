"""Unit tests for the LLM draft renderer: scoping, candidate binding and escaping.

The draft renderer substitutes the model's `{fact_ref}` placeholders and binds the
model's candidates to the card's candidates. Both steps decide which number ends up
next to which person's name, so they are pinned here: a placeholder that resolves
outside its scope, or a candidate bound by list position, publishes a wrong number
about a real person.
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError
from scouting_fixtures import profile, replacements, valuation

from delphos_backend.services.draft_render import (
    UnknownCandidateError,
    UnknownPlaceholderError,
    render_draft,
    substitute_placeholders,
)
from delphos_backend.services.report_facts import build_fact_card
from delphos_backend.services.report_schema import ScoutingReportDraft
from delphos_backend.services.report_scope import MODEL_INTERNAL_KEYS

_TAG_RE = re.compile(r"</?(?:p|strong|em)[^>]*>")


def _card(**profile_overrides: object):
    return build_fact_card(profile(**profile_overrides), valuation(), replacements())


def _draft(**overrides: object) -> ScoutingReportDraft:
    """A well-formed draft whose numbers are all {fact_ref} placeholders."""
    base: dict[str, object] = {
        "dictamen_financiero": {
            "headline": "Margen favorable.",
            "body": "Cotiza {market_value_eur} frente a {fair_value_eur}.",
        },
        "rendimiento": {
            "headline": "Temporada de alta producción.",
            "body": "Autor de {goals} goles en {minutes} minutos.",
        },
        "alternativas": {
            "headline": "Dos alternativas cualificadas.",
            "body": "Perfil {cluster_id} con {qualifying_count} pares.",
            "candidatos": [
                {"nombre": "Jonathan David", "valoracion": "Ahorra {cost_savings_eur}"},
                {"nombre": "Serhou Guirassy", "valoracion": "Ahorra {cost_savings_eur}"},
            ],
        },
    }
    base.update(overrides)
    return ScoutingReportDraft.model_validate(base)


def _alternatives(*candidates: dict[str, str]) -> dict[str, object]:
    return {
        "headline": "Dos alternativas cualificadas.",
        "body": "Perfil {cluster_id} con {qualifying_count} pares.",
        "candidatos": list(candidates),
    }


def test_candidate_scope_never_resolves_the_target_players_facts() -> None:
    """A candidate citing the target's own key is an error, not the target's figure."""
    draft = _draft(
        alternativas=_alternatives(
            {"nombre": "Jonathan David", "valoracion": "El objetivo cotiza {market_value_eur}."}
        )
    )

    with pytest.raises(UnknownPlaceholderError):
        render_draft(draft, _card())


def test_top_level_scope_never_resolves_a_candidate_key() -> None:
    draft = _draft(
        dictamen_financiero={
            "headline": "Margen favorable.",
            "body": "Ahorra {cost_savings_eur}.",
        }
    )

    with pytest.raises(UnknownPlaceholderError):
        render_draft(draft, _card())


def test_candidates_are_bound_by_name_not_by_list_position() -> None:
    """The model's reversed list keeps each candidate's own savings."""
    draft = _draft(
        alternativas=_alternatives(
            {"nombre": "Serhou Guirassy", "valoracion": "Ahorra {cost_savings_eur}."},
            {"nombre": "Jonathan David", "valoracion": "Ahorra {cost_savings_eur}."},
        )
    )

    html = render_draft(draft, _card())

    assert "<strong>Serhou Guirassy</strong>: Ahorra €3.5M" in html
    assert "<strong>Jonathan David</strong>: Ahorra €4.0M" in html


def test_candidate_name_the_card_does_not_contain_is_rejected() -> None:
    draft = _draft(
        alternativas=_alternatives(
            {"nombre": "Jugador Inventado", "valoracion": "Ahorra {cost_savings_eur}."}
        )
    )

    with pytest.raises(UnknownCandidateError):
        render_draft(draft, _card())


def test_model_prose_is_escaped() -> None:
    draft = _draft(
        dictamen_financiero={
            "headline": "<script>alert('xss')</script>",
            "body": "Cotiza {market_value_eur}.",
        }
    )

    html = render_draft(draft, _card())

    assert "<script>" not in html
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html


def test_substituted_database_text_is_escaped() -> None:
    card = _card(club_name="<img src=x onerror=alert('xss')>")
    draft = _draft(
        rendimiento={
            "headline": "Temporada de alta producción.",
            "body": "Juega en {club_name}.",
        }
    )

    html = render_draft(draft, card)

    assert "<img" not in html
    assert "&lt;img src=x onerror=alert(&#x27;xss&#x27;)&gt;" in html


def test_no_unescaped_angle_bracket_survives_outside_the_rendered_markup() -> None:
    card = _card(name="<b>x</b>", club_name="<i>y</i>")
    draft = _draft(
        dictamen_financiero={
            "headline": "<b>headline</b>",
            "body": "Cotiza {market_value_eur}.",
        }
    )

    html = render_draft(draft, card)

    assert "<" not in _TAG_RE.sub("", html)


def test_candidates_are_joined_with_a_comma_like_the_deterministic_renderer() -> None:
    draft = _draft()

    html = render_draft(draft, _card())

    assert "Ahorra €4.0M, <strong>Serhou Guirassy</strong>" in html


def test_a_candidate_assessment_that_ends_with_a_full_stop_reads_as_one_sentence() -> None:
    """The model's own full stop must not collide with the separator."""
    draft = _draft(
        alternativas=_alternatives(
            {"nombre": "Jonathan David", "valoracion": "Ahorra {cost_savings_eur}."}
        )
    )

    html = render_draft(draft, _card())

    assert "%.," not in html
    assert "<strong>Jonathan David</strong>: Ahorra €4.0M." in html


def test_the_models_own_exclamation_mark_is_kept() -> None:
    """An assessment that ends with '!' keeps it: flattening it into a full stop
    would change what the model wrote."""
    draft = _draft(
        alternativas=_alternatives(
            {"nombre": "Jonathan David", "valoracion": "¡Ahorra {cost_savings_eur}!"}
        )
    )

    html = render_draft(draft, _card())

    assert "<strong>Jonathan David</strong>: ¡Ahorra €4.0M!" in html
    assert "€4.0M!." not in html  # no full stop is appended after the exclamation


def test_the_models_own_question_mark_is_kept() -> None:
    draft = _draft(
        alternativas=_alternatives(
            {"nombre": "Jonathan David", "valoracion": "¿Ahorra {cost_savings_eur}?"}
        )
    )

    html = render_draft(draft, _card())

    assert "<strong>Jonathan David</strong>: ¿Ahorra €4.0M?" in html
    assert "€4.0M?." not in html  # no full stop is appended after the question


def test_a_blank_assessment_is_rejected_by_the_schema() -> None:
    """A blank assessment must not render as 'Nombre: .' — and must not render at all.

    The renderer skips a candidate with no assessment, so publishing one would
    lose a market option silently. The schema refuses it instead: the draft
    spends the one repair attempt and the report falls back if the repair still
    leaves it blank.
    """
    with pytest.raises(ValidationError):
        _draft(
            alternativas=_alternatives(
                {"nombre": "Jonathan David", "valoracion": "   "},
                {"nombre": "Serhou Guirassy", "valoracion": "Ahorra {cost_savings_eur}."},
            )
        )


def test_a_model_diagnostic_cannot_be_cited_in_the_verdict() -> None:
    """The model's own diagnostics are not scouting facts: they are not citable."""
    card = _card()

    for key in MODEL_INTERNAL_KEYS:
        assert key in card["facts"]  # the card still carries them for the renderer
        with pytest.raises(UnknownPlaceholderError):
            substitute_placeholders("{" + key + "}", card)


def test_a_model_diagnostic_in_a_draft_falls_back_instead_of_being_published() -> None:
    """A draft that quotes a diagnostic is refused, not rendered."""
    draft = _draft(
        dictamen_financiero={
            "headline": "Margen favorable.",
            "body": "Probabilidad de infravaloración {rf_undervalued_prob}.",
        }
    )

    with pytest.raises(UnknownPlaceholderError):
        render_draft(draft, _card())
