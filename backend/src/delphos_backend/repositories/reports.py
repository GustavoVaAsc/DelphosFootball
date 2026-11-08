"""Database repository queries for persisted AI scouting reports in app.reports.

Input: Active model_run_id, player_id, report_id, and generated report content.
Output: Report dictionary rows from app.reports joined with analytics.dim_players.
Responsibility: Reads and writes scouting report records in the app schema.
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection


async def get_latest_player_report(
    conn: AsyncConnection,
    player_id: int,
    model_run_id: str,
    report_type: str = "scouting",
) -> dict[str, Any] | None:
    """Fetch the most recent report for a player and model run from app.reports."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                r.id, r.player_id, p.name AS player_name,
                r.model_run_id, r.report_type, r.content, r.created_at
            FROM app.reports r
            LEFT JOIN analytics.dim_players p
              ON p.model_run_id = r.model_run_id AND p.player_id = r.player_id
            WHERE r.player_id = %s AND r.model_run_id = %s AND r.report_type = %s
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT 1;
            """,
            (player_id, model_run_id, report_type),
        )
        return await cur.fetchone()


async def get_report_by_id(
    conn: AsyncConnection,
    report_id: int,
) -> dict[str, Any] | None:
    """Fetch a single persisted scouting report by primary key id."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                r.id, r.player_id, p.name AS player_name,
                r.model_run_id, r.report_type, r.content, r.created_at
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
                r.model_run_id, r.report_type, r.content, r.created_at
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
) -> dict[str, Any]:
    """Insert a newly generated scouting report into app.reports and commit."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO app.reports (player_id, model_run_id, report_type, content)
            VALUES (%s, %s, %s, %s)
            RETURNING id, player_id, model_run_id, report_type, content, created_at;
            """,
            (player_id, model_run_id, report_type, content),
        )
        row = await cur.fetchone()
    await conn.commit()
    return {**(dict(row) if row else {}), "player_name": player_name}
