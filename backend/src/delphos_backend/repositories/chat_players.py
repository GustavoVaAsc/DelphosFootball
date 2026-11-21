"""Hydrate compact visual metadata for players referenced in chat answers.

Input: active model_run_id and an ordered list of player IDs.
Output: player dicts carrying portrait, club crest, country, league, price
and valuation status for the UI player chips/rows below PitIA's answer.
Responsibility: parameterized batch lookup over analytics.* that short-circuits
before opening a cursor when no player IDs are present.
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from delphos_backend.repositories.players import ACTIVE_SEASON, build_club_logo_url

CHAT_PLAYER_KEYS = (
    "player_id",
    "name",
    "position",
    "sub_position",
    "country",
    "club_name",
    "club_logo_url",
    "league_id",
    "image_url",
    "market_value_eur",
    "fair_value_eur",
    "valuation_status",
)


def _unique_positive_ids(player_ids: list[int]) -> list[int]:
    """Preserve order while keeping positive ints once each."""
    seen: set[int] = set()
    ordered: list[int] = []
    for pid in player_ids:
        if isinstance(pid, int) and pid > 0 and pid not in seen:
            seen.add(pid)
            ordered.append(pid)
    return ordered


def _project_row(row: dict[str, Any]) -> dict[str, Any]:
    """Build one ChatReferencedPlayer-shaped dict with computed club crest URL."""
    enriched = {**row, "club_logo_url": build_club_logo_url(row.get("club_id"))}
    return {key: enriched.get(key) for key in CHAT_PLAYER_KEYS}


async def get_chat_players_by_ids(
    conn: AsyncConnection, model_run_id: str, player_ids: list[int]
) -> dict[int, dict[str, Any]]:
    """Fetch metadata for [player_ids] keyed by player_id; zero SQL when empty."""
    unique_ids = _unique_positive_ids(player_ids)
    if not unique_ids:
        return {}
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                p.player_id, p.name, p.position, p.sub_position,
                p.country_of_citizenship AS country, p.image_url,
                s.club_id, s.league_id, c.name AS club_name,
                pred.market_value_eur, pred.fair_value_eur, pred.valuation_status
            FROM analytics.dim_players p
            LEFT JOIN analytics.fct_player_seasons s
              ON s.model_run_id = p.model_run_id AND s.player_id = p.player_id AND s.season = %s
            LEFT JOIN analytics.dim_clubs c
              ON c.model_run_id = p.model_run_id AND c.club_id = s.club_id
            LEFT JOIN analytics.fct_player_predictions pred
              ON pred.model_run_id = p.model_run_id
             AND pred.player_id = p.player_id AND pred.season = s.season
            WHERE p.model_run_id = %s AND p.player_id = ANY(%s);
            """,
            (ACTIVE_SEASON, model_run_id, unique_ids),
        )
        rows = await cur.fetchall()
    return {row["player_id"]: _project_row(dict(row)) for row in rows if row.get("player_id")}


async def hydrate_chat_players(
    conn: AsyncConnection, model_run_id: str, player_ids: list[int]
) -> list[dict[str, Any]]:
    """Return hydrated player dicts in the same order as [player_ids]."""
    unique_ids = _unique_positive_ids(player_ids)
    if not unique_ids:
        return []
    by_id = await get_chat_players_by_ids(conn, model_run_id, unique_ids)
    return [by_id[pid] for pid in unique_ids if pid in by_id]
