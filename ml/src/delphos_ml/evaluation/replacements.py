"""Athletic-equivalence replacement ranking and elite-asset tagging (§3.13).

Input: `player_seasons`, `player_predictions`, `clusters`, and the fitted `cluster_preprocessor`.
Output: `(replacement_targets_df, replacements_df, elite_by_pos, radii, active_season)`.
Responsibility: rank up to 3 unpadded profitable replacements per active-season player using
`train`-calibrated thresholds and record explicit shortfall codes whenever fewer than 3 qualify.
The module stays unified around the single ranking loop to preserve end-to-end vector cohesion.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from delphos_ml.evaluation._calibration import (
    calibrate_replacement_thresholds,
    classify_shortfall,
)
from delphos_ml.evaluation.specs import (
    COST_CEILING_RATIO,
    REPLACEMENT_COLUMNS,
    TARGET_COLUMNS,
    TOP_K_REPLACEMENTS,
)
from delphos_ml.models.scoring import to_dense

_PRED_COLS = [
    "player_id",
    "season",
    "split",
    "market_value_eur",
    "fair_value_eur",
    "residual_log10",
    "valuation_status",
]


def build_replacements(
    player_seasons: pd.DataFrame,
    player_predictions: pd.DataFrame,
    clusters: pd.DataFrame,
    *,
    cluster_preprocessor: Any,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float], dict[str, float], int]:
    """Fit §3.13 thresholds on `train` and rank top-3 replacements on `max(season)`."""
    joined = (
        player_seasons.merge(
            player_predictions[_PRED_COLS],
            on=["player_id", "season", "split"],
            validate="one_to_one",
        )
        .merge(
            clusters[["player_id", "season", "split", "cluster_id"]],
            on=["player_id", "season", "split"],
            validate="one_to_one",
        )
        .sort_values(["season", "player_id"])
        .reset_index(drop=True)
    )
    if len(joined) != len(player_seasons):
        raise ValueError("key mismatch across player_seasons, player_predictions, and clusters")

    train_df = joined[joined["split"] == "train"].reset_index(drop=True)
    if train_df.empty:
        return (
            pd.DataFrame(columns=TARGET_COLUMNS),
            pd.DataFrame(columns=REPLACEMENT_COLUMNS),
            {},
            {},
            0,
        )
    x_train = to_dense(cluster_preprocessor.transform(train_df))
    elite_by_pos, default_elite, radii, fallback_r = calibrate_replacement_thresholds(
        train_df, x_train
    )

    active_season = int(joined["season"].max()) if not joined.empty else 0
    active = joined[joined["season"] == active_season].reset_index(drop=True)
    x_act = to_dense(cluster_preprocessor.transform(active)) if len(active) else np.empty((0, 0))

    pids = active["player_id"].to_numpy(dtype="int64")
    pos_arr = active["position"].astype(str).to_numpy()
    cid_arr = active["cluster_id"].to_numpy(dtype="int64")
    mv_arr = np.round(active["market_value_eur"].to_numpy(dtype="float64"), 2)
    fv_arr = active["fair_value_eur"].to_numpy(dtype="float64")
    res_arr = active["residual_log10"].to_numpy(dtype="float64")
    st_arr = active["valuation_status"].astype(str).to_numpy()

    target_rows: list[dict[str, Any]] = []
    repl_rows: list[dict[str, Any]] = []
    for i in range(len(active)):
        pos, cid, mv = pos_arr[i], int(cid_arr[i]), float(mv_arr[i])
        el_thresh = elite_by_pos.get(pos, default_elite)
        is_elite = bool(mv >= el_thresh)
        r_ceil = radii.get(f"{cid}:{pos}", fallback_r)

        same_idx = np.flatnonzero((pids != pids[i]) & (cid_arr == cid) & (pos_arr == pos))
        dists = (
            np.linalg.norm(x_act[same_idx] - x_act[i], axis=1)
            if len(same_idx)
            else np.array([], dtype="float64")
        )
        dist_mask = dists <= r_ceil
        cheap_mask = dist_mask & (mv_arr[same_idx] <= COST_CEILING_RATIO * mv)
        qual_local = np.flatnonzero(cheap_mask & (st_arr[same_idx] != "overvalued"))

        if len(qual_local):
            q_idx, q_dist = same_idx[qual_local], dists[qual_local]
            order = np.lexsort((pids[q_idx], -res_arr[q_idx], q_dist))[:TOP_K_REPLACEMENTS]
        else:
            q_idx = np.array([], dtype="int64")
            q_dist = np.array([], dtype="float64")
            order = np.array([], dtype="int64")

        reason = classify_shortfall(
            int(len(same_idx)), int(dist_mask.sum()), int(cheap_mask.sum()), int(len(qual_local))
        )
        target_rows.append(
            {
                "player_id": int(pids[i]),
                "season": active_season,
                "position": pos,
                "cluster_id": cid,
                "market_value_eur": mv,
                "elite_mv_threshold_eur": el_thresh,
                "is_elite_asset": is_elite,
                "distance_ceiling": r_ceil,
                "qualifying_count": int(len(order)),
                "shortfall_reason": reason,
            }
        )
        for rank, local_pos in enumerate(order, start=1):
            c_i, d_val = int(q_idx[local_pos]), float(q_dist[local_pos])
            c_mv = float(mv_arr[c_i])
            repl_rows.append(
                {
                    "target_player_id": int(pids[i]),
                    "season": active_season,
                    "rank": rank,
                    "candidate_player_id": int(pids[c_i]),
                    "cluster_id": cid,
                    "position": pos,
                    "euclidean_distance": d_val,
                    "similarity_score": float(1.0 / (1.0 + d_val)),
                    "target_market_value_eur": mv,
                    "candidate_market_value_eur": c_mv,
                    "cost_savings_eur": float(mv - c_mv),
                    "cost_ratio": float(c_mv / mv) if mv > 0 else 0.0,
                    "candidate_fair_value_eur": float(fv_arr[c_i]),
                    "candidate_residual_log10": float(res_arr[c_i]),
                    "candidate_valuation_status": str(st_arr[c_i]),
                    "target_is_elite_asset": is_elite,
                }
            )
    t_df = pd.DataFrame(target_rows) if target_rows else pd.DataFrame(columns=TARGET_COLUMNS)
    r_df = pd.DataFrame(repl_rows) if repl_rows else pd.DataFrame(columns=REPLACEMENT_COLUMNS)
    return t_df, r_df, elite_by_pos, radii, active_season
