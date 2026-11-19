"""The one structured generation call the report path makes (LLM_PLAN §7.2).

Input: the prompt messages, the endpoint chain, the settings and the seed. Output: the
draft the model answered with — validated against the draft schema — and the
completion result.
Responsibility: ask one endpoint for a JSON-schema-constrained draft and validate the
answer. The caller owns the transport, the settings, the seed and the repair policy.

The call goes to the chain's endpoint, so the draft and its repair are served by the
same one (ADR-033).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from delphos_backend.core.config import Settings
from delphos_backend.services.llm_chain import EndpointChain
from delphos_backend.services.llm_client import CompletionResult
from delphos_backend.services.report_schema import ScoutingReportDraft

__all__ = ["DRAFT_FORMAT", "complete_draft"]

DRAFT_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "scouting_report_draft",
        "schema": ScoutingReportDraft.model_json_schema(),
    },
}
"""The JSON schema the draft is asked for, so the answer needs no parsing."""


async def complete_draft(
    messages: Sequence[dict[str, Any]],
    chain: EndpointChain,
    cfg: Settings,
    seed: int | None,
) -> tuple[ScoutingReportDraft, CompletionResult]:
    """One structured generation call: request the draft, parse and validate it.

    The call goes to the chain's endpoint, so the draft and its repair are
    served by the same one.
    """
    completion = await chain.complete(
        list(messages),
        max_tokens=cfg.llm_report_max_tokens,
        enable_thinking=cfg.llm_enable_thinking,
        seed=seed,
        response_format=DRAFT_FORMAT,
    )
    draft = ScoutingReportDraft.model_validate_json(completion.content)
    return draft, completion
