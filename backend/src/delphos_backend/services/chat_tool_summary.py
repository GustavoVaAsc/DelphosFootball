"""Client- and log-facing text derived from a chat tool call and its result.

Input: the tool name (model-controlled) and the bounded result payload.
Output: a sanitised tool name and a one-sentence Spanish summary.
Responsibility: keep model-controlled text out of log lines and out of the raw
row shapes shipped to the client. The summary describes the outcome (how many
rows, which entity) instead of serializing a database row, and the tool name
is stripped of control characters so it cannot forge a log record.
"""

from __future__ import annotations

import re
from typing import Any

MAX_TOOL_NAME_CHARS = 64
_CONTROL_CHARS = re.compile(r"[\r\n\t]")


def safe_tool_name(name: str) -> str:
    """The tool name without control characters, capped in length."""
    return _CONTROL_CHARS.sub(" ", str(name))[:MAX_TOOL_NAME_CHARS]


def summarize_tool_result(name: str, payload: dict[str, Any]) -> str:
    """Describe the tool outcome in one sentence, without a serialized row."""
    tool = safe_tool_name(name)
    error = payload.get("error")
    if isinstance(error, dict):
        message = str(error.get("message", "error desconocido"))
        return f"La herramienta «{tool}» devolvió un error: {message}."
    if payload.get("found") is False:
        return f"La herramienta «{tool}» no encontró el jugador solicitado."
    if isinstance(payload.get("players"), list):
        return f"La herramienta «{tool}» devolvió {len(payload['players'])} jugadores."
    if isinstance(payload.get("profile"), dict):
        profile = payload["profile"]
        return f"La herramienta «{tool}» devolvió el perfil de {profile.get('name', 'un jugador')}."
    if isinstance(payload.get("valuation"), dict):
        valuation = payload["valuation"]
        name_found = valuation.get("name") or valuation.get("player_id")
        return f"La herramienta «{tool}» devolvió la valoración de {name_found}."
    if isinstance(payload.get("replacements"), list):
        return f"La herramienta «{tool}» devolvió {len(payload['replacements'])} sustitutos."
    if isinstance(payload.get("clusters"), list):
        return f"La herramienta «{tool}» devolvió {len(payload['clusters'])} grupos."
    return f"La herramienta «{tool}» devolvió un resultado."
