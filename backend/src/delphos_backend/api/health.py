"""Liveness and readiness health check endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import AsyncConnection

from delphos_backend.core.db import get_db
from delphos_backend.repositories.active_run import get_active_model_run
from delphos_backend.schemas.health import LiveResponse, ReadyResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", response_model=LiveResponse, summary="Process liveness probe")
async def liveness() -> LiveResponse:
    """Return HTTP 200 indicating that the backend process is running."""
    return LiveResponse(status="live")


@router.get("/ready", response_model=ReadyResponse, summary="Dependency readiness probe")
async def readiness(conn: Annotated[AsyncConnection, Depends(get_db)]) -> ReadyResponse:
    """Verify that PostgreSQL is reachable and an active model run is available."""
    try:
        active_run = await get_active_model_run(conn)
    except Exception as exc:
        logger.error("Readiness probe database query failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failure",
        ) from exc

    if not active_run:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No active model run published in database",
        )

    return ReadyResponse(
        status="ready",
        active_model_run_id=active_run["model_run_id"],
        dataset_version=active_run["dataset_version"],
        activated_at=active_run["activated_at"],
    )

