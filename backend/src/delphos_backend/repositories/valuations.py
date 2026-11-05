"""Database queries for player valuation predictions and diagnostics."""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

ACTIVE_SEASON = 2025


async def get_player_valuation(
    conn: AsyncConnection, model_run_id: str, player_id: int
) -> dict[str, Any] | None:
    """Fetch valuation prediction details for a player in the active season."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                p.player_id, p.name, pred.model_run_id, pred.season,
                pred.market_value_eur, pred.fair_value_eur, pred.residual_log10,
                pred.valuation_status, pred.is_undervalued, pred.rf_undervalued_prob,
                pred.dt_undervalued_pred, pred.rf_undervalued_pred
            FROM analytics.fct_player_predictions pred
            JOIN analytics.dim_players p
              ON p.model_run_id = pred.model_run_id AND p.player_id = pred.player_id
            WHERE pred.model_run_id = %s AND pred.player_id = %s AND pred.season = %s;
            """,
            (model_run_id, player_id, ACTIVE_SEASON),
        )
        return await cur.fetchone()
