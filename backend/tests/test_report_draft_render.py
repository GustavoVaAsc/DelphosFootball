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
from scouting_fixtures import profile, replacements, valuation

from delphos_backend.services.draft_render import (
    UnknownCandidateError,
    UnknownPlaceholderError,
    render_draft,
)
from delphos_backend.services.report_facts import build_fact_card
from delphos_backend.services.report_schema import ScoutingReportDraft

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
