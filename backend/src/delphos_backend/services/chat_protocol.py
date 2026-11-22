"""Heuristics and message framing of the chat protocol.

Input: the raw text of one model completion, or a tool result.
Output: whether an unparsed reply still reads as an attempted tool call, and the user
message that carries tool results or typed errors back to the model.
Responsibility: keep an unparsed attempted call from ever being shown as an answer, and
frame results. Reply parsing lives in chat_call_parse (parse_tool_call is re-exported
here for its existing callers) and the specific retry error in chat_call_errors.
"""

from __future__ import annotations

import json
import re
from typing import Any

from delphos_backend.services.chat_budget import TOOL_RESULT_PREFIX
from delphos_backend.services.chat_call_parse import parse_tool_call as parse_tool_call
from delphos_backend.services.chat_tools import TOOL_NAMES

_FENCE_OPEN = re.compile(r"^```[a-zA-Z]*\s*")
_CALL_TAG = re.compile(r"<\s*\|?\s*/?\s*(tool_call|function_call|tool_use)", re.IGNORECASE)
_TOOL_KEY = re.compile(r"""["']tool["']\s*:""")
_NAME_KEY = re.compile(r"""["'](name|function)["']\s*:""")
_ARGUMENTS_KEY = re.compile(r"""["']arguments["']\s*:""")


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


def tool_result_block(name: str, payload: dict[str, Any]) -> str:
    """One framed tool result (or typed error), the unit a result message is made of."""
    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    return f"{TOOL_RESULT_PREFIX}{name}»:\n{serialized}"


def tool_results_message(blocks: list[str]) -> dict[str, str]:
    """One user message carrying every result of a reply, so roles keep alternating.

    The several results of one assistant reply travel together: the budget trim then
    drops the reply and all of its results as a unit and never splits the group.
    """
    return {"role": "user", "content": "\n\n".join(blocks)}


def tool_result_message(name: str, payload: dict[str, Any]) -> dict[str, str]:
    """The data message that carries one tool result (or a typed error) to the model."""
    return tool_results_message([tool_result_block(name, payload)])
