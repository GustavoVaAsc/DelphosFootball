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

from delphos_backend.services.chat_tool_text import safe_display_text

MAX_TOOL_NAME_CHARS = 64
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")


def safe_tool_name(name: str) -> str:
    """The tool name without control characters, capped in length."""
    return _CONTROL_CHARS.sub(" ", str(name))[:MAX_TOOL_NAME_CHARS]


def _shown(name: Any) -> str:
    """A database name cleaned by the shared display rule, or a generic phrase."""
    return safe_display_text(str(name or "")) or "el jugador solicitado"


def summarize_tool_result(name: str, payload: dict[str, Any]) -> str:
    """Describe the tool outcome in natural Spanish, without literal tool names."""
    safe_tool_name(name)
    error = payload.get("error")
    if isinstance(error, dict):
        message = str(error.get("message", "error desconocido"))
        return f"No se pudo completar un paso de la consulta: {message}."
    if payload.get("found") is False:
        return "No se encontró el jugador solicitado en el mercado."
    if isinstance(payload.get("players"), list):
        count = len(payload["players"])
        total = payload.get("total")
        if isinstance(total, int) and total > count:
            return f"Se consultaron {count} jugadores en el mercado (de {total} coincidencias)."
        return f"Se consultaron {count} jugadores en el mercado."
    if isinstance(payload.get("profile"), dict):
        profile = payload["profile"]
        player_name = _shown(profile.get("name"))
        return f"Se consultó el perfil y las estadísticas de {player_name}."
    if isinstance(payload.get("valuation"), dict):
        valuation = payload["valuation"]
        name_found = _shown(valuation.get("name"))
        return f"Se revisó la valoración y el diagnóstico de {name_found}."
    if isinstance(payload.get("replacements"), list):
        target = _shown(payload.get("target_name"))
        return (
            f"Se evaluaron {len(payload['replacements'])} candidatos de reemplazo "
            f"táctico para {target}."
        )
    if isinstance(payload.get("clusters"), list):
        return f"Se consultó el resumen de {len(payload['clusters'])} arquetipos tácticos."
    return "Paso de consulta completado."
