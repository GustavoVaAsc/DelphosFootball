"""Database queries for AI scouting reports in app.reports.

Input: player/run/report ids, generated content, and provenance. Output: report
rows joined with analytics.dim_players. Responsibility: read and write
scouting-report records in the app schema. The cache lookup lives in
`report_cache.py`, which owns the provenance keys of a stored report.
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection


async def get_report_by_id(conn: AsyncConnection, report_id: int) -> dict[str, Any] | None:
    """Fetch a single persisted scouting report by primary key id."""
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
            WHERE r.id = %s;
            """,
            (report_id,),
        )
        return await cur.fetchone()


async def list_reports(
    conn: AsyncConnection,
    model_run_id: str,
    player_id: int | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """List saved scouting reports for the active model run, optionally filtered by player."""
    conditions = ["r.model_run_id = %s"]
    params: list[Any] = [model_run_id]
    if player_id is not None:
        conditions.append("r.player_id = %s")
        params.append(player_id)

    where_sql = " AND ".join(conditions)
    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT
                r.id, r.player_id, p.name AS player_name,
                r.model_run_id, r.report_type, r.content, r.created_at,
                r.source, r.llm_model, r.prompt_version
            FROM app.reports r
            LEFT JOIN analytics.dim_players p
              ON p.model_run_id = r.model_run_id AND p.player_id = r.player_id
            WHERE {where_sql}
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT %s;
            """,
            [*params, limit],
        )
        return [dict(row) for row in await cur.fetchall()]


async def save_report(
    conn: AsyncConnection,
    player_id: int,
    model_run_id: str,
    content: str,
    report_type: str = "scouting",
    player_name: str | None = None,
    source: str = "llm",
    llm_model: str | None = None,
    prompt_version: str | None = None,
) -> dict[str, Any]:
    """Insert a generated report with its provenance and commit (LLM_PLAN §12)."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO app.reports
                (player_id, model_run_id, report_type, content, source, llm_model, prompt_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, player_id, model_run_id, report_type, content, created_at,
                source, llm_model, prompt_version;
            """,
            (player_id, model_run_id, report_type, content, source, llm_model, prompt_version),
        )
        row = await cur.fetchone()
    await conn.commit()
    return {**(dict(row) if row else {}), "player_name": player_name}
