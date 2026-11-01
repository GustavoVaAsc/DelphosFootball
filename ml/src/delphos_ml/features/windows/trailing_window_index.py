"""Trailing-365-day per-player window index over the ingest appearance and lineup frames.

Input: the raw `appearances`, `club_games`, `game_lineups` and `competitions` frames from
`data/ingest/`.
Output: a `TrailingWindowIndex` whose `query()` returns per-request `(player_id, day)` sums
of the aggregated appearance and lineup metrics over the trailing 365-day window.
Responsibility: own the sorted `(player_id * KEY_STRIDE + day)` prefix-sum encoding so
callers answer any batch of window queries with `searchsorted` in O(N log M), with no
per-player Python loop.

The module passes the ~130-line guidance because the frame preparation, the prefix-sum build
and the batched query are one algorithm that only makes sense read together: splitting the
encoding from its readers would hide the invariant `query()` depends on.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EPOCH_ANCHOR = pd.Timestamp("1900-01-01")
KEY_STRIDE = 1_000_000
WINDOW_DAYS = 365

APP_METRIC_COLS: tuple[str, ...] = (
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
)
LU_METRIC_COLS: tuple[str, ...] = ("starts", "squad_inclusions", "captain")


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _to_days(date_series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(date_series.str.slice(0, 10), format="%Y-%m-%d", errors="coerce")
    return (parsed - EPOCH_ANCHOR).dt.days


class TrailingWindowIndex:
    """Prefix-sum index answering trailing-365-day per-player window queries in bulk."""

    def __init__(
        self,
        appearances: pd.DataFrame,
        club_games: pd.DataFrame,
        lineups: pd.DataFrame,
        competitions: pd.DataFrame,
    ) -> None:
        """Build the per-`(player_id, day)` prefix sums from the raw ingest frames."""
        apps = appearances[
            [
                "game_id",
                "player_id",
                "player_club_id",
                "date",
                "competition_id",
                "minutes_played",
                "goals",
                "assists",
                "yellow_cards",
                "red_cards",
            ]
        ].copy()
        apps["pid"] = _to_numeric(apps["player_id"])
        apps["day"] = _to_days(apps["date"])
        apps = apps.dropna(subset=["pid", "day"]).copy()
        apps["pid"] = apps["pid"].astype(np.int64)
        apps["day"] = apps["day"].astype(np.int64)

        for col in ("minutes_played", "goals", "assists", "yellow_cards", "red_cards"):
            apps[col] = _to_numeric(apps[col]).fillna(0.0)

        cg = club_games[["game_id", "club_id", "own_goals", "opponent_goals", "is_win"]].copy()
        cg["own_goals"] = _to_numeric(cg["own_goals"])
        cg["opponent_goals"] = _to_numeric(cg["opponent_goals"])
        cg["win_flag"] = (cg["is_win"] == "1").astype(np.float64)
        cg["clean_sheet_flag"] = (cg["opponent_goals"] == 0).astype(np.float64)
        cg["goals_conceded"] = cg["opponent_goals"].fillna(0.0)

        apps = apps.merge(
            cg[["game_id", "club_id", "win_flag", "clean_sheet_flag", "goals_conceded"]],
            left_on=["game_id", "player_club_id"],
            right_on=["game_id", "club_id"],
            how="left",
        )
        for col in ("win_flag", "clean_sheet_flag", "goals_conceded"):
            apps[col] = apps[col].fillna(0.0)

        uefa_mask = (competitions["type"] == "international_cup") | (
            competitions["sub_type"].fillna("").str.startswith("uefa_")
        )
        uefa_ids = set(competitions.loc[uefa_mask, "competition_id"])
        apps["uefa_minutes"] = np.where(
            apps["competition_id"].isin(uefa_ids), apps["minutes_played"], 0.0
        )
        apps["apps_count"] = 1.0
        apps["key"] = apps["pid"] * KEY_STRIDE + apps["day"]

        daily_apps = apps.groupby("key", sort=True)[list(APP_METRIC_COLS)].sum()
        self._app_keys = daily_apps.index.to_numpy(dtype=np.int64)
        self._app_cumsums = {
            col: np.concatenate([[0.0], np.cumsum(daily_apps[col].to_numpy(dtype=np.float64))])
            for col in APP_METRIC_COLS
        }

        lu = lineups[["player_id", "date", "type", "team_captain"]].copy()
        lu["pid"] = _to_numeric(lu["player_id"])
        lu["day"] = _to_days(lu["date"])
        lu = lu.dropna(subset=["pid", "day"]).copy()
        lu["pid"] = lu["pid"].astype(np.int64)
        lu["day"] = lu["day"].astype(np.int64)
        lu["starts"] = (lu["type"] == "starting_lineup").astype(np.float64)
        lu["squad_inclusions"] = 1.0
        lu["captain"] = (lu["team_captain"] == "1").astype(np.float64)
        lu["key"] = lu["pid"] * KEY_STRIDE + lu["day"]
        daily_lu = lu.groupby("key", sort=True)[list(LU_METRIC_COLS)].sum()
        self._lu_keys = daily_lu.index.to_numpy(dtype=np.int64)
        self._lu_cumsums = {
            col: np.concatenate([[0.0], np.cumsum(daily_lu[col].to_numpy(dtype=np.float64))])
            for col in LU_METRIC_COLS
        }

    def query(
        self,
        pids: np.ndarray,
        days: np.ndarray,
        *,
        strict_before: bool = False,
    ) -> dict[str, np.ndarray]:
        """Return the trailing-window metric sums for each requested `(pid, day)` pair.

        With `strict_before=False` the window is `(day - 365, day]`, so the as-of day itself
        is included; used for valuation rows. With `strict_before=True` the window is
        `[day - 365, day - 1]`, so the as-of day itself is excluded; used for transfer rows
        so appearances after joining the buying club never leak in.
        """
        hi_keys = pids * KEY_STRIDE + days
        lo_keys = pids * KEY_STRIDE + (days - WINDOW_DAYS)
        side = "left" if strict_before else "right"

        hi_a = np.searchsorted(self._app_keys, hi_keys, side=side)
        lo_a = np.searchsorted(self._app_keys, lo_keys, side=side)
        out: dict[str, np.ndarray] = {
            col: self._app_cumsums[col][hi_a] - self._app_cumsums[col][lo_a]
            for col in APP_METRIC_COLS
        }

        hi_l = np.searchsorted(self._lu_keys, hi_keys, side=side)
        lo_l = np.searchsorted(self._lu_keys, lo_keys, side=side)
        for col in LU_METRIC_COLS:
            out[col] = self._lu_cumsums[col][hi_l] - self._lu_cumsums[col][lo_l]
        return out
