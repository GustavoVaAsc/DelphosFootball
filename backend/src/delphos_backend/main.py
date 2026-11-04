"""FastAPI application factory, lifespan management, and router configuration.

Input: Settings, connection pool, and route modules.
Output: ASGI application instance.
Responsibility: Exposes the DelphosFootball REST API.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from delphos_backend.api import clusters, health, players
from delphos_backend.core.config import get_settings
from delphos_backend.core.db import close_db_pool, init_db_pool

logger = logging.getLogger(__name__)


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

    # Configure CORS middleware for Flutter web/mobile clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    app.include_router(health.router)
    app.include_router(players.router)
    app.include_router(clusters.router)

    return app


app = create_app()
