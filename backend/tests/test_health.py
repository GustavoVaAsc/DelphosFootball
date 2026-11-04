"""Unit tests for /health/live and /health/ready probes."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_live(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


@pytest.mark.asyncio
async def test_health_ready_with_active_run(client: AsyncClient, mock_db: AsyncMock) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.return_value = {
        "model_run_id": "run_20261104_010203",
        "dataset_version": 679,
        "activated_at": "2026-11-04T02:30:00Z",
    }

    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["active_model_run_id"] == "run_20261104_010203"
    assert data["dataset_version"] == 679


@pytest.mark.asyncio
async def test_health_ready_without_active_run(client: AsyncClient, mock_db: AsyncMock) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.return_value = None

    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert "No active model run" in response.json()["detail"]


@pytest.mark.asyncio
async def test_health_ready_db_failure(client: AsyncClient, mock_db: AsyncMock) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.execute.side_effect = RuntimeError("Connection severed")

    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert "Database connection failure" in response.json()["detail"]
