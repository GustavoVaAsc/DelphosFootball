"""FastAPI application factory, lifespan management, and router configuration.

Input: Settings, connection pool, and route modules.
Output: ASGI application instance.
Responsibility: Exposes the DelphosFootball REST API.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from delphos_backend.api import clusters, health, players, reports
from delphos_backend.core.config import get_settings
from delphos_backend.core.db import close_db_pool, init_db_pool
from delphos_backend.schemas.errors import ProblemDetails

logger = logging.getLogger(__name__)

HTTP_TITLES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "Bad Request",
    status.HTTP_404_NOT_FOUND: "Not Found",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "Unprocessable Content",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal Server Error",
    status.HTTP_503_SERVICE_UNAVAILABLE: "Service Unavailable",
}


async def problem_details_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Format exceptions as RFC 9457 problem details."""
    title = HTTP_TITLES.get(exc.status_code, "Error")
    problem = ProblemDetails(
        type="about:blank",
        title=title,
        status=exc.status_code,
        detail=str(exc.detail),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application startup and shutdown lifecycle hooks."""
    logger.info("Starting DelphosFootball FastAPI backend...")
    await init_db_pool()
    yield
    logger.info("Shutting down DelphosFootball FastAPI backend...")
    await close_db_pool()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title="DelphosFootball API",
        version="0.1.0",
        description="REST backend for undervalued player detection and tactical scouting",
        lifespan=lifespan,
    )

    # Configure CORS middleware for Flutter Web client
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register RFC 9457 error handler
    app.add_exception_handler(HTTPException, problem_details_handler)

    # Register API routers
    app.include_router(health.router)
    app.include_router(players.router)
    app.include_router(clusters.router)
    app.include_router(reports.router)

    return app


app = create_app()
