"""Deterministic K-Means fitting with descending attacking-rate centroid permutation.

Input: `train` slice DataFrame plus `empirical_bayes_m` and `prior_grouping`.
Output: `(cluster_preprocessor, fitted_kmeans, cluster_order_metadata)`.
Responsibility: fit `RobustScaler` + `KMeans(n_clusters=3)` strictly on `train` and permute
`cluster_centers_` and `labels_` in place by descending `goals_per90 + assists_per90` (with raw
centroid index tie-breaking) so `kmeans.predict(X)` deterministically assigns `0, 1, 2`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import RobustScaler

from delphos_ml.features.feature_sets import CLUSTER
from delphos_ml.features.preprocess import build_preprocessor
from delphos_ml.models.scoring import to_dense
from delphos_ml.models.specs import (
    KMEANS_K,
    KMEANS_MAX_ITER,
    KMEANS_N_INIT,
    KMEANS_RANDOM_STATE,
)


def fit_ordered_kmeans(
    train_df: pd.DataFrame, *, m: float, prior_grouping: str
) -> tuple[Any, KMeans, tuple[dict[str, Any], ...]]:
    """Fit `CLUSTER` preprocessor + `KMeans` on `train` and order centroids deterministically."""
    if len(train_df) < KMEANS_K:
        raise ValueError(f"train split needs at least {KMEANS_K} rows for K-Means")
    prep = build_preprocessor(
        CLUSTER, empirical_bayes_m=m, prior_grouping=prior_grouping, scaler=RobustScaler()
    )
    km = KMeans(
        n_clusters=KMEANS_K,
        n_init=KMEANS_N_INIT,
        max_iter=KMEANS_MAX_ITER,
        random_state=KMEANS_RANDOM_STATE,
    ).fit(to_dense(prep.fit_transform(train_df)))
    # Columns 0 and 1 of `CLUSTER` are Empirical Bayes `goals_per90` and `assists_per90`.
    scores = -(km.cluster_centers_[:, 0] + km.cluster_centers_[:, 1])
    order = np.lexsort((np.arange(KMEANS_K), scores))
    inv = np.empty(KMEANS_K, dtype=np.int64)
    inv[order] = np.arange(KMEANS_K, dtype=np.int64)
    km.cluster_centers_ = np.ascontiguousarray(km.cluster_centers_[order])
    km.labels_ = inv[km.labels_].astype(np.int32)
    meta = tuple(
        {
            "cluster_id": int(new_id),
            "raw_centroid_index": int(old_id),
            "centroid_goals_plus_assists_per90": float(
                km.cluster_centers_[new_id, 0] + km.cluster_centers_[new_id, 1]
            ),
            "train_rows": int((km.labels_ == new_id).sum()),
        }
        for new_id, old_id in enumerate(order)
    )
    return prep, km, meta
