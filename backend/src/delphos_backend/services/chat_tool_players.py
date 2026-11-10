"""Executors for the three player-entity chat tools: profile, valuation, replacements.

Input: validated player_id argument, the active model_run_id, and a connection.
Output: a capped result payload, or "found: False" for an unknown player.
Responsibility: one executor per player tool (LLM_PLAN §10.2), each calling its
existing repository function — no new SQL — with Spanish labels from
delphos_domain. The payloads are projected onto the allow-list the report fact
card cites, so no personal data (date of birth, citizenship, height, foot,
player code) and no external image URL leaves the database.
"""

from __future__ import annotations

from typing import Any

from delphos_domain import (
    SUB_POSITION_LABELS,
    resolve_cluster_label,
    resolve_position_label,
    resolve_valuation_label,
)
from psycopg import AsyncConnection

from delphos_backend.repositories.players import get_player_profile
from delphos_backend.repositories.replacements import get_player_replacements
from delphos_backend.repositories.valuations import get_player_valuation
from delphos_backend.services.chat_tool_args import PLAYER_ID_RANGE, int_arg

MAX_REPLACEMENT_CANDIDATES = 5
PROFILE_SEASON_FIELDS = (
    "season",
    "league_id",
    "age",
    "minutes",
    "apps",
    "starts",
    "goals",
    "assists",
    "starter_ratio",
    "win_rate",
    "clean_sheet_rate",
)
CANDIDATE_FIELDS = (
    "rank",
    "candidate_name",
    "candidate_club_name",
    "similarity_score",
    "candidate_market_value_eur",
    "candidate_fair_value_eur",
    "candidate_valuation_status",
    "cost_savings_eur",
    "cost_ratio",
)


def _fetch_player_id(tool: str, args: dict[str, Any]) -> tuple[int | None, dict[str, Any] | None]:
    """Validate the shared player_id argument of the three player tools."""
    lo, hi = PLAYER_ID_RANGE
    return int_arg(tool, "player_id", args, lo=lo, hi=hi)


def _profile_payload(profile: dict[str, Any]) -> dict[str, Any]:
    """Project the raw profile row onto the fields the report fact card cites."""
    season = profile.get("active_season") or {}
    cluster = resolve_cluster_label(profile.get("cluster_id"))
    return {
        "player_id": profile.get("player_id"),
        "name": profile.get("name"),
        "club_name": profile.get("club_name"),
        "position_label": resolve_position_label(
            profile.get("position"), profile.get("sub_position")
        ),
        "sub_position_label": SUB_POSITION_LABELS.get(
            profile.get("sub_position"), profile.get("sub_position")
        ),
        "cluster_label": cluster[0] if isinstance(cluster, tuple) else cluster,
        "active_season": {key: season.get(key) for key in PROFILE_SEASON_FIELDS},
    }


def _candidate_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    """Project one replacement candidate onto the report card's candidate fields."""
    return {key: candidate.get(key) for key in CANDIDATE_FIELDS}


async def get_player_profile_tool(
    conn: AsyncConnection, run_id: str, args: dict[str, Any]
) -> dict[str, Any]:
    player_id, error = _fetch_player_id("get_player_profile", args)
    if error:
        return error
    profile = await get_player_profile(conn, run_id, player_id)
    if profile is None:  # unknown entity: empty result, not an error
        return {"player_id": player_id, "found": False, "profile": None}
    return {"found": True, "profile": _profile_payload(profile)}


async def get_player_valuation_tool(
    conn: AsyncConnection, run_id: str, args: dict[str, Any]
) -> dict[str, Any]:
    player_id, error = _fetch_player_id("get_player_valuation", args)
    if error:
        return error
    valuation = await get_player_valuation(conn, run_id, player_id)
    if valuation is None:
        return {"player_id": player_id, "found": False, "valuation": None}
    valuation["valuation_label"] = resolve_valuation_label(valuation.get("valuation_status") or "")
    return {"found": True, "valuation": valuation}


async def get_player_replacements_tool(
    conn: AsyncConnection, run_id: str, args: dict[str, Any]
) -> dict[str, Any]:
    player_id, error = _fetch_player_id("get_player_replacements", args)
    if error:
        return error
    replacements = await get_player_replacements(conn, run_id, player_id)
    if replacements is None:
        return {"player_id": player_id, "found": False, "replacements": None}
    # The repository returns the candidate list under "replacements"; the tool
    # keeps that single key and caps the list.
    payload = {key: value for key, value in replacements.items() if key != "replacements"}
    candidates = (replacements.get("replacements") or [])[:MAX_REPLACEMENT_CANDIDATES]
    payload["replacements"] = [_candidate_payload(candidate) for candidate in candidates]
    return {"found": True, **payload}
