"""The slim, Spanish-labelled player row the search_players tool returns.

Input: one row of the player search (repository shape).
Output: the compact summary dict the model reads, with the season age rounded.
Responsibility: keep 10 results inside the JSON cap and the vocabulary in Spanish.
Split from chat_tool_queries to keep both modules inside the size budget.
"""

from __future__ import annotations

from typing import Any

from delphos_domain import resolve_position_label, resolve_valuation_label


def player_summary(row: dict[str, Any]) -> dict[str, Any]:
    """Slim, Spanish-labelled player row so 10 results stay inside the JSON cap."""
    return {
        "player_id": row.get("player_id"),
        "name": row.get("name"),
        "position_label": resolve_position_label(row.get("position"), row.get("sub_position")),
        "club_name": row.get("club_name"),
        "market_value_eur": row.get("market_value_eur"),
        "valuation_label": resolve_valuation_label(row.get("valuation_status") or ""),
        "cluster_id": row.get("cluster_id"),
        "age": season_age(row.get("age")),
    }


def season_age(age: float | None) -> float | None:
    """The age the search reports: fct_player_seasons.age, as of the active season.

    It is the same column get_player_profile returns in its `age`, rounded to one
    decimal here to keep 10 rows inside the JSON cap and the figure readable.
    """
    return round(age, 1) if age is not None else None
