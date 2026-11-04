"""Container returned by `delphos_ml.load_model()`.

Input: the verified `manifest.json` dictionary and unpickled estimators for one `model_run_id`.
Output: a frozen `LoadedArtifacts` instance.
Responsibility: hold every fitted preprocessor and estimator of an artifact bundle behind typed
attributes so live scoring (`POST /players/what-if`) and offline evaluation share one bundle type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sklearn.base import BaseEstimator


@dataclass(frozen=True)
class LoadedArtifacts:
    """Verified artifact bundle loaded in memory from `artifacts/<model_run_id>/`."""

    model_run_id: str
    manifest: dict[str, Any]
    preprocessor: BaseEstimator
    model: BaseEstimator
    polynomial_preprocessor: BaseEstimator
    polynomial_model: BaseEstimator
    cluster_preprocessor: BaseEstimator
    kmeans_model: BaseEstimator
    classifier_preprocessor: BaseEstimator
    decision_tree_model: BaseEstimator
    random_forest_model: BaseEstimator
