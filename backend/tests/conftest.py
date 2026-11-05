"""Pytest fixtures for DelphosFootball backend testing."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from delphos_backend.core.db import get_db
from delphos_backend.main import app


@pytest.fixture(autouse=True)
def mock_pool_lifecycle(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the connection pool lifecycle to run unit tests offline."""
    if "live_db" in request.keywords or "test_live_integration" in request.node.nodeid:
        return
    monkeypatch.setattr("delphos_backend.main.init_db_pool", AsyncMock())
    monkeypatch.setattr("delphos_backend.main.close_db_pool", AsyncMock())


@pytest.fixture
def mock_db() -> MagicMock:
    """Mock psycopg AsyncConnection and cursor for isolated route testing."""
    conn = MagicMock()
    cur = AsyncMock()

    cursor_ctx = MagicMock()
    cursor_ctx.__aenter__ = AsyncMock(return_value=cur)
    cursor_ctx.__aexit__ = AsyncMock(return_value=None)
    conn.cursor.return_value = cursor_ctx

    return conn


@pytest_asyncio.fixture
async def client(mock_db: MagicMock) -> AsyncGenerator[AsyncClient]:
    """Async HTTP test client with database dependency override."""

    async def override_get_db() -> AsyncGenerator[MagicMock]:
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
