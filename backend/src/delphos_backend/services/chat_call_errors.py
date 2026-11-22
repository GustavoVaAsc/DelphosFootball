"""The typed error that tells the model why its tool call could not be read.

Input: the reason code chat_call_parse reports for a broken call.
Output: an {"error": {...}} payload that names what was detected and shows the format.
Responsibility: replace one generic complaint with a specific, retryable message. The
payload goes only to the model and never echoes the model's own text: it carries
fixed Spanish sentences and the numeric call cap, nothing taken from the reply.
"""

from __future__ import annotations

from typing import Any

from delphos_backend.services.chat_call_parse import (
    INVALID_JSON,
    MAX_CALLS_PER_REPLY,
    MIXED_TEXT,
    NO_TOOL_KEY,
    TOO_MANY_CALLS,
)

EXPECTED_FORMAT = (
    'una llamada: {"tool": "<nombre>", "arguments": {...}}; varias llamadas: un objeto '
    f"JSON por línea, sin texto alrededor (máximo {MAX_CALLS_PER_REPLY})"
)
_DETECTED = {
    INVALID_JSON: "el JSON es inválido o está truncado",
    MIXED_TEXT: "hay texto mezclado con la llamada; responde solo con el JSON",
    TOO_MANY_CALLS: f"hay demasiadas llamadas en una respuesta (máximo {MAX_CALLS_PER_REPLY})",
    NO_TOOL_KEY: 'falta la clave "tool" con el nombre de la herramienta en algún objeto',
}


def malformed_call_error(reason: str | None) -> dict[str, Any]:
    """The error payload for a reply that looked like a tool call but was not readable."""
    detected = _DETECTED.get(reason or "", _DETECTED[INVALID_JSON])
    return {
        "error": {
            "tool": "llamada",
            "message": f"llamada a herramienta mal formada: {detected}",
            "expected": EXPECTED_FORMAT,
        }
    }
