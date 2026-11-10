"""LLM draft rendering: `{fact_ref}` substitution plus the executive HTML wrapper.

Input: a validated `ScoutingReportDraft` and the fact card from `report_facts`.
Output: the final report HTML — three `<p>` paragraphs shaped like
`report_render.render_deterministic_report`.
Responsibility: replace every `{fact_ref}` placeholder with the fact's formatted
display string and wrap the sections in the backend-owned labels, so the LLM path
and the deterministic renderer emit the same markup by construction (LLM_PLAN §7.1).
An unknown placeholder raises `UnknownPlaceholderError`: substituting an empty
string would silently publish a broken sentence, so the caller falls back to the
deterministic renderer instead (LLM_PLAN §8.2).

Scoping: a placeholder resolves against exactly one scope. The three top-level
sections resolve against the card's top-level facts, and a candidate's prose
resolves against that candidate's own cells only. The card's candidates share key
names with the target's facts, so a candidate scope that fell back to the top-level
facts would let a candidate's sentence quote the TARGET player's figures — a wrong
number about a real person, published as if the model had written it. An unknown key
is therefore an error, not a fallback. Which card candidate a drafted candidate
refers to is decided by `report_bindings`.

Escaping: the prose and every substituted value are escaped for an HTML text
context, because the stored content is injected with innerHTML. Model prose and
database text are equally untrusted there; the labels this module emits are markup
and are not escaped.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from html import escape
from typing import Any

from delphos_backend.services.report_bindings import (
    UnknownCandidateError,
    UnknownPlaceholderError,
    bind_candidate_scope,
)
from delphos_backend.services.report_prompt import PLACEHOLDER_RE
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


def substitute_placeholders(
    text: str,
    card: Mapping[str, Any],
    candidate: Mapping[str, dict[str, Any]] | None = None,
) -> str:
    """Replace each `{fact_ref}` with its display string; unknown keys raise.

    `candidate` scopes the lookup to that candidate's own cells; without it the
    lookup is the card's top-level facts. The two scopes never mix.
    """

    def replace(match: re.Match[str]) -> str:
        key = match.group(0)[1:-1]
        scope = candidate if candidate is not None else card["facts"]
        fact = scope.get(key)
        if fact is None:
            raise UnknownPlaceholderError(key)
        return str(fact["display"])

    return PLACEHOLDER_RE.sub(replace, text)


def _section(label: str, section: ReportSection, card: Mapping[str, Any]) -> str:
    headline = substitute_placeholders(section.headline, card)
    body = substitute_placeholders(section.body, card)
    return f"<p>{label} {_esc(headline)} {_esc(body)}</p>"


def _alternatives_section(section: AlternativesSection, card: Mapping[str, Any]) -> str:
    headline = _esc(substitute_placeholders(section.headline, card))
    body = _esc(substitute_placeholders(section.body, card))
    sentences = ", ".join(_candidate_sentence(candidate, card) for candidate in section.candidatos)
    prose = f"{headline} {body}".strip()
    if sentences:
        prose = f"{prose} {sentences}"
    return f"<p><strong>{_ALTERNATIVES_LABEL}:</strong> {prose}</p>"


def _candidate_sentence(candidate: Any, card: Mapping[str, Any]) -> str:
    """`<strong>Name</strong>: assessment`, bound to the card's candidate of that name."""
    scope = bind_candidate_scope(candidate, card)
    name = scope["candidate_name"]["display"]
    assessment = substitute_placeholders(candidate.valoracion, card, scope)
    return f"<strong>{_esc(name)}</strong>: {_esc(assessment)}"


def _esc(value: Any) -> str:
    """Escape a value for an HTML text context, quotes included."""
    return escape(str(value), quote=True)
