"""Natural Spanish description of a chat tool call, built before the tool runs.

Input: the tool name and arguments (both model-controlled) and the player names
already seen in the same turn's tool results.
Output: one short Spanish sentence in the progressive form, plus the name registry.
Responsibility: give the UI a live step ("Buscando ...") without a database round
trip. The sentence is assembled from validated, typed arguments only: enum values
map to the delphos_domain labels or a fixed local map, never to the raw value; a
free-text name is stripped of control characters and structural punctuation and
length-capped; a bare player id becomes a known name or a generic phrase. Invalid
arguments and unknown tools get a generic sentence, so no tool name, argument key,
brace or snake_case identifier can reach the client through this text.
"""

from __future__ import annotations

from typing import Any

from delphos_backend.services.chat_search_describe import describe_search
from delphos_backend.services.chat_tool_args import PLAYER_ID_RANGE, int_arg
from delphos_backend.services.chat_tool_text import cluster_name, contract, safe_display_text

GENERIC_DESCRIPTION = "Consultando los datos del modelo…"
UNKNOWN_PLAYER = "el jugador seleccionado"
_PLAYER_TOOLS = {
    "get_player_profile": "Consultando el perfil de",
    "get_player_valuation": "Revisando la valoración de",
    "get_player_replacements": "Evaluando reemplazos para",
}


def remember_player_names(payload: dict[str, Any], names: dict[int, str]) -> None:
    """Record the (player_id -> name) pairs a tool result already carries."""
    rows = list(payload.get("players") or [])
    for key in ("profile", "valuation"):
        if isinstance(payload.get(key), dict):
            rows.append(payload[key])
    rows.append({"player_id": payload.get("player_id"), "name": payload.get("target_name")})
    for row in rows:
        if not isinstance(row, dict):
            continue
        player_id, name = row.get("player_id"), row.get("name")
        if isinstance(player_id, int) and isinstance(name, str) and safe_display_text(name):
            names[player_id] = safe_display_text(name)


def describe_tool_call(name: str, arguments: Any, names: dict[int, str]) -> str:
    """One Spanish sentence for the call; the generic sentence when it is not valid."""
    args = arguments if isinstance(arguments, dict) else {}
    if name == "search_players":
        return describe_search(args) or GENERIC_DESCRIPTION
    if name == "get_cluster_summary":
        return _describe_clusters(args) or GENERIC_DESCRIPTION
    if name in _PLAYER_TOOLS:
        lo, hi = PLAYER_ID_RANGE
        player_id, error = int_arg(name, "player_id", args, lo=lo, hi=hi)
        if error or player_id is None:
            return GENERIC_DESCRIPTION
        return f"{contract(_PLAYER_TOOLS[name], names.get(player_id, UNKNOWN_PLAYER))}…"
    return GENERIC_DESCRIPTION


def _describe_clusters(args: dict[str, Any]) -> str | None:
    cluster_id, error = int_arg("", "cluster_id", args, lo=0, hi=2, required=False)
    if error:
        return None
    if cluster_id is None:
        return "Consultando los arquetipos tácticos…"
    return f"Consultando el arquetipo táctico {cluster_name(cluster_id)}…"
