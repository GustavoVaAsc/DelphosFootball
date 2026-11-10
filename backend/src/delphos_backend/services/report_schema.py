"""Structured output schema for the LLM's scouting-report draft.

Input: JSON produced by the model under llama.cpp schema constraint.
Output: ScoutingReportDraft and its section models.
Responsibility: Defines the placeholder-only shape of the model's editorial
contribution (LLM_PLAN §7.2). The three sections are fixed by the product and the
prose fields accept {fact_ref} placeholders but no raw digits, so numeric
hallucination is rejected at parse time. The section models are one schema
concept, so they share this module rather than each owning a file.

The module also owns the repair request for a draft the schema rejected: the
pipeline spends exactly one repair attempt on it, and the request names the
offending fields so the model rewrites what failed (LLM_PLAN §8.2).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, Field, ValidationError, field_validator

from delphos_backend.services.report_prompt import PLACEHOLDER_RE


def ensure_no_raw_numbers(value: str) -> str:
    """Return value unchanged when it holds no digits outside {fact_ref} placeholders.

    Placeholders are backend-controlled references, so their keys may contain
    digits; every other digit would be a numeric claim the backend must instead
    substitute from the verified fact card.
    """
    without_placeholders = PLACEHOLDER_RE.sub("", value)
    if any(character.isdigit() for character in without_placeholders):
        raise ValueError("numbers are only allowed as {fact_ref} placeholders, not as digits")
    return value


class ReportSection(BaseModel):
    """One executive section of the scouting report."""

    headline: str = Field(
        description="One-line verdict in Spanish prose. No digits; {fact_ref} placeholders only."
    )
    body: str = Field(
        description=(
            "Section body in Spanish prose. No digits; only {fact_ref} placeholders "
            "such as {fair_value_eur} for numbers, keyed from the fact-card list."
        )
    )

    @field_validator("headline", "body")
    @classmethod
    def _prose_has_no_raw_numbers(cls, value: str) -> str:
        return ensure_no_raw_numbers(value)


class ReplacementCandidate(BaseModel):
    """One replacement candidate listed by the alternatives section."""

    nombre: str = Field(
        description=(
            "Candidate name copied verbatim from the fact card. No digits: the name "
            "identifies the candidate the assessment belongs to."
        )
    )
    valoracion: str = Field(
        description="Assessment in Spanish prose. No digits; only {fact_ref} placeholders."
    )

    @field_validator("nombre", "valoracion")
    @classmethod
    def _prose_has_no_raw_numbers(cls, value: str) -> str:
        return ensure_no_raw_numbers(value)


class AlternativesSection(ReportSection):
    """The market-alternatives section: prose plus the computed candidates."""

    candidatos: list[ReplacementCandidate] = Field(
        description="Replacement candidates calculated by the backend, from the fact card."
    )


class ScoutingReportDraft(BaseModel):
    """The model's editorial contribution: three fixed sections, placeholders for every number."""

    dictamen_financiero: ReportSection = Field(description="Financial verdict section.")
    rendimiento: ReportSection = Field(description="Performance summary section.")
    alternativas: AlternativesSection = Field(description="Market alternatives section.")


def build_schema_repair_messages(
    messages: Sequence[Mapping[str, str]], error: ValidationError
) -> list[dict[str, str]]:
    """Append the one repair request for a draft the schema rejected.

    Every offending field is named, so the model rewrites exactly what failed
    instead of the whole report blindly. The caller re-issues the generation call
    once; a second rejection falls through to the deterministic renderer
    (LLM_PLAN §8.2).
    """
    fields = ", ".join(f"«{path}»" for path in _offending_fields(error))
    repair = (
        f"Tu borrador anterior no era válido: los campos {fields} no cumplen el formato. "
        "Reescribe el informe completo sin ninguna cifra escrita a mano: escribe cada "
        "número como un marcador {fact_ref} de la tarjeta de datos, y copia cada nombre "
        "de candidato tal cual aparece en la lista de candidatos."
    )
    return [dict(message) for message in messages] + [{"role": "user", "content": repair}]


def _offending_fields(error: ValidationError) -> list[str]:
    """The dotted paths of the fields the schema rejected."""
    paths = []
    for item in error.errors():
        path = ".".join(str(part) for part in item["loc"])
        if path:
            paths.append(path)
    return paths
