"""Parsing of the model's chat replies into tool calls or plain answers.

Input: the raw text of one model completion.
Output: a {"tool", "arguments"} call, or None when the reply is a plain answer.
Responsibility: parse the model's JSON reply defensively. The reply is
model-controlled, so it may be truncated, malformed, or adversarially nested;
the parser bounds its input and treats an unparsable reply as a plain answer
instead of raising, so a hostile payload cannot become a 500.
"""

from __future__ import annotations

import json
from typing import Any

MAX_TOOL_CALL_CHARS = 4000


def parse_tool_call(content: str) -> dict[str, Any] | None:
    """Parse a model reply into {"tool", "arguments"}; None for a plain answer."""
    text = content.strip()[:MAX_TOOL_CALL_CHARS]
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        # A truncated or deeply nested payload is a plain (bad) answer, not a crash.
        return None
    if isinstance(data, dict) and isinstance(data.get("tool"), str):
        return {"tool": data["tool"], "arguments": data.get("arguments")}
    return None
