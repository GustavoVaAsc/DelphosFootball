"""Database repository queries for tactical cluster archetypes."""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

ACTIVE_SEASON = 2025

CLUSTER_NAMES: dict[int, str] = {
    0: "Attacking Creators & Scorers",
    1: "Balanced Box-to-Box & Flank Runners",
    2: "Defensive Anchors & Low-Output Outfielders",
}


async def get_clusters_summary(conn: AsyncConnection, model_run_id: str) -> list[dict[str, Any]]:
    """Return aggregated tactical archetypes across active season outfield players."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                c.cluster_id,
                COUNT(*) AS player_count,
                AVG(s.minutes) AS avg_minutes,
                AVG(s.goals) AS avg_goals,
                AVG(s.assists) AS avg_assists,
                AVG(p.market_value_eur) AS avg_market_value_eur
            FROM analytics.fct_clusters c
            JOIN analytics.fct_player_seasons s
              ON s.model_run_id = c.model_run_id
             AND s.player_id = c.player_id
             AND s.season = c.season
            LEFT JOIN analytics.fct_player_predictions p
              ON p.model_run_id = c.model_run_id
             AND p.player_id = c.player_id
             AND p.season = c.season
            WHERE c.model_run_id = %s AND c.season = %s
            GROUP BY c.cluster_id
            ORDER BY c.cluster_id ASC;
            """,
            (model_run_id, ACTIVE_SEASON),
        )
        rows = await cur.fetchall()

    return [
        {
            "cluster_id": row["cluster_id"],
            "name": CLUSTER_NAMES.get(row["cluster_id"], f"Archetype {row['cluster_id']}"),
            "player_count": int(row["player_count"]),
            "avg_minutes": round(float(row["avg_minutes"] or 0), 1),
            "avg_goals": round(float(row["avg_goals"] or 0), 2),
            "avg_assists": round(float(row["avg_assists"] or 0), 2),
            "avg_market_value_eur": round(float(row["avg_market_value_eur"] or 0), 2),
        }
        for row in rows
    ]
