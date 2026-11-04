"""Result container for the fitted model suite produced by `delphos_ml.models.fitting`.

Input: fitted estimators, OOF thresholds, cluster ordering metadata, and scored DataFrames.
Output: a frozen `TrainedSuite` dataclass instance.
Responsibility: bundle all five fitted models, their preprocessors, and their batch predictions so
`delphos_ml.pipeline.train` serializes artifacts and Parquet tables without re-scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
from sklearn.base import BaseEstimator


@dataclass(frozen=True)
class TrainedSuite:
    """All fitted estimators, thresholds, and batch-scored tables produced by `train`."""

    preprocessor: BaseEstimator
    linear_model: BaseEstimator
    polynomial_preprocessor: BaseEstimator
    polynomial_model: BaseEstimator
    cluster_preprocessor: BaseEstimator
    kmeans_model: BaseEstimator
    classifier_preprocessor: BaseEstimator
    decision_tree_model: BaseEstimator
    random_forest_model: BaseEstimator
    q25_overvalued_log10: float
    q75_undervalued_log10: float
    oof_seasons: tuple[int, ...]
    oof_rows: int
    cluster_order: tuple[dict[str, Any], ...]
    player_predictions: pd.DataFrame
    clusters: pd.DataFrame
    transfer_predictions: pd.DataFrame
