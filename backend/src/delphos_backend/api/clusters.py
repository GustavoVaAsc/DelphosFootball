"""API route handler for K-Means cluster tactical archetypes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import AsyncConnection

from delphos_backend.core.db import get_db
from delphos_backend.repositories.active_run import get_active_model_run
from delphos_backend.repositories.clusters import (
    ACTIVE_SEASON,
    get_clusters_as_of_date,
    get_clusters_summary,
)
from delphos_backend.schemas.clusters import ClusterArchetype, ClusterListResponse

router = APIRouter(prefix="/clusters", tags=["Clusters"])


@router.get("", response_model=ClusterListResponse, summary="List tactical cluster archetypes")
async def list_clusters(
    conn: Annotated[AsyncConnection, Depends(get_db)],
) -> ClusterListResponse:
    """Return summary profiles and averages for the 3 K-Means player archetypes."""
    active_run = await get_active_model_run(conn)
    if not active_run:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No active model run published in database",
        )

    run_id = active_run["model_run_id"]
    clusters_data = await get_clusters_summary(conn, run_id)
    as_of_date = await get_clusters_as_of_date(conn, run_id)
    return ClusterListResponse(
        model_run_id=run_id,
        season=ACTIVE_SEASON,
        as_of_date=as_of_date,
        clusters=[ClusterArchetype(**c) for c in clusters_data],
    )
