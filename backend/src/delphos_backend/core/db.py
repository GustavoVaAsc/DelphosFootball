"""PostgreSQL asynchronous connection pool lifecycle and FastAPI dependency.

Input: Database connection URL from core.config.
Output: Active psycopg AsyncConnection instances.
Responsibility: Manages application-wide connection pooling and cleanup.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from delphos_backend.core.config import get_settings

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None


async def init_db_pool() -> AsyncConnectionPool:
    """Initialize the global asynchronous PostgreSQL connection pool."""
    global _pool
    if _pool is None:
        settings = get_settings()
        db_url = settings.get_database_url()
        logger.info(
            "Initializing PostgreSQL connection pool on %s:%s",
            settings.db_host,
            settings.db_port,
        )
        _pool = AsyncConnectionPool(
            conninfo=db_url,
            min_size=1,
            max_size=10,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        await _pool.open()
    return _pool


async def close_db_pool() -> None:
    """Close the global PostgreSQL connection pool gracefully."""
    global _pool
    if _pool is not None:
        logger.info("Closing PostgreSQL connection pool")
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    """Return the active connection pool or raise RuntimeError if uninitialized."""
    if _pool is None:
        raise RuntimeError("Database pool has not been initialized.")
    return _pool


async def get_db() -> AsyncGenerator[AsyncConnection]:
    """FastAPI dependency yielding an asynchronous database connection."""
    pool = get_pool()
    async with pool.connection() as conn:
        yield conn
