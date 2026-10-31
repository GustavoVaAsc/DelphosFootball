import datetime as dt
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from typer.testing import CliRunner, Result

from delphos_ml.pipeline import clean as clean_module
from delphos_ml.pipeline.cli import app

runner = CliRunner()

RowDict = dict[str, Any]

BASE_TABLES: dict[str, tuple[list[str], list[RowDict]]] = {
    "appearances": (
        [
            "appearance_id",
            "game_id",
            "player_id",
            "player_club_id",
            "player_current_club_id",
            "date",
            "player_name",
            "competition_id",
            "yellow_cards",
            "red_cards",
            "goals",
            "assists",
            "minutes_played",
        ],
        [
            {
                "appearance_id": "100_1",
                "game_id": "100",
                "player_id": "1",
                "player_club_id": "10",
                "player_current_club_id": "99",
                "date": "2024-05-12",
                "player_name": "Forward One",
                "competition_id": "IT1",
                "yellow_cards": "0",
                "red_cards": "0",
                "goals": "1",
                "assists": "0",
                "minutes_played": "90",
            }
        ],
    ),
    "club_games": (
        [
            "game_id",
            "club_id",
            "own_goals",
            "own_position",
            "own_manager_name",
            "opponent_id",
            "opponent_goals",
            "opponent_position",
            "opponent_manager_name",
            "hosting",
            "is_win",
        ],
        [
            {
                "game_id": "100",
                "club_id": "10",
                "own_goals": "2",
                "own_position": "4",
                "own_manager_name": "Coach A",
                "opponent_id": "20",
                "opponent_goals": "0",
                "opponent_position": None,
                "opponent_manager_name": None,
                "hosting": "Home",
                "is_win": "1",
            },
            {
                "game_id": "100",
                "club_id": "20",
                "own_goals": "0",
                "own_position": None,
                "own_manager_name": "Coach B",
                "opponent_id": "10",
                "opponent_goals": "2",
                "opponent_position": "4",
                "opponent_manager_name": "Coach A",
                "hosting": "Away",
                "is_win": "0",
            },
        ],
    ),
    "clubs": (
        [
            "club_id",
            "club_code",
            "name",
            "domestic_competition_id",
            "total_market_value",
            "squad_size",
            "average_age",
            "foreigners_number",
            "foreigners_percentage",
            "national_team_players",
            "stadium_name",
            "stadium_seats",
            "net_transfer_record",
            "coach_name",
            "last_season",
            "filename",
            "url",
        ],
        [
            {
                "club_id": "10",
                "club_code": "ac-example",
                "name": "AC Example",
                "domestic_competition_id": "IT1",
                "total_market_value": None,
                "squad_size": "26",
                "average_age": "25.4",
                "foreigners_number": "14",
                "foreigners_percentage": "53.8",
                "national_team_players": "8",
                "stadium_name": "Stadio Uno",
                "stadium_seats": "45000",
                "net_transfer_record": "+€5.0m",
                "coach_name": "Coach A",
                "last_season": "2025",
                "filename": "../data/raw/2025/clubs.json.gz",
                "url": "https://example.test/club/10",
            }
        ],
    ),
    "competitions": (
        [
            "competition_id",
            "competition_code",
            "name",
            "sub_type",
            "type",
            "country_id",
            "country_name",
            "domestic_league_code",
            "confederation",
            "total_clubs",
            "url",
        ],
        [
            {
                "competition_id": "IT1",
                "competition_code": "serie-a",
                "name": "serie-a",
                "sub_type": "first_tier",
                "type": "domestic_league",
                "country_id": "75",
                "country_name": "Italy",
                "domestic_league_code": "IT1",
                "confederation": "europa",
                "total_clubs": "20",
                "url": "https://example.test/comp/IT1",
            },
            {
                "competition_id": "CL",
                "competition_code": "uefa-champions-league",
                "name": "uefa-champions-league",
                "sub_type": "uefa_champions_league",
                "type": "international_cup",
                "country_id": "-1",
                "country_name": None,
                "domestic_league_code": None,
                "confederation": "europa",
                "total_clubs": None,
                "url": "https://example.test/comp/CL",
            },
        ],
    ),
    "game_lineups": (
        [
            "game_lineups_id",
            "date",
            "game_id",
            "player_id",
            "club_id",
            "player_name",
            "type",
            "position",
            "number",
            "team_captain",
        ],
        [
            {
                "game_lineups_id": "b2dbe01c3656b06c8e23e9de714e26bb",
                "date": "2024-05-12",
                "game_id": "100",
                "player_id": "1",
                "club_id": "10",
                "player_name": "Forward One\xa0",
                "type": "starting_lineup",
                "position": "Centre-Forward",
                "number": "9",
                "team_captain": "1",
            },
            {
                "game_lineups_id": "c3ecf12d4767c17d9f34f0ef825f37cc",
                "date": "2024-05-12",
                "game_id": "100",
                "player_id": "2",
                "club_id": "10",
                "player_name": "Bench Two",
                "type": "substitutes",
                "position": "",
                "number": "-",
                "team_captain": "0",
            },
        ],
    ),
    "games": (
        [
            "game_id",
            "competition_id",
            "season",
            "round",
            "date",
            "home_club_id",
            "away_club_id",
            "home_club_goals",
            "away_club_goals",
            "home_club_position",
            "away_club_position",
            "home_club_manager_name",
            "away_club_manager_name",
            "stadium",
            "attendance",
            "referee",
            "url",
            "home_club_formation",
            "away_club_formation",
            "home_club_name",
            "away_club_name",
            "aggregate",
            "competition_type",
        ],
        [
            {
                "game_id": "100",
                "competition_id": "IT1",
                "season": "2023",
                "round": "36. Matchday",
                "date": "2024-05-12",
                "home_club_id": "10",
                "away_club_id": "20",
                "home_club_goals": "2",
                "away_club_goals": "0",
                "home_club_position": "4",
                "away_club_position": None,
                "home_club_manager_name": "Coach A",
                "away_club_manager_name": "Coach B",
                "stadium": "Stadio Uno",
                "attendance": "41200",
                "referee": "Ref One",
                "url": "https://example.test/game/100",
                "home_club_formation": "4-3-3",
                "away_club_formation": None,
                "home_club_name": "AC Example",
                "away_club_name": "FC Rival",
                "aggregate": "2:0",
                "competition_type": "domestic_league",
            }
        ],
    ),
    "player_valuations": (
        [
            "player_id",
            "date",
            "market_value_in_eur",
            "current_club_name",
            "current_club_id",
            "player_club_domestic_competition_id",
        ],
        [
            {
                "player_id": "1",
                "date": "2024-06-01",
                "market_value_in_eur": "12000000",
                "current_club_name": "AC Example",
                "current_club_id": "10",
                "player_club_domestic_competition_id": "IT1",
            }
        ],
    ),
    "players": (
        [
            "player_id",
            "first_name",
            "last_name",
            "name",
            "last_season",
            "current_club_id",
            "player_code",
            "country_of_birth",
            "city_of_birth",
            "country_of_citizenship",
            "date_of_birth",
            "sub_position",
            "position",
            "foot",
            "height_in_cm",
            "contract_expiration_date",
            "agent_name",
            "image_url",
            "international_caps",
            "international_goals",
            "current_national_team_id",
            "url",
            "current_club_domestic_competition_id",
            "current_club_name",
            "market_value_in_eur",
            "highest_market_value_in_eur",
        ],
        [
            {
                "player_id": "1",
                "first_name": "Forward",
                "last_name": "One",
                "name": "Forward One",
                "last_season": "2025",
                "current_club_id": "99",
                "player_code": "forward-one",
                "country_of_birth": "Poland",
                "city_of_birth": "Opole\xa0\xa0",
                "country_of_citizenship": "Poland",
                "date_of_birth": "1998-12-20 00:00:00",
                "sub_position": "Centre-Forward",
                "position": "Attack",
                "foot": "right",
                "height_in_cm": "185",
                "contract_expiration_date": "2027-06-30 00:00:00",
                "agent_name": "Agency X",
                "image_url": "https://example.test/img/1.jpg",
                "international_caps": "15",
                "international_goals": "4",
                "current_national_team_id": "3584",
                "url": "https://example.test/player/1",
                "current_club_domestic_competition_id": "GB1",
                "current_club_name": "Future Club",
                "market_value_in_eur": "40000000",
                "highest_market_value_in_eur": "45000000",
            }
        ],
    ),
    "transfers": (
        [
            "player_id",
            "transfer_date",
            "transfer_season",
            "from_club_id",
            "to_club_id",
            "from_club_name",
            "to_club_name",
            "transfer_fee",
            "market_value_in_eur",
            "player_name",
        ],
        [
            {
                "player_id": "1",
                "transfer_date": "2024-07-01",
                "transfer_season": "24/25",
                "from_club_id": "10",
                "to_club_id": "99",
                "from_club_name": "AC Example",
                "to_club_name": "Future Club",
                "transfer_fee": "15500000.000",
                "market_value_in_eur": "12000000.000",
                "player_name": "Forward One",
            },
            {
                "player_id": "1",
                "transfer_date": "2022-07-01",
                "transfer_season": "22/23",
                "from_club_id": "5",
                "to_club_id": "10",
                "from_club_name": "Youth FC",
                "to_club_name": "AC Example",
                "transfer_fee": "0.000",
                "market_value_in_eur": None,
                "player_name": "Forward One",
            },
        ],
    ),
    "countries": (
        ["country_id", "country_name"],
        [{"country_id": "75", "country_name": "Italy"}],
    ),
    "game_events": (
        ["game_event_id", "type"],
        [{"game_event_id": "ev1", "type": "Substitutions"}],
    ),
    "national_teams": (
        ["national_team_id", "name"],
        [{"national_team_id": "3584", "name": "Poland"}],
    ),
}


