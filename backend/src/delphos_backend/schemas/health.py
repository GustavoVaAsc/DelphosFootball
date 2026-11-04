"""Health check response models for liveness and readiness probes.

Responsibility: Enforces OpenAPI response contracts for /health endpoints.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LiveResponse(BaseModel):
    """Response payload for GET /health/live."""

    status: str = "live"


class ReadyResponse(BaseModel):
    """Response payload for GET /health/ready."""

    status: str = "ready"
    active_model_run_id: str
    dataset_version: int
    activated_at: datetime | None = None
