"""API route handlers for player search, profiles, valuations, and replacements."""

from __future__ import annotations

import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import AsyncConnection

from delphos_backend.core.db import get_db
from delphos_backend.repositories.active_run import get_active_model_run
from delphos_backend.repositories.players import (
    get_player_profile,
    get_player_valuation,
    list_players,
)
from delphos_backend.repositories.replacements import get_player_replacements
from delphos_backend.schemas.players import (
    PlayerListResponse,
    PlayerProfileResponse,
    PlayerSummary,
    PlayerValuationResponse,
)
from delphos_backend.schemas.replacements import TargetReplacementsResponse

router = APIRouter(prefix="/players", tags=["Players"])


async def _resolve_active_run_id(conn: AsyncConnection) -> str:
    active_run = await get_active_model_run(conn)
    if not active_run:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No active model run published in database",
        )
    return active_run["model_run_id"]


@router.get("", response_model=PlayerListResponse, summary="Search and list outfield players")
async def get_players(
    conn: Annotated[AsyncConnection, Depends(get_db)],
    name: Annotated[str | None, Query(description="Filter by name substring")] = None,
    position: Annotated[str | None, Query(description="Filter by position (e.g. Attack)")] = None,
    club_id: Annotated[int | None, Query(description="Filter by club ID")] = None,
    valuation_status: Annotated[
        str | None, Query(description="undervalued, overvalued, or fair")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PlayerListResponse:
    """Return paginated players with valuation badges for the active model run."""
    run_id = await _resolve_active_run_id(conn)
    items, total = await list_players(
        conn, run_id, name, position, club_id, valuation_status, page, page_size
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return PlayerListResponse(
        items=[PlayerSummary(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{player_id}",
    response_model=PlayerProfileResponse,
    summary="Get player biography and stats",
)
async def get_player(
    player_id: int,
    conn: Annotated[AsyncConnection, Depends(get_db)],
) -> PlayerProfileResponse:
    """Return biography and active-season performance metrics for a player."""
    run_id = await _resolve_active_run_id(conn)
    profile = await get_player_profile(conn, run_id, player_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return PlayerProfileResponse(**profile)


@router.get(
    "/{player_id}/valuation",
    response_model=PlayerValuationResponse,
    summary="Get player valuation diagnostic and predictions",
)
async def get_valuation(
    player_id: int,
    conn: Annotated[AsyncConnection, Depends(get_db)],
) -> PlayerValuationResponse:
    """Return fair value, residual, and undervaluation probability for a player."""
    run_id = await _resolve_active_run_id(conn)
    val = await get_player_valuation(conn, run_id, player_id)
    if not val:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Valuation not found for player in active season",
        )
    return PlayerValuationResponse(**val)


@router.get(
    "/{player_id}/replacements",
    response_model=TargetReplacementsResponse,
    summary="Get tactical replacement recommendations",
)
async def get_replacements(
    player_id: int,
    conn: Annotated[AsyncConnection, Depends(get_db)],
) -> TargetReplacementsResponse:
    """Return precomputed top-3 tactical replacements with cost savings."""
    run_id = await _resolve_active_run_id(conn)
    rep = await get_player_replacements(conn, run_id, player_id)
    if not rep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not evaluated as a replacement target",
        )
    return TargetReplacementsResponse(**rep)
