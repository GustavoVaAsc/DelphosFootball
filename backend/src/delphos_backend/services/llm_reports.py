"""Context assembly and HTTP client for local llama.cpp scouting report generation.

Input: Player profile, valuation diagnostics, and replacement candidates.
Output: Natural-language scouting report string from the local GGUF inference service.
Responsibility: Grounded context serialization and bounded OpenAI-compatible HTTP calls.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

from delphos_backend.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# TODO(Gustavo): Replace this placeholder with the scouting report writing rules / skill prompt.
DEFAULT_SYSTEM_PROMPT = "You are a football scouting analyst for DelphosFootball."


def assemble_player_scouting_context(
    profile: dict[str, Any],
    valuation: dict[str, Any],
    replacements: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assemble grounded KDD metrics for the target player into a compact JSON-serializable dict."""
    season_stats = profile.get("active_season") or {}
    rep_items = (replacements or {}).get("replacements") or []
    return {
        "model_run_id": valuation["model_run_id"],
        "season": valuation["season"],
        "player": {
            "player_id": profile["player_id"],
            "name": profile["name"],
            "position": profile["position"],
            "sub_position": profile.get("sub_position"),
            "country_of_citizenship": profile.get("country_of_citizenship"),
            "club_name": profile.get("club_name"),
            "age": season_stats.get("age"),
            "height_in_cm": profile.get("height_in_cm"),
            "foot": profile.get("foot"),
            "cluster_id": profile.get("cluster_id"),
            "cluster_name": profile.get("cluster_name"),
        },
        "performance_2025": {
            "league_id": season_stats.get("league_id"),
            "minutes": season_stats.get("minutes"),
            "apps": season_stats.get("apps"),
            "starts": season_stats.get("starts"),
            "starter_ratio": season_stats.get("starter_ratio"),
            "goals": season_stats.get("goals"),
            "assists": season_stats.get("assists"),
            "win_rate": season_stats.get("win_rate"),
            "clean_sheet_rate": season_stats.get("clean_sheet_rate"),
        },
        "valuation": {
            "market_value_eur": valuation["market_value_eur"],
            "fair_value_eur": valuation["fair_value_eur"],
            "residual_log10": valuation["residual_log10"],
            "valuation_status": valuation["valuation_status"],
            "is_undervalued": valuation["is_undervalued"],
            "rf_undervalued_prob": valuation["rf_undervalued_prob"],
            "rf_undervalued_pred": valuation["rf_undervalued_pred"],
            "dt_undervalued_pred": valuation["dt_undervalued_pred"],
        },
        "replacement_analysis": {
            "is_elite_asset": (replacements or {}).get("is_elite_asset", False),
            "qualifying_count": (replacements or {}).get("qualifying_count", 0),
            "shortfall_reason": (replacements or {}).get("shortfall_reason"),
            "candidates": [
                {
                    "rank": item["rank"],
                    "candidate_name": item["candidate_name"],
                    "candidate_club_name": item.get("candidate_club_name"),
                    "similarity_score": item["similarity_score"],
                    "candidate_market_value_eur": item["candidate_market_value_eur"],
                    "cost_savings_eur": item["cost_savings_eur"],
                    "cost_ratio": item["cost_ratio"],
                    "candidate_valuation_status": item["candidate_valuation_status"],
                }
                for item in rep_items
            ],
        },
    }


async def generate_llm_report_text(
    context_payload: dict[str, Any],
    settings: Settings | None = None,
) -> str:
    """Call the local llama.cpp OpenAI-compatible server to draft a scouting report."""
    cfg = settings or get_settings()
    endpoint = f"{cfg.llm_api_url.rstrip('/')}/chat/completions"
    request_body = {
        "model": cfg.llm_model_name,
        "messages": [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context_payload, default=str)},
        ],
        "max_tokens": cfg.llm_max_tokens,
        "temperature": cfg.llm_temperature,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=cfg.llm_timeout_seconds) as client:
            response = await client.post(endpoint, json=request_body)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Local LLM inference call failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM inference service unavailable",
        ) from exc

    choices = data.get("choices") or []
    content = (choices[0].get("message") or {}).get("content", "").strip() if choices else ""
    if not content:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM inference service returned an empty completion",
        )
    return content
