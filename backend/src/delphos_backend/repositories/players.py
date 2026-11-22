"""Database repository queries for outfield players and valuations.

Input: Active model_run_id and search filters.
Output: Paginated player summaries and their total count.
Responsibility: Executes the parameterized search SQL over analytics.dim_players and season
facts. The single-player profile lives in player_profile.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg import AsyncConnection

from delphos_backend.repositories.clusters import CLUSTER_NAMES
from delphos_backend.repositories.player_filters import build_filters
from delphos_backend.repositories.player_order import DEFAULT_SORT, order_by_sql
from delphos_backend.repositories.player_search import build_search_clause
from delphos_backend.repositories.valuations import (
    get_player_valuation as get_player_valuation,
)

ACTIVE_SEASON = 2025
TM_CLUB_LOGO_TEMPLATE = "https://tmssl.akamaized.net/images/wappen/head/{club_id}.png"


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
    *,
    sub_position: str | Sequence[str] | None = None,
    sort_by: str = DEFAULT_SORT,
    min_age: int | None = None,
    max_age: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return paginated player summaries matching filters for the active model run.

    sub_position is one value or several (any of them matches); min_age and max_age
    bound the age in completed years (s.age >= min_age and s.age < max_age + 1). All of
    them also bound the total.
    """
    order_sql = order_by_sql(sort_by)
    conditions = ["p.model_run_id = %s", "s.season = %s"]
    params: list[Any] = [model_run_id, ACTIVE_SEASON]
    if search_clause := build_search_clause(name):
        search_sql, search_params = search_clause
        conditions.append(search_sql)
        params.extend(search_params)
    filter_conditions, filter_params = build_filters(
        position=position,
        sub_position=sub_position,
        club_id=club_id,
        valuation_status=valuation_status,
        cluster_id=cluster_id,
        min_age=min_age,
        max_age=max_age,
    )
    conditions.extend(filter_conditions)
    params.extend(filter_params)

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
                pred.market_value_eur, pred.fair_value_eur, pred.valuation_status,
                s.age, cl.cluster_id
            {base_joins}
            WHERE {where_sql}
            ORDER BY {order_sql}
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
