"""Paid-transfer event rows for the `transform` stage.

Input: the typed `transfers`, `players` and `clubs` frames from `data/clean/`, the prebuilt
point-in-time club league-position lookup (built by the stage from `club_games` and `games`),
and the shared trailing-window indexes.
Output: one row per paid outfield transfer with the pre-transfer window counts and biography,
on the player-season feature schema plus `transfer_date`, `transfer_fee` and
`pre_transfer_market_value`.
Responsibility: enforce the population rules of docs/ML_ARCHITECTURE.md section 3.3 —
`transfer_fee > 0`, seasons 2017 to 2025, at least one club in the 14 covered leagues, a
pre-transfer valuation, and `>= minutes_floor` minutes in the strict-before window
`[transfer_date - 365, transfer_date - 1]` so appearances after joining the buying club never
leak in.

The row's `club_id` and `league_id` are the covered side of the transfer: the buying club when
its domestic league is covered, otherwise the selling club, so `league_id` is always one of the
14 covered codes. `as_of_date` duplicates `transfer_date` so both transform tables share one
feature schema. Window and league-position helpers are shared with `build_player_seasons`.

The module passes the ~130-line guidance because the population filters, the covered-side
league join, the strict-before window rows and the schema assembly are one row contract that
must stay readable in one place; the shared helpers live in `build_player_seasons`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from delphos_ml.features.snapshots.build_player_seasons import (
    _BIO_COLUMNS,
    COVERED_LEAGUE_IDS,
    FIRST_SEASON,
    LAST_SEASON,
    OUTFIELD_POSITIONS,
    WINDOW_METRIC_COLUMNS,
    _LatestClubPositions,
    _window_row_metrics,
)
from delphos_ml.features.snapshots.season import assign_split, season_of
from delphos_ml.features.windows import TrailingWindowIndex
from delphos_ml.features.windows.trailing_window_index import EPOCH_ANCHOR


def build_transfer_events(
    transfers: pd.DataFrame,
    players: pd.DataFrame,
    clubs: pd.DataFrame,
    positions: _LatestClubPositions,
    window: TrailingWindowIndex,
    cup_window: TrailingWindowIndex,
    *,
    minutes_floor: int,
) -> pd.DataFrame:
    """Build the paid-transfer event rows from the cleaned transfer frames.

    One row per paid (`transfer_fee > 0`) outfield transfer in seasons 2017 to 2025 that
    involves at least one club in the 14 covered leagues and has a positive pre-transfer
    valuation, requiring `>= minutes_floor` trailing minutes in the strict-before window
    `[transfer_date - 365, transfer_date - 1]`. League position comes from the shared
    `positions` lookup the stage builds once for both row builders. Rows are sorted by
    `(player_id, transfer_date, from_club_id, to_club_id)`.
    """
    tr = transfers[
        [
            "player_id",
            "transfer_date",
            "from_club_id",
            "to_club_id",
            "transfer_fee",
            "market_value_in_eur",
        ]
    ].copy()
    tr["season"] = season_of(tr["transfer_date"])
    tr = tr.loc[tr["season"].between(FIRST_SEASON, LAST_SEASON)]
    tr = tr.loc[tr["transfer_fee"].notna() & (tr["transfer_fee"] > 0.0)]
    tr = tr.loc[tr["market_value_in_eur"].notna() & (tr["market_value_in_eur"] > 0.0)]

    leagues = clubs[["club_id", "domestic_competition_id"]]
    tr = tr.merge(
        leagues.rename(columns={"club_id": "to_club_id", "domestic_competition_id": "_to_league"}),
        on="to_club_id",
        how="left",
    )
    tr = tr.merge(
        leagues.rename(
            columns={"club_id": "from_club_id", "domestic_competition_id": "_from_league"}
        ),
        on="from_club_id",
        how="left",
    )
    to_covered = tr["_to_league"].isin(COVERED_LEAGUE_IDS)
    tr = tr.loc[to_covered | tr["_from_league"].isin(COVERED_LEAGUE_IDS)]
    to_covered = tr["_to_league"].isin(COVERED_LEAGUE_IDS)
    tr["club_id"] = np.where(to_covered, tr["to_club_id"], tr["from_club_id"])
    tr["league_id"] = np.where(to_covered, tr["_to_league"], tr["_from_league"])

    tr = tr.merge(players[list(_BIO_COLUMNS)], on="player_id", how="inner")
    tr = tr.loc[tr["position"].isin(OUTFIELD_POSITIONS)]
    # Deterministic artifact order, as the docstring promises: the window metrics and every
    # derived column below follow this order into the output rows.
    tr = tr.sort_values(["player_id", "transfer_date", "from_club_id", "to_club_id"])
    tr["day"] = (tr["transfer_date"] - EPOCH_ANCHOR).dt.days
    tr = tr.reset_index(drop=True)

    out = pd.concat(
        [
            tr,
            _window_row_metrics(
                window,
                cup_window,
                tr["player_id"].to_numpy(dtype=np.int64),
                tr["day"].to_numpy(dtype=np.int64),
                strict_before=True,
            ),
        ],
        axis=1,
    )
    out = out.loc[out["minutes"] >= minutes_floor].reset_index(drop=True)

    league_position = positions.position_at(
        out["club_id"].to_numpy(dtype=np.int64),
        out["day"].to_numpy(dtype=np.int64),
    )
    out["league_position"] = league_position
    out["league_position_missing"] = np.isnan(league_position)
    out["age"] = (out["transfer_date"] - out["date_of_birth"]).dt.days / 365.25
    out["log10_market_value"] = np.log10(out["market_value_in_eur"].astype("float64"))

    return pd.DataFrame(
        {
            "player_id": out["player_id"].astype("int64"),
            "season": out["season"].astype("int64"),
            "as_of_date": out["transfer_date"],
            "split": assign_split(out["season"]),
            "club_id": out["club_id"].astype("int64"),
            "league_id": out["league_id"],
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
            "transfer_date": out["transfer_date"],
            "transfer_fee": out["transfer_fee"].astype("float64"),
            "pre_transfer_market_value": out["market_value_in_eur"].astype("float64"),
        }
    )