@pytest.fixture(autouse=True)
def no_rename_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clean_module, "_RENAME_RETRY_DELAY_SECONDS", 0)


def invoke_clean() -> Result:
    return runner.invoke(app, ["clean"])


def write_ingest_fixture(
    data_dir: Path,
    overrides: Mapping[str, Sequence[RowDict]] | None = None,
    schema_overrides: Mapping[str, pa.Schema] | None = None,
    omit_tables: Sequence[str] = (),
) -> Path:
    ingest_path = data_dir / "ingest"
    ingest_path.mkdir(parents=True, exist_ok=True)
    tables_meta: dict[str, dict[str, Any]] = {}
    for table_name, (columns, default_rows) in sorted(BASE_TABLES.items()):
        if table_name in omit_tables:
            continue
        rows = (
            list(overrides[table_name]) if overrides and table_name in overrides else default_rows
        )
        if schema_overrides and table_name in schema_overrides:
            schema = schema_overrides[table_name]
            arrays = [
                pa.array([row.get(field.name) for row in rows], type=field.type) for field in schema
            ]
            arrow_table = pa.Table.from_arrays(arrays, schema=schema)
        else:
            schema = pa.schema([(col, pa.string()) for col in columns])
            arrays = [pa.array([row.get(col) for row in rows], type=pa.string()) for col in columns]
            arrow_table = pa.Table.from_arrays(arrays, schema=schema)
        parquet_file = f"{table_name}.parquet"
        pq.write_table(arrow_table, ingest_path / parquet_file)
        tables_meta[table_name] = {
            "source_file": f"{table_name}.csv",
            "parquet_file": parquet_file,
            "sha256": "0" * 64,
            "rows": len(rows),
            "columns": len(schema.names),
            "column_names": list(schema.names),
        }
    snapshot = {
        "dataset": "davidcariboo/player-scores",
        "version": 679,
        "handle": "davidcariboo/player-scores/versions/679",
        "ingested_at": "2026-10-17T12:00:00Z",
        "snapshot_sha256": "94f42930f5d50d76f5226f64bd2b9e4c70552e110ad28743b5edce4041c8b1c1",
        "tool_versions": {"kagglehub": "1.0.2", "pyarrow": "26.0.0"},
        "tables": tables_meta,
    }
    (ingest_path / "_snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n", "utf-8")
    return ingest_path


