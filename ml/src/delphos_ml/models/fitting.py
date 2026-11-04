"""Leak-free fitting of the five DelphosFootball models on the `train` split.

Input: `player_seasons` and `transfer_events` DataFrames from `transform` plus validated
`empirical_bayes_m` and `prior_grouping` settings.
Output: a `TrainedSuite` (defined in `trained_suite.py`) with fitted estimators and scored frames.
Responsibility: fit every learned statistic strictly on `train` (and chronological `train` OOF for
valuation thresholds and classifiers), delegate ordered K-Means to `_kmeans.py`, delegate batch
scoring to `scoring.py`, and reset `RandomForestClassifier(n_jobs=1)` before artifact serialization
so live single-row inference avoids parallel-dispatch overhead. Kept in one ~150-line module so
every estimator's fit boundary against `train_df` / `oof_df` is auditable in one place.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeClassifier

from delphos_ml.features.feature_sets import FULL, POLY_REDUCED
from delphos_ml.features.preprocess import build_preprocessor
from delphos_ml.models import specs
from delphos_ml.models._kmeans import fit_ordered_kmeans
from delphos_ml.models.scoring import (
    TARGET,
    score_clusters,
    score_player_predictions,
    score_transfer_predictions,
    to_dense,
)
from delphos_ml.models.trained_suite import TrainedSuite


def _chronological_oof(
    train_df: pd.DataFrame, *, seasons: list[int], m: float, prior_grouping: str
) -> tuple[pd.DataFrame, np.ndarray]:
    pieces, preds = [], []
    for season in seasons[1:]:
        past = train_df[train_df["season"] < season]
        cur = train_df[train_df["season"] == season]
        prep = build_preprocessor(FULL, empirical_bayes_m=m, prior_grouping=prior_grouping)
        ols = LinearRegression().fit(
            to_dense(prep.fit_transform(past)), past[TARGET].to_numpy(dtype="float64")
        )
        pieces.append(cur)
        preds.append(ols.predict(to_dense(prep.transform(cur))))
    return pd.concat(pieces, axis=0), np.concatenate(preds)


def fit_and_score_all(
    player_seasons: pd.DataFrame,
    transfer_events: pd.DataFrame,
    *,
    empirical_bayes_m: float,
    prior_grouping: str,
) -> TrainedSuite:
    """Fit all five models strictly on `train` and score player-seasons and transfers."""
    player_seasons = player_seasons.reset_index(drop=True)
    transfer_events = transfer_events.reset_index(drop=True)
    train_df = player_seasons[player_seasons["split"] == "train"]
    seasons = sorted(int(s) for s in train_df["season"].unique())
    if len(seasons) < 2:
        raise ValueError("train split must span at least two seasons for chronological OOF labels")

    oof_df, oof_pred = _chronological_oof(
        train_df, seasons=seasons, m=empirical_bayes_m, prior_grouping=prior_grouping
    )
    oof_res = oof_pred - oof_df[TARGET].to_numpy(dtype="float64")
    q25, q75 = (
        float(v) for v in np.percentile(oof_res, [specs.Q25_PERCENTILE, specs.Q75_PERCENTILE])
    )
    y_oof = (oof_res >= q75).astype(np.int64)
    if set(np.unique(y_oof)) != {0, 1}:
        raise ValueError("chronological OOF labels collapsed to a single class")

    full_prep = build_preprocessor(
        FULL, empirical_bayes_m=empirical_bayes_m, prior_grouping=prior_grouping
    )
    y_train = train_df[TARGET].to_numpy(dtype="float64")
    lin = LinearRegression().fit(to_dense(full_prep.fit_transform(train_df)), y_train)
    poly_prep = build_preprocessor(
        POLY_REDUCED,
        empirical_bayes_m=empirical_bayes_m,
        prior_grouping=prior_grouping,
        poly_degree=specs.POLY_DEGREE,
        poly_interaction_only=specs.POLY_INTERACTION_ONLY,
    )
    poly = LinearRegression().fit(to_dense(poly_prep.fit_transform(train_df)), y_train)
    cl_prep, km, cl_meta = fit_ordered_kmeans(
        train_df, m=empirical_bayes_m, prior_grouping=prior_grouping
    )
    cls_prep = build_preprocessor(
        FULL, empirical_bayes_m=empirical_bayes_m, prior_grouping=prior_grouping
    )
    x_oof = to_dense(cls_prep.fit_transform(oof_df))
    dt = DecisionTreeClassifier(
        max_depth=specs.DT_MAX_DEPTH,
        min_samples_leaf=specs.DT_MIN_SAMPLES_LEAF,
        class_weight="balanced",
        random_state=specs.CLASSIFIER_RANDOM_STATE,
    ).fit(x_oof, y_oof)
    rf = RandomForestClassifier(
        n_estimators=specs.RF_N_ESTIMATORS,
        max_depth=specs.RF_MAX_DEPTH,
        min_samples_leaf=specs.RF_MIN_SAMPLES_LEAF,
        class_weight="balanced",
        random_state=specs.CLASSIFIER_RANDOM_STATE,
        n_jobs=-1,
    ).fit(x_oof, y_oof)
    est = {
        "full_prep": full_prep,
        "lin": lin,
        "poly_prep": poly_prep,
        "poly": poly,
        "cl_prep": cl_prep,
        "km": km,
        "cls_prep": cls_prep,
        "dt": dt,
        "rf": rf,
    }
    preds_df = score_player_predictions(
        player_seasons,
        est,
        oof_index=oof_df.index,
        oof_pred=oof_pred,
        anchor_season=seasons[0],
        q25=q25,
        q75=q75,
    )
    clusters_df = score_clusters(player_seasons, cl_prep=cl_prep, km=km)
    transfers_df = score_transfer_predictions(transfer_events, est)
    rf.set_params(n_jobs=1)
    return TrainedSuite(
        preprocessor=full_prep,
        linear_model=lin,
        polynomial_preprocessor=poly_prep,
        polynomial_model=poly,
        cluster_preprocessor=cl_prep,
        kmeans_model=km,
        classifier_preprocessor=cls_prep,
        decision_tree_model=dt,
        random_forest_model=rf,
        q25_overvalued_log10=q25,
        q75_undervalued_log10=q75,
        oof_seasons=tuple(seasons[1:]),
        oof_rows=int(len(oof_df)),
        cluster_order=cl_meta,
        player_predictions=preds_df,
        clusters=clusters_df,
        transfer_predictions=transfers_df,
    )
