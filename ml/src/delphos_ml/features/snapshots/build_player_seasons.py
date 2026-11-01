"""Option A end-of-season player-season snapshot rows for the `transform` stage.

Input: the typed `player_valuations` and `players` frames from `data/clean/`, the `club_games`
and `games` frames for point-in-time league position, and the shared trailing-window indexes.
Output: one row per `(player_id, season)` holding the anchor date and split, the point-in-time
club and league, the raw trailing-window counts (plus domestic-cup minutes), the biography
fields, and the log10 market-value target — ready for the stage's deterministic derivations.
Responsibility: enforce the population rules of docs/ML_ARCHITECTURE.md sections 3.2 and 3.3 —
latest valuation per July-to-June season in the 14 covered leagues, outfield players only,
`>= minutes_floor` trailing minutes — without learning any statistic from the data.

This module also owns the two small helpers shared with `build_transfer_events`: renaming a
`TrailingWindowIndex` query into schema metric columns (plus domestic-cup minutes, read from a
second cup-only index instance so the 13 public metrics stay byte-identical for
`analysis/eda.py`) and the point-in-time club league-position lookup. Both builders need them
and the two populations are one concept, so they live here instead of a file each.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from delphos_ml.features.snapshots.season import assign_split, season_of
from delphos_ml.features.windows import TrailingWindowIndex
from delphos_ml.features.windows.trailing_window_index import EPOCH_ANCHOR

COVERED_LEAGUE_IDS: frozenset[str] = frozenset(
    {
        "IT1",
        "ES1",
        "GB1",
        "FR1",
        "TR1",
        "L1",
        "NL1",
        "PO1",
        "BE1",
        "RU1",
        "GR1",
        "SC1",
        "UKR1",
        "DK1",
    }
)
OUTFIELD_POSITIONS: frozenset[str] = frozenset({"Defender", "Midfield", "Attack"})
FIRST_SEASON = 2017
LAST_SEASON = 2025

_BIO_COLUMNS: tuple[str, ...] = (
    "player_id",
    "date_of_birth",
    "position",
    "sub_position",
    "foot",
    "height_in_cm",
    "country_of_citizenship",
)

_WINDOW_METRIC_RENAME: dict[str, str] = {
    "minutes_played": "minutes",
    "apps_count": "apps",
    "starts": "starts",
    "captain": "captain",
    "squad_inclusions": "squad_inclusions",
    "goals": "goals",
    "assists": "assists",
    "yellow_cards": "yellow_cards",
    "red_cards": "red_cards",
    "win_flag": "win_flag",
    "clean_sheet_flag": "clean_sheet_flag",
    "goals_conceded": "goals_conceded",
    "uefa_minutes": "uefa_minutes",
}
WINDOW_METRIC_COLUMNS: tuple[str, ...] = tuple(_WINDOW_METRIC_RENAME.values())


def _window_row_metrics(
    window: TrailingWindowIndex,
    cup_window: TrailingWindowIndex,
    pids: np.ndarray,
    days: np.ndarray,
    *,
    strict_before: bool,
) -> pd.DataFrame:
    """Return the schema-named window metrics plus domestic-cup minutes per anchor row."""
    metrics = window.query(pids, days, strict_before=strict_before)
    cup_minutes = cup_window.query(pids, days, strict_before=strict_before)["minutes_played"]
    columns: dict[str, np.ndarray] = {
        new_name: metrics[old_name] for old_name, new_name in _WINDOW_METRIC_RENAME.items()
    }
    columns["cup_minutes"] = cup_minutes
    return pd.DataFrame(columns)


class _LatestClubPositions:
    """Point-in-time `club_games.own_position`: each club's latest game on or before a day.

    `club_games` carries no date, so the lookup joins `games` for game dates. When the club
    has no game on or before the anchor day (or that game's `own_position` is null) the
    position is NaN and the caller sets its missing flag.
    """

    def __init__(self, club_games: pd.DataFrame, games: pd.DataFrame) -> None:
        cg = club_games[["game_id", "club_id", "own_position"]].merge(
            games[["game_id", "date"]], on="game_id", how="left"
        )
        cg["day"] = (pd.to_datetime(cg["date"]) - EPOCH_ANCHOR).dt.days
        cg = cg.dropna(subset=["club_id", "day"])
        cg = cg.sort_values(["club_id", "day", "game_id"]).drop_duplicates(
            subset=["club_id", "day"], keep="last"
        )
        self._by_club: dict[int, tuple[np.ndarray, np.ndarray]] = {
            int(club_id): (
                group["day"].to_numpy(dtype=np.int64),
                group["own_position"].astype("float64").to_numpy(dtype=np.float64),
            )
            for club_id, group in cg.groupby("club_id", sort=True)
        }

    def position_at(self, club_ids: np.ndarray, days: np.ndarray) -> np.ndarray:
        """Return each club's last recorded `own_position` on or before `days` (NaN if none)."""
        out = np.full(len(club_ids), np.nan, dtype=np.float64)
        anchors = pd.DataFrame({"club_id": club_ids, "day": days})
        for club_id, group in anchors.groupby("club_id", sort=False):
            entry = self._by_club.get(int(club_id))
            if entry is None:
                continue
            club_days, positions = entry
            idx = np.searchsorted(club_days, group["day"].to_numpy(dtype=np.int64), side="right")
            hit = idx > 0
            out[group.index.to_numpy()] = np.where(hit, positions[np.maximum(idx - 1, 0)], np.nan)
        return out


def build_player_seasons(
    valuations: pd.DataFrame,
    players: pd.DataFrame,
    club_games: pd.DataFrame,
    games: pd.DataFrame,
    window: TrailingWindowIndex,
    cup_window: TrailingWindowIndex,
    *,
    minutes_floor: int,
) -> pd.DataFrame:
    """Build the Option A player-season rows from the cleaned valuation frames.

    One row per `(player_id, season)` anchored on the player's latest `player_valuations.date`
    within that July-to-June season (`as_of_date`), restricted to the 14 covered leagues and
    outfield players, requiring `>= minutes_floor` trailing minutes in the valuation window
    `(as_of_date - 365, as_of_date]`. Club and league come only from the anchor valuation row;
    biography only from `players`. Rows are sorted by `(player_id, season)`.
    """
    vals = valuations[
        [
            "player_id",
            "date",
            "market_value_in_eur",
            "current_club_id",
            "player_club_domestic_competition_id",
        ]
    ].copy()
    vals["season"] = season_of(vals["date"])
    vals = vals.loc[vals["season"].between(FIRST_SEASON, LAST_SEASON)]
    vals = vals.loc[vals["player_club_domestic_competition_id"].isin(COVERED_LEAGUE_IDS)]
    vals = vals.merge(players[list(_BIO_COLUMNS)], on="player_id", how="inner")
    vals = vals.loc[vals["position"].isin(OUTFIELD_POSITIONS)]
    vals["day"] = (vals["date"] - EPOCH_ANCHOR).dt.days
    vals = (
        vals.sort_values(["player_id", "season", "day"])
        .drop_duplicates(subset=["player_id", "season"], keep="last")
        .reset_index(drop=True)
    )

    out = pd.concat(
        [
            vals,
            _window_row_metrics(
                window,
                cup_window,
                vals["player_id"].to_numpy(dtype=np.int64),
                vals["day"].to_numpy(dtype=np.int64),
                strict_before=False,
            ),
        ],
        axis=1,
    )
    out = out.loc[out["minutes"] >= minutes_floor].reset_index(drop=True)

    positions = _LatestClubPositions(club_games, games).position_at(
        out["current_club_id"].to_numpy(dtype=np.int64),
        out["day"].to_numpy(dtype=np.int64),
    )
    out["league_position"] = positions
    out["league_position_missing"] = np.isnan(positions)
    out["age"] = (out["date"] - out["date_of_birth"]).dt.days / 365.25
    out["log10_market_value"] = np.log10(out["market_value_in_eur"].astype("float64"))

    return pd.DataFrame(
        {
            "player_id": out["player_id"].astype("int64"),
            "season": out["season"].astype("int64"),
            "as_of_date": out["date"],
            "split": assign_split(out["season"]),
            "club_id": out["current_club_id"].astype("int64"),
            "league_id": out["player_club_domestic_competition_id"],
            **{name: out[name] for name in WINDOW_METRIC_COLUMNS},
            "cup_minutes": out["cup_minutes"],
            "league_position": out["league_position"],
            "league_position_missing": out["league_position_missing"],
            "age": out["age"],
            "height_in_cm": out["height_in_cm"].astype("float64"),
            "foot": out["foot"],
            "position": out["position"],
            "sub_position": out["sub_position"],
            "country_of_citizenship": out["country_of_citizenship"],
            "log10_market_value": out["log10_market_value"],
        }
    )
