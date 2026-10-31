"""Unit tests for `TrailingWindowIndex`, the trailing-365-day window index.

The fixtures are tiny synthetic frames shaped like the `ingest` outputs. Day offsets are
expressed from the 1900-01-01 epoch anchor the index uses internally, so a window boundary
is a plain integer offset from the query's as-of day.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from delphos_ml.features.windows import TrailingWindowIndex

EPOCH_ANCHOR = pd.Timestamp("1900-01-01")

ALL_METRICS = {
    "minutes_played",
    "goals",
    "assists",
    "yellow_cards",
    "red_cards",
    "apps_count",
    "win_flag",
    "clean_sheet_flag",
    "goals_conceded",
    "uefa_minutes",
    "starts",
    "squad_inclusions",
    "captain",
}


def _date(day: int) -> str:
    """Format a day offset from the epoch anchor as an ingest-style date string."""
    return (EPOCH_ANCHOR + pd.Timedelta(days=day)).strftime("%Y-%m-%d")


def _make_index(
    app_rows: list[dict[str, object]],
    *,
    club_game_rows: list[dict[str, object]] | None = None,
    lineup_rows: list[dict[str, object]] | None = None,
    comp_rows: list[dict[str, object]] | None = None,
) -> TrailingWindowIndex:
    """Build an index over minimal frames; games without a club_games row behave as misses."""
    apps = pd.DataFrame(app_rows)
    club_games = (
        pd.DataFrame(club_game_rows)
        if club_game_rows is not None
        else pd.DataFrame(
            {
                "game_id": pd.Series(dtype="int64"),
                "club_id": pd.Series(dtype="int64"),
                "own_goals": pd.Series(dtype="object"),
                "opponent_goals": pd.Series(dtype="object"),
                "is_win": pd.Series(dtype="object"),
            }
        )
    )
    lineups = (
        pd.DataFrame(lineup_rows)
        if lineup_rows is not None
        else pd.DataFrame(
            {
                "player_id": pd.Series(dtype="object"),
                "date": pd.Series(dtype="object"),
                "type": pd.Series(dtype="object"),
                "team_captain": pd.Series(dtype="object"),
            }
        )
    )
    comps = (
        pd.DataFrame(comp_rows)
        if comp_rows is not None
        else pd.DataFrame({"competition_id": ["L1"], "type": ["domestic_league"], "sub_type": [""]})
    )
    return TrailingWindowIndex(apps, club_games, lineups, comps)


def _app(
    game_id: int,
    player_id: int,
    day: int,
    minutes: float,
    *,
    club_id: int = 10,
    competition_id: str = "L1",
    goals: float = 0.0,
    assists: float = 0.0,
    yellow: float = 0.0,
    red: float = 0.0,
) -> dict[str, object]:
    return {
        "game_id": game_id,
        "player_id": player_id,
        "player_club_id": club_id,
        "date": _date(day),
        "competition_id": competition_id,
        "minutes_played": minutes,
        "goals": goals,
        "assists": assists,
        "yellow_cards": yellow,
        "red_cards": red,
    }


def _query(index: TrailingWindowIndex, player_id: int, day: int, *, strict_before: bool) -> dict:
    out = index.query(
        np.array([player_id], dtype=np.int64),
        np.array([day], dtype=np.int64),
        strict_before=strict_before,
    )
    return {key: float(value[0]) for key, value in out.items()}


def test_window_includes_the_as_of_day_and_the_previous_364_days() -> None:
    as_of = 45_000
    index = _make_index(
        [
            _app(1, 1, as_of - 364, 90.0),
            _app(2, 1, as_of - 1, 60.0),
            _app(3, 1, as_of, 30.0),
        ]
    )

    result = _query(index, 1, as_of, strict_before=False)

    assert result["minutes_played"] == 180.0
    assert result["apps_count"] == 3.0


def test_window_excludes_matches_at_or_before_day_minus_365() -> None:
    as_of = 45_000
    index = _make_index(
        [
            _app(1, 1, as_of - 366, 90.0),
            _app(2, 1, as_of - 365, 45.0),
            _app(3, 1, as_of - 1, 60.0),
        ]
    )

    result = _query(index, 1, as_of, strict_before=False)

    # The valuation window as implemented is `(as_of - 365, as_of]`: half-open at the low
    # end. docs/TRANSFORM_PLAN.md describes it as closed `[as_of - 365, as_of]`; the code
    # that produced the recorded EDA figures excludes the exact boundary, so the refactor
    # preserves that behaviour.
    assert result["minutes_played"] == 60.0


def test_strict_before_excludes_the_as_of_day_and_includes_day_minus_365() -> None:
    as_of = 45_000
    index = _make_index(
        [
            _app(1, 1, as_of - 365, 90.0),
            _app(2, 1, as_of - 1, 60.0),
            _app(3, 1, as_of, 30.0),
        ]
    )

    result = _query(index, 1, as_of, strict_before=True)

    # Transfer window as implemented is `[transfer_day - 365, transfer_day - 1]`.
    assert result["minutes_played"] == 150.0
    assert result["apps_count"] == 2.0


def test_windows_do_not_bleed_across_players() -> None:
    as_of = 45_000
    index = _make_index(
        [
            _app(1, 1, as_of - 5, 100.0),
            _app(2, 2, as_of - 5, 200.0),
        ]
    )

    first = _query(index, 1, as_of, strict_before=False)
    second = _query(index, 2, as_of, strict_before=False)

    assert first["minutes_played"] == 100.0
    assert second["minutes_played"] == 200.0
    assert first["goals"] == 0.0
    assert second["goals"] == 0.0


def test_player_without_rows_in_the_window_gets_zeros() -> None:
    as_of = 45_000
    index = _make_index([_app(1, 1, as_of - 5, 90.0)])

    missing_player = _query(index, 99, as_of, strict_before=False)
    before_all_rows = _query(index, 1, as_of - 1_000, strict_before=True)

    for result in (missing_player, before_all_rows):
        assert set(result) == ALL_METRICS
        assert all(value == 0.0 for value in result.values())


def test_metric_sums_match_hand_computed_values() -> None:
    as_of = 45_000
    index = _make_index(
        [
            # Domestic league win: 90 minutes, 1 goal, 1 yellow, clean sheet.
            _app(101, 1, as_of - 10, 90.0, goals=1.0, yellow=1.0),
            # UEFA cup loss: 60 minutes, 1 assist, 1 red, 2 goals conceded.
            _app(
                102,
                1,
                as_of - 5,
                60.0,
                competition_id="UC1",
                assists=1.0,
                red=1.0,
            ),
            # Domestic league win: 45 minutes, 2 goals.
            _app(103, 1, as_of - 2, 45.0, goals=2.0),
        ],
        club_game_rows=[
            {"game_id": 101, "club_id": 10, "own_goals": "2", "opponent_goals": "0", "is_win": "1"},
            {"game_id": 102, "club_id": 10, "own_goals": "1", "opponent_goals": "2", "is_win": "0"},
            {"game_id": 103, "club_id": 10, "own_goals": "3", "opponent_goals": "0", "is_win": "1"},
        ],
        lineup_rows=[
            {
                "player_id": "1",
                "date": _date(as_of - 10),
                "type": "starting_lineup",
                "team_captain": "1",
            },
            {"player_id": "1", "date": _date(as_of - 2), "type": "substitute", "team_captain": "0"},
        ],
        comp_rows=[
            {"competition_id": "L1", "type": "domestic_league", "sub_type": ""},
            {"competition_id": "UC1", "type": "international_cup", "sub_type": ""},
        ],
    )

    result = _query(index, 1, as_of, strict_before=False)

    assert result == {
        "minutes_played": 195.0,
        "goals": 3.0,
        "assists": 1.0,
        "yellow_cards": 1.0,
        "red_cards": 1.0,
        "apps_count": 3.0,
        "win_flag": 2.0,
        "clean_sheet_flag": 2.0,
        "goals_conceded": 2.0,
        "uefa_minutes": 60.0,
        "starts": 1.0,
        "squad_inclusions": 2.0,
        "captain": 1.0,
    }