def test_clean_writes_nine_typed_tables_excludes_three_and_strips_leakage_columns(
    project_dir: Path,
) -> None:
    write_ingest_fixture(project_dir / "data")

    result = invoke_clean()

    assert result.exit_code == 0, result.output
    out = project_dir / "data" / "clean"
    assert sorted(p.name for p in out.glob("*.parquet")) == [
        "appearances.parquet",
        "club_games.parquet",
        "clubs.parquet",
        "competitions.parquet",
        "game_lineups.parquet",
        "games.parquet",
        "player_valuations.parquet",
        "players.parquet",
        "transfers.parquet",
    ]
    assert (out / "_clean.json").is_file()

    players_schema = pq.read_schema(out / "players.parquet")
    assert players_schema.names == [
        "player_id",
        "first_name",
        "last_name",
        "name",
        "player_code",
        "country_of_birth",
        "city_of_birth",
        "country_of_citizenship",
        "date_of_birth",
        "sub_position",
        "position",
        "foot",
        "height_in_cm",
        "image_url",
        "url",
    ]
    clubs_schema = pq.read_schema(out / "clubs.parquet")
    assert clubs_schema.names == [
        "club_id",
        "club_code",
        "name",
        "domestic_competition_id",
        "stadium_name",
        "stadium_seats",
        "url",
    ]
    appearances_schema = pq.read_schema(out / "appearances.parquet")
    assert "player_current_club_id" not in appearances_schema.names
    assert appearances_schema.field("appearance_id").type == pa.string()
    assert appearances_schema.field("minutes_played").type == pa.int64()
    assert appearances_schema.field("date").type == pa.date32()


