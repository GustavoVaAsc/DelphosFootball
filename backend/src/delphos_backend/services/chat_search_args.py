"""Validation of the search_players arguments that take a list or an age.

Input: model-supplied search arguments (free text, numbers, lists, or absent keys).
Output: coerced sub-positions and age bounds, or the typed {"error": {...}} payload
naming the offending argument.
Responsibility: validate sub_position (one allowed value or a short list of them) and
min_age/max_age before the query runs, on top of the primitives in chat_tool_args.
Split from it to keep both modules under the size budget.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from delphos_backend.services.chat_tool_args import arg_error, int_arg

MAX_SUB_POSITIONS = 4
AGE_RANGE = (15, 45)


def sub_positions_arg(
    tool: str, args: Mapping[str, Any], allowed: Mapping[str, Any]
) -> tuple[list[str] | None, dict[str, Any] | None]:
    """Validate sub_position: one allowed value or a list of 1 to MAX_SUB_POSITIONS of them.

    Returns the distinct values in the order given (a single value becomes a one-item
    list), or None when the argument is absent.
    """
    value = args.get("sub_position")
    if value is None:
        return None, None
    values = value if isinstance(value, list) else [value]
    valid = 1 <= len(values) <= MAX_SUB_POSITIONS and all(
        isinstance(item, str) and item in allowed for item in values
    )
    if not valid:
        expected = f"un valor o una lista de 1 a {MAX_SUB_POSITIONS} valores de: " + ", ".join(
            allowed
        )
        return None, arg_error(tool, "sub_position", value, expected)
    return list(dict.fromkeys(values)), None


def age_args(
    tool: str, args: Mapping[str, Any]
) -> tuple[int | None, int | None, dict[str, Any] | None]:
    """Validate min_age and max_age: integers inside AGE_RANGE, min not above max.

    Both bounds are ages in completed years and inclusive (see player_filters).

    Returns (min_age, max_age, error); an absent bound is None. Floats, numeric
    strings and booleans are rejected, because an age is stated in whole years.
    """
    lo, hi = AGE_RANGE
    bounds: list[int | None] = []
    for argument in ("min_age", "max_age"):
        value = args.get(argument)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            return None, None, arg_error(tool, argument, value, f"entero entre {lo} y {hi}")
        bound, error = int_arg(tool, argument, args, lo=lo, hi=hi, required=False)
        if error:
            return None, None, error
        bounds.append(bound)
    min_age, max_age = bounds
    if min_age is not None and max_age is not None and min_age > max_age:
        return None, None, arg_error(tool, "min_age", min_age, "no mayor que max_age")
    return min_age, max_age, None
