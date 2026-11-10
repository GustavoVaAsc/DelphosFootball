"""LLM draft acquisition and the single repair attempt (LLM_PLAN §8.2).

Input: the prompt messages, the function that asks the LLM for a draft, the fact
card and its allowed numbers. Output: the report text the draft renders to, or None
when no grounded draft was obtained. Responsibility: validate the answer against the
draft schema and spend at most one repair attempt on whichever failure comes first —
a schema rejection (a hand-written number, a candidate name that is not the card's) or
a number in the rendered prose the card does not ground.

The LLM call itself belongs to the caller: the pipeline owns the transport, the
settings and the seed, and hands the draft request in as a function.

The draft schema and the numeric verifier own one failure each, so the repair
request is built by the module that knows the failure: `report_schema` for a
rejected draft, `report_verify` for an ungrounded number.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from pydantic import ValidationError

from delphos_backend.services.draft_render import render_draft
from delphos_backend.services.llm_client import CompletionResult
from delphos_backend.services.report_schema import (
    ScoutingReportDraft,
    build_schema_repair_messages,
)
from delphos_backend.services.report_verify import build_repair_messages, verify_prose_numbers

logger = logging.getLogger(__name__)

DraftCompleter = Callable[
    [Sequence[dict[str, Any]]], Awaitable[tuple[ScoutingReportDraft, CompletionResult]]
]
"""Asks the LLM for a draft of the given messages and validates the answer."""


async def draft_report_text(
    messages: Sequence[dict[str, Any]],
    complete: DraftCompleter,
    card: dict[str, Any],
    allowed: set[str],
) -> tuple[str, CompletionResult] | None:
    """The rendered, grounded report text, or None when no draft could be grounded.

    A `ValidationError` from the draft schema and an ungrounded number are both
    repaired once. The repair attempt is spent on whichever failure comes first,
    so the pipeline never issues more than two generation calls.
    """
    repair_used = False
    try:
        draft, completion = await complete(messages)
    except ValidationError as exc:
        if not _has_offending_fields(exc):
            raise  # a malformed answer, not a draft that can be repaired
        repair_used = True
        logger.info("Draft rejected by the schema; one repair attempt: %s", exc)
        draft, completion = await complete(build_schema_repair_messages(messages, exc))
    text = render_draft(draft, card)
    check = verify_prose_numbers(text, allowed)
    if check.passed:
        return text, completion
    if repair_used:
        logger.warning(
            "Draft ungrounded after its repair attempt; using the deterministic renderer"
        )
        return None
    draft, completion = await complete(build_repair_messages(messages, check))
    text = render_draft(draft, card)
    if not verify_prose_numbers(text, allowed).passed:
        logger.warning("Draft ungrounded after one repair; using the deterministic renderer")
        return None
    return text, completion


def _has_offending_fields(error: ValidationError) -> bool:
    """Whether the rejection names a field, as opposed to a malformed answer."""
    return any(item["loc"] for item in error.errors())
