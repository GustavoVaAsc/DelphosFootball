"""Fact-cell constructors for the scouting report card (LLM_PLAN §8.1).

Input: one raw value, or one replacement-payload item. Output: the `{"value",
"display"}` cell(s) of the fact card. Responsibility: pair every raw value with its
pre-formatted display string — `N/D` for missing values, Spanish copy for boolean
flags and shortfall codes — so `report_facts` reads as a list of the card's schema.

These constructors are a group of small related functions: one file each would
scatter the card's display rules, while inlining them in `report_facts` would push
that module far past the 130-line cap of backend/AGENTS.md §4, so they share this
module. The role label resolution lives here too: the role is a card cell like the
others, and it must not resolve differently from the position cells.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from delphos_domain import (
    POSITION_LABELS,
    SUB_POSITION_LABELS,
    resolve_cluster_label,
    resolve_valuation_label,
)

from delphos_backend.services.report_format import (
    format_count,
    format_eur_m,
    format_pct,
    format_ratio,
    js_round,
)

_NOT_AVAILABLE = "N/D"
_NO_CANDIDATE_SHORTFALL = "ningún candidato cualificado en los datos disponibles"

# Neutral Spanish placeholders for a position the vocabulary does not manage: the
# model must never read unmanaged English ("Wingback") in the card it is given.
UNKNOWN_POSITION_LABEL = "Posición Desconocida"
UNKNOWN_SUB_POSITION_LABEL = "Subposición Desconocida"

# Spanish fragment per `classify_shortfall` bottleneck code
# (ml/src/delphos_ml/evaluation/_calibration.py:70-85). Unknown codes fall back so
# a snake_case code can never leak into the prose.
_SHORTFALL_PHRASES = {
    "no_same_cluster_and_position_peer": "no hay pares del mismo perfil táctico",
    "no_peer_within_athletic_distance": "no hay pares con similitud atlética suficiente",
    "no_peer_below_cost_ceiling": "no hay pares por debajo del techo de precio",
    "no_non_overvalued_peer": "todos los pares disponibles están sobrevalorados",
    "fewer_than_three_qualifying_peers": "hay menos de tres pares cualificados",
}


def fact_entry(value: Any, display_of: Callable[[Any], Any] = str) -> dict[str, Any]:
    """One fact cell: raw value plus display string, `N/D` when the value is absent."""
    if value is None:
        return {"value": None, "display": _NOT_AVAILABLE}
    return {"value": value, "display": str(display_of(value))}


def flag_entry(value: Any) -> dict[str, Any]:
    """A boolean cell rendered as the Spanish `Sí`/`No`."""
    if value is None:
        return {"value": None, "display": _NOT_AVAILABLE}
    return {"value": bool(value), "display": "Sí" if value else "No"}


def points_entry(value: int | None) -> dict[str, Any]:
    """An already-percentage integer (margin points, discount points) as `80%`."""
    if value is None:
        return {"value": None, "display": _NOT_AVAILABLE}
    return {"value": int(value), "display": f"{int(value)}%"}


def shortfall_entry(value: Any) -> dict[str, Any]:
    """The bottleneck code with a quotable Spanish fragment as its display string."""
    if value is None:
        return {"value": None, "display": _NO_CANDIDATE_SHORTFALL}
    return {"value": value, "display": _SHORTFALL_PHRASES.get(value, _NO_CANDIDATE_SHORTFALL)}


def cluster_short_label(cluster_id: Any) -> Any:
    """The cluster's short Spanish name, or the raw id when the cluster is unknown."""
    resolved = resolve_cluster_label(cluster_id)
    return resolved[0] if isinstance(resolved, tuple) else resolved


def resolve_role_label(position: str | None, sub_position: str | None) -> str:
    """The role the report prints, resolved like the design preview's chain.

    The preview prefers the sub-position, then the position; a position the
    vocabulary does not manage falls back to the neutral Spanish placeholder.
    """
    if sub_position and (label := SUB_POSITION_LABELS.get(sub_position)):
        return label
    if position and (label := POSITION_LABELS.get(position)):
        return label
    return UNKNOWN_POSITION_LABEL


def role_entry(position: str | None, sub_position: str | None) -> dict[str, Any]:
    """One role cell: the database's position text and the Spanish role label.

    The label resolves from the sub-position first, so a player whose `position`
    is NULL still gets the role their sub-position names.
    """
    return {
        "value": sub_position or position,
        "display": resolve_role_label(position, sub_position),
    }


def replacement_entry(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """One candidate's cells plus the derived discount the renderer prints as `-N%`."""
    ratio = item.get("cost_ratio")
    discount = None if ratio is None else js_round((1.0 - ratio) * 100)
    return {
        "rank": fact_entry(item.get("rank"), format_count),
        "candidate_name": fact_entry(item.get("candidate_name")),
        "candidate_club_name": fact_entry(item.get("candidate_club_name")),
        "similarity_score": fact_entry(item.get("similarity_score"), format_pct),
        "candidate_market_value_eur": fact_entry(
            item.get("candidate_market_value_eur"), format_eur_m
        ),
        "cost_savings_eur": fact_entry(item.get("cost_savings_eur"), format_eur_m),
        "cost_ratio": fact_entry(ratio, format_ratio),
        "cost_discount_pct": points_entry(discount),
        "candidate_valuation_status": fact_entry(
            item.get("candidate_valuation_status"), resolve_valuation_label
        ),
    }