def test_clean_parses_dates_timestamps_decimals_booleans_and_unicode_whitespace(
    project_dir: Path,
) -> None:
    write_ingest_fixture(project_dir / "data")

    assert invoke_clean().exit_code == 0

    out = project_dir / "data" / "clean"
    players = pq.read_table(out / "players.parquet").to_pylist()
    assert players[0]["date_of_birth"] == dt.date(1998, 12, 20)
    assert players[0]["city_of_birth"] == "Opole"
    assert players[0]["height_in_cm"] == 185

    transfers = pq.read_table(out / "transfers.parquet").to_pylist()
    assert transfers[0]["transfer_fee"] == pytest.approx(15_500_000.0)
    assert transfers[0]["market_value_in_eur"] == pytest.approx(12_000_000.0)
    assert transfers[1]["transfer_fee"] == 0.0
    assert transfers[1]["market_value_in_eur"] is None

    club_games = pq.read_table(out / "club_games.parquet").to_pylist()
    assert club_games[0]["is_win"] is True
    assert club_games[1]["is_win"] is False
    assert club_games[1]["own_goals"] == 0

    lineups = pq.read_table(out / "game_lineups.parquet").to_pylist()
    assert lineups[0]["player_name"] == "Forward One"
    assert lineups[0]["team_captain"] is True
    assert lineups[0]["number"] == 9
    assert lineups[1]["team_captain"] is False


def test_clean_maps_sentinels_and_empty_strings_to_null(project_dir: Path) -> None:
    players_row = dict(BASE_TABLES["players"][1][0], foot="")
    write_ingest_fixture(project_dir / "data", overrides={"players": [players_row]})

    assert invoke_clean().exit_code == 0

    out = project_dir / "data" / "clean"
    lineups = pq.read_table(out / "game_lineups.parquet").to_pylist()
    assert lineups[1]["number"] is None
    assert lineups[1]["position"] is None

    competitions = pq.read_table(out / "competitions.parquet").to_pylist()
    by_id = {row["competition_id"]: row for row in competitions}
    assert by_id["IT1"]["country_id"] == 75
    assert by_id["CL"]["country_id"] is None

    players = pq.read_table(out / "players.parquet").to_pylist()
    assert players[0]["foot"] is None

    manifest = json.loads((out / "_clean.json").read_text(encoding="utf-8"))
    assert manifest["tables"]["game_lineups"]["nulled_cells"] == 2
    assert manifest["tables"]["competitions"]["nulled_cells"] == 1
    assert manifest["tables"]["players"]["nulled_cells"] == 1
    assert manifest["tables"]["players"]["stripped_cells"] == 1


