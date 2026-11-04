"""Repository helper to retrieve the active model run metadata.

Responsibility: Ensures all analytics queries filter strictly on the active model run.
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection


async def get_active_model_run(conn: AsyncConnection) -> dict[str, Any] | None:
    """Fetch the active model run record or return None if no active run is marked."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT model_run_id, dataset_version, activated_at
            FROM analytics.model_runs
            WHERE status = 'active'
            ORDER BY activated_at DESC NULLS LAST
            LIMIT 1;
            """
        )
        return await cur.fetchone()
