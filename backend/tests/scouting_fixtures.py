"""Shared raw fixtures for the fact-card and deterministic-renderer tests.

The dicts mirror the shapes `llm_reports.assemble_player_scouting_context` reads:
a player profile with `active_season`, a valuation payload, and a replacements
payload, so one fixture player drives both the fact-card and the golden-renderer
tests.
"""

from __future__ import annotations

from typing import Any


def profile(**overrides: Any) -> dict[str, Any]:
    """Player profile for Lionel Messi at Inter Miami (positive-verdict fixture)."""
    base: dict[str, Any] = {
        "player_id": 100,
        "name": "Lionel Messi",
        "position": "Attack",
        "sub_position": "Right Winger",
        "club_name": "Inter Miami",
        "cluster_id": 0,
        "active_season": {
            "league_id": "ES1",
            "minutes": 1800.0,
            "apps": 20.0,
            "starts": 20.0,
            "goals": 15.0,
            "assists": 12.0,
            "win_rate": 0.75,
            "clean_sheet_rate": 0.3,
            "starter_ratio": 1.0,
            "age": 37.0,
        },
    }
    base.update(overrides)
    return base


def valuation(**overrides: Any) -> dict[str, Any]:
    """Valuation payload with a €20M margin over market value by default."""
    base: dict[str, Any] = {
        "model_run_id": "run_test_001",
        "season": 2025,
        "market_value_eur": 25_000_000.0,
        "fair_value_eur": 45_000_000.0,
        "residual_log10": 0.255,
        "valuation_status": "undervalued",
        "is_undervalued": True,
        "rf_undervalued_prob": 0.82,
        "rf_undervalued_pred": True,
        "dt_undervalued_pred": True,
    }
    base.update(overrides)
    return base


def replacements(**overrides: Any) -> dict[str, Any]:
    """Two qualifying replacement candidates (the multi-replacement fixture)."""
    base: dict[str, Any] = {
        "target_player_id": 100,
        "model_run_id": "run_test_001",
        "season": 2025,
        "is_elite_asset": False,
        "qualifying_count": 2,
        "shortfall_reason": None,
        "replacements": [
            {
                "rank": 1,
                "candidate_name": "Jonathan David",
                "candidate_club_name": "LOSC Lille",
                "similarity_score": 0.87,
                "candidate_market_value_eur": 21_000_000.0,
                "cost_savings_eur": 4_000_000.0,
                "cost_ratio": 0.84,
                "candidate_valuation_status": "undervalued",
            },
            {
                "rank": 2,
                "candidate_name": "Serhou Guirassy",
                "candidate_club_name": "Borussia Dortmund",
                "similarity_score": 0.81,
                "candidate_market_value_eur": 18_000_000.0,
                "cost_savings_eur": 3_500_000.0,
                "cost_ratio": 0.78,
                "candidate_valuation_status": "fair",
            },
        ],
    }
    base.update(overrides)
    return base
