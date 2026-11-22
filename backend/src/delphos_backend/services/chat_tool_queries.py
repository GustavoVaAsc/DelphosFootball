"""Query executors behind the list chat tools, mapped for dispatch.

Input: validated arguments, the active model_run_id, and a database connection.
Output: capped result payloads; an empty result for an unknown filter combination.
Responsibility: the search and cluster executors (LLM_PLAN §10.2) calling existing
repository functions — no new SQL — with list caps and Spanish labels from
delphos_domain; TOOL_HANDLERS binds all five tool names for chat_tools dispatch.
The three player-entity executors live in chat_tool_players.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from delphos_domain import (
    POSITION_LABELS,
    SUB_POSITION_LABELS,
    VALUATION_STATUS_LABELS,
    resolve_cluster_label,
)
from psycopg import AsyncConnection

from delphos_backend.repositories.clusters import get_clusters_summary
from delphos_backend.repositories.player_order import DEFAULT_SORT, PLAYER_ORDERINGS
from delphos_backend.repositories.players import list_players
from delphos_backend.services.chat_player_summary import player_summary
from delphos_backend.services.chat_search_args import age_args, sub_positions_arg
from delphos_backend.services.chat_tool_args import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    enum_arg,
    int_arg,
    str_arg,
)
from delphos_backend.services.chat_tool_players import (
    get_player_profile_tool,
    get_player_replacements_tool,
    get_player_valuation_tool,
)

ToolExecutor = Callable[[AsyncConnection, str, dict[str, Any]], Awaitable[dict[str, Any]]]


async def search_players_tool(
    conn: AsyncConnection, run_id: str, args: dict[str, Any]
) -> dict[str, Any]:
    name, error = str_arg("search_players", "name", args)
    if error:
        return error
    for argument, allowed in (
        ("position", POSITION_LABELS),
        ("sort_by", PLAYER_ORDERINGS),
        ("valuation_status", VALUATION_STATUS_LABELS),
    ):
        if error := enum_arg("search_players", argument, args, allowed):
            return error
    sub_positions, error = sub_positions_arg("search_players", args, SUB_POSITION_LABELS)
    if error:
        return error
    min_age, max_age, error = age_args("search_players", args)
    if error:
        return error
    cluster_id, error = int_arg("search_players", "cluster_id", args, lo=0, hi=2, required=False)
    if error:
        return error
    limit, error = int_arg("search_players", "limit", args, lo=1, hi=MAX_LIMIT, required=False)
    if error:
        return error
    page_size = limit or DEFAULT_LIMIT
    sort_by = args.get("sort_by") or DEFAULT_SORT  # a null argument means "unset"
    players, total = await list_players(
        conn,
        run_id,
        name=name,
        position=args.get("position"),
        sub_position=sub_positions,
        min_age=min_age,
        max_age=max_age,
        sort_by=sort_by,
        valuation_status=args.get("valuation_status"),
        cluster_id=cluster_id,
        page_size=page_size,
    )
    return {
        "players": [player_summary(p) for p in players],
        "total": total,
        "limit": page_size,
        "sort_by": sort_by,
    }


async def get_cluster_summary_tool(
    conn: AsyncConnection, run_id: str, args: dict[str, Any]
) -> dict[str, Any]:
    cluster_id, error = int_arg(
        "get_cluster_summary", "cluster_id", args, lo=0, hi=2, required=False
    )
    if error:
        return error
    rows = await get_clusters_summary(conn, run_id)
    if cluster_id is not None:
        rows = [row for row in rows if row.get("cluster_id") == cluster_id]
    clusters = []
    for row in rows:
        label = resolve_cluster_label(row.get("cluster_id"))
        clusters.append({**row, "cluster_label": label[0] if isinstance(label, tuple) else label})
    return {"clusters": clusters, "total": len(clusters)}


TOOL_HANDLERS: dict[str, ToolExecutor] = {
    "search_players": search_players_tool,
    "get_player_profile": get_player_profile_tool,
    "get_player_valuation": get_player_valuation_tool,
    "get_player_replacements": get_player_replacements_tool,
    "get_cluster_summary": get_cluster_summary_tool,
}
