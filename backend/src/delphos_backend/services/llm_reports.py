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
logged separately: with no completed draft there is nothing to repair. `seed` is sent
when available (the offline experiments pass a fixed one, §17).

Two data failures take the same exit before the model is contacted: a candidate name
the request cannot represent (it would carry an instruction into the prompt) and a
card whose candidates do not share one key set. The first is answered with the
deterministic rendering of the same card, which escapes every value; the second means
the request cannot be built at all.

The prose of one report comes wholly from ONE endpoint: the endpoint is resolved
once, the draft and its repair go to it, and the stored `llm_model` is the id of
the model that wrote the whole text. The stored id is the model the backend ASKED
for — the primary's id, or the fallback's when the fallback served the call; the id
the server reports back is logged when the two differ. The cache accepts a report
written by either configured model, so the stored id is always one of the lookup's
candidates; the endpoint is not part of the key, and the provenance names the model,
not the machine that served it (ADR-033).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from pydantic import ValidationError

from delphos_backend.core.config import Settings, get_settings
from delphos_backend.services.llm_chain import EndpointChain
from delphos_backend.services.llm_client import (
    PRIMARY_ENDPOINT,
    CompletionResult,
    InferenceError,
    InferenceTimeout,
    chat_completion,
    resolve_target,
)
from delphos_backend.services.report_bindings import UnknownPlaceholderError
from delphos_backend.services.report_drafting import complete_draft, draft_report_text
from delphos_backend.services.report_facts import (
    allowed_number_tokens,
    build_deterministic_card,
    build_fact_card,
)
from delphos_backend.services.report_names import UnrepresentableCandidateNameError
from delphos_backend.services.report_prompt import SYSTEM_PROMPT, build_prompt_version
from delphos_backend.services.report_prompt_scope import build_user_message
from delphos_backend.services.report_render import render_deterministic_report
from delphos_backend.services.report_schema import ScoutingReportDraft
from delphos_backend.services.report_scope import InconsistentCandidateScope

logger = logging.getLogger(__name__)


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
    transport: httpx.AsyncBaseTransport | None = None,
) -> ReportResult:
    """Generate the scouting report; never raises for an LLM failure (falls back)."""
    cfg = settings or get_settings()
    try:
        card = build_fact_card(profile, valuation, replacements)
    except UnrepresentableCandidateNameError as exc:
        # A candidate name the request cannot represent never reaches the model: the
        # deterministic renderer reads the same card and escapes every value.
        logger.warning("Report generation used the deterministic renderer: %s", exc)
        return _deterministic(
            render_deterministic_report(build_deterministic_card(profile, valuation, replacements))
        )
    fallback_text = render_deterministic_report(card)
    allowed = allowed_number_tokens(card)
    try:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(card)},
        ]
    except InconsistentCandidateScope as exc:
        logger.warning("Report generation fell back to the deterministic renderer: %s", exc)
        return _deterministic(fallback_text)

    async def complete(
        request: Sequence[dict[str, Any]],
    ) -> tuple[ScoutingReportDraft, CompletionResult]:
        """One structured generation call, bound to this request's settings."""
        return await complete_draft(request, chain, cfg, seed)

    try:
        # One endpoint for the whole report: it is resolved here, before the
        # first answer exists, and the chain keeps the draft and its repair on it.
        chain = EndpointChain(await resolve_target(cfg, transport), cfg, transport, chat_completion)
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
    requested = completion.requested_model or cfg.llm_model_name
    if completion.model and completion.model != requested:
        # The server answered with a model nobody asked for: the prose cannot
        # be attributed to the club's model, so it is not stored.
        logger.warning(
            "The inference endpoint answered with model %s for the requested model %s; "
            "using the deterministic renderer",
            completion.model,
            requested,
        )
        return _deterministic(fallback_text)
    if completion.endpoint != PRIMARY_ENDPOINT:
        logger.warning(
            "The scouting report was served by the %s inference endpoint", completion.endpoint
        )
    return ReportResult(
        text=text,
        source="llm",
        llm_model=requested,
        prompt_version=build_prompt_version(cfg),
    )


def _deterministic(text: str) -> ReportResult:
    return ReportResult(text=text, source="deterministic", llm_model=None, prompt_version=None)
