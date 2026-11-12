"""Pydantic schemas for player search, profiles, and valuations."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class PlayerSummary(BaseModel):
    """Compact player item returned in list and search results."""

    player_id: int
    name: str
    first_name: str | None = None
    last_name: str
    position: str
    sub_position: str | None = None
    country_of_citizenship: str | None = None
    club_id: int | None = None
    club_name: str | None = None
    club_logo_url: str | None = None
    market_value_eur: float | None = None
    fair_value_eur: float | None = None
    valuation_status: str | None = None
    age: float | None = None
    cluster_id: int | None = None
    cluster_name: str | None = None
    image_url: str | None = None


class PlayerListResponse(BaseModel):
    """Paginated list of players."""

    model_run_id: str
    items: list[PlayerSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class PlayerSeasonMetrics(BaseModel):
    """Active season performance and volume metrics."""

    season: int
    as_of_date: date
    league_id: str
    minutes: float
    apps: float
    starts: float
    goals: float
    assists: float
    yellow_cards: float
    red_cards: float
    starter_ratio: float
    win_rate: float
    clean_sheet_rate: float
    goals_conceded_per_match: float
    league_position: float | None = None
    age: float


class PlayerProfileResponse(BaseModel):
    """Comprehensive player biography and season performance."""

    model_run_id: str
    player_id: int
    name: str
    first_name: str | None = None
    last_name: str
    player_code: str
    country_of_citizenship: str | None = None
    date_of_birth: date
    position: str
    sub_position: str | None = None
    foot: str | None = None
    height_in_cm: int | None = None
    club_id: int | None = None
    club_name: str | None = None
    club_logo_url: str | None = None
    image_url: str | None = None
    url: str
    cluster_id: int | None = None
    cluster_name: str | None = None
    active_season: PlayerSeasonMetrics | None = None


class PlayerValuationResponse(BaseModel):
    """Model predictions and valuation diagnostic for a player."""

    player_id: int
    name: str
    model_run_id: str
    season: int
    market_value_eur: float
    fair_value_eur: float
    residual_log10: float
    valuation_status: str = Field(description="undervalued, overvalued, or fair")
    is_undervalued: bool
    rf_undervalued_prob: float
    dt_undervalued_pred: bool
    rf_undervalued_pred: bool
