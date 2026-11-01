"""Unit tests for the snapshot builders: season calendar, split labels, and population rules.

The fixtures are tiny synthetic frames shaped like the `clean` outputs (datetime64 dates),
driving `build_player_seasons` and `build_transfer_events` through real
`TrailingWindowIndex` instances so window semantics are exercised end to end. Day offsets are
expressed from the 1900-01-01 epoch anchor the window index uses internally, so a window
boundary is a plain integer offset from the anchor's as-of day.
"""

from __future__ import annotations

import pandas as pd
import pytest

from delphos_ml.features.snapshots import (
    assign_split,
    build_player_seasons,
    build_transfer_events,
    season_of,
)
from delphos_ml.features.windows import TrailingWindowIndex
from delphos_ml.features.windows.trailing_window_index import EPOCH_ANCHOR

AS_OF = 45_000
COVERED_LEAGUES = ("L1", "ES1")


def _date(day: int) -> pd.Timestamp:
    """Return the timestamp `day` offsets from the epoch anchor the index uses internally."""
    return EPOCH_ANCHOR + pd.Timedelta(days=day)


def _app(
    game_id: int,
    player_id: int,
    day: int,
    minutes: float,
    *,
    club_id: int = 10,
    competition_id: str = "L1",
    goals: float = 0.0,
) -> dict[str, object]:
    return {
        "game_id": game_id,
        "player_id": player_id,
        "player_club_id": club_id,
        "date": _date(day).strftime("%Y-%m-%d"),
        "competition_id": competition_id,
        "minutes_played": minutes,
        "goals": goals,
        "assists": 0.0,
        "yellow_cards": 0.0,
        "red_cards": 0.0,
    }


def _index(app_rows: list[dict[str, object]]) -> tuple[TrailingWindowIndex, TrailingWindowIndex]:
    """Build indexes over minimal frames; games without club_games rows behave as misses."""
    apps = pd.DataFrame(app_rows)
    club_games = pd.DataFrame(
        {
            "game_id": pd.Series(dtype="int64"),
            "club_id": pd.Series(dtype="int64"),
            "own_goals": pd.Series(dtype="float64"),
            "opponent_goals": pd.Series(dtype="float64"),
            "is_win": pd.Series(dtype="object"),
        }
    )
    lineups = pd.DataFrame(
        {
            "player_id": pd.Series(dtype="object"),
            "date": pd.Series(dtype="object"),
            "type": pd.Series(dtype="object"),
            "team_captain": pd.Series(dtype="object"),
        }
    )
    comps = pd.DataFrame(
        {
            "competition_id": [*COVERED_LEAGUES, "CUP1"],
            "type": ["domestic_league", "domestic_league", "domestic_cup"],
            "sub_type": ["", "", ""],
        }
    )
    window = TrailingWindowIndex(apps, club_games, lineups, comps)
    cup_ids = {"CUP1"}
    cup_window = TrailingWindowIndex(
        apps.loc[apps["competition_id"].isin(cup_ids)], club_games, lineups, comps
    )
    return window, cup_window


def _valuations(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.astype(
        {
            "player_id": "int64",
            "market_value_in_eur": "float64",
            "current_club_id": "int64",
        }
    )


def _players(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["date_of_birth"] = pd.to_datetime(frame["date_of_birth"])
    return frame


def _player_row(player_id: int, position: str, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "player_id": player_id,
        "date_of_birth": _date(34_000),
        "position": position,
        "sub_position": "Centre-Forward" if position == "Attack" else None,
        "foot": "right",
        "height_in_cm": 180.0,
        "country_of_citizenship": "AR",
    }
    row.update(extra)
    return row


def _valuation_row(
    player_id: int, day: int, *, club_id: int = 10, league_id: str = "L1"
) -> dict[str, object]:
    return {
        "player_id": player_id,
        "date": _date(day),
        "market_value_in_eur": 1_000_000.0,
        "current_club_id": club_id,
        "player_club_domestic_competition_id": league_id,
    }


def _empty_club_games() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": pd.Series(dtype="int64"),
            "club_id": pd.Series(dtype="int64"),
            "own_position": pd.Series(dtype="float64"),
        }
    )


