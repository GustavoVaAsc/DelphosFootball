"""Tests for RFC 9457 problem details on every error path, including validation.

Input: HTTP requests against the FastAPI app.
Output: assertions on status, media type, and problem body.
Responsibility: ensures request-validation failures are formatted like every
other error instead of falling back to FastAPI's default `{"detail": [...]}`
JSON body.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_unknown_report_type_returns_problem_json(client: AsyncClient) -> None:
    """A rejected report_type answers 422 as application/problem+json."""
    response = await client.post(
        "/reports/generate",
        json={"player_id": 100, "report_type": "replacement"},
    )
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == 422
    assert body["title"] == "Unprocessable Content"
    assert body["type"] == "about:blank"
    assert body["detail"]


@pytest.mark.asyncio
async def test_missing_required_field_returns_problem_json(client: AsyncClient) -> None:
    """A missing body field answers 422 as application/problem+json."""
    response = await client.post("/reports/generate", json={})
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == 422
    assert "player_id" in body["detail"]
