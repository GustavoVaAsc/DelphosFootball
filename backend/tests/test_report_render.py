"""Golden tests for the deterministic report renderer (LLM_PLAN §7.5).

The positive and negative expected strings were captured from `node` running the
verbatim `buildExecutiveNarrativeHtml` reference for the same fixture player, so
each assertion pins the design preview's output byte for byte. The zero-replacement
sentence has no JS reference (the JS emits a dangling colon there) and is asserted
against the wording this renderer deliberately introduces instead.
"""

from __future__ import annotations

import re

import pytest
from scouting_fixtures import profile, replacements, valuation

from delphos_backend.services.report_facts import allowed_number_tokens, build_fact_card
from delphos_backend.services.report_render import render_deterministic_report
from delphos_backend.services.report_verify import verify_prose_numbers

POSITIVE_P1 = (
    "<p><strong>Dictamen Financiero:</strong> Lionel Messi cotiza actualmente en "
    "<strong>€25.0M</strong> frente a un Valor Justo estimado de <strong>€45.0M</strong>, "
    "generando un margen favorable de <strong>+€20.0M (+80%)</strong> por su impacto "
    "real en cancha.</p>"
)
POSITIVE_P2 = (
    "<p><strong>Rendimiento Deportivo (LaLiga):</strong> Como extremo derecho en "
    "Inter Miami, registra <strong>1800 minutos</strong> en <strong>20 partidos "
    "(20 como titular)</strong>, aportando <strong>15 goles</strong>, "
    "<strong>12 asistencias</strong> y un <strong>75% de victorias</strong>.</p>"
)
POSITIVE_P3 = (
    "<p><strong>Alternativas de Mercado:</strong> Dentro del perfil "
    "<em>Creador Ofensivo</em>, destacan como opciones de reemplazo rentable: "
    "<strong>Jonathan David</strong> (LOSC Lille, ahorra €4.0M / -16%), "
    "<strong>Serhou Guirassy</strong> (Borussia Dortmund, ahorra €3.5M / -22%).</p>"
)
NEGATIVE_P1 = (
    "<p><strong>Dictamen Financiero:</strong> La cotización de mercado actual de "
    "<strong>€25.0M</strong> supera el Valor Justo estimado (<strong>€20.0M</strong>), "
    "por lo que se recomienda priorizar las alternativas de ahorro táctico.</p>"
)
_TAG_RE = re.compile(r"</?(?:p|strong|em)[^>]*>")


def _positive_card():
    return build_fact_card(profile(), valuation(), replacements())


def _negative_card():
    return build_fact_card(profile(), valuation(fair_value_eur=20_000_000.0), replacements())


def _empty_card():
    return build_fact_card(
        profile(),
        valuation(),
        replacements(
            replacements=[], qualifying_count=0, shortfall_reason="no_peer_below_cost_ceiling"
        ),
    )


def test_positive_financial_branch_matches_reference_golden() -> None:
    html = render_deterministic_report(_positive_card())

    assert html == POSITIVE_P1 + POSITIVE_P2 + POSITIVE_P3


def test_negative_financial_branch_matches_reference_golden() -> None:
    html = render_deterministic_report(_negative_card())

    # Same performance and alternatives paragraphs; only paragraph 1 changes.
    assert html == NEGATIVE_P1 + POSITIVE_P2 + POSITIVE_P3
    assert "cotiza actualmente" not in html
    assert verify_prose_numbers(html, allowed_number_tokens(_negative_card())).passed


def test_zero_qualifying_replacements_renders_sensible_sentence() -> None:
    html = render_deterministic_report(_empty_card())
    expected_p3 = (
        "<p><strong>Alternativas de Mercado:</strong> Dentro del perfil "
        "<em>Creador Ofensivo</em>, no se identificaron alternativas de reemplazo "
        "rentable: no hay pares por debajo del techo de precio (0 pares cualificados).</p>"
    )

    assert html == POSITIVE_P1 + POSITIVE_P2 + expected_p3
    assert ": ." not in html
    assert "destacan como opciones de reemplazo rentable: ." not in html


def test_multiple_replacements_join_with_comma_and_discount() -> None:
    html = render_deterministic_report(_positive_card())

    assert "ahorra €4.0M / -16%" in html
    assert "ahorra €3.5M / -22%" in html
    # The list is joined with ", " exactly as Array.prototype.join(", ") does.
    assert "-16%), <strong>Serhou Guirassy</strong>" in html


def test_section_labels_are_exactly_the_three_spanish_labels() -> None:
    html = render_deterministic_report(_positive_card())

    assert html.count("<p>") == 3
    assert html.count("</p>") == 3
    assert html.count(":</strong>") == 3
    assert "<strong>Dictamen Financiero:</strong>" in html
    assert "<strong>Rendimiento Deportivo (LaLiga):</strong>" in html
    assert "<strong>Alternativas de Mercado:</strong>" in html


def test_golden_output_passes_numeric_verifier_and_tampering_fails() -> None:
    card = _positive_card()
    allowed = allowed_number_tokens(card)
    html = render_deterministic_report(card)

    clean = verify_prose_numbers(html, allowed)
    assert clean.passed, [violation.token for violation in clean.violations]

    tampered = verify_prose_numbers(html.replace("€25.0M", "€99.9M", 1), allowed)
    assert [violation.token for violation in tampered.violations] == ["€99.9M"]


def test_missing_fact_raises_key_error_naming_the_key() -> None:
    with pytest.raises(KeyError, match="market_value_eur"):
        render_deterministic_report({"facts": {}, "replacements": []})


def test_database_text_is_escaped_in_the_rendered_html() -> None:
    """The stored content is injected with innerHTML, so database text is escaped."""
    card = build_fact_card(
        profile(name="<b>x</b>", club_name="<script>alert(1)</script>"),
        valuation(),
        replacements(),
    )

    html = render_deterministic_report(card)

    assert "<b>x</b>" not in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_no_unescaped_angle_bracket_survives_outside_the_rendered_markup() -> None:
    card = build_fact_card(
        profile(name="<b>x</b>", club_name="<i>y</i>"),
        valuation(),
        replacements(),
    )

    html = render_deterministic_report(card)

    assert "<" not in _TAG_RE.sub("", html)


def test_an_apostrophe_in_a_name_is_not_a_numeric_violation() -> None:
    """The escaped apostrophe must not read as the number 27."""
    card = build_fact_card(profile(name="Kouadio N'Golo"), valuation(), replacements())

    html = render_deterministic_report(card)

    assert "Kouadio N&#x27;Golo" in html
    check = verify_prose_numbers(html, allowed_number_tokens(card))
    assert check.passed, [violation.token for violation in check.violations]


def test_a_null_position_still_renders_the_sub_position_role() -> None:
    """The role comes from the card, so a NULL position does not print 'n/d'."""
    card = build_fact_card(
        profile(position=None, sub_position="Right Winger"),
        valuation(),
        replacements(),
    )

    html = render_deterministic_report(card)

    assert "Como extremo derecho en" in html
    assert "n/d" not in html


def test_unknown_position_renders_the_guarded_spanish_role() -> None:
    """The role comes from the card, so an unknown position stays Spanish."""
    card = build_fact_card(
        profile(position="Goalkeeper", sub_position=None),
        valuation(),
        replacements(),
    )

    html = render_deterministic_report(card)

    assert "Como posición desconocida en" in html
    assert "goalkeeper" not in html
