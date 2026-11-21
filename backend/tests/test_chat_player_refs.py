"""Unit tests for deterministic chat player extraction and hydration."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from delphos_backend.repositories.chat_players import (
    get_chat_players_by_ids,
    hydrate_chat_players,
)
from delphos_backend.services.chat_player_refs import extract_referenced_player_ids
from delphos_backend.services.chat_tool_describe import remember_player_names


def test_extracts_full_names_in_mention_order_with_accent_folding() -> None:
    seen = {10: "Lamine Yamal", 20: "Pau Cubarsí", 30: "Pedri"}
    answer = (
        "Los dos mejores perfiles son **Cubarsi** y Lamine Yamal; "
        "aunque no aparecen otros extremos."
    )

    assert extract_referenced_player_ids(answer, seen) == [20, 10]


def test_surname_fallback_requires_turn_uniqueness_and_word_boundaries() -> None:
    seen = {
        1: "Lisandro Martínez",
        2: "Lautaro Martínez",
        3: "Harry Kane",
        4: "Rodrigo Hernández",
    }
    answer = "Arkane y Martínez son interesantes, pero **Harry Kane** lidera."

    assert extract_referenced_player_ids(answer, seen) == [3]


def test_caps_at_limit_and_skips_short_surnames() -> None:
    seen = {i: f"Jugador Ejemplo{i}" for i in range(1, 8)}
    seen[99] = "Jugador Li"
    answer = "Li destaca? No. " + " ".join(f"Jugador Ejemplo{i}" for i in range(7, 0, -1))

    assert extract_referenced_player_ids(answer, seen) == [7, 6, 5, 4, 3]


def test_remember_player_names_records_replacement_targets_and_candidates() -> None:
    seen: dict[int, str] = {}
    remember_player_names(
        {
            "found": True,
            "target_player_id": 100,
            "target_name": "Harry Kane",
            "replacements": [
                {"candidate_player_id": 201, "candidate_name": "Viktor Gyökeres"},
                {"candidate_player_id": 202, "candidate_name": "Benjamin Šeško"},
            ],
        },
        seen,
    )

    assert seen == {100: "Harry Kane", 201: "Viktor Gyökeres", 202: "Benjamin Šeško"}


@pytest.mark.asyncio
async def test_get_chat_players_by_ids_short_circuits_without_cursor(mock_db: MagicMock) -> None:
    assert await get_chat_players_by_ids(mock_db, "run_1", []) == {}
    assert await hydrate_chat_players(mock_db, "run_1", [-1, 0]) == []
    mock_db.cursor.assert_not_called()


@pytest.mark.asyncio
async def test_hydrate_chat_players_preserves_order_and_builds_crest_url(
    mock_db: MagicMock,
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchall.return_value = [
        {
            "player_id": 20,
            "name": "Pau Cubarsí",
            "position": "Defender",
            "sub_position": "Centre-Back",
            "country": "Spain",
            "image_url": "https://img.a.akamaihd.net/portrait/20.jpg",
            "club_id": 131,
            "league_id": "ES1",
            "club_name": "FC Barcelona",
            "market_value_eur": 70000000.0,
            "fair_value_eur": 95000000.0,
            "valuation_status": "undervalued",
        },
        {
            "player_id": 10,
            "name": "Harry Kane",
            "position": "Attack",
            "sub_position": "Centre-Forward",
            "country": "England",
            "image_url": "https://img.a.akamaihd.net/portrait/10.jpg",
            "club_id": 27,
            "league_id": "L1",
            "club_name": "Bayern Munich",
            "market_value_eur": 90000000.0,
            "fair_value_eur": 120000000.0,
            "valuation_status": "undervalued",
        },
    ]

    players = await hydrate_chat_players(mock_db, "run_1", [10, 20, 10])

    assert [p["player_id"] for p in players] == [10, 20]
    assert players[0]["club_logo_url"] == "https://tmssl.akamaized.net/images/wappen/head/27.png"
    assert players[1]["country"] == "Spain"
    assert players[1]["league_id"] == "ES1"
