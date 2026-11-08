"""Pydantic request and response schemas for AI-generated scouting reports.

Input: JSON request payloads and database rows from app.reports.
Output: Validated OpenAPI schemas for /reports endpoints.
Responsibility: Defines contracts for generating and retrieving scouting reports.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReportGenerateRequest(BaseModel):
    """Request payload for POST /reports/generate."""

    player_id: int = Field(description="Target outfield player ID to analyze")
    report_type: str = Field(default="scouting", max_length=64)
    force_regenerate: bool = Field(
        default=False,
        description="If False, returns an existing report for the active model run when available",
    )


class ReportResponse(BaseModel):
    """Persisted scouting report returned by /reports endpoints."""

    id: int
    player_id: int
    player_name: str | None = None
    model_run_id: str
    report_type: str = "scouting"
    content: str
    created_at: datetime


class ReportListResponse(BaseModel):
    """Response payload for GET /reports."""

    model_run_id: str
    items: list[ReportResponse]
    total: int