def _empty_games() -> pd.DataFrame:
    return pd.DataFrame(
        {"game_id": pd.Series(dtype="int64"), "date": pd.Series(dtype="datetime64[s]")}
    )


def _build_player_seasons(
    app_rows: list[dict[str, object]],
    valuation_rows: list[dict[str, object]],
    player_rows: list[dict[str, object]],
    *,
    minutes_floor: int = 180,
) -> pd.DataFrame:
    window, cup_window = _index(app_rows)
    return build_player_seasons(
        _valuations(valuation_rows),
        _players(player_rows),
        _empty_club_games(),
        _empty_games(),
        window,
        cup_window,
        minutes_floor=minutes_floor,
    )


def test_season_of_splits_june_and_july_into_different_seasons() -> None:
    seasons = season_of(pd.Series(pd.to_datetime(["2024-06-30", "2024-07-01", "2024-01-15"])))

    assert seasons.tolist() == [2023, 2024, 2023]


def test_assign_split_maps_the_decided_seasons_and_raises_on_the_rest() -> None:
    seasons = pd.Series(list(range(2017, 2026)), dtype="int64")

    assert assign_split(seasons).tolist() == ["train"] * 7 + ["validation", "test"]
    assert assign_split(2017) == "train"
    assert assign_split(2023) == "train"
    assert assign_split(2024) == "validation"
    assert assign_split(2025) == "test"
    with pytest.raises(ValueError, match="unknown season 2016"):
        assign_split(2016)
    with pytest.raises(ValueError, match="unknown season 2026"):
        assign_split(pd.Series([2024, 2026], dtype="int64"))


def test_minutes_floor_excludes_179_and_keeps_180() -> None:
    rows = _build_player_seasons(
        [
            _app(1, 1, AS_OF - 10, 90.0),
            _app(2, 1, AS_OF - 5, 89.0),
            _app(3, 2, AS_OF - 10, 90.0),
            _app(4, 2, AS_OF - 5, 90.0),
        ],
        [_valuation_row(1, AS_OF), _valuation_row(2, AS_OF)],
        [_player_row(1, "Attack"), _player_row(2, "Midfield")],
    )

    assert rows["player_id"].tolist() == [2]
    assert rows["minutes"].tolist() == [180.0]


def test_goalkeepers_and_uncovered_leagues_never_appear() -> None:
    rows = _build_player_seasons(
        [
            _app(1, 1, AS_OF - 10, 300.0),
            _app(2, 2, AS_OF - 10, 300.0, club_id=30, competition_id="MX1"),
        ],
        [
            _valuation_row(1, AS_OF),
            _valuation_row(2, AS_OF, club_id=30, league_id="MX1"),
        ],
        [_player_row(1, "Goalkeeper"), _player_row(2, "Attack")],
    )

    assert rows.empty


def test_no_row_aggregates_a_match_dated_after_its_as_of_date() -> None:
    rows = _build_player_seasons(
        [
            _app(1, 1, AS_OF - 10, 90.0, goals=1.0),
            _app(2, 1, AS_OF, 90.0),
            _app(3, 1, AS_OF + 10, 90.0, goals=5.0),
            _app(4, 1, AS_OF + 400, 90.0, goals=9.0),
        ],
        [_valuation_row(1, AS_OF)],
        [_player_row(1, "Attack")],
    )

    (row,) = rows.itertuples(index=False)
    assert row.as_of_date == _date(AS_OF)
    assert row.minutes == 180.0
    assert row.apps == 2.0
    assert row.goals == 1.0


