"""End-to-end tests for the `transform` stage over small synthetic `clean` outputs.

The fixture writes typed Parquet tables shaped exactly like `clean`'s output (date32 dates,
explicit Arrow types) plus `_clean.json`, then drives the registered CLI subcommand. Match
dates are chosen around the 2024-09-15 anchor (July-to-June season 2024, so the anchor row
lands in the validation split) so the half-open valuation window `(as_of - 365, as_of]` and
the strict-before transfer window are pinned by the aggregated minute counts.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from typer.testing import CliRunner, Result

from delphos_ml.pipeline import transform as transform_module
from delphos_ml.pipeline.cli import app

runner = CliRunner()

RowDict = dict[str, Any]
TableSpec = tuple[list[tuple[str, pa.DataType]], list[RowDict]]

AS_OF = "2024-09-15"

BASE_TABLES: dict[str, TableSpec] = {
    "appearances": (
        [
            ("game_id", pa.int64()),
            ("player_id", pa.int64()),
            ("player_club_id", pa.int64()),
            ("date", pa.date32()),
            ("competition_id", pa.string()),
            ("minutes_played", pa.int64()),
            ("goals", pa.int64()),
            ("assists", pa.int64()),
            ("yellow_cards", pa.int64()),
            ("red_cards", pa.int64()),
        ],
        [
            # Player 1, anchored at AS_OF = 2024-09-15; the valuation window is the
            # half-open (as_of - 365, as_of] = (2023-09-16, 2024-09-15]. 101/102 predate
            # the window and 112 falls after the anchor, so none of them counts; 103 sits
            # on the earliest counted day (2023-09-17 = as_of - 364) and does count.
            {
                "game_id": 101,
                "player_id": 1,
                "player_club_id": 10,
                "date": "2023-05-15",
                "competition_id": "L1",
                "minutes_played": 90,
                "goals": 1,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            {
                "game_id": 102,
                "player_id": 1,
                "player_club_id": 10,
                "date": "2023-05-14",
                "competition_id": "L1",
                "minutes_played": 120,
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            {
                "game_id": 103,
                "player_id": 1,
                "player_club_id": 10,
                "date": "2023-09-17",
                "competition_id": "L1",
                "minutes_played": 90,
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            {
                "game_id": 104,
                "player_id": 1,
                "player_club_id": 10,
                "date": "2024-05-12",
                "competition_id": "L1",
                "minutes_played": 60,
                "goals": 1,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            {
                "game_id": 105,
                "player_id": 1,
                "player_club_id": 10,
                "date": "2024-05-14",
                "competition_id": "CUP1",
                "minutes_played": 30,
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            {
                "game_id": 106,
                "player_id": 1,
                "player_club_id": 10,
                "date": "2024-06-01",
                "competition_id": "L1",
                "minutes_played": 120,
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            # On the transfer day itself; the strict-before transfer window excludes it
            # (it still counts in the later valuation window).
            {
                "game_id": 107,
                "player_id": 1,
                "player_club_id": 10,
                "date": "2024-07-15",
                "competition_id": "L1",
                "minutes_played": 90,
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            # Ten days after the valuation anchor: outside the valuation and transfer windows.
            {
                "game_id": 112,
                "player_id": 1,
                "player_club_id": 10,
                "date": "2024-09-25",
                "competition_id": "L1",
                "minutes_played": 120,
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            # Player 2: 179 trailing minutes, below the floor.
            {
                "game_id": 108,
                "player_id": 2,
                "player_club_id": 10,
                "date": "2024-03-15",
                "competition_id": "L1",
                "minutes_played": 179,
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            # Player 3 is a goalkeeper; player 4 plays for an uncovered club.
            {
                "game_id": 109,
                "player_id": 3,
                "player_club_id": 10,
                "date": "2024-04-01",
                "competition_id": "L1",
                "minutes_played": 300,
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            {
                "game_id": 110,
                "player_id": 4,
                "player_club_id": 30,
                "date": "2024-02-10",
                "competition_id": "MX1",
                "minutes_played": 300,
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            # Player 5: a train-season row with no club_games history.
            {
                "game_id": 111,
                "player_id": 5,
                "player_club_id": 20,
                "date": "2019-04-01",
                "competition_id": "ES1",
                "minutes_played": 200,
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
        ],
    ),
    "club_games": (
        [
            ("game_id", pa.int64()),
            ("club_id", pa.int64()),
            ("own_position", pa.int64()),
            ("own_goals", pa.int64()),
            ("opponent_goals", pa.int64()),
            ("is_win", pa.bool_()),
        ],
        [
            {
                "game_id": 103,
                "club_id": 10,
                "own_position": 5,
                "own_goals": 1,
                "opponent_goals": 1,
                "is_win": False,
            },
            {
                "game_id": 104,
                "club_id": 10,
                "own_position": 3,
                "own_goals": 2,
                "opponent_goals": 0,
                "is_win": True,
            },
        ],
    ),
    "clubs": (
        [("club_id", pa.int64()), ("domestic_competition_id", pa.string())],
        [
            {"club_id": 10, "domestic_competition_id": "L1"},
            {"club_id": 20, "domestic_competition_id": "ES1"},
            {"club_id": 30, "domestic_competition_id": "MX1"},
        ],
    ),
    "competitions": (
        [
            ("competition_id", pa.string()),
            ("type", pa.string()),
            ("sub_type", pa.string()),
        ],
        [
            {"competition_id": "L1", "type": "domestic_league", "sub_type": ""},
            {"competition_id": "ES1", "type": "domestic_league", "sub_type": ""},
            {"competition_id": "MX1", "type": "domestic_league", "sub_type": ""},
            {"competition_id": "CUP1", "type": "domestic_cup", "sub_type": ""},
        ],
    ),
    "game_lineups": (
        [
            ("player_id", pa.int64()),
            ("date", pa.date32()),
            ("type", pa.string()),
            ("team_captain", pa.bool_()),
        ],
        [
            {"player_id": 1, "date": "2024-05-12", "type": "starting_lineup", "team_captain": True},
        ],
    ),
    "games": (
        [("game_id", pa.int64()), ("date", pa.date32())],
        [
            {"game_id": 103, "date": "2023-09-17"},
            {"game_id": 104, "date": "2024-05-12"},
        ],
    ),
    "player_valuations": (
        [
            ("player_id", pa.int64()),
            ("date", pa.date32()),
            ("market_value_in_eur", pa.float64()),
            ("current_club_id", pa.int64()),
            ("player_club_domestic_competition_id", pa.string()),
        ],
        [
            # An earlier season-2024 valuation; the anchor takes the latest one (AS_OF).
            {
                "player_id": 1,
                "date": "2024-08-01",
                "market_value_in_eur": 1_000_000.0,
                "current_club_id": 10,
                "player_club_domestic_competition_id": "L1",
            },
            {
                "player_id": 1,
                "date": AS_OF,
                "market_value_in_eur": 2_000_000.0,
                "current_club_id": 10,
                "player_club_domestic_competition_id": "L1",
            },
            {
                "player_id": 2,
                "date": "2024-04-01",
                "market_value_in_eur": 500_000.0,
                "current_club_id": 10,
                "player_club_domestic_competition_id": "L1",
            },
            {
                "player_id": 3,
                "date": "2024-04-01",
                "market_value_in_eur": 700_000.0,
                "current_club_id": 10,
                "player_club_domestic_competition_id": "L1",
            },
            {
                "player_id": 4,
                "date": "2024-02-01",
                "market_value_in_eur": 300_000.0,
                "current_club_id": 30,
                "player_club_domestic_competition_id": "MX1",
            },
            {
                "player_id": 5,
                "date": "2019-05-20",
                "market_value_in_eur": 400_000.0,
                "current_club_id": 20,
                "player_club_domestic_competition_id": "ES1",
            },
        ],
    ),
    "players": (
        [
            ("player_id", pa.int64()),
            ("date_of_birth", pa.date32()),
            ("position", pa.string()),
            ("sub_position", pa.string()),
            ("foot", pa.string()),
            ("height_in_cm", pa.int64()),
            ("country_of_citizenship", pa.string()),
        ],
        [
            {
                "player_id": 1,
                "date_of_birth": "1997-06-20",
                "position": "Attack",
                "sub_position": "Centre-Forward",
                "foot": "right",
                "height_in_cm": 180,
                "country_of_citizenship": "AR",
            },
            {
                "player_id": 2,
                "date_of_birth": "1995-01-01",
                "position": "Midfield",
                "sub_position": "Central Midfield",
                "foot": "left",
                "height_in_cm": 175,
                "country_of_citizenship": "DE",
            },
            {
                "player_id": 3,
                "date_of_birth": "1990-02-02",
                "position": "Goalkeeper",
                "sub_position": "Goalkeeper",
                "foot": "right",
                "height_in_cm": 190,
                "country_of_citizenship": "IT",
            },
            {
                "player_id": 4,
                "date_of_birth": "1998-08-08",
                "position": "Attack",
                "sub_position": "Centre-Forward",
                "foot": "right",
                "height_in_cm": 182,
                "country_of_citizenship": "BR",
            },
            {
                "player_id": 5,
                "date_of_birth": "2000-12-12",
                "position": "Defender",
                "sub_position": "Centre-Back",
                "foot": None,
                "height_in_cm": None,
                "country_of_citizenship": "IT",
            },
        ],
    ),
    "transfers": (
        [
            ("player_id", pa.int64()),
            ("transfer_date", pa.date32()),
            ("from_club_id", pa.int64()),
            ("to_club_id", pa.int64()),
            ("transfer_fee", pa.float64()),
            ("market_value_in_eur", pa.float64()),
        ],
        [
            {
                "player_id": 1,
                "transfer_date": "2024-07-15",
                "from_club_id": 10,
                "to_club_id": 30,
                "transfer_fee": 5_000_000.0,
                "market_value_in_eur": 2_500_000.0,
            },
            # Free transfer and a move between two uncovered clubs: both drop out.
            {
                "player_id": 2,
                "transfer_date": "2024-01-10",
                "from_club_id": 10,
                "to_club_id": 20,
                "transfer_fee": 0.0,
                "market_value_in_eur": 1_000_000.0,
            },
            {
                "player_id": 2,
                "transfer_date": "2024-02-10",
                "from_club_id": 30,
                "to_club_id": 40,
                "transfer_fee": 9_000_000.0,
                "market_value_in_eur": 1_000_000.0,
            },
        ],
    ),
}

EXPECTED_PLAYER_SEASON_TYPES = [
    ("player_id", "int64"),
    ("season", "int64"),
    ("as_of_date", "date32[day]"),
    ("split", "string"),
    ("club_id", "int64"),
    ("league_id", "string"),
    ("minutes", "double"),
    ("apps", "double"),
    ("starts", "double"),
    ("captain", "double"),
    ("squad_inclusions", "double"),
    ("goals", "double"),
    ("assists", "double"),
    ("yellow_cards", "double"),
    ("red_cards", "double"),
    ("win_flag", "double"),
    ("clean_sheet_flag", "double"),
    ("goals_conceded", "double"),
    ("uefa_minutes", "double"),
    ("starter_ratio", "double"),
    ("captain_ratio", "double"),
    ("win_rate", "double"),
    ("clean_sheet_rate", "double"),
    ("goals_conceded_per_match", "double"),
    ("uefa_share", "double"),
    ("cup_share", "double"),
    ("league_position", "double"),
    ("league_position_missing", "bool"),
    ("age", "double"),
    ("age_sq", "double"),
    ("height_in_cm", "double"),
    ("foot", "string"),
    ("position", "string"),
    ("sub_position", "string"),
    ("country_group", "string"),
    ("log10_market_value", "double"),
]
EXPECTED_TRANSFER_EVENT_TYPES = [
    *EXPECTED_PLAYER_SEASON_TYPES,
    ("transfer_date", "date32[day]"),
    ("transfer_fee", "double"),
    ("pre_transfer_market_value", "double"),
]


@pytest.fixture(autouse=True)
def no_rename_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transform_module, "_RENAME_RETRY_DELAY_SECONDS", 0)


def invoke_transform() -> Result:
    return runner.invoke(app, ["transform"])


def write_clean_fixture(
    data_dir: Path,
    overrides: Mapping[str, Sequence[RowDict]] | None = None,
    omit_tables: Sequence[str] = (),
) -> Path:
    """Write typed Parquet tables shaped like `clean`'s output plus a valid `_clean.json`."""
    clean_path = data_dir / "clean"
    clean_path.mkdir(parents=True, exist_ok=True)
    tables_meta: dict[str, dict[str, Any]] = {}
    for table_name, (schema, default_rows) in sorted(BASE_TABLES.items()):
        if table_name in omit_tables:
            continue
        rows = (
            list(overrides[table_name])
            if overrides and table_name in overrides
            else list(default_rows)
        )
        arrays = []
        for column_name, column_type in schema:
            values = [row.get(column_name) for row in rows]
            if column_type == pa.date32():
                values = [None if value is None else pd.Timestamp(value).date() for value in values]
            arrays.append(pa.array(values, type=column_type, from_pandas=True))
        pq.write_table(
            pa.Table.from_arrays(arrays, names=[name for name, _ in schema]),
            clean_path / f"{table_name}.parquet",
        )
        tables_meta[table_name] = {
            "parquet_file": f"{table_name}.parquet",
            "rows": len(rows),
        }
    manifest = {
        "dataset": "davidcariboo/player-scores",
        "version": 679,
        "cleaned_at": "2026-10-29T00:00:00Z",
        "tables": tables_meta,
    }
    (clean_path / "_clean.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return clean_path


def read_table(path: Path) -> pd.DataFrame:
    return pq.read_table(path).to_pandas()


def _age_days(birth: str, anchor: str) -> float:
    return (pd.Timestamp(anchor) - pd.Timestamp(birth)).days / 365.25


def test_transform_writes_three_outputs_with_expected_schema_and_manifest(
    project_dir: Path,
) -> None:
    clean_path = write_clean_fixture(project_dir / "data")

    result = invoke_transform()

    assert result.exit_code == 0, result.output
    out = project_dir / "data" / "transform"
    player_seasons = pq.ParquetFile(out / "player_seasons.parquet").schema_arrow
    transfer_events = pq.ParquetFile(out / "transfer_events.parquet").schema_arrow
    assert list(zip(player_seasons.names, map(str, player_seasons.types), strict=True)) == (
        EXPECTED_PLAYER_SEASON_TYPES
    )
    assert list(zip(transfer_events.names, map(str, transfer_events.types), strict=True)) == (
        EXPECTED_TRANSFER_EVENT_TYPES
    )

    manifest = json.loads((out / "_transform.json").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "davidcariboo/player-scores"
    assert manifest["version"] == 679
    assert (
        manifest["clean_manifest_sha256"]
        == hashlib.sha256((clean_path / "_clean.json").read_bytes()).hexdigest()
    )
    assert manifest["window_days"] == 365
    assert manifest["minutes_floor"] == 180
    assert manifest["empirical_bayes_m"] == 5
    assert manifest["prior_grouping"] == "position"
    assert manifest["season_month_start"] == 7
    assert manifest["country_top_n"] == 10
    # The vocabulary is fitted on the training split's rows only (player 5, IT).
    assert manifest["country_groups"] == ["IT"]
    assert manifest["rows_per_split"] == {"train": 1, "validation": 1}
    assert manifest["rows_per_season"] == {"2018": 1, "2024": 1}
    player_meta = manifest["tables"]["player_seasons"]
    assert player_meta["parquet_file"] == "player_seasons.parquet"
    assert player_meta["rows"] == 2
    assert player_meta["columns"] == [name for name, _ in EXPECTED_PLAYER_SEASON_TYPES]
    assert player_meta["dtypes"] == dict(EXPECTED_PLAYER_SEASON_TYPES)
    transfer_meta = manifest["tables"]["transfer_events"]
    assert transfer_meta["parquet_file"] == "transfer_events.parquet"
    assert transfer_meta["rows"] == 1
    assert transfer_meta["rows_per_split"] == {"validation": 1}
    assert transfer_meta["rows_per_season"] == {"2024": 1}
    assert transfer_meta["dtypes"] == dict(EXPECTED_TRANSFER_EVENT_TYPES)


def test_transform_player_season_rows_match_the_synthetic_fixture(project_dir: Path) -> None:
    write_clean_fixture(project_dir / "data")

    assert invoke_transform().exit_code == 0
    df = read_table(project_dir / "data" / "transform" / "player_seasons.parquet")
    df.index = df["player_id"]

    # Excluded populations: below the minutes floor, a goalkeeper, an uncovered league.
    assert sorted(df.index.tolist()) == [1, 5]

    row = df.loc[1]
    assert pd.Timestamp(row["as_of_date"]) == pd.Timestamp(AS_OF)
    assert row["season"] == 2024
    assert row["split"] == "validation"
    assert row["club_id"] == 10
    assert row["league_id"] == "L1"
    # (2023-09-16, 2024-09-15]: 103 (2023-09-17 = as_of - 364, the earliest counted day),
    # 104, 105, 106 and 107 count; 101/102 (May 2023), 112 (after the anchor) and 101's
    # goal do not — 104's goal is the one that lands in the aggregates.
    assert row["minutes"] == 390.0
    assert row["apps"] == 5.0
    assert row["goals"] == 1.0
    assert row["starts"] == 1.0
    assert row["captain"] == 1.0
    assert row["squad_inclusions"] == 1.0
    assert row["win_flag"] == 1.0
    assert row["clean_sheet_flag"] == 1.0
    assert row["goals_conceded"] == 1.0
    assert row["uefa_minutes"] == 0.0
    assert row["starter_ratio"] == 0.2
    assert row["captain_ratio"] == 1.0
    assert row["win_rate"] == 0.2
    assert row["clean_sheet_rate"] == 0.2
    assert row["goals_conceded_per_match"] == 0.2
    assert row["uefa_share"] == 0.0
    assert row["cup_share"] == pytest.approx(30.0 / 390.0)
    assert row["league_position"] == 3.0
    assert bool(row["league_position_missing"]) is False
    assert row["age"] == pytest.approx(_age_days("1997-06-20", AS_OF))
    assert row["age_sq"] == pytest.approx(row["age"] ** 2)
    assert row["height_in_cm"] == 180.0
    assert row["foot"] == "right"
    assert row["position"] == "Attack"
    assert row["sub_position"] == "Centre-Forward"
    # The validation row's AR never entered the vocabulary: the training split (player 5)
    # carries only IT, so every other citizenship collapses to "other".
    assert row["country_group"] == "other"
    assert row["log10_market_value"] == pytest.approx(float(np.log10(2_000_000.0)))

    row = df.loc[5]
    assert row["season"] == 2018
    assert row["split"] == "train"
    assert row["league_id"] == "ES1"
    assert row["minutes"] == 200.0
    assert pd.isna(row["league_position"])
    assert bool(row["league_position_missing"]) is True
    assert pd.isna(row["height_in_cm"])
    assert pd.isna(row["foot"])
    assert row["sub_position"] == "Centre-Back"
    assert row["country_group"] == "IT"


def test_valuation_window_includes_day_365_and_excludes_day_366(project_dir: Path) -> None:
    """A closed window would count both 200-minute matches; the half-open window counts one."""
    # Window day 365 (as_of - 364 = 2023-09-17) is the last counted day of the trailing
    # 365-day window; day 366 (as_of - 365 = 2023-09-16) is the excluded boundary of the
    # half-open window (a closed window would count it too).
    extra_apps = [
        {
            "game_id": 201,
            "player_id": 6,
            "player_club_id": 10,
            "date": "2023-09-17",
            "competition_id": "L1",
            "minutes_played": 200,
            "goals": 0,
            "assists": 0,
            "yellow_cards": 0,
            "red_cards": 0,
        },
        {
            "game_id": 202,
            "player_id": 6,
            "player_club_id": 10,
            "date": "2023-09-16",
            "competition_id": "L1",
            "minutes_played": 200,
            "goals": 0,
            "assists": 0,
            "yellow_cards": 0,
            "red_cards": 0,
        },
    ]
    write_clean_fixture(
        project_dir / "data",
        overrides={
            "appearances": [*_BASE("appearances"), *extra_apps],
            "player_valuations": [
                *_BASE("player_valuations"),
                {
                    "player_id": 6,
                    "date": AS_OF,
                    "market_value_in_eur": 100_000.0,
                    "current_club_id": 10,
                    "player_club_domestic_competition_id": "L1",
                },
            ],
            "players": [
                *_BASE("players"),
                {
                    "player_id": 6,
                    "date_of_birth": "1999-01-01",
                    "position": "Midfield",
                    "sub_position": None,
                    "foot": None,
                    "height_in_cm": None,
                    "country_of_citizenship": None,
                },
            ],
        },
    )

    assert invoke_transform().exit_code == 0
    df = read_table(project_dir / "data" / "transform" / "player_seasons.parquet")
    df.index = df["player_id"]

    assert df.loc[6]["minutes"] == 200.0


def test_transfer_window_excludes_matches_on_the_transfer_date(project_dir: Path) -> None:
    write_clean_fixture(project_dir / "data")

    assert invoke_transform().exit_code == 0
    df = read_table(project_dir / "data" / "transform" / "transfer_events.parquet")

    (row,) = df.itertuples(index=False)
    # The strict-before window [2023-07-15, 2024-07-14] holds the 2023-09-17, 2024-05-12,
    # 2024-05-14 and 2024-06-01 matches (300 minutes); leaking the transfer-day match would
    # make it 390, admitting the 2023-05-15 match would too, and 112 (2024-09-25) postdates it.
    assert row.minutes == 300.0
    assert row.apps == 4.0
    assert row.transfer_date == dt.date(2024, 7, 15)
    assert row.as_of_date == dt.date(2024, 7, 15)
    assert row.split == "validation"
    assert row.club_id == 10
    assert row.league_id == "L1"
    assert row.transfer_fee == 5_000_000.0
    assert row.pre_transfer_market_value == 2_500_000.0
    assert row.log10_market_value == pytest.approx(float(np.log10(2_500_000.0)))


def test_failed_run_leaves_previous_transform_output_intact(project_dir: Path) -> None:
    data_dir = project_dir / "data"
    write_clean_fixture(data_dir)
    assert invoke_transform().exit_code == 0
    out = data_dir / "transform"
    before = {path.name: path.read_bytes() for path in sorted(out.iterdir())}

    manifest_path = data_dir / "clean" / "_clean.json"
    stale = json.loads(manifest_path.read_text(encoding="utf-8"))
    stale["version"] = 680
    manifest_path.write_text(json.dumps(stale, indent=2) + "\n", encoding="utf-8")

    failed = invoke_transform()

    assert failed.exit_code == 1
    assert "transform failed:" in failed.output
    assert "does not match configured dataset" in failed.output
    assert {path.name: path.read_bytes() for path in sorted(out.iterdir())} == before
    assert list(data_dir.glob(".transform-staging-*")) == []


def test_country_group_keeps_the_top_n_and_sends_the_rest_to_other() -> None:
    top = [f"C{index:02d}" for index in range(10)]
    citizenship = pd.Series([*top, *top, *top, "ZZ", None])
    country_map = transform_module._country_group_map(citizenship)
    assert sorted(country_map) == top

    frame = pd.DataFrame(
        {
            "starts": [1.0, 1.0, 1.0],
            "apps": [2.0, 2.0, 2.0],
            "captain": [0.0, 0.0, 0.0],
            "squad_inclusions": [2.0, 2.0, 2.0],
            "win_flag": [1.0, 1.0, 1.0],
            "clean_sheet_flag": [0.0, 0.0, 0.0],
            "goals_conceded": [1.0, 1.0, 1.0],
            "uefa_minutes": [0.0, 0.0, 0.0],
            "minutes": [180.0, 180.0, 180.0],
            "cup_minutes": [0.0, 0.0, 0.0],
            "age": [25.0, 25.0, 25.0],
            "country_of_citizenship": ["ZZ", None, "C00"],
        }
    )

    derived = transform_module._with_deterministic_columns(frame, country_map)

    assert derived["country_group"].tolist() == ["other", "other", "C00"]
    assert "cup_minutes" not in derived.columns
    assert "country_of_citizenship" not in derived.columns


def test_country_group_vocabulary_is_fitted_on_training_rows_only(project_dir: Path) -> None:
    """Changing a validation-only or test-only citizenship must not move the vocabulary."""
    data_dir = project_dir / "data"
    write_clean_fixture(data_dir)
    assert invoke_transform().exit_code == 0
    manifest_path = data_dir / "transform" / "_transform.json"
    baseline = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Only the train row (player 5) carries IT; the validation row's AR must not enter.
    assert baseline["country_groups"] == ["IT"]

    # Change the validation row's citizenship (AR -> ZZ) and add a test-split row (season
    # 2025, citizenship YY): neither may move the vocabulary, and both must score as
    # "other".
    players_after = [
        {
            **row,
            "country_of_citizenship": (
                "ZZ" if row["player_id"] == 1 else row["country_of_citizenship"]
            ),
        }
        for row in _BASE("players")
    ]
    players_after.append(
        {
            "player_id": 6,
            "date_of_birth": "1999-03-03",
            "position": "Midfield",
            "sub_position": "Central Midfield",
            "foot": "right",
            "height_in_cm": 177,
            "country_of_citizenship": "YY",
        }
    )
    write_clean_fixture(
        data_dir,
        overrides={
            "players": players_after,
            "player_valuations": [
                *_BASE("player_valuations"),
                {
                    "player_id": 6,
                    "date": "2025-08-01",
                    "market_value_in_eur": 900_000.0,
                    "current_club_id": 10,
                    "player_club_domestic_competition_id": "L1",
                },
            ],
            "appearances": [
                *_BASE("appearances"),
                {
                    "game_id": 301,
                    "player_id": 6,
                    "player_club_id": 10,
                    "date": "2025-07-10",
                    "competition_id": "L1",
                    "minutes_played": 120,
                    "goals": 0,
                    "assists": 0,
                    "yellow_cards": 0,
                    "red_cards": 0,
                },
                {
                    "game_id": 302,
                    "player_id": 6,
                    "player_club_id": 10,
                    "date": "2025-07-20",
                    "competition_id": "L1",
                    "minutes_played": 90,
                    "goals": 0,
                    "assists": 0,
                    "yellow_cards": 0,
                    "red_cards": 0,
                },
            ],
        },
    )
    assert invoke_transform().exit_code == 0
    after = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert after["country_groups"] == baseline["country_groups"]
    rows = read_table(data_dir / "transform" / "player_seasons.parquet")
    rows.index = rows["player_id"]
    assert rows.loc[1]["country_group"] == "other"  # validation row, now citizenship ZZ
    assert rows.loc[6]["country_group"] == "other"  # test row, citizenship YY

    # Positive control: change the *training* row's citizenship (IT -> DE) and only then
    # the vocabulary follows, proving the mapping tracks the training split alone.
    train_players = [
        {
            **row,
            "country_of_citizenship": (
                "DE" if row["player_id"] == 5 else row["country_of_citizenship"]
            ),
        }
        for row in players_after
    ]
    write_clean_fixture(data_dir, overrides={"players": train_players})
    assert invoke_transform().exit_code == 0
    third = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert third["country_groups"] == ["DE"]


def _BASE(table_name: str) -> list[RowDict]:
    """Return fresh copies of the base fixture rows for one table."""
    _, rows = BASE_TABLES[table_name]
    return [dict(row) for row in rows]
