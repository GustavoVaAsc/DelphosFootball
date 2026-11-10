"""Numeric fidelity check (L2) over rendered scouting-report prose.

Input: rendered Spanish prose plus the allowed numbers from the fact card.
Output: NumericCheckResult naming every ungrounded numeric token, and the
one-shot repair request (LLM_PLAN §8.2).
Responsibility: flag the numbers the fact card does not ground and build the repair
messages. The allowed set itself is built by `report_facts.allowed_number_tokens` —
the single source of truth for the numbers a report may contain — and the tokeniser
lives in `report_numbers`, which this module re-exports so a caller that only needs
the verifier keeps one import.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from delphos_backend.services.report_numbers import (
    NumberToken,
    canonicalize_number,
    extract_number_tokens,
)

__all__ = [
    "NumberToken",
    "NumericCheckResult",
    "build_repair_messages",
    "canonicalize_number",
    "extract_number_tokens",
    "verify_prose_numbers",
]


@dataclass(frozen=True)
class NumericCheckResult:
    """Outcome of the check: each token the fact card does not ground."""

    violations: tuple[NumberToken, ...]

    @property
    def passed(self) -> bool:
        return not self.violations


def verify_prose_numbers(prose: str, allowed: Iterable[str]) -> NumericCheckResult:
    """Flag every number in prose that the allowed set does not ground (LLM_PLAN §8.2)."""
    allowed_canonical: set[str] = set()
    for entry in allowed:
        _collect_numbers(str(entry), allowed_canonical)
    violations = tuple(
        occurrence
        for occurrence in extract_number_tokens(prose)
        if canonicalize_number(occurrence.token) not in allowed_canonical
    )
    return NumericCheckResult(violations=violations)


def build_repair_messages(
    messages: Sequence[Mapping[str, str]],
    result: NumericCheckResult,
) -> list[dict[str, str]]:
    """Append the one repair request, naming each offending token explicitly.

    The caller re-issues the generation call once; a second violation falls through
    to the deterministic renderer (LLM_PLAN §8.2).
    """
    flagged = ", ".join(f"«{violation.token}»" for violation in result.violations)
    repair = (
        "Tu borrador anterior contenía números que no figuran en la tarjeta de datos: "
        f"{flagged}. Reescribe el informe completo sin ninguna cifra fuera de los "
        "marcadores {fact_ref}; cada número debe provenir de la lista de tarjetas."
    )
    return [dict(message) for message in messages] + [{"role": "user", "content": repair}]


def _collect_numbers(text: str, target: set[str]) -> None:
    """Add every canonical number reachable from a raw value or display string."""
    direct = canonicalize_number(text)
    if direct is not None:
        target.add(direct)
    for occurrence in extract_number_tokens(text):
        canonical = canonicalize_number(occurrence.token)
        if canonical is not None:
            target.add(canonical)
