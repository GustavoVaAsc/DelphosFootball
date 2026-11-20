"""Natural Spanish description of a search_players call.

Input: the model-supplied search arguments (untrusted).
Output: a sentence such as "Buscando extremos izquierdos infravalorados en Ataque,
ordenados por infravaloración…", or None when any argument fails validation.
Responsibility: read like a scouting request with number and gender agreement.
Position and cluster names come from delphos_domain; the plural nouns, the
masculine plural valuation adjectives and the sort phrases are local maps because
the domain vocabulary only holds singular labels. No raw argument value is ever
echoed except a sanitised, length-capped player name.
"""

from __future__ import annotations

from typing import Any

from delphos_domain import POSITION_LABELS, SUB_POSITION_LABELS, VALUATION_STATUS_LABELS

from delphos_backend.services.chat_tool_args import enum_arg, int_arg, str_arg
from delphos_backend.services.chat_tool_text import cluster_name, safe_display_text

SORT_LABELS = {
    "market_value": "valor de mercado",
    "undervaluation": "infravaloración",
    "overvaluation": "sobrevaloración",
}
STATUS_PHRASES = {
    "undervalued": "infravalorados",
    "fair": "con valor justo",
    "overvalued": "sobrevalorados",
}
SUB_POSITION_PLURALS = {
    "Centre-Forward": "delanteros centro",
    "Right Winger": "extremos derechos",
    "Left Winger": "extremos izquierdos",
    "Second Striker": "segundos delanteros",
    "Attacking Midfield": "mediapuntas",
    "Central Midfield": "mediocentros",
    "Defensive Midfield": "pivotes defensivos",
    "Right Midfield": "interiores derechos",
    "Left Midfield": "interiores izquierdos",
    "Centre-Back": "defensas centrales",
    "Right-Back": "laterales derechos",
    "Left-Back": "laterales izquierdos",
}
_ENUMS = {
    "position": POSITION_LABELS,
    "sub_position": SUB_POSITION_LABELS,
    "valuation_status": VALUATION_STATUS_LABELS,
    "sort_by": SORT_LABELS,
}


def describe_search(args: dict[str, Any]) -> str | None:
    """The progressive-form sentence for the search, or None when arguments are invalid."""
    text, text_error = str_arg("", "name", args)
    cluster_id, cluster_error = int_arg("", "cluster_id", args, lo=0, hi=2, required=False)
    _, limit_error = int_arg("", "limit", args, lo=1, hi=10, required=False)
    if text_error or cluster_error or limit_error:
        return None
    if any(enum_arg("", key, args, labels) for key, labels in _ENUMS.items()):
        return None
    sub_position = args.get("sub_position")
    parts = ["Buscando", SUB_POSITION_PLURALS.get(sub_position, "jugadores")]
    if args.get("valuation_status"):
        parts.append(STATUS_PHRASES[args["valuation_status"]])
    if args.get("position") and not sub_position:
        parts.append(f"en {POSITION_LABELS[args['position']]}")
    if cluster_id is not None:
        parts.append(f"del arquetipo {cluster_name(cluster_id)}")
    if text and safe_display_text(text):
        parts.append(f"que coinciden con «{safe_display_text(text)}»")
    sentence = " ".join(parts)
    if args.get("sort_by"):
        sentence += f", ordenados por {SORT_LABELS[args['sort_by']]}"
    return sentence + "…"
