"""Database repository queries for tactical player replacements."""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection


async def get_player_replacements(
    conn: AsyncConnection, model_run_id: str, target_player_id: int
) -> dict[str, Any] | None:
    """Fetch precalculated replacement rankings and target shortfall diagnostic."""
    async with conn.cursor() as cur:
        # 1. Fetch target metadata
        await cur.execute(
            """
            SELECT
                t.player_id AS target_player_id, p.name AS target_name,
                t.model_run_id, t.season, t.is_elite_asset,
                t.market_value_eur AS target_market_value_eur,
                t.qualifying_count, t.shortfall_reason
            FROM analytics.fct_replacement_targets t
            JOIN analytics.dim_players p
              ON p.model_run_id = t.model_run_id AND p.player_id = t.player_id
            WHERE t.model_run_id = %s AND t.player_id = %s;
            """,
            (model_run_id, target_player_id),
        )
        target = await cur.fetchone()
        if not target:
            return None

        # 2. Fetch up to 3 precalculated replacement candidates
        await cur.execute(
            """
            SELECT
                r.rank, r.candidate_player_id, cand.name AS candidate_name,
                r.position, r.similarity_score, r.euclidean_distance,
                r.candidate_market_value_eur, r.cost_savings_eur,
                r.cost_ratio, r.candidate_fair_value_eur,
                r.candidate_valuation_status
            FROM analytics.fct_replacements r
            JOIN analytics.dim_players cand
              ON cand.model_run_id = r.model_run_id AND cand.player_id = r.candidate_player_id
            WHERE r.model_run_id = %s AND r.target_player_id = %s
            ORDER BY r.rank ASC;
            """,
            (model_run_id, target_player_id),
        )
        rows = await cur.fetchall()

    return {
        **dict(target),
        "replacements": [dict(row) for row in rows],
    }
