"""Database repository queries for outfield players and valuations.

Input: Active model_run_id, search filters, and player_id.
Output: Paginated player summaries and detailed biography/season metrics.
Responsibility: Executes parameterized SQL over analytics.dim_players and season facts.
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from delphos_backend.repositories.clusters import CLUSTER_NAMES
from delphos_backend.repositories.valuations import (
    get_player_valuation as get_player_valuation,
)

ACTIVE_SEASON = 2025
TM_CLUB_LOGO_TEMPLATE = "https://tmssl.akamaized.net/images/wappen/head/{club_id}.png"
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


def build_club_logo_url(club_id: int | None) -> str | None:
    """Return Transfermarkt CDN crest URL for a club ID."""
    return TM_CLUB_LOGO_TEMPLATE.format(club_id=club_id) if club_id is not None else None


async def list_players(
    conn: AsyncConnection,
    model_run_id: str,
    name: str | None = None,
    position: str | None = None,
    club_id: int | None = None,
    valuation_status: str | None = None,
    cluster_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """Return paginated player summaries matching filters for the active model run."""
    conditions = ["p.model_run_id = %s", "s.season = %s"]
    params: list[Any] = [model_run_id, ACTIVE_SEASON]
    for cond, val in (
        ("p.name ILIKE %s", f"%{name}%" if name else None),
        ("p.position = %s", position),
        ("s.club_id = %s", club_id),
        ("pred.valuation_status = %s", valuation_status),
        ("cl.cluster_id = %s", cluster_id),
    ):
        if val is not None:
            conditions.append(cond)
            params.append(val)

    where_sql = " AND ".join(conditions)
    base_joins = """
        FROM analytics.dim_players p
        JOIN analytics.fct_player_seasons s
          ON s.model_run_id = p.model_run_id AND s.player_id = p.player_id
        LEFT JOIN analytics.dim_clubs c
          ON c.model_run_id = p.model_run_id AND c.club_id = s.club_id
        LEFT JOIN analytics.fct_player_predictions pred
          ON pred.model_run_id = p.model_run_id
         AND pred.player_id = p.player_id AND pred.season = s.season
        LEFT JOIN analytics.fct_clusters cl
          ON cl.model_run_id = p.model_run_id
         AND cl.player_id = p.player_id AND cl.season = s.season
    """
    async with conn.cursor() as cur:
        await cur.execute(f"SELECT COUNT(*) AS total {base_joins} WHERE {where_sql};", params)
        total_row = await cur.fetchone()
        total = total_row["total"] if total_row else 0

        offset = (page - 1) * page_size
        await cur.execute(
            f"""
            SELECT
                p.player_id, p.name, p.first_name, p.last_name,
                p.position, p.sub_position, p.country_of_citizenship, p.image_url,
                s.club_id, c.name AS club_name,
                pred.market_value_eur, pred.valuation_status, cl.cluster_id
            {base_joins}
            WHERE {where_sql}
            ORDER BY pred.market_value_eur DESC NULLS LAST, p.name ASC
            LIMIT %s OFFSET %s;
            """,
            [*params, page_size, offset],
        )
        items = [
            {
                **dict(r),
                "club_logo_url": build_club_logo_url(r.get("club_id")),
                "cluster_name": CLUSTER_NAMES.get(r.get("cluster_id")),
            }
            for r in await cur.fetchall()
        ]
    return items, total


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
