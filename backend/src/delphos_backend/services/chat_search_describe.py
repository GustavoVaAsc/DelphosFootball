"""Natural Spanish description of a search_players call.

Input: the model-supplied search arguments (untrusted).
Output: a sentence such as "Buscando extremos izquierdos y extremos derechos
infravalorados de hasta 23 años, ordenados por infravaloración…", or None when any
argument fails validation.
Responsibility: read like a scouting request with number and gender agreement; several
sub-positions are joined with "y" ("a, b y c" from three).
Position and cluster names come from delphos_domain; the plural nouns, the
masculine plural valuation adjectives and the sort phrases are local maps because
the domain vocabulary only holds singular labels. No raw argument value is ever
echoed except a sanitised, length-capped player name.
"""

from __future__ import annotations

from typing import Any

from delphos_domain import POSITION_LABELS, SUB_POSITION_LABELS, VALUATION_STATUS_LABELS

from delphos_backend.services.chat_search_args import age_args, sub_positions_arg
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
    "valuation_status": VALUATION_STATUS_LABELS,
    "sort_by": SORT_LABELS,
}


def _join(items: list[str]) -> str:
    """Spanish enumeration: "a", "a y b", "a, b y c"."""
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} y {items[-1]}"


def _sub_position_noun(sub_positions: list[str] | None) -> str:
    if not sub_positions:
        return "jugadores"
    return _join([SUB_POSITION_PLURALS.get(value, "jugadores") for value in sub_positions])


def _age_phrase(min_age: int | None, max_age: int | None) -> str | None:
    if min_age is not None and max_age is not None:
        return (
            f"de {min_age} años" if min_age == max_age else f"de entre {min_age} y {max_age} años"
        )
    if max_age is not None:
        return f"de hasta {max_age} años"
    return f"de {min_age} años o más" if min_age is not None else None


def describe_search(args: dict[str, Any]) -> str | None:
    """The progressive-form sentence for the search, or None when arguments are invalid."""
    text, text_error = str_arg("", "name", args)
    cluster_id, cluster_error = int_arg("", "cluster_id", args, lo=0, hi=2, required=False)
    _, limit_error = int_arg("", "limit", args, lo=1, hi=10, required=False)
    sub_positions, sub_error = sub_positions_arg("", args, SUB_POSITION_LABELS)
    min_age, max_age, age_error = age_args("", args)
    if text_error or cluster_error or limit_error or sub_error or age_error:
        return None
    if any(enum_arg("", key, args, labels) for key, labels in _ENUMS.items()):
        return None
    parts = ["Buscando", _sub_position_noun(sub_positions)]
    if args.get("valuation_status"):
        parts.append(STATUS_PHRASES[args["valuation_status"]])
    if age := _age_phrase(min_age, max_age):
        parts.append(age)
    if args.get("position") and not sub_positions:
        parts.append(f"en {POSITION_LABELS[args['position']]}")
    if cluster_id is not None:
        parts.append(f"del arquetipo {cluster_name(cluster_id)}")
    if text and safe_display_text(text):
        parts.append(f"que coinciden con «{safe_display_text(text)}»")
    sentence = " ".join(parts)
    if args.get("sort_by"):
        sentence += f", ordenados por {SORT_LABELS[args['sort_by']]}"
    return sentence + "…"
