"""The player facts of the scouting report card (LLM_PLAN §8.1).

Input: the raw player profile, valuation and replacement-payload dicts. Output: the
card's `facts` mapping — every citable fact of the evaluated player, keyed by a flat
short name and carrying its raw value and its pre-formatted display string.
Responsibility: read the three raw dicts once and pair every value with its display
string, so `report_facts` reads as the card's public surface rather than as a list of
extractions.

The key is flat (`fair_value_eur`, never `valuation.fair_value_eur`) because each
`{fact_ref}` placeholder is re-emitted per paragraph and path segments cost tokens.
Provenance ids and fields without approved Spanish vocabulary (foot, height,
citizenship, the English cluster name) are excluded, so the model never sees
unmanaged English. The model's own diagnostics (`residual_log10`, the classifier
predictions and probability) are part of the card — the deterministic renderer reads
them — but they are not citable: `report_scope` excludes them from the player scope.
"""

from __future__ import annotations

from typing import Any

from delphos_domain import (
    POSITION_LABELS,
    SUB_POSITION_LABELS,
    resolve_league_label,
    resolve_valuation_label,
)

from delphos_backend.services.report_card_cells import (
    UNKNOWN_POSITION_LABEL,
    UNKNOWN_SUB_POSITION_LABEL,
    cluster_short_label,
    fact_entry,
    flag_entry,
    points_entry,
    role_entry,
    shortfall_entry,
)
from delphos_backend.services.report_format import (
    format_count,
    format_eur_m,
    format_fixed,
    format_pct,
    js_round,
)

__all__ = ["player_facts"]


def player_facts(
    profile: dict[str, Any],
    valuation: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """The card's player facts, in the order the request lists them."""
    season_stats = profile.get("active_season") or {}

    market = valuation.get("market_value_eur")
    fair = valuation.get("fair_value_eur")
    gap: float | None = None
    gap_pct: int | None = None
    if market is not None and fair is not None and market != 0:
        gap = fair - market
        gap_pct = js_round((gap / market) * 100)

    return {
        "season": fact_entry(valuation.get("season"), format_count),
        "player_name": fact_entry(profile.get("name")),
        "role": role_entry(profile.get("position"), profile.get("sub_position")),
        "position": fact_entry(
            profile.get("position"), lambda raw: POSITION_LABELS.get(raw, UNKNOWN_POSITION_LABEL)
        ),
        "sub_position": fact_entry(
            profile.get("sub_position"),
            lambda raw: SUB_POSITION_LABELS.get(raw, UNKNOWN_SUB_POSITION_LABEL),
        ),
        "club_name": fact_entry(profile.get("club_name")),
        "cluster_id": fact_entry(profile.get("cluster_id"), cluster_short_label),
        "league_id": fact_entry(season_stats.get("league_id"), resolve_league_label),
        "age": fact_entry(season_stats.get("age"), format_count),
        "minutes": fact_entry(season_stats.get("minutes"), format_count),
        "apps": fact_entry(season_stats.get("apps"), format_count),
        "starts": fact_entry(season_stats.get("starts"), format_count),
        "starter_ratio": fact_entry(season_stats.get("starter_ratio"), format_pct),
        "goals": fact_entry(season_stats.get("goals"), format_count),
        "assists": fact_entry(season_stats.get("assists"), format_count),
        "win_rate": fact_entry(season_stats.get("win_rate"), format_pct),
        "clean_sheet_rate": fact_entry(season_stats.get("clean_sheet_rate"), format_pct),
        "market_value_eur": fact_entry(market, format_eur_m),
        "fair_value_eur": fact_entry(fair, format_eur_m),
        "value_gap_eur": fact_entry(gap, format_eur_m),
        "value_gap_pct": points_entry(gap_pct),
        "residual_log10": fact_entry(
            valuation.get("residual_log10"), lambda raw: format_fixed(raw, 2)
        ),
        "valuation_status": fact_entry(valuation.get("valuation_status"), resolve_valuation_label),
        "is_undervalued": flag_entry(valuation.get("is_undervalued")),
        "rf_undervalued_prob": fact_entry(valuation.get("rf_undervalued_prob"), format_pct),
        "rf_undervalued_pred": flag_entry(valuation.get("rf_undervalued_pred")),
        "dt_undervalued_pred": flag_entry(valuation.get("dt_undervalued_pred")),
        "qualifying_count": fact_entry(payload.get("qualifying_count", 0), format_count),
        "shortfall_reason": shortfall_entry(payload.get("shortfall_reason")),
        "is_elite_asset": flag_entry(payload.get("is_elite_asset", False)),
    }
