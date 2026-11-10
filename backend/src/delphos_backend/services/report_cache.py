"""Report cache policy: which stored report may answer a generate request (LLM_PLAN §12).

Input: a database connection and the cache key of the request.
Output: the cached report row, or None when nothing matches.
Responsibility: decide which stored row may be served without calling the LLM. The
row the current model and prompt configuration produced is served as it is; the
deterministic row the last fallback wrote is served only while it is fresh, so a
recovered LLM replaces it instead of leaving the player on the fallback forever.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from psycopg import AsyncConnection

from delphos_backend.repositories.report_cache import get_cached_player_report

DETERMINISTIC_CACHE_TTL = timedelta(minutes=15)
"""How long the deterministic row written by a fallback may answer a request."""


async def find_cached_report(
    conn: AsyncConnection,
    *,
    player_id: int,
    model_run_id: str,
    report_type: str,
    llm_model: str,
    prompt_version: str,
) -> dict[str, Any] | None:
    """The stored report that answers the request, or None when there is none.

    The LLM row is the one the current model and prompt produced. The deterministic
    row is the fallback of the last failed generation; it is served while it is
    fresh, which keeps a request from waiting for a model that is down.
    """
    row = await get_cached_player_report(
        conn,
        player_id,
        model_run_id,
        report_type,
        llm_model=llm_model,
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
