"""LLM draft rendering: the executive HTML wrapper around the substituted draft.

Input: a validated `ScoutingReportDraft` and the fact card from `report_facts`.
Output: the final report HTML — three `<p>` paragraphs shaped like
`report_render.render_deterministic_report`.
Responsibility: wrap the sections in the backend-owned labels, so the LLM path and
the deterministic renderer emit the same markup by construction (LLM_PLAN §7.1).

The `{fact_ref}` substitution lives in `draft_placeholders`, which this module
re-exports: the placeholder syntax, the scope it resolves against and the error an
unknown key raises are one concern, and the markup around the result is another.

Escaping: the prose and every substituted value are escaped for an HTML text
context, because the stored content is injected with innerHTML. Model prose and
database text are equally untrusted there; the labels this module emits are markup
and are not escaped.
"""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

from delphos_backend.services.draft_placeholders import (
    UnknownPlaceholderError,
    substitute_placeholders,
)
from delphos_backend.services.report_bindings import UnknownCandidateError, bind_candidate_scope
from delphos_backend.services.report_schema import (
    AlternativesSection,
    ReportSection,
    ScoutingReportDraft,
)

__all__ = [
    "UnknownCandidateError",
    "UnknownPlaceholderError",
    "render_draft",
    "substitute_placeholders",
]

_FINANCIAL_LABEL = "Dictamen Financiero"
_PERFORMANCE_LABEL = "Rendimiento Deportivo"
_ALTERNATIVES_LABEL = "Alternativas de Mercado"


def render_draft(draft: ScoutingReportDraft, card: dict[str, Any]) -> str:
    """Wrap the three draft sections in the deterministic renderer's markup."""
    league = card["facts"]["league_id"]["display"]
    return "".join(
        (
            _section(f"<strong>{_FINANCIAL_LABEL}:</strong>", draft.dictamen_financiero, card),
            _section(
                f"<strong>{_PERFORMANCE_LABEL} ({_esc(league)}):</strong>", draft.rendimiento, card
            ),
            _alternatives_section(draft.alternativas, card),
        )
    )


def _section(label: str, section: ReportSection, card: Mapping[str, Any]) -> str:
    headline = substitute_placeholders(section.headline, card)
    body = substitute_placeholders(section.body, card)
    return f"<p>{label} {_esc(headline)} {_esc(body)}</p>"


def _alternatives_section(section: AlternativesSection, card: Mapping[str, Any]) -> str:
    headline = _esc(substitute_placeholders(section.headline, card))
    body = _esc(substitute_placeholders(section.body, card))
    sentences = ", ".join(
        sentence
        for sentence in (_candidate_sentence(candidate, card) for candidate in section.candidatos)
        if sentence
    )
    if sentences and not sentences.endswith((".", "!", "?")):
        # Each assessment lost its own trailing full stop (see `_one_sentence`); the
        # section ends with one, unless the last assessment already ends the sentence.
        sentences = f"{sentences}."
    prose = f"{headline} {body}".strip()
    if sentences:
        prose = f"{prose} {sentences}"
    return f"<p><strong>{_ALTERNATIVES_LABEL}:</strong> {prose}</p>"


def _candidate_sentence(candidate: Any, card: Mapping[str, Any]) -> str:
    """`<strong>Name</strong>: assessment`, bound to the card's candidate of that name.

    A candidate whose assessment is blank is left out of the sentence join: an empty
    assessment would otherwise render as "Name: ." and say nothing.
    """
    scope = bind_candidate_scope(candidate, card)
    name = scope["candidate_name"]["display"]
    assessment = _one_sentence(substitute_placeholders(candidate.valoracion, card, scope))
    if not assessment:
        return ""
    return f"<strong>{_esc(name)}</strong>: {_esc(assessment)}"


def _one_sentence(text: str) -> str:
    """The text as one sentence: no trailing full stop, so the join reads well.

    The candidates are joined with ", ", and the model's assessment usually
    ends with a full stop of its own: "similitud del 63%." + ", " reads as
    "63%.,". Only the full stop is dropped: an assessment that ends with "!" or "?"
    keeps it, because flattening it into a full stop would change what the model
    wrote.
    """
    stripped = text.strip()
    if stripped.endswith("."):
        stripped = stripped[:-1].rstrip()
    return stripped


def _esc(value: Any) -> str:
    """Escape a value for an HTML text context, quotes included."""
    return escape(str(value), quote=True)
