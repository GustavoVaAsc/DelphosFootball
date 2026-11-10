"""Deterministic scouting-report renderer — the correctness floor (LLM_PLAN §7.5).

Input: the fact card from `report_facts.build_fact_card`.
Output: an HTML string of three `<p>` paragraphs with `<strong>`/`<em>` marks,
byte-compatible with `buildExecutiveNarrativeHtml`
(frontend/design-preview/index.html:1622-1650).
Responsibility: produce the full report with no LLM involved — the fallback for
every generation failure and the baseline the LLM output is measured against.

Output form: HTML, deliberately. The reference function returns `<p>`/`<strong>`/
`<em>`, the product's `.scouting-report-box` CSS styles exactly those tags
(index.html:1066-1074), and both report paths wrap their prose in backend-owned
templates, so the LLM path and this renderer emit the same markup by construction.
`app.reports.content` is a TEXT column and HTML is a string: it is stored verbatim
and injected with innerHTML, as the design preview does. Plain text was rejected
because it would drop the bold labels the product styles and force a second, weaker
markup convention onto the LLM path.

Every interpolated value is escaped for an HTML text context: the names, club and
league strings come from the database and are as untrusted as model prose once the
content is injected with innerHTML. The reference JS does not escape (the preview
renders its own hard-coded data), but the stored report is rendered from the
database, so escaping is the backend's job; the markup this module emits itself is
not escaped and stays byte-identical to the reference.

Every number comes from the card's pre-formatted display strings; the renderer
never recomputes a figure. The role is the card's resolved `role` display string,
lower-cased, mirroring the reference's `subPosEs.toLowerCase()`: reading it from
the card instead of the raw English keys is what keeps the renderer and the card
from disagreeing about a position the vocabulary does not manage.
"""

from __future__ import annotations

from html import escape
from typing import Any


def render_deterministic_report(fact_card: dict[str, Any]) -> str:
    """Render the three executive sections as the design preview's HTML string."""
    facts = fact_card["facts"]
    market = _display(facts, "market_value_eur")
    fair = _display(facts, "fair_value_eur")
    name = _display(facts, "player_name")

    gap = facts["value_gap_eur"]["value"]
    if gap is not None and gap > 0:
        p1 = (
            f"<p><strong>Dictamen Financiero:</strong> {_esc(name)} cotiza actualmente en "
            f"<strong>{_esc(market)}</strong> frente a un Valor Justo estimado de "
            f"<strong>{_esc(fair)}</strong>, generando un margen favorable de "
            f"<strong>+{_esc(_display(facts, 'value_gap_eur'))} "
            f"(+{_esc(_display(facts, 'value_gap_pct'))})</strong> por su impacto real en "
            "cancha.</p>"
        )
    else:
        p1 = (
            "<p><strong>Dictamen Financiero:</strong> La cotización de mercado actual de "
            f"<strong>{_esc(market)}</strong> supera el Valor Justo estimado "
            f"(<strong>{_esc(fair)}</strong>), por lo que se recomienda priorizar las "
            "alternativas de ahorro táctico.</p>"
        )

    role = _display(facts, "role").lower()
    p2 = (
        f"<p><strong>Rendimiento Deportivo ({_esc(_display(facts, 'league_id'))}):</strong> "
        f"Como {_esc(role)} en {_esc(_display(facts, 'club_name'))}, registra "
        f"<strong>{_esc(_display(facts, 'minutes'))} minutos</strong> en "
        f"<strong>{_esc(_display(facts, 'apps'))} partidos "
        f"({_esc(_display(facts, 'starts'))} como titular)</strong>, aportando "
        f"<strong>{_esc(_display(facts, 'goals'))} goles</strong>, "
        f"<strong>{_esc(_display(facts, 'assists'))} asistencias</strong> y un "
        f"<strong>{_esc(_display(facts, 'win_rate'))} de victorias</strong>.</p>"
    )

    cluster = _display(facts, "cluster_id")
    candidates = fact_card.get("replacements") or []
    if candidates:
        joined = ", ".join(_candidate_phrase(candidate) for candidate in candidates)
        p3 = (
            f"<p><strong>Alternativas de Mercado:</strong> Dentro del perfil "
            f"<em>{_esc(cluster)}</em>, destacan como opciones de reemplazo rentable: "
            f"{joined}.</p>"
        )
    else:
        # The JS reference renders a dangling colon here; the product's data names
        # why nothing qualified instead (LLM_PLAN §7.5, task AC5).
        count = _display(facts, "qualifying_count")
        tail = f" ({_esc(count)} pares cualificados)" if count != "N/D" else ""
        p3 = (
            f"<p><strong>Alternativas de Mercado:</strong> Dentro del perfil "
            f"<em>{_esc(cluster)}</em>, no se identificaron alternativas de reemplazo "
            f"rentable: {_esc(_display(facts, 'shortfall_reason'))}{tail}.</p>"
        )

    return p1 + p2 + p3


def _candidate_phrase(candidate: dict[str, dict[str, Any]]) -> str:
    """`<strong>Name</strong> (Club, ahorra €4.0M / -16%)`, one replacement item."""
    club = candidate["candidate_club_name"]["display"]
    savings = candidate["cost_savings_eur"]["display"]
    discount = candidate["cost_discount_pct"]["display"]
    return (
        f"<strong>{_esc(candidate['candidate_name']['display'])}</strong> "
        f"({_esc(club)}, ahorra {_esc(savings)} / -{_esc(discount)})"
    )


def _display(facts: dict[str, dict[str, Any]], key: str) -> str:
    """The pre-formatted display string of `key`, with context if the card lacks it."""
    try:
        return facts[key]["display"]
    except KeyError as exc:
        raise KeyError(f"fact card is missing required fact {key!r}") from exc


def _esc(value: Any) -> str:
    """Escape a value for an HTML text context, quotes included."""
    return escape(str(value), quote=True)
