"""Unit tests for AI scouting report generation and retrieval routes (/reports)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from delphos_backend.services.llm_client import CompletionResult, InferenceTimeout, TokenUsage
from delphos_backend.services.report_prompt import PROMPT_VERSION

_DRAFT = {
    "dictamen_financiero": {
        "headline": "Margen favorable.",
        "body": "Cotiza {market_value_eur} frente a {fair_value_eur}.",
    },
    "rendimiento": {
        "headline": "Temporada sólida.",
        "body": "Autor de {goals} goles en {minutes} minutos.",
    },
    "alternativas": {
        "headline": "Sin alternativas cualificadas.",
        "body": "Perfil {cluster_id} con {qualifying_count} pares.",
        "candidatos": [],
    },
}


def _completion(content: str) -> CompletionResult:
    """A fake structured completion as llm_client would return it."""
    return CompletionResult(
        content=content,
        reasoning_content=None,
        usage=TokenUsage(),
        timings=None,
        model="qwen/qwen3.5-9b",
    )


def _stored_insert(cur: AsyncMock) -> object:
    """The single INSERT into app.reports the route executed."""
    matches = [
        call for call in cur.execute.call_args_list if "INSERT INTO app.reports" in call.args[0]
    ]
    assert len(matches) == 1, "expected exactly one INSERT into app.reports"
    return matches[0]


@pytest.mark.asyncio
async def test_generate_report_returns_cached_when_available(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        {
            "id": 7,
            "player_id": 100,
            "player_name": "Lionel Messi",
            "model_run_id": "run_test_001",
            "report_type": "scouting",
            "content": "Cached scouting report for Lionel Messi.",
            "created_at": datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
        },
    ]

    response = await client.post("/reports/generate", json={"player_id": 100})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 7
    assert data["player_name"] == "Lionel Messi"
    assert data["content"] == "Cached scouting report for Lionel Messi."


@pytest.mark.asyncio
async def test_generate_report_calls_llm_and_persists(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    # 1. active run
    # 2. cached report -> None
    # 3. get_player_profile
    # 4. get_player_valuation
    # 5. get_player_replacements (target)
    # 6. save_report INSERT RETURNING
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        None,
        {
            "model_run_id": "run_test_001",
            "player_id": 100,
            "name": "Lionel Messi",
            "first_name": "Lionel",
            "last_name": "Messi",
            "player_code": "lionel-messi",
            "country_of_citizenship": "Argentina",
            "date_of_birth": "1987-06-24",
            "position": "Attack",
            "sub_position": "Right Winger",
            "foot": "left",
            "height_in_cm": 170,
            "club_id": 1,
            "club_name": "Inter Miami",
            "image_url": "http://img.png",
            "url": "http://tm.de/messi",
            "cluster_id": 0,
            "season": 2025,
            "as_of_date": "2025-06-01",
            "league_id": "ES1",
            "minutes": 1800.0,
            "apps": 20.0,
            "starts": 20.0,
            "goals": 15.0,
            "assists": 12.0,
            "yellow_cards": 1.0,
            "red_cards": 0.0,
            "starter_ratio": 1.0,
            "win_rate": 0.75,
            "clean_sheet_rate": 0.3,
            "goals_conceded_per_match": 1.0,
            "league_position": 1.0,
            "age": 37.0,
        },
        {
            "player_id": 100,
            "name": "Lionel Messi",
            "model_run_id": "run_test_001",
            "season": 2025,
            "market_value_eur": 25000000.0,
            "fair_value_eur": 45000000.0,
            "residual_log10": 0.255,
            "valuation_status": "undervalued",
            "is_undervalued": True,
            "rf_undervalued_prob": 0.82,
            "dt_undervalued_pred": True,
            "rf_undervalued_pred": True,
        },
        {
            "target_player_id": 100,
            "target_name": "Lionel Messi",
            "model_run_id": "run_test_001",
            "season": 2025,
            "is_elite_asset": True,
            "target_market_value_eur": 25000000.0,
            "qualifying_count": 0,
            "shortfall_reason": "no_peer_below_cost_ceiling",
        },
        {
            "id": 8,
            "player_id": 100,
            "model_run_id": "run_test_001",
            "report_type": "scouting",
            "content": "Generated executive scouting report.",
            "created_at": datetime(2026, 11, 7, 12, 5, tzinfo=UTC),
        },
    ]
    cur.fetchall.return_value = []

    with patch("delphos_backend.services.llm_reports.chat_completion") as chat:
        chat.side_effect = [_completion(json.dumps(_DRAFT, ensure_ascii=False))]
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 8
    assert data["player_name"] == "Lionel Messi"
    assert data["content"] == "Generated executive scouting report."
    stored_content, source, llm_model, prompt_version = _stored_insert(cur).args[1][3:]
    assert (source, llm_model, prompt_version) == ("llm", "qwen/qwen3.5-9b", PROMPT_VERSION)
    assert "€45.0M" in stored_content  # {fair_value_eur} substituted from the fact card
    assert chat.call_count == 1
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_report_llm_unavailable_returns_deterministic_report(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        None,
        {
            "model_run_id": "run_test_001",
            "player_id": 100,
            "name": "Lionel Messi",
            "first_name": "Lionel",
            "last_name": "Messi",
            "player_code": "lionel-messi",
            "country_of_citizenship": "Argentina",
            "date_of_birth": "1987-06-24",
            "position": "Attack",
            "sub_position": "Right Winger",
            "foot": "left",
            "height_in_cm": 170,
            "club_id": 1,
            "club_name": "Inter Miami",
            "image_url": "http://img.png",
            "url": "http://tm.de/messi",
            "cluster_id": 0,
            "season": None,
        },
        {
            "player_id": 100,
            "name": "Lionel Messi",
            "model_run_id": "run_test_001",
            "season": 2025,
            "market_value_eur": 25000000.0,
            "fair_value_eur": 45000000.0,
            "residual_log10": 0.255,
            "valuation_status": "undervalued",
            "is_undervalued": True,
            "rf_undervalued_prob": 0.82,
            "dt_undervalued_pred": True,
            "rf_undervalued_pred": True,
        },
        None,
        {
            "id": 9,
            "player_id": 100,
            "model_run_id": "run_test_001",
            "report_type": "scouting",
            "content": "Deterministic scouting report.",
            "created_at": datetime(2026, 11, 7, 12, 5, tzinfo=UTC),
            "source": "deterministic",
            "llm_model": None,
            "prompt_version": None,
        },
    ]

    with patch("delphos_backend.services.llm_reports.chat_completion") as chat:
        chat.side_effect = InferenceTimeout("timed out after 120s")
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "deterministic"
    assert data["llm_model"] is None
    assert data["prompt_version"] is None
    stored_content, source, llm_model, prompt_version = _stored_insert(cur).args[1][3:]
    assert (source, llm_model, prompt_version) == ("deterministic", None, None)
    assert stored_content.startswith("<p><strong>Dictamen Financiero:</strong>")
    assert chat.call_count == 1


@pytest.mark.asyncio
async def test_list_and_get_reports(client: AsyncClient, mock_db: AsyncMock) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        None,
    ]
    cur.fetchall.return_value = [
        {
            "id": 1,
            "player_id": 100,
            "player_name": "Lionel Messi",
            "model_run_id": "run_test_001",
            "report_type": "scouting",
            "content": "Report text.",
            "created_at": datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
        }
    ]

    res_list = await client.get("/reports?player_id=100")
    assert res_list.status_code == 200
    assert res_list.json()["total"] == 1

    res_missing = await client.get("/reports/999")
    assert res_missing.status_code == 404
    assert res_missing.json()["detail"] == "Report not found"
