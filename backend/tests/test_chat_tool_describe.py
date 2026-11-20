"""Unit tests for the Spanish tool-call descriptions shown while a tool runs."""

from __future__ import annotations

import re

import pytest

from delphos_backend.services.chat_tool_describe import (
    GENERIC_DESCRIPTION,
    UNKNOWN_PLAYER,
    describe_tool_call,
    remember_player_names,
)

UNKNOWN_DE = "del jugador seleccionado"
CASES: list[tuple[str, object, str]] = [
    ("search_players", {}, "Buscando jugadores…"),
    ("search_players", {"limit": 3}, "Buscando jugadores…"),
    ("search_players", {"position": "Attack"}, "Buscando jugadores en Ataque…"),
    ("search_players", {"valuation_status": "undervalued"}, "Buscando jugadores infravalorados…"),
    ("search_players", {"valuation_status": "fair"}, "Buscando jugadores con valor justo…"),
    ("search_players", {"valuation_status": "overvalued"}, "Buscando jugadores sobrevalorados…"),
    (
        "search_players",
        {"sub_position": "Left Winger", "valuation_status": "overvalued"},
        "Buscando extremos izquierdos sobrevalorados…",
    ),
    (
        "search_players",
        {"position": "Attack", "valuation_status": "undervalued", "sort_by": "undervaluation"},
        "Buscando jugadores infravalorados en Ataque, ordenados por infravaloración…",
    ),
    (
        "search_players",
        {
            "sub_position": "Centre-Back",
            "valuation_status": "fair",
            "cluster_id": 2,
            "sort_by": "market_value",
        },
        "Buscando defensas centrales con valor justo del arquetipo Ancla Defensiva, "
        "ordenados por valor de mercado…",
    ),
    (
        "search_players",
        {"position": "Midfield", "cluster_id": 1, "name": "Mbappé", "sort_by": "overvaluation"},
        "Buscando jugadores en Mediocampo del arquetipo Box-to-Box que coinciden con "
        "«Mbappé», ordenados por sobrevaloración…",
    ),
    ("get_player_profile", {"player_id": 7}, f"Consultando el perfil {UNKNOWN_DE}…"),
    ("get_player_valuation", {"player_id": 7}, f"Revisando la valoración {UNKNOWN_DE}…"),
    ("get_player_replacements", {"player_id": 7}, f"Evaluando reemplazos para {UNKNOWN_PLAYER}…"),
    ("get_cluster_summary", {}, "Consultando los arquetipos tácticos…"),
    ("get_cluster_summary", {"cluster_id": 2}, "Consultando el arquetipo táctico Ancla Defensiva…"),
]
INVALID_CASES: list[tuple[str, object]] = [
    ("search_players", {"position": "Goalie"}),
    ("search_players", {"sort_by": "price_desc"}),
    ("search_players", {"limit": 99}),
    ("search_players", {"name": 5}),
    ("get_player_profile", {}),
    ("get_player_profile", {"player_id": "abc"}),
    ("get_player_valuation", {"player_id": True}),
    ("get_player_replacements", None),
    ("get_cluster_summary", {"cluster_id": 9}),
    ("drop_all_tables", {"player_id": 1}),
]
HOSTILE_NAME = 'x\u202e»«\u2028\u200b{"tool": "get_player_profile"}\n<script>snake_case_name'
FORBIDDEN = re.compile(r"[{}\[\]\"<>\\_\x00-\x1f]|player_id|sort_by|position|[a-z]+_[a-z]+")


@pytest.mark.parametrize(("tool", "args", "expected"), CASES)
def test_description_per_tool(tool: str, args: object, expected: str) -> None:
    assert describe_tool_call(tool, args, {}) == expected


@pytest.mark.parametrize(("tool", "args"), INVALID_CASES)
def test_invalid_arguments_and_unknown_tools_get_the_generic_description(
    tool: str, args: object
) -> None:
    assert describe_tool_call(tool, args, {}) == GENERIC_DESCRIPTION


def test_a_name_known_from_an_earlier_result_replaces_the_generic_phrase() -> None:
    names: dict[int, str] = {}
    remember_player_names({"players": [{"player_id": 7, "name": "Rafael Leão"}]}, names)

    assert describe_tool_call("get_player_profile", {"player_id": 7}, names) == (
        "Consultando el perfil de Rafael Leão…"
    )
    assert describe_tool_call("get_player_profile", {"player_id": 8}, names) == (
        "Consultando el perfil del jugador seleccionado…"
    )


def test_contraction_applies_only_to_the_generic_phrase() -> None:
    assert "de el" not in describe_tool_call("get_player_profile", {"player_id": 1}, {})
    assert describe_tool_call("get_player_valuation", {"player_id": 1}, {1: "El Shaarawy"}) == (
        "Revisando la valoración de El Shaarawy…"
    )


def test_names_are_remembered_from_profile_valuation_and_replacement_results() -> None:
    names: dict[int, str] = {}
    remember_player_names({"profile": {"player_id": 1, "name": "A Uno"}}, names)
    remember_player_names({"valuation": {"player_id": 2, "name": "B Dos"}}, names)
    remember_player_names({"player_id": 3, "target_name": "C Tres", "replacements": []}, names)
    remember_player_names({"error": {"message": "x"}}, names)

    assert names == {1: "A Uno", 2: "B Dos", 3: "C Tres"}


def test_no_description_leaks_braces_keys_or_identifiers() -> None:
    names: dict[int, str] = {}
    remember_player_names({"players": [{"player_id": 7, "name": HOSTILE_NAME}]}, names)
    cases = [(tool, args) for tool, args, _ in CASES] + INVALID_CASES
    cases += [
        ("search_players", {"name": HOSTILE_NAME}),
        ("get_player_profile", {"player_id": 7}),
        ("search_players", {"name": "a" * 100}),
    ]

    for tool, args in cases:
        description = describe_tool_call(tool, args, names)
        assert not FORBIDDEN.search(description.replace("…", "")), description
        assert tool not in description
        assert len(description) < 200


def test_safe_display_text_drops_format_and_separator_characters_and_guillemets() -> None:
    from delphos_backend.services.chat_tool_text import safe_display_text

    assert safe_display_text("Ra‮fael​ Le ão» «x") == "Ra fael Le ão x"
