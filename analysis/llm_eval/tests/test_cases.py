"""Case-set validation against the local Parquet — no database, no server.

The entity rules of LLM_PLAN §17.3: a fictional name must have zero matches in
`ml/data/clean/players.parquet`, a real player must resolve to exactly one row, and the
structural shape of the 20 chat cases and the 9 report cells must match §17.3/§17.2.
"""

from __future__ import annotations

from itertools import product

import cases_report
import pandas as pd
import pytest
from cases_chat import (
    CHAT_CASES,
    OUTCOME_NOT_FOUND,
    OUTCOME_REFUSAL,
    players_parquet_path,
    validate_against_parquet,
)

from delphos_domain import LEAGUE_LABELS


@pytest.fixture(scope="module")
def name_counts() -> pd.Series:
    path = players_parquet_path()
    assert path.is_file(), f"missing {path}; run `delphos-pipeline clean` first"
    names = pd.read_parquet(path, columns=["player_id", "name"])["name"]
    return names.value_counts()


@pytest.fixture(scope="module")
def cases_by_id() -> dict[str, object]:
    return {case.case_id: case for case in CHAT_CASES}


def test_case_set_passes_the_parquet_validation() -> None:
    assert validate_against_parquet() == []


def test_fictional_entity_has_zero_matches(name_counts: pd.Series) -> None:
    fictional = [case.fictional_name for case in CHAT_CASES if case.fictional_name]
    assert fictional == ["Marco Nobody"]
    for name in fictional:
        assert int(name_counts.get(name, 0)) == 0


def test_every_named_real_player_resolves_to_exactly_one_row(name_counts: pd.Series) -> None:
    named = [case.player_name for case in CHAT_CASES if case.player_name]
    assert named, "the case set must name real players"
    for name in named:
        assert int(name_counts.get(name, 0)) == 1, f"{name!r} is not unique in the dataset"


def test_dataset_spelling_traps_are_documented_and_unused(name_counts: pd.Series) -> None:
    # "Kylian Mbappe" is absent (the dataset spells it "Kylian Mbappé"); "João Silva" is
    # real (2 matches). Neither may appear in the case set — the second would silently
    # turn the empty-result case into a name-resolution case.
    assert int(name_counts.get("Kylian Mbappe", 0)) == 0
    assert int(name_counts.get("Kylian Mbappé", 0)) == 1
    assert int(name_counts.get("João Silva", 0)) == 2
    used = {case.player_name for case in CHAT_CASES} | {case.fictional_name for case in CHAT_CASES}
    assert "Kylian Mbappe" not in used
    assert "João Silva" not in used


def test_twenty_cases_with_the_section_17_3_shapes(cases_by_id: dict) -> None:
    assert len(CHAT_CASES) == 20
    assert list(cases_by_id) == [f"q{i:02d}" for i in range(1, 21)]
    for i in range(1, 5):
        case = cases_by_id[f"q{i:02d}"]
        assert case.expected_tool == "search_players"
    for i in range(5, 9):
        case = cases_by_id[f"q{i:02d}"]
        assert case.expected_tool in ("get_player_profile", "get_player_valuation")
        assert case.player_name is not None
        assert case.expected_args.keys() == {"player_id"}
        assert case.expected_args["player_id"] is None  # resolved at load, recorded as fact
    for i in range(9, 13):
        assert cases_by_id[f"q{i:02d}"].expected_tool == "get_player_replacements"
    for i in range(13, 17):
        case = cases_by_id[f"q{i:02d}"]
        assert case.expected_tool == "get_cluster_summary"
        assert case.expected_args["cluster_id"] in (0, 1, 2)
    for i in (17, 18):
        case = cases_by_id[f"q{i:02d}"]
        assert case.expected_tool == "search_players"
        assert case.next_tool == "get_player_valuation"
        assert case.next_args == {"player_id": None}
        assert case.player_name is not None


def test_league_filters_use_league_ids(cases_by_id: dict) -> None:
    for case_id in ("q02", "q04"):
        league_id = cases_by_id[case_id].expected_args["league_id"]
        assert league_id in LEAGUE_LABELS, f"{case_id} league {league_id!r} is not a league_id"


def test_case_19_is_a_refusal_without_a_tool(cases_by_id: dict) -> None:
    case = cases_by_id["q19"]
    assert case.expected_tool is None
    assert case.outcome == OUTCOME_REFUSAL


def test_case_20_is_the_empty_result_path(cases_by_id: dict) -> None:
    case = cases_by_id["q20"]
    assert case.expected_tool is None
    assert case.outcome == OUTCOME_NOT_FOUND
    assert case.fictional_name == "Marco Nobody"


def test_report_cells_cover_the_full_grid_once() -> None:
    expected = set(product(cases_report.CLUSTERS, cases_report.ZONES))
    assert cases_report.ZONES == ("undervalued", "fair", "overvalued")
    assert cases_report.CLUSTERS == (0, 1, 2)
    assert len(cases_report.CELLS) == 9
    assert set(cases_report.CELLS) == expected
    assert len(set(cases_report.CELLS)) == 9
