"""The cache lookup for scouting reports in app.reports.

Input: the cache key of a generate request and the model ids a report may
carry. Output: the stored report row that answers it, if any. Responsibility:
read the report the cache keys on, and reach both provenance keys in one query:
the row a configured model and the current prompt produced, and the
deterministic row the last failed generation wrote.

Provenance is part of the cache key (LLM_PLAN §12): a row written by another
model or prompt/sampling configuration is not a hit. The model id is matched
against the whole candidate set, because either configured endpoint may have
written the report: the primary's id and, when it is set, the fallback's. The
invariant is therefore that the stored model id is one of the lookup
candidates, not that the lookup and the provenance read the same setting. The
endpoint is not part of the key: the column names the model that wrote the
text, not the machine that served it (ADR-033).

`IS NOT DISTINCT FROM` matches NULLs only to NULLs, so a pre-0004 LLM row (NULL
provenance) never satisfies the deterministic key, and vice versa. How long the
deterministic row may answer a request is the cache policy's decision, applied
by `services.report_cache`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg import AsyncConnection


async def get_cached_player_report(
    conn: AsyncConnection,
    player_id: int,
    model_run_id: str,
    report_type: str = "scouting",
    llm_models: Sequence[str] = (),
    prompt_version: str | None = None,
) -> dict[str, Any] | None:
    """Fetch the stored report that answers a generate request, if any.

    Two keys are reachable in one query: the row a configured model and the
    current prompt produced, and the deterministic row the last failed
    generation wrote. The LLM row wins when both exist: it is the report a
    configured model produced, and the deterministic row is the fallback of a
    model that was down. How long the deterministic row may answer a request is
    the cache policy's decision, applied by `services.report_cache` on the row
    this returns.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                r.id, r.player_id, p.name AS player_name,
                r.model_run_id, r.report_type, r.content, r.created_at,
                r.source, r.llm_model, r.prompt_version
            FROM app.reports r
            LEFT JOIN analytics.dim_players p
              ON p.model_run_id = r.model_run_id AND p.player_id = r.player_id
            WHERE r.player_id = %s AND r.model_run_id = %s AND r.report_type = %s
              AND (
                    (r.source = 'llm'
                     AND r.llm_model = ANY(%s)
                     AND r.prompt_version IS NOT DISTINCT FROM %s)
                 OR (r.source = 'deterministic'
                     AND r.llm_model IS NULL
                     AND r.prompt_version IS NULL)
                   )
            ORDER BY (r.source = 'llm') DESC, r.created_at DESC, r.id DESC
            LIMIT 1;
            """,
            (player_id, model_run_id, report_type, list(llm_models), prompt_version),
        )
        return await cur.fetchone()
