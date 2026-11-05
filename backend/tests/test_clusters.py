"""Unit tests for cluster archetype routes."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_clusters_success(client: AsyncClient, mock_db: AsyncMock) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.return_value = {
        "model_run_id": "run_test_001",
        "dataset_version": 679,
        "activated_at": None,
    }
    cur.fetchall.return_value = [
        {
            "cluster_id": 0,
            "player_count": 1200,
            "avg_minutes": 1850.5,
            "avg_goals": 6.5,
            "avg_assists": 4.2,
            "avg_market_value_eur": 12500000.0,
        },
        {
            "cluster_id": 1,
            "player_count": 2100,
            "avg_minutes": 1620.0,
            "avg_goals": 1.8,
            "avg_assists": 2.1,
            "avg_market_value_eur": 8200000.0,
        },
        {
            "cluster_id": 2,
            "player_count": 2222,
            "avg_minutes": 1910.0,
            "avg_goals": 0.4,
            "avg_assists": 0.6,
            "avg_market_value_eur": 6100000.0,
        },
    ]

    response = await client.get("/clusters")
    assert response.status_code == 200
    data = response.json()
    assert data["model_run_id"] == "run_test_001"
    assert len(data["clusters"]) == 3
    assert data["clusters"][0]["name"] == "Attacking Creators & Scorers"
    assert data["clusters"][0]["player_count"] == 1200
