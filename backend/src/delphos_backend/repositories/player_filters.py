"""WHERE conditions for the structured player-search filters.

Input: the optional filter values of a player search (position, sub-position or a list
of them, club, valuation status, cluster, and an age range).
Output: the parameterized SQL conditions and their bind parameters, in order.
Responsibility: turn each supplied filter into a bound predicate; no caller value is
ever interpolated into the SQL text. Ages compare against s.age, the season age the
search results and the player profile report: min_age and max_age are completed years,
so a player aged 21.7 is 21 and `max_age=21` admits every age below 22. Kept separate
from players.py to preserve the 130-line module budget.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def build_filters(
    *,
    position: str | None,
    sub_position: str | Sequence[str] | None,
    club_id: int | None,
    valuation_status: str | None,
    cluster_id: int | None,
    min_age: int | None,
    max_age: int | None,
) -> tuple[list[str], list[Any]]:
    """Return the conditions and bind parameters for every filter that was supplied."""
    conditions: list[str] = []
    params: list[Any] = []
    sub_condition, sub_value = "p.sub_position = %s", sub_position
    if sub_position is not None and not isinstance(sub_position, str):
        sub_condition, sub_value = "p.sub_position = ANY(%s)", list(sub_position)
    for cond, val in (
        ("p.position = %s", position),
        (sub_condition, sub_value),
        ("s.club_id = %s", club_id),
        ("pred.valuation_status = %s", valuation_status),
        ("cl.cluster_id = %s", cluster_id),
        ("s.age >= %s", min_age),
        ("s.age < %s", None if max_age is None else max_age + 1),
    ):
        if val is not None:
            conditions.append(cond)
            params.append(val)
    return conditions, params