def test_clean_applies_row_filters_minutes_cap_and_height_outlier_nulling(
    project_dir: Path,
) -> None:
    base_app = BASE_TABLES["appearances"][1][0]
    appearances_rows = [
        dict(base_app, appearance_id="100_1", minutes_played="90"),
        dict(base_app, appearance_id="100_2", minutes_played="0"),
        dict(base_app, appearance_id="100_3", minutes_played="-3"),
        dict(base_app, appearance_id="100_4", minutes_played="126"),
    ]
    base_val = BASE_TABLES["player_valuations"][1][0]
    valuation_rows = [
        dict(base_val, player_id="1", date="2024-06-01", market_value_in_eur="500000"),
        dict(base_val, player_id="2", date="2024-06-01", market_value_in_eur="0"),
        dict(base_val, player_id="3", date="2024-06-01", market_value_in_eur="-50"),
        dict(base_val, player_id="4", date="2024-06-01", market_value_in_eur=None),
    ]
    base_player = BASE_TABLES["players"][1][0]
    player_rows = [
        dict(base_player, player_id="1", position="Attack", height_in_cm="185"),
        dict(base_player, player_id="2", position="Midfield", height_in_cm="139"),
        dict(base_player, player_id="3", position="Defender", height_in_cm="0"),
        dict(base_player, player_id="4", position="Defender", height_in_cm="140"),
        dict(base_player, player_id="5", position="Goalkeeper", height_in_cm="192"),
        dict(base_player, player_id="6", position="Missing", height_in_cm="180"),
        dict(base_player, player_id="7", position="Attack", date_of_birth=None),
        dict(base_player, player_id="8", position="Goalkeeper", date_of_birth=""),
    ]
    write_ingest_fixture(
        project_dir / "data",
        overrides={
            "appearances": appearances_rows,
            "player_valuations": valuation_rows,
            "players": player_rows,
        },
    )

    assert invoke_clean().exit_code == 0

    out = project_dir / "data" / "clean"
    apps = pq.read_table(out / "appearances.parquet").to_pylist()
    assert [(r["appearance_id"], r["minutes_played"]) for r in apps] == [
        ("100_1", 90),
        ("100_4", 120),
    ]

    vals = pq.read_table(out / "player_valuations.parquet").to_pylist()
    assert [r["player_id"] for r in vals] == [1]

    players = pq.read_table(out / "players.parquet").to_pylist()
    assert [(r["player_id"], r["height_in_cm"]) for r in players] == [
        (1, 185),
        (2, None),
        (3, None),
        (4, 140),
    ]

    manifest = json.loads((out / "_clean.json").read_text(encoding="utf-8"))
    assert manifest["tables"]["appearances"]["dropped_rows"] == 2
    assert manifest["tables"]["appearances"]["capped_rows"] == 1
    assert manifest["tables"]["player_valuations"]["dropped_rows"] == 3
    assert manifest["tables"]["players"]["input_rows"] == 8
    assert manifest["tables"]["players"]["output_rows"] == 4
    assert manifest["tables"]["players"]["dropped_rows"] == 4
    assert manifest["tables"]["players"]["nulled_cells"] == 2


def test_clean_manifest_records_provenance_tool_versions_and_counts(project_dir: Path) -> None:
    write_ingest_fixture(project_dir / "data")

    assert invoke_clean().exit_code == 0

    manifest = json.loads((project_dir / "data" / "clean" / "_clean.json").read_text("utf-8"))
    assert manifest["dataset"] == "davidcariboo/player-scores"
    assert manifest["version"] == 679
    assert (
        manifest["source_snapshot_sha256"]
        == "94f42930f5d50d76f5226f64bd2b9e4c70552e110ad28743b5edce4041c8b1c1"
    )
    assert manifest["cleaned_at"].endswith("Z")
    assert set(manifest["tool_versions"]) == {"pandas", "pyarrow"}
    assert manifest["excluded_tables"] == ["countries", "game_events", "national_teams"]
    assert len(manifest["tables"]) == 9
    players_info = manifest["tables"]["players"]
    assert len(players_info["dropped_columns"]) == 11
    assert players_info["columns"] == 15
    assert players_info["dtypes"]["date_of_birth"] == "date32[day]"
    assert players_info["dtypes"]["player_id"] == "int64"


