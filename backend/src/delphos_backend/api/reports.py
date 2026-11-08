"""API route handlers for AI-generated scouting reports (/reports).

Input: ReportGenerateRequest or query filters for saved reports.
Output: ReportResponse and ReportListResponse payloads.
Responsibility: Orchestrates context lookup, local LLM generation, and app.reports persistence.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import AsyncConnection

from delphos_backend.core.db import get_db
from delphos_backend.repositories.active_run import get_active_model_run
from delphos_backend.repositories.players import get_player_profile, get_player_valuation
from delphos_backend.repositories.replacements import get_player_replacements
from delphos_backend.repositories.reports import (
    get_latest_player_report,
    get_report_by_id,
    list_reports,
    save_report,
)
from delphos_backend.schemas.reports import (
    ReportGenerateRequest,
    ReportListResponse,
    ReportResponse,
)
from delphos_backend.services.llm_reports import (
    assemble_player_scouting_context,
    generate_llm_report_text,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


async def _resolve_active_run_id(conn: AsyncConnection) -> str:
    active_run = await get_active_model_run(conn)
    if not active_run:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No active model run published in database",
        )
    return active_run["model_run_id"]


@router.post(
    "/generate",
    response_model=ReportResponse,
    summary="Generate or retrieve an AI scouting report for a player",
)
async def generate_report(
    body: ReportGenerateRequest,
    conn: Annotated[AsyncConnection, Depends(get_db)],
) -> ReportResponse:
    """Generate a natural-language scouting report using the local GGUF inference service."""
    run_id = await _resolve_active_run_id(conn)

    if not body.force_regenerate:
        cached = await get_latest_player_report(conn, body.player_id, run_id, body.report_type)
        if cached:
            return ReportResponse(**cached)

    profile = await get_player_profile(conn, run_id, body.player_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found",
        )

    valuation = await get_player_valuation(conn, run_id, body.player_id)
    if not valuation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Valuation not found for player in active season",
        )

    replacements = await get_player_replacements(conn, run_id, body.player_id)
    context_payload = assemble_player_scouting_context(profile, valuation, replacements)
    content = await generate_llm_report_text(context_payload)

    saved = await save_report(
        conn,
        player_id=body.player_id,
        model_run_id=run_id,
        content=content,
        report_type=body.report_type,
        player_name=profile["name"],
    )
    return ReportResponse(**saved)


@router.get("", response_model=ReportListResponse, summary="List generated scouting reports")
async def get_reports(
    conn: Annotated[AsyncConnection, Depends(get_db)],
    player_id: Annotated[int | None, Query(description="Filter by player ID")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReportListResponse:
    """Return previously generated scouting reports for the active model run."""
    run_id = await _resolve_active_run_id(conn)
    items = await list_reports(conn, run_id, player_id=player_id, limit=limit)
    return ReportListResponse(
        model_run_id=run_id,
        items=[ReportResponse(**item) for item in items],
        total=len(items),
    )


@router.get("/{report_id}", response_model=ReportResponse, summary="Get scouting report by ID")
async def get_report(
    report_id: int,
    conn: Annotated[AsyncConnection, Depends(get_db)],
) -> ReportResponse:
    """Return a single persisted scouting report by its ID."""
    await _resolve_active_run_id(conn)
    report = await get_report_by_id(conn, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    return ReportResponse(**report)
