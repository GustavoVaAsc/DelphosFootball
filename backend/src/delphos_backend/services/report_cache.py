"""Report cache policy: which stored report may answer a generate request (LLM_PLAN §12).

Input: a database connection and the cache key of the request.
Output: the cached report row, or None when nothing matches.
Responsibility: decide which stored row may be served without calling the LLM. The
row a configured model and the current prompt produced is served as it is; the
deterministic row the last fallback wrote is served only while it is fresh, so a
recovered LLM replaces it instead of leaving the player on the fallback forever.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from psycopg import AsyncConnection

from delphos_backend.core.config import Settings
from delphos_backend.repositories.report_cache import get_cached_player_report

DETERMINISTIC_CACHE_TTL = timedelta(minutes=15)
"""How long the deterministic row written by a fallback may answer a request."""


def report_cache_model_candidates(cfg: Settings) -> list[str]:
    """The model ids a stored report may carry: the primary's and the fallback's.

    Either configured endpoint may have written the report, so both ids are
    accepted by the lookup. The endpoint is not part of the key: the column
    names the model that wrote the text, and the two endpoints are
    interchangeable producers of the model they share (ADR-033).
    """
    candidates = [cfg.llm_model_name]
    fallback = cfg.llm_fallback_model_name.strip()
    if fallback and fallback not in candidates:
        candidates.append(fallback)
    return candidates


async def find_cached_report(
    conn: AsyncConnection,
    *,
    player_id: int,
    model_run_id: str,
    report_type: str,
    llm_models: Sequence[str],
    prompt_version: str,
) -> dict[str, Any] | None:
    """The stored report that answers the request, or None when there is none.

    The LLM row is the one a configured model and the current prompt produced.
    The deterministic row is the fallback of the last failed generation; it is
    served while it is fresh, which keeps a request from waiting for a model
    that is down.
    """
    row = await get_cached_player_report(
        conn,
        player_id,
        model_run_id,
        report_type,
        llm_models=llm_models,
        prompt_version=prompt_version,
    )
    if row is None:
        return None
    if row.get("source") == "deterministic" and not _is_fresh(row.get("created_at")):
        return None
    return row


def _is_fresh(created_at: datetime | None) -> bool:
    """Whether a stored row was written within the deterministic cache window."""
    if created_at is None:
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return datetime.now(UTC) - created_at <= DETERMINISTIC_CACHE_TTL
