"""Parsing of the model's chat replies into tool calls or plain answers.

Input: the raw text of one model completion.
Output: a {"tool", "arguments"} call, or None when the reply is a plain answer; a
heuristic that spots an unparsed attempted call so it is never shown as an answer.
Responsibility: build the tool-result messages and parse the model's JSON reply
defensively. The reply is model-controlled, so it may be truncated, malformed,
or adversarially nested; the parser bounds its input and returns None for an
unparsable reply instead of raising, so a hostile payload cannot become a 500. The caller then asks
looks_like_tool_call whether that None is a plain answer or a broken call.
"""

from __future__ import annotations

import json
import re
from typing import Any

from delphos_backend.services.chat_budget import TOOL_RESULT_PREFIX
from delphos_backend.services.chat_tools import TOOL_NAMES

MAX_TOOL_CALL_CHARS = 4000
_FENCE_OPEN = re.compile(r"^```[a-zA-Z]*\s*")
_CALL_TAG = re.compile(r"<\s*\|?\s*/?\s*(tool_call|function_call|tool_use)", re.IGNORECASE)
_TOOL_KEY = re.compile(r"""["']tool["']\s*:""")
_NAME_KEY = re.compile(r"""["'](name|function)["']\s*:""")
_ARGUMENTS_KEY = re.compile(r"""["']arguments["']\s*:""")


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


def looks_like_tool_call(content: str) -> bool:
    """True when a reply that did not parse still reads as an attempted tool call.

    Conservative on purpose: the reply must start with a brace or a code fence
    opening one, carry a tool-call tag or special token, a fence with a brace,
    a quoted "tool" key, a "name"/"function" key next to "arguments", or a
    tool identifier. A Spanish
    answer that merely mentions a braced value or a quoted word does not match.
    """
    text = _FENCE_OPEN.sub("", content.strip(), count=1).lstrip()
    if text.startswith(("{", "[{")) or _CALL_TAG.search(text) or _TOOL_KEY.search(text):
        return True
    if "```" in text and "{" in text:
        return True
    if _NAME_KEY.search(text) and _ARGUMENTS_KEY.search(text):
        return True
    return any(tool in text for tool in TOOL_NAMES)


MALFORMED_CALL_ERROR = {
    "error": {
        "tool": "llamada",
        "message": "llamada a herramienta mal formada",
        "expected": 'solo un objeto JSON válido {"tool": "<nombre>", "arguments": {...}}',
    }
}


def tool_result_message(name: str, payload: dict[str, Any]) -> dict[str, str]:
    """The data message that carries a tool result (or a typed error) to the model."""
    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    return {"role": "user", "content": f"{TOOL_RESULT_PREFIX}{name}»:\n{serialized}"}
