"""Pydantic schemas for precalculated tactical player replacements."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReplacementItem(BaseModel):
    """A ranked replacement candidate offering athletic similarity and cost savings."""

    rank: int = Field(ge=1, le=3)
    candidate_player_id: int
    candidate_name: str
    position: str
    similarity_score: float = Field(description="Normalized similarity metric [0, 1]")
    euclidean_distance: float
    candidate_market_value_eur: float
    cost_savings_eur: float
    cost_ratio: float
    candidate_fair_value_eur: float
    candidate_valuation_status: str


class TargetReplacementsResponse(BaseModel):
    """Response payload for GET /players/{id}/replacements."""

    target_player_id: int
    target_name: str
    model_run_id: str
    season: int
    is_elite_asset: bool
    target_market_value_eur: float
    qualifying_count: int
    shortfall_reason: str | None = None
    replacements: list[ReplacementItem] = Field(default_factory=list)
