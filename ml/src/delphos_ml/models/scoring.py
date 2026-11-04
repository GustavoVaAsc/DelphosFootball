"""Batch scoring helpers assembling the three Parquet tables emitted by `train`.

Input: `player_seasons` and `transfer_events` DataFrames, fitted preprocessors/estimators, OOF
predictions on `train`, and OOF quartile thresholds `(q25, q75)`.
Output: typed `player_predictions`, `clusters`, and `transfer_predictions` DataFrames.
Responsibility: project all splits through the `train`-fitted estimators, guard index alignment and
numerical finiteness, and attach leak-free canonical residuals, 3-zone valuation statuses, cluster
distances, and transfer fee gaps. Kept in one module because the three tables share dense matrix
conversion and fitted estimators.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

TARGET = "log10_market_value"


def to_dense(matrix: Any) -> np.ndarray:
    """Convert sparse or dense sklearn transformer output to a float64 ndarray."""
    return matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix, dtype="float64")


def _require_finite(label: str, *arrays: np.ndarray) -> None:
    if not all(np.isfinite(arr).all() for arr in arrays):
        raise ValueError(f"non-finite numeric values encountered while scoring {label}")


def score_player_predictions(
    player_seasons: pd.DataFrame,
    estimators: dict[str, Any],
    *,
    oof_index: pd.Index,
    oof_pred: np.ndarray,
    anchor_season: int,
    q25: float,
    q75: float,
) -> pd.DataFrame:
    """Assemble `player_predictions` with chronological OOF residuals on `train` (post-anchor)."""
    lin_all = estimators["lin"].predict(to_dense(estimators["full_prep"].transform(player_seasons)))
    poly_all = estimators["poly"].predict(
        to_dense(estimators["poly_prep"].transform(player_seasons))
    )
    indexer = player_seasons.index.get_indexer(oof_index)
    if (indexer < 0).any():
        raise ValueError("chronological OOF index failed to align with player_seasons")
    canonical_log10 = lin_all.copy()
    canonical_log10[indexer] = oof_pred

    y_all = player_seasons[TARGET].to_numpy(dtype="float64")
    mv_eur = np.power(10.0, y_all)
    fair_eur = np.maximum(0.0, np.power(10.0, canonical_log10))
    res_all = canonical_log10 - y_all
    x_cls = to_dense(estimators["cls_prep"].transform(player_seasons))
    dt_prob = estimators["dt"].predict_proba(x_cls)[:, 1]
    rf_prob = estimators["rf"].predict_proba(x_cls)[:, 1]
    _require_finite(
        "player_predictions",
        y_all,
        mv_eur,
        lin_all,
        poly_all,
        canonical_log10,
        fair_eur,
        dt_prob,
        rf_prob,
    )
    splits = player_seasons["split"].to_numpy()
    res_source = np.where(
        splits != "train",
        splits,
        np.where(player_seasons["season"].to_numpy() == anchor_season, "in_sample_anchor", "oof"),
    )
    status = np.where(res_all >= q75, "undervalued", np.where(res_all <= q25, "overvalued", "fair"))
    return pd.DataFrame(
        {
            "player_id": player_seasons["player_id"].to_numpy(dtype="int64"),
            "season": player_seasons["season"].to_numpy(dtype="int64"),
            "as_of_date": player_seasons["as_of_date"].to_numpy(),
            "split": player_seasons["split"].astype(str).to_numpy(),
            "residual_source": res_source.astype(str),
            "log10_market_value": y_all,
            "market_value_eur": mv_eur,
            "linear_log10_pred": lin_all,
            "poly_log10_pred": poly_all,
            "predicted_log10_value": canonical_log10,
            "fair_value_eur": fair_eur,
            "residual_log10": res_all,
            "valuation_status": status,
            "is_undervalued": res_all >= q75,
            "dt_undervalued_prob": dt_prob,
            "dt_undervalued_pred": estimators["dt"].predict(x_cls).astype(bool),
            "rf_undervalued_prob": rf_prob,
            "rf_undervalued_pred": estimators["rf"].predict(x_cls).astype(bool),
        }
    )


def score_clusters(player_seasons: pd.DataFrame, *, cl_prep: Any, km: Any) -> pd.DataFrame:
    """Assemble `clusters` with ordered `cluster_id` and Euclidean `centroid_distance`."""
    x_cl = to_dense(cl_prep.transform(player_seasons))
    cl_ids = km.predict(x_cl).astype(np.int64)
    dist = np.linalg.norm(x_cl - km.cluster_centers_[cl_ids], axis=1)
    _require_finite("clusters", dist)
    return pd.DataFrame(
        {
            "player_id": player_seasons["player_id"].to_numpy(dtype="int64"),
            "season": player_seasons["season"].to_numpy(dtype="int64"),
            "split": player_seasons["split"].astype(str).to_numpy(),
            "cluster_id": cl_ids,
            "centroid_distance": dist,
        }
    )


def score_transfer_predictions(
    transfer_events: pd.DataFrame, estimators: dict[str, Any]
) -> pd.DataFrame:
    """Assemble `transfer_predictions` for market-inefficiency evaluation in `evaluate`."""
    tr_fee = transfer_events["transfer_fee"].to_numpy(dtype="float64")
    tr_mv = transfer_events["pre_transfer_market_value"].to_numpy(dtype="float64")
    if not ((tr_fee > 0).all() and (tr_mv > 0).all()):
        raise ValueError("transfer_events requires strictly positive transfer_fee and market_value")
    tr_lin = estimators["lin"].predict(to_dense(estimators["full_prep"].transform(transfer_events)))
    tr_poly = estimators["poly"].predict(
        to_dense(estimators["poly_prep"].transform(transfer_events))
    )
    tr_cl = (
        estimators["km"]
        .predict(to_dense(estimators["cl_prep"].transform(transfer_events)))
        .astype(np.int64)
    )
    tr_rf_prob = estimators["rf"].predict_proba(
        to_dense(estimators["cls_prep"].transform(transfer_events))
    )[:, 1]
    log10_fee = np.log10(tr_fee)
    log10_mv = np.log10(tr_mv)
    fair_eur = np.maximum(0.0, np.power(10.0, tr_lin))
    _require_finite(
        "transfer_predictions", log10_fee, log10_mv, tr_lin, tr_poly, fair_eur, tr_rf_prob
    )
    buyer_league = (
        transfer_events["buyer_league_id"]
        .where(transfer_events["buyer_league_id"].notna(), None)
        .to_numpy()
        if "buyer_league_id" in transfer_events
        else np.full(len(transfer_events), None, dtype=object)
    )
    buyer_league = (
        transfer_events["buyer_league_id"]
        .where(transfer_events["buyer_league_id"].notna(), None)
        .to_numpy()
        if "buyer_league_id" in transfer_events
        else np.full(len(transfer_events), None, dtype=object)
    )
    return pd.DataFrame(
        {
            "player_id": transfer_events["player_id"].to_numpy(dtype="int64"),
            "season": transfer_events["season"].to_numpy(dtype="int64"),
            "split": transfer_events["split"].astype(str).to_numpy(),
            "transfer_date": transfer_events["transfer_date"].to_numpy(),
            "club_id": transfer_events["club_id"].to_numpy(dtype="int64"),
            "league_id": transfer_events["league_id"].astype(str).to_numpy(),
            "buyer_league_id": buyer_league,
            "transfer_fee": tr_fee,
            "pre_transfer_market_value": tr_mv,
            "log10_transfer_fee": log10_fee,
            "linear_log10_pred": tr_lin,
            "poly_log10_pred": tr_poly,
            "fair_value_eur": fair_eur,
            "fee_minus_fair_log10": log10_fee - tr_lin,
            "fee_minus_mv_log10": log10_fee - log10_mv,
            "cluster_id": tr_cl,
            "rf_undervalued_prob": tr_rf_prob,
        }
    )
