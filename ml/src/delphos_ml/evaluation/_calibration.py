"""Train-split threshold calibration and shortfall classification for replacements (§3.13).

Input: `train` slice of joined player-seasons + scaled `CLUSTER` matrix, or filter survivor counts.
Output: `(elite_by_pos, default_elite, radii, fallback_r)` and deterministic shortfall codes.
Responsibility: keep `train`-only threshold calibration isolated from active-season candidate search
so `test` rows can never influence `elite_mv_threshold_eur` or `distance_ceiling`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist

from delphos_ml.evaluation.specs import (
    DISTANCE_PERCENTILE,
    ELITE_PERCENTILE,
    SILHOUETTE_RANDOM_STATE,
    SILHOUETTE_SAMPLE_MAX,
    TOP_K_REPLACEMENTS,
)


def calibrate_replacement_thresholds(
    train_frame: pd.DataFrame, x_train: np.ndarray
) -> tuple[dict[str, float], float, dict[str, float], float]:
    """Fit `P75` elite MV per `position` and `P25` tactical distance radii strictly on `train`."""
    if train_frame.empty:
        raise ValueError("cannot calibrate replacement thresholds on an empty train split")
    if len(train_frame) != len(x_train):
        raise ValueError("train_frame and x_train row counts mismatch")
    train_df = train_frame.reset_index(drop=True)
    rounded_mv = np.round(train_df["market_value_eur"].to_numpy(dtype="float64"), 2)
    elite_by_pos = {
        str(pos): float(np.percentile(rounded_mv[grp.index.to_numpy()], ELITE_PERCENTILE))
        for pos, grp in train_df.groupby("position")
    }
    default_elite = float(np.percentile(rounded_mv, ELITE_PERCENTILE))

    all_dists: list[np.ndarray] = []
    radii: dict[str, float] = {}
    for (cid, pos), grp in train_df.groupby(["cluster_id", "position"]):
        cell_dists: list[np.ndarray] = []
        for _season, s_grp in grp.groupby("season"):
            idx = s_grp.index.to_numpy()
            if len(idx) < 2:
                continue
            cell_dists.append(pdist(x_train[idx], metric="euclidean"))
        if cell_dists:
            merged_d = np.concatenate(cell_dists)
            all_dists.append(merged_d)
            radii[f"{int(cid)}:{pos}"] = float(np.percentile(merged_d, DISTANCE_PERCENTILE))

    if all_dists:
        fallback_r = float(np.percentile(np.concatenate(all_dists), DISTANCE_PERCENTILE))
    elif len(x_train) >= 2:
        if len(x_train) > SILHOUETTE_SAMPLE_MAX:
            rng = np.random.default_rng(SILHOUETTE_RANDOM_STATE)
            sub_idx = rng.choice(len(x_train), size=SILHOUETTE_SAMPLE_MAX, replace=False)
            fallback_r = float(
                np.percentile(pdist(x_train[sub_idx], metric="euclidean"), DISTANCE_PERCENTILE)
            )
        else:
            fallback_r = float(
                np.percentile(pdist(x_train, metric="euclidean"), DISTANCE_PERCENTILE)
            )
    else:
        fallback_r = 1.0
    return elite_by_pos, default_elite, radii, fallback_r


def classify_shortfall(
    same_peer: int, within_dist: int, cheaper: int, qualifying: int
) -> str | None:
    """Return `None` when `>= 3` candidates qualify, else the earliest binding bottleneck code."""
    if qualifying >= TOP_K_REPLACEMENTS:
        return None
    if same_peer == 0:
        return "no_same_cluster_and_position_peer"
    if within_dist == 0:
        return "no_peer_within_athletic_distance"
    if cheaper == 0:
        return "no_peer_below_cost_ceiling"
    if qualifying == 0:
        return "no_non_overvalued_peer"
    return "fewer_than_three_qualifying_peers"
