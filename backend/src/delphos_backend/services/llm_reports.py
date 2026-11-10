"""Scouting-report pipeline: schema-constrained LLM draft with deterministic fallback.

Input: the raw profile, valuation, and replacement payloads for the active run
(the dicts `report_facts.build_fact_card` reads). Output: a `ReportResult` with
the report text and its provenance (`source`, `llm_model`, `prompt_version`).
Responsibility: orchestrate LLM_PLAN §7.1 — fact card, schema-constrained Spanish
draft, `{fact_ref}` substitution, numeric verification with exactly one repair
attempt, and `report_render.render_deterministic_report` for every failure.

Every LLM failure — timeout, transport or protocol error, malformed or empty
completion, schema validation failure, unknown placeholder, a failed repair, or a
second numeric violation — returns the deterministic text instead of raising, so the
endpoint answers 200 with a report in every case (LLM_PLAN §7.1, C5). A timeout is
logged separately: with no completed draft there is nothing to repair. `seed` is
sent when available (the offline experiments pass a fixed one, §17). The stored
`llm_model` is the model the backend ASKED for (`cfg.llm_model_name`), because that
is the id the cache key is built from; the id the server reports back is logged
when the two differ.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from delphos_backend.core.config import Settings, get_settings
from delphos_backend.services.llm_client import (
    CompletionResult,
    InferenceError,
    InferenceTimeout,
    chat_completion,
)
from delphos_backend.services.report_bindings import UnknownPlaceholderError
from delphos_backend.services.report_drafting import draft_report_text
from delphos_backend.services.report_facts import allowed_number_tokens, build_fact_card
from delphos_backend.services.report_prompt import SYSTEM_PROMPT, build_prompt_version
from delphos_backend.services.report_render import render_deterministic_report
from delphos_backend.services.report_schema import ScoutingReportDraft

logger = logging.getLogger(__name__)

_DRAFT_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "scouting_report_draft",
        "schema": ScoutingReportDraft.model_json_schema(),
    },
}


@dataclass(frozen=True)
class ReportResult:
    """One generated report: its text plus the provenance stored with it."""

    text: str
    source: Literal["llm", "deterministic"]
    llm_model: str | None
    prompt_version: str | None


async def generate_report(
    profile: dict[str, Any],
    valuation: dict[str, Any],
    replacements: dict[str, Any] | None,
    *,
    settings: Settings | None = None,
    seed: int | None = None,
) -> ReportResult:
    """Generate the scouting report; never raises for an LLM failure (falls back)."""
    cfg = settings or get_settings()
    card = build_fact_card(profile, valuation, replacements)
    fallback_text = render_deterministic_report(card)
    allowed = allowed_number_tokens(card)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(card, ensure_ascii=False)},
    ]

    async def complete(
        request: Sequence[dict[str, Any]],
    ) -> tuple[ScoutingReportDraft, CompletionResult]:
        """One structured generation call, bound to this request's settings."""
        return await _complete_draft(request, cfg, seed)

    try:
        drafted = await draft_report_text(messages, complete, card, allowed)
    except InferenceTimeout as exc:
        logger.warning("Report generation timed out; using the deterministic renderer: %s", exc)
        return _deterministic(fallback_text)
    except (InferenceError, ValidationError, UnknownPlaceholderError) as exc:
        logger.warning("Report generation fell back to the deterministic renderer: %s", exc)
        return _deterministic(fallback_text)
    if drafted is None:
        return _deterministic(fallback_text)
    text, completion = drafted
    if completion.model != cfg.llm_model_name:
        logger.info(
            "Server reported model %s for the requested model %s",
            completion.model,
            cfg.llm_model_name,
        )
    return ReportResult(
        text=text,
        source="llm",
        llm_model=cfg.llm_model_name,
        prompt_version=build_prompt_version(cfg),
    )


async def _complete_draft(
    messages: Sequence[dict[str, Any]],
    cfg: Settings,
    seed: int | None,
) -> tuple[ScoutingReportDraft, CompletionResult]:
    """One structured generation call: request the draft, parse and validate it."""
    completion = await chat_completion(
        list(messages),
        settings=cfg,
        max_tokens=cfg.llm_report_max_tokens,
        enable_thinking=cfg.llm_enable_thinking,
        seed=seed,
        response_format=_DRAFT_FORMAT,
    )
    draft = ScoutingReportDraft.model_validate_json(completion.content)
    return draft, completion


def _deterministic(text: str) -> ReportResult:
    return ReportResult(text=text, source="deterministic", llm_model=None, prompt_version=None)
