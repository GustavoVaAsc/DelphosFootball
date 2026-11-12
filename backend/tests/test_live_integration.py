"""Live integration tests running against the real PostgreSQL container.

These tests execute against the active model run in PostgreSQL without mocks.
If the database is unreachable, tests are safely skipped.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from delphos_backend.core.db import close_db_pool, init_db_pool
from delphos_backend.main import app


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.live_db
@pytest.mark.asyncio
async def test_live_full_api_flow() -> None:
    """Verify live database responses across all API endpoints."""
    # Check if live database is reachable; if not, skip test gracefully
    try:
        pool = await init_db_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT 1;")
    except Exception as exc:
        pytest.skip(f"Live PostgreSQL database is not reachable ({exc})")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Health probes
            res_live = await client.get("/health/live")
            assert res_live.status_code == 200
            assert res_live.json() == {"status": "live"}

            res_ready = await client.get("/health/ready")
            assert res_ready.status_code == 200
            ready_data = res_ready.json()
            assert ready_data["status"] == "ready"
            run_id = ready_data["active_model_run_id"]
            assert run_id.startswith("run_")

            # 2. Clusters
            res_clusters = await client.get("/clusters")
            assert res_clusters.status_code == 200
            clusters_data = res_clusters.json()
            assert clusters_data["model_run_id"] == run_id
            assert len(clusters_data["clusters"]) == 3
            assert clusters_data["clusters"][0]["player_count"] > 0
            assert clusters_data["as_of_date"] is not None

            # 3. Player search & filtering
            res_players = await client.get("/players?page=1&page_size=10&cluster_id=0")
            assert res_players.status_code == 200
            players_data = res_players.json()
            assert players_data["model_run_id"] == run_id
            assert players_data["total"] > 1000
            assert len(players_data["items"]) == 10
            for item in players_data["items"]:
                assert item["cluster_id"] == 0
                assert item["age"] is not None
                assert "fair_value_eur" in item
                assert item["cluster_name"] == "Attacking Creators & Scorers"

            # 4. Target player lookup (Erling Haaland, player_id=418560)
            target_id = 418560
            res_profile = await client.get(f"/players/{target_id}")
            assert res_profile.status_code == 200
            profile_data = res_profile.json()
            assert profile_data["name"] == "Erling Haaland"
            assert profile_data["model_run_id"] == run_id
            assert profile_data["active_season"]["season"] == 2025

            # 5. Valuation diagnostics
            res_val = await client.get(f"/players/{target_id}/valuation")
            assert res_val.status_code == 200
            val_data = res_val.json()
            assert val_data["model_run_id"] == run_id
            assert val_data["valuation_status"] == "overvalued"
            assert val_data["fair_value_eur"] > 0

            # 6. Tactical replacements
            res_rep = await client.get(f"/players/{target_id}/replacements")
            assert res_rep.status_code == 200
            rep_data = res_rep.json()
            assert rep_data["target_player_id"] == target_id
            assert len(rep_data["replacements"]) == 3
            for r in rep_data["replacements"]:
                assert r["cost_savings_eur"] > 0
                assert r["similarity_score"] > 0

            # 7. RFC 9457 error handling
            res_404 = await client.get("/players/99999999")
            assert res_404.status_code == 404
            assert res_404.headers["content-type"] == "application/problem+json"
            err_data = res_404.json()
            assert err_data["title"] == "Not Found"
            assert err_data["status"] == 404
            assert "Player not found" in err_data["detail"]
    finally:
        await close_db_pool()