def test_clean_fails_when_ingest_snapshot_or_required_table_is_missing(project_dir: Path) -> None:
    missing_res = invoke_clean()
    assert missing_res.exit_code == 1
    assert "clean failed:" in missing_res.output
    assert "_snapshot.json" in missing_res.output

    write_ingest_fixture(project_dir / "data", omit_tables=["transfers"])
    omitted_res = invoke_clean()
    assert omitted_res.exit_code == 1
    assert "clean failed:" in omitted_res.output
    assert "transfers" in omitted_res.output


def test_clean_fails_on_duplicate_primary_keys_even_before_row_filtering(
    project_dir: Path,
) -> None:
    base_player = BASE_TABLES["players"][1][0]
    dup_players = [
        dict(base_player, player_id="1", position="Attack"),
        dict(base_player, player_id="1", position="Goalkeeper"),
    ]
    write_ingest_fixture(project_dir / "data", overrides={"players": dup_players})

    res = invoke_clean()
    assert res.exit_code == 1
    assert "clean failed:" in res.output
    assert "duplicate primary key" in res.output
    assert "players" in res.output

    base_val = BASE_TABLES["player_valuations"][1][0]
    write_ingest_fixture(
        project_dir / "data",
        overrides={"player_valuations": [base_val, dict(base_val, market_value_in_eur="900000")]},
    )
    val_res = invoke_clean()
    assert val_res.exit_code == 1
    assert "duplicate primary key" in val_res.output
    assert "player_valuations" in val_res.output


@pytest.mark.parametrize(
    ("table_name", "patch", "expected_fragment"),
    [
        ("appearances", {"minutes_played": "12.5"}, "appearances.minutes_played"),
        ("club_games", {"is_win": "True"}, "club_games.is_win"),
        ("players", {"date_of_birth": "2023-02-29 00:00:00"}, "players.date_of_birth"),
        ("appearances", {"goals": "-1"}, "appearances.goals"),
        ("transfers", {"transfer_fee": "-100.000"}, "transfers.transfer_fee"),
        ("games", {"home_club_id": None}, "games.home_club_id"),
    ],
)
def test_clean_fails_on_invalid_values_or_null_required_fields(
    project_dir: Path,
    table_name: str,
    patch: dict[str, str | None],
    expected_fragment: str,
) -> None:
    base_rows = list(BASE_TABLES[table_name][1])
    base_rows[0] = dict(base_rows[0], **patch)
    write_ingest_fixture(project_dir / "data", overrides={table_name: base_rows})

    res = invoke_clean()

    assert res.exit_code == 1
    assert "clean failed:" in res.output
    assert expected_fragment in res.output


def test_clean_rejects_schema_drift_and_non_string_ingest_columns(project_dir: Path) -> None:
    bad_schema = pa.schema(
        [(col, pa.int64() if col == "club_id" else pa.string()) for col in BASE_TABLES["clubs"][0]]
    )
    clubs_row: RowDict = dict(BASE_TABLES["clubs"][1][0])
    clubs_row["club_id"] = 10
    write_ingest_fixture(
        project_dir / "data",
        overrides={"clubs": [clubs_row]},
        schema_overrides={"clubs": bad_schema},
    )

    non_str_res = invoke_clean()
    assert non_str_res.exit_code == 1
    assert "string" in non_str_res.output

    extra_cols = [*BASE_TABLES["clubs"][0], "future_leak_column"]
    extra_schema = pa.schema([(col, pa.string()) for col in extra_cols])
    extra_row = dict(BASE_TABLES["clubs"][1][0], future_leak_column="oops")
    write_ingest_fixture(
        project_dir / "data",
        overrides={"clubs": [extra_row]},
        schema_overrides={"clubs": extra_schema},
    )

    drift_res = invoke_clean()
    assert drift_res.exit_code == 1
    assert "future_leak_column" in drift_res.output


