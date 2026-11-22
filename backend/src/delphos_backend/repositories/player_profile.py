"""Database repository query for one player's profile and active-season metrics.

Input: Active model_run_id and player_id.
Output: Complete biography plus active-season statistics, or None for an unknown player.
Responsibility: Executes the parameterized profile SQL over analytics.dim_players and the
season facts. Split from players.py to keep both modules inside the size budget.
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from delphos_backend.repositories.clusters import CLUSTER_NAMES
from delphos_backend.repositories.players import ACTIVE_SEASON, build_club_logo_url

SEASON_METRICS_KEYS = (
    "season",
    "as_of_date",
    "league_id",
    "minutes",
    "apps",
    "starts",
    "goals",
    "assists",
    "yellow_cards",
    "red_cards",
    "starter_ratio",
    "win_rate",
    "clean_sheet_rate",
    "goals_conceded_per_match",
    "league_position",
    "age",
)


async def get_player_profile(
    conn: AsyncConnection, model_run_id: str, player_id: int
) -> dict[str, Any] | None:
    """Fetch complete player profile and active season statistics."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                p.model_run_id, p.player_id, p.name, p.first_name, p.last_name, p.player_code,
                p.country_of_citizenship, p.date_of_birth, p.position, p.sub_position,
                p.foot, p.height_in_cm, p.image_url, p.url,
                s.club_id, c.name AS club_name, cl.cluster_id,
                s.season, s.as_of_date, s.league_id, s.minutes, s.apps, s.starts,
                s.goals, s.assists, s.yellow_cards, s.red_cards, s.starter_ratio,
                s.win_rate, s.clean_sheet_rate, s.goals_conceded_per_match,
                s.league_position, s.age
            FROM analytics.dim_players p
            LEFT JOIN analytics.fct_player_seasons s
              ON s.model_run_id = p.model_run_id AND s.player_id = p.player_id AND s.season = %s
            LEFT JOIN analytics.dim_clubs c
              ON c.model_run_id = p.model_run_id AND c.club_id = s.club_id
            LEFT JOIN analytics.fct_clusters cl
              ON cl.model_run_id = p.model_run_id AND cl.player_id = p.player_id AND cl.season = %s
            WHERE p.model_run_id = %s AND p.player_id = %s;
            """,
            (ACTIVE_SEASON, ACTIVE_SEASON, model_run_id, player_id),
        )
        row = await cur.fetchone()
        if not row:
            return None

        season_metrics = (
            {k: row[k] for k in SEASON_METRICS_KEYS} if row["season"] is not None else None
        )
        c_name = CLUSTER_NAMES.get(row["cluster_id"]) if row.get("cluster_id") is not None else None
        return {
            **dict(row),
            "club_logo_url": build_club_logo_url(row.get("club_id")),
            "cluster_name": c_name,
            "active_season": season_metrics,
        }
