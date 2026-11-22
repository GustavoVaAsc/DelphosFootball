"""The unit of progress the chat tool loop emits.

Input: an event type and its JSON-ready data.
Output: the frozen ChatEvent value.
Responsibility: own the event type alone, so the loop (chat_agent) and the tool runner
(chat_call_run) share it without importing each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChatEvent:
    """One unit of turn progress: "tool_start" and "tool" while working, "message" last."""

    type: str
    data: dict[str, Any]