def test_clean_preserves_previous_output_on_failure_and_checks_ownership(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom_dir = project_dir / "custom_data"
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(custom_dir))
    write_ingest_fixture(custom_dir)

    first = invoke_clean()
    assert first.exit_code == 0, first.output
    before_manifest = (custom_dir / "clean" / "_clean.json").read_text(encoding="utf-8")

    bad_games = [dict(BASE_TABLES["games"][1][0], season="not-an-int")]
    write_ingest_fixture(custom_dir, overrides={"games": bad_games})
    failed = invoke_clean()
    assert failed.exit_code == 1
    assert (custom_dir / "clean" / "_clean.json").read_text(encoding="utf-8") == before_manifest
    assert list(custom_dir.glob(".clean-staging-*")) == []

    unowned_dir = project_dir / "unowned_data"
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(unowned_dir))
    write_ingest_fixture(unowned_dir)
    (unowned_dir / "clean").mkdir(parents=True)
    (unowned_dir / "clean" / "handwritten.txt").write_text("keep", encoding="utf-8")

    refused = invoke_clean()
    assert refused.exit_code == 1
    assert "refusing to replace" in refused.output
    assert (unowned_dir / "clean" / "handwritten.txt").is_file()


def test_clean_recovers_complete_retired_copy_when_target_is_missing(project_dir: Path) -> None:
    data_dir = project_dir / "data"
    write_ingest_fixture(data_dir)
    assert invoke_clean().exit_code == 0

    clean_dir = data_dir / "clean"
    retired_dir = data_dir / ".clean-retired-deadbeef"
    clean_dir.rename(retired_dir)
    (data_dir / "ingest" / "_snapshot.json").unlink()

    res = invoke_clean()

    assert res.exit_code == 1
    assert "restored" in res.output
    assert (clean_dir / "_clean.json").is_file()
    assert not retired_dir.exists()


def test_clean_fails_when_parquet_row_count_disagrees_with_snapshot(project_dir: Path) -> None:
    ingest_path = write_ingest_fixture(project_dir / "data")
    snapshot_file = ingest_path / "_snapshot.json"
    snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
    snapshot["tables"]["players"]["rows"] = 999
    snapshot_file.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

    res = invoke_clean()

    assert res.exit_code == 1
    assert "clean failed:" in res.output
    assert "row count" in res.output
    assert "Traceback" not in res.output


def test_clean_maps_stripped_dash_sentinel_in_city_of_birth_without_double_counting(
    project_dir: Path,
) -> None:
    players_row = dict(BASE_TABLES["players"][1][0], city_of_birth="-\xa0\xa0")
    write_ingest_fixture(project_dir / "data", overrides={"players": [players_row]})

    res = invoke_clean()
    assert res.exit_code == 0, res.output

    out = project_dir / "data" / "clean"
    players = pq.read_table(out / "players.parquet").to_pylist()
    assert players[0]["city_of_birth"] is None

    manifest = json.loads((out / "_clean.json").read_text(encoding="utf-8"))
    assert manifest["tables"]["players"]["nulled_cells"] == 1
    assert manifest["tables"]["players"]["stripped_cells"] == 0


def test_clean_enforces_exact_arrow_schema_and_nullability_across_all_nine_tables(
    project_dir: Path,
) -> None:
    write_ingest_fixture(project_dir / "data")
    assert invoke_clean().exit_code == 0

    out = project_dir / "data" / "clean"
    arrow_types = clean_module._ARROW_TYPES
    for spec in clean_module.TABLE_SPECS:
        schema = pq.read_schema(out / f"{spec.name}.parquet")
        actual = [(field.name, field.type, field.nullable) for field in schema]
        expected = [(col.name, arrow_types[col.kind], col.nullable) for col in spec.columns]
        assert actual == expected, spec.name


