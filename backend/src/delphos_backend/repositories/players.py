"""Database repository queries for outfield players and valuations."""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

ACTIVE_SEASON = 2025


async def list_players(
    conn: AsyncConnection,
    model_run_id: str,
    name: str | None = None,
    position: str | None = None,
    club_id: int | None = None,
    valuation_status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """Return paginated player summaries matching filters for the active model run."""
    conditions = ["p.model_run_id = %s", "s.season = %s"]
    params: list[Any] = [model_run_id, ACTIVE_SEASON]

    if name:
        conditions.append("p.name ILIKE %s")
        params.append(f"%{name}%")
    if position:
        conditions.append("p.position = %s")
        params.append(position)
    if club_id:
        conditions.append("s.club_id = %s")
        params.append(club_id)
    if valuation_status:
        conditions.append("pred.valuation_status = %s")
        params.append(valuation_status)

    where_clause = " AND ".join(conditions)

    async with conn.cursor() as cur:
        # Count total
        count_sql = f"""
            SELECT COUNT(*) AS total
            FROM analytics.dim_players p
            JOIN analytics.fct_player_seasons s
              ON s.model_run_id = p.model_run_id AND s.player_id = p.player_id
            LEFT JOIN analytics.fct_player_predictions pred
              ON pred.model_run_id = p.model_run_id
             AND pred.player_id = p.player_id
             AND pred.season = s.season
            WHERE {where_clause};
        """
        await cur.execute(count_sql, params)
        total_row = await cur.fetchone()
        total = total_row["total"] if total_row else 0

        # Query page items
        offset = (page - 1) * page_size
        query_sql = f"""
            SELECT
                p.player_id, p.name, p.first_name, p.last_name,
                p.position, p.sub_position, p.image_url,
                s.club_id, c.name AS club_name,
                pred.market_value_eur, pred.valuation_status
            FROM analytics.dim_players p
            JOIN analytics.fct_player_seasons s
              ON s.model_run_id = p.model_run_id AND s.player_id = p.player_id
            LEFT JOIN analytics.dim_clubs c
              ON c.model_run_id = p.model_run_id AND c.club_id = s.club_id
            LEFT JOIN analytics.fct_player_predictions pred
              ON pred.model_run_id = p.model_run_id
             AND pred.player_id = p.player_id
             AND pred.season = s.season
            WHERE {where_clause}
            ORDER BY pred.market_value_eur DESC NULLS LAST, p.name ASC
            LIMIT %s OFFSET %s;
        """
        await cur.execute(query_sql, [*params, page_size, offset])
        items = await cur.fetchall()

    return list(items), total


async def get_player_profile(
    conn: AsyncConnection, model_run_id: str, player_id: int
) -> dict[str, Any] | None:
    """Fetch complete player profile and active season statistics."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                p.player_id, p.name, p.first_name, p.last_name, p.player_code,
                p.country_of_citizenship, p.date_of_birth, p.position, p.sub_position,
                p.foot, p.height_in_cm, p.image_url, p.url,
                s.season, s.as_of_date, s.league_id, s.minutes, s.apps, s.starts,
                s.goals, s.assists, s.yellow_cards, s.red_cards, s.starter_ratio,
                s.win_rate, s.clean_sheet_rate, s.goals_conceded_per_match,
                s.league_position, s.age
            FROM analytics.dim_players p
            LEFT JOIN analytics.fct_player_seasons s
              ON s.model_run_id = p.model_run_id
             AND s.player_id = p.player_id
             AND s.season = %s
            WHERE p.model_run_id = %s AND p.player_id = %s;
            """,
            (ACTIVE_SEASON, model_run_id, player_id),
        )
        row = await cur.fetchone()
        if not row:
            return None

        season_metrics = None
        if row["season"] is not None:
            metrics_keys = (
                "season", "as_of_date", "league_id", "minutes", "apps", "starts",
                "goals", "assists", "yellow_cards", "red_cards", "starter_ratio",
                "win_rate", "clean_sheet_rate", "goals_conceded_per_match",
                "league_position", "age",
            )
            season_metrics = {k: row[k] for k in metrics_keys}

        return {**dict(row), "active_season": season_metrics}


# Re-export valuation query for repository facade compatibility
from delphos_backend.repositories.valuations import (  # noqa: E402
    get_player_valuation as get_player_valuation,
)