def test_row_anchors_on_the_latest_valuation_of_the_season() -> None:
    rows = _build_player_seasons(
        [
            _app(1, 1, AS_OF - 200, 90.0),
            _app(2, 1, AS_OF - 10, 90.0),
        ],
        [
            _valuation_row(1, AS_OF - 30),
            _valuation_row(1, AS_OF),
        ],
        [_player_row(1, "Attack")],
    )

    (row,) = rows.itertuples(index=False)
    assert row.as_of_date == _date(AS_OF)
    # 2023-03-14 falls in season 2022, which is a train season.
    assert row.season == 2022
    assert row.split == "train"


def test_transfer_events_use_the_covered_club_and_strict_before_window() -> None:
    window, cup_window = _index(
        [
            _app(1, 1, AS_OF - 300, 90.0),
            _app(2, 1, AS_OF - 10, 90.0),
            _app(3, 1, AS_OF, 90.0),
        ]
    )
    clubs = pd.DataFrame({"club_id": [10, 20, 30], "domestic_competition_id": ["L1", "ES1", "MX1"]})
    transfers = pd.DataFrame(
        {
            "player_id": [1, 1],
            "transfer_date": pd.to_datetime([_date(AS_OF), _date(AS_OF)]),
            "from_club_id": [10, 30],
            "to_club_id": [30, 10],
            "transfer_fee": [5_000_000.0, 5_000_000.0],
            "market_value_in_eur": [2_500_000.0, 2_500_000.0],
        }
    )

    rows = build_transfer_events(
        transfers,
        _players([_player_row(1, "Attack")]),
        clubs,
        _empty_club_games(),
        _empty_games(),
        window,
        cup_window,
        minutes_floor=180,
    )

    # Both transfers involve a covered club: the first takes the covered selling club 10
    # (to_club 30 is uncovered), the second takes the covered buying club 10.
    assert rows["club_id"].tolist() == [10, 10]
    assert rows["league_id"].tolist() == ["L1", "L1"]
    # The window is [transfer_day - 365, transfer_day - 1]: the match on the transfer day
    # itself is excluded, so only the two earlier matches count. 2023-03-14 is a train season.
    assert rows["minutes"].tolist() == [180.0, 180.0]
    assert rows["split"].tolist() == ["train", "train"]


def test_transfer_events_drop_free_transfers_and_uncovered_only_moves() -> None:
    window, cup_window = _index([_app(1, 1, AS_OF - 10, 300.0)])
    clubs = pd.DataFrame({"club_id": [30, 40], "domestic_competition_id": ["MX1", "BR1"]})
    transfers = pd.DataFrame(
        {
            "player_id": [1, 1],
            "transfer_date": pd.to_datetime([_date(AS_OF), _date(AS_OF)]),
            "from_club_id": [30, 30],
            "to_club_id": [40, 40],
            "transfer_fee": [0.0, 9_000_000.0],
            "market_value_in_eur": [2_500_000.0, 2_500_000.0],
        }
    )

    rows = build_transfer_events(
        transfers,
        _players([_player_row(1, "Attack")]),
        clubs,
        _empty_club_games(),
        _empty_games(),
        window,
        cup_window,
        minutes_floor=180,
    )

    assert rows.empty


def test_league_position_uses_the_latest_game_on_or_before_the_anchor() -> None:
    club_games = pd.DataFrame(
        {
            "game_id": [1, 2],
            "club_id": [10, 10],
            "own_position": [5.0, 3.0],
        }
    )
    games = pd.DataFrame(
        {
            "game_id": [1, 2],
            "date": pd.to_datetime([_date(AS_OF - 200), _date(AS_OF - 10)]),
        }
    )
    window, cup_window = _index([_app(1, 1, AS_OF - 10, 90.0), _app(2, 1, AS_OF - 5, 90.0)])

    rows = build_player_seasons(
        _valuations([_valuation_row(1, AS_OF)]),
        _players([_player_row(1, "Attack")]),
        club_games,
        games,
        window,
        cup_window,
        minutes_floor=180,
    )

    (row,) = rows.itertuples(index=False)
    assert row.league_position == 3.0
    assert not row.league_position_missing