@pytest.mark.parametrize(
    ("table_name", "patch", "expected_fragment"),
    [
        ("appearances", {"game_id": "9223372036854775808"}, "appearances.game_id"),
        ("players", {"height_in_cm": "99999999999999999999"}, "players.height_in_cm"),
        ("players", {"date_of_birth": "1998-12-20 99:88:77"}, "players.date_of_birth"),
        ("players", {"position": "Wingback"}, "players.position"),
        ("player_valuations", {"date": None}, "null primary key"),
        ("appearances", {"minutes_played": None}, "appearances.minutes_played"),
        ("players", {"position": None}, "players.position"),
    ],
)
def test_clean_rejects_int64_overflow_bad_timestamps_unknown_positions_and_null_keys(
    project_dir: Path,
    table_name: str,
    patch: dict[str, str | None],
    expected_fragment: str,
) -> None:
    base_rows = list(BASE_TABLES[table_name][1])
    base_rows[0] = dict(base_rows[0], **patch)
    write_ingest_fixture(project_dir / "data", overrides={table_name: base_rows})

    res = invoke_clean()

    assert res.exit_code == 1
    assert "clean failed:" in res.output
    assert expected_fragment in res.output
    assert "Traceback" not in res.output


def test_clean_keeps_exact_120_minutes_uncapped_and_validates_snapshot_alignment(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_row = dict(BASE_TABLES["appearances"][1][0], minutes_played="120")
    ingest_path = write_ingest_fixture(
        project_dir / "data",
        overrides={"appearances": [app_row]},
        omit_tables=["game_events"],
    )
    ok_res = invoke_clean()
    assert ok_res.exit_code == 0, ok_res.output
    manifest = json.loads((project_dir / "data" / "clean" / "_clean.json").read_text("utf-8"))
    assert manifest["tables"]["appearances"]["capped_rows"] == 0
    assert manifest["excluded_tables"] == ["countries", "national_teams"]

    monkeypatch.setenv("DELPHOS_KAGGLE_DATASET_VERSION", "680")
    mismatch = invoke_clean()
    assert mismatch.exit_code == 1
    assert "680" in mismatch.output
    assert "Traceback" not in mismatch.output

    monkeypatch.setenv("DELPHOS_KAGGLE_DATASET_VERSION", "not-an-int")
    bad_cfg = invoke_clean()
    assert bad_cfg.exit_code == 1
    assert "clean failed:" in bad_cfg.output
    assert "Traceback" not in bad_cfg.output

    monkeypatch.delenv("DELPHOS_KAGGLE_DATASET_VERSION")
    snapshot_file = ingest_path / "_snapshot.json"
    snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
    snapshot["version"] = True
    snapshot_file.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    bool_ver = invoke_clean()
    assert bool_ver.exit_code == 1
    assert "snapshot" in bool_ver.output

    snapshot["version"] = 679
    snapshot["tables"]["unexpected_table"] = {"rows": 1}
    snapshot_file.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    extra_tbl = invoke_clean()
    assert extra_tbl.exit_code == 1
    assert "unexpected_table" in extra_tbl.output


def test_clean_replaces_existing_output_and_handles_swap_rollback_and_incomplete_retired(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = project_dir / "data"
    write_ingest_fixture(data_dir)
    assert invoke_clean().exit_code == 0
    assert invoke_clean().exit_code == 0
    assert list(data_dir.glob(".clean-retired-*")) == []

    real_rename = Path.rename
    calls = 0

    def fail_on_staging_swap(self: Path, target: Path) -> Path:
        nonlocal calls
        calls += 1
        if self.name.startswith(".clean-staging-"):
            raise PermissionError("simulated lock on target")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_on_staging_swap)
    rolled_back = invoke_clean()
    assert rolled_back.exit_code == 1
    assert "previous output was put back" in rolled_back.output
    assert (data_dir / "clean" / "_clean.json").is_file()
    assert calls >= 2
    monkeypatch.undo()

    import shutil as std_shutil

    std_shutil.rmtree(data_dir / "clean")
    incomplete = data_dir / ".clean-retired-broken"
    incomplete.mkdir()
    (incomplete / "_clean.json").write_text("{}", encoding="utf-8")
    recovered = invoke_clean()
    assert recovered.exit_code == 0, recovered.output
    assert "discarding .clean-retired-broken" in recovered.output
    assert not incomplete.exists()
