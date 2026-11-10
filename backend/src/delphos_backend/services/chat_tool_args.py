"""Argument validation for the chat tools: typed, model-readable errors.

Input: model-supplied tool arguments (free text, numbers, or absent keys).
Output: coerced values plus {"error": {...}} payloads naming the offending argument.
Responsibility: validate arguments BEFORE execution (LLM_PLAN §10.2) so a bad
argument reaches the model as a retryable message, never as an exception. No
I/O happens here, which is why validation lives apart from the tool queries.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEFAULT_LIMIT = 5
MAX_LIMIT = 10
MAX_RESULT_CHARS = 4000
PLAYER_ID_RANGE = (1, 10**9)


def arg_error(tool: str, argument: str, value: Any, expected: str) -> dict[str, Any]:
    """Build the typed error the model reads and retries with corrected arguments."""
    return {
        "error": {
            "tool": tool,
            "argument": argument,
            "value": value if isinstance(value, str | int | float | bool) else None,
            "message": f"argumento inválido: {argument}",
            "expected": expected,
        }
    }


def enum_arg(
    tool: str, argument: str, args: Mapping[str, Any], allowed: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Validate a free-text argument against a vocabulary; None when absent or valid."""
    value = args.get(argument)
    if value is None:
        return None
    if isinstance(value, str) and value in allowed:
        return None
    return arg_error(tool, argument, value, "valores: " + ", ".join(allowed))


def int_arg(
    tool: str,
    argument: str,
    args: Mapping[str, Any],
    *,
    lo: int,
    hi: int,
    required: bool = True,
) -> tuple[int | None, dict[str, Any] | None]:
    """Coerce an argument to an int inside [lo, hi]; returns (value, error).

    Booleans are rejected explicitly: bool is a subclass of int, so `True`
    would otherwise silently become 1.
    """
    expected = f"entero entre {lo} y {hi}" + ("" if not required else " (requerido)")
    value = args.get(argument)
    if value is None:
        return (None, arg_error(tool, argument, None, expected)) if required else (None, None)
    if isinstance(value, bool):
        return None, arg_error(tool, argument, value, expected)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, arg_error(tool, argument, value, expected)
    out_of_range = not lo <= parsed <= hi
    if (isinstance(value, float) and not value.is_integer()) or out_of_range:
        return None, arg_error(tool, argument, value, expected)
    return parsed, None
