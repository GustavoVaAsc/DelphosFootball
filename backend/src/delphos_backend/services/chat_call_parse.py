"""Parsing of a model reply into one or several tool calls.

Input: the raw text of one model completion.
Output: the ordered list of {"tool", "arguments"} calls it carries, or a reason code
for a reply that looks like a call attempt but cannot be read as one.
Responsibility: accept a reply made only of tool-call objects (newline-separated,
concatenated, or a JSON array of objects, with optional surrounding whitespace and
one code fence) and nothing else. The reply is model-controlled, so a reply over
MAX_TOOL_CALL_CHARS is rejected whole, the number of calls is capped, non-finite
numbers (Infinity, NaN, 1e999) are invalid, and an unparsable or deeply nested payload
yields a reason instead of an exception. Prose mixed with a call stays malformed.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

MAX_TOOL_CALL_CHARS = 4000
MAX_CALLS_PER_REPLY = 4
INVALID_JSON = "invalid_json"
MIXED_TEXT = "mixed_text"
TOO_MANY_CALLS = "too_many_calls"
NO_TOOL_KEY = "no_tool_key"
_FENCE_OPEN = re.compile(r"\A```[A-Za-z]*[ \t]*\n?")
_FENCE_CLOSE = re.compile(r"\s*```\Z")


def _reject_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON constant: {value}")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"non-finite JSON number: {text}")
    return value


_DECODER = json.JSONDecoder(parse_constant=_reject_constant, parse_float=_finite_float)


def scan_calls(content: str) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Read a reply as tool calls: (calls, None) on success, (None, reason) otherwise.

    The reason is MIXED_TEXT when the unreadable remainder starts with prose (a letter
    or a tag), and INVALID_JSON for anything else: truncation, a stray character, a
    trailing comma, or a second code fence.
    """
    text = content.strip()
    if len(text) > MAX_TOOL_CALL_CHARS:
        return None, INVALID_JSON
    text = _FENCE_CLOSE.sub("", _FENCE_OPEN.sub("", text, count=1), count=1).strip()
    objects: list[Any] = []
    pos = 0
    try:
        while pos < len(text):
            value, end = _DECODER.raw_decode(text, pos)
            objects.extend(value if isinstance(value, list) else [value])
            if len(objects) > MAX_CALLS_PER_REPLY:
                return None, TOO_MANY_CALLS
            pos = end
            while pos < len(text) and text[pos].isspace():
                pos += 1
    except (ValueError, RecursionError):
        # A truncated or deeply nested payload is a bad answer, not a crash.
        rest = text[pos : pos + 1]
        return None, MIXED_TEXT if rest.isalpha() or rest == "<" else INVALID_JSON
    calls = [
        {"tool": obj["tool"], "arguments": obj.get("arguments")}
        for obj in objects
        if isinstance(obj, dict) and isinstance(obj.get("tool"), str)
    ]
    if not objects or len(calls) != len(objects):
        return None, NO_TOOL_KEY
    return calls, None


def parse_tool_call(content: str) -> dict[str, Any] | None:
    """Parse a reply carrying exactly one call into {"tool", "arguments"}; else None."""
    calls, _ = scan_calls(content)
    return calls[0] if calls is not None and len(calls) == 1 else None
