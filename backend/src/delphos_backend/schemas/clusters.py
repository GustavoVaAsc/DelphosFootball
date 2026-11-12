"""Pydantic schemas for K-Means cluster tactical archetypes."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class ClusterArchetype(BaseModel):
    """Summary metrics of a K-Means player archetype."""

    cluster_id: int
    name: str
    player_count: int
    avg_market_value_eur: float
    avg_minutes: float
    avg_goals: float
    avg_assists: float


class ClusterListResponse(BaseModel):
    """Response payload for GET /clusters."""

    model_run_id: str
    season: int
    as_of_date: date | None = None
    clusters: list[ClusterArchetype]
