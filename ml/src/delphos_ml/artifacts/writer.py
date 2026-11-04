"""Artifact bundle serializer and self-verifier for `delphos_ml.pipeline.train`.

Input: staging directory, `model_run_id`, fitted `TrainedSuite`, provenance hashes, and validated
transform configuration.
Output: a `{filename: sha256_hex}` dictionary covering every `.joblib` file and `manifest.json`.
Responsibility: serialize the nine fitted estimators and `manifest.json` under
`<staging>/<model_run_id>/`, compute SHA-256 digests, and immediately self-verify the written
bundle through `delphos_ml.load_model()`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import joblib

from delphos_ml.artifacts._verification import BUNDLE_JOBLIB_FILES, collect_runtime_versions
from delphos_ml.artifacts.loader import load_model
from delphos_ml.features.feature_sets import CLUSTER, FULL, POLY_REDUCED, FeatureSet
from delphos_ml.features.preprocess.build_preprocessor import DEFAULT_MINUTES_COLUMN
from delphos_ml.models import specs
from delphos_ml.models.specs import ValidatedTransformConfig
from delphos_ml.models.trained_suite import TrainedSuite


def _raw_columns(feature_set: FeatureSet, prior_grouping: str) -> list[str]:
    cols: list[str] = []
    if feature_set.rates:
        cols.extend([prior_grouping, DEFAULT_MINUTES_COLUMN, *feature_set.rates])
    cols.extend(feature_set.numeric)
    if "height_in_cm" in feature_set.numeric:
        cols.append("position")
    cols.extend(feature_set.categorical)
    return list(dict.fromkeys(cols))


def write_verified_bundle(
    staging: Path,
    run_id: str,
    suite: TrainedSuite,
    *,
    trained_at: str,
    dataset_handle: str,
    dataset_version: int,
    snapshot_sha256: str,
    clean_sha256: str,
    transform_sha256: str,
    cfg: ValidatedTransformConfig,
    rows_per_split: dict[str, int],
) -> dict[str, str]:
    """Write `<staging>/<run_id>/`, verify via `load_model()`, and return SHA-256 digests."""
    bundle_dir = staging / run_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    objects: dict[str, Any] = {
        "preprocessor.joblib": suite.preprocessor,
        "model.joblib": suite.linear_model,
        "polynomial_preprocessor.joblib": suite.polynomial_preprocessor,
        "polynomial_model.joblib": suite.polynomial_model,
        "cluster_preprocessor.joblib": suite.cluster_preprocessor,
        "kmeans_model.joblib": suite.kmeans_model,
        "classifier_preprocessor.joblib": suite.classifier_preprocessor,
        "decision_tree_model.joblib": suite.decision_tree_model,
        "random_forest_model.joblib": suite.random_forest_model,
    }
    digests: dict[str, str] = {}
    for filename in BUNDLE_JOBLIB_FILES:
        out_path = bundle_dir / filename
        joblib.dump(objects[filename], out_path)
        digests[filename] = hashlib.sha256(out_path.read_bytes()).hexdigest()

    full_names = [str(n) for n in suite.preprocessor.get_feature_names_out()]
    full_raw = _raw_columns(FULL, cfg.prior_grouping)
    manifest = {
        "schema_version": 1,
        "model_run_id": run_id,
        "created_at": trained_at,
        "dataset": {
            "handle": dataset_handle,
            "version": dataset_version,
            "snapshot_sha256": snapshot_sha256,
        },
        "versions": collect_runtime_versions(),
        "files": list(BUNDLE_JOBLIB_FILES),
        "champion_regressor": "linear_regression",
        "champion_classifier": "random_forest",
        "feature_names": full_names,
        "feature_sets": {
            "full": {"raw_columns": full_raw, "transformed_names": full_names},
            "poly_reduced": {
                "raw_columns": _raw_columns(POLY_REDUCED, cfg.prior_grouping),
                "transformed_names": [
                    str(n) for n in suite.polynomial_preprocessor.get_feature_names_out()
                ],
            },
            "cluster": {
                "raw_columns": _raw_columns(CLUSTER, cfg.prior_grouping),
                "transformed_names": [
                    str(n) for n in suite.cluster_preprocessor.get_feature_names_out()
                ],
            },
            "classifier_full": {
                "raw_columns": full_raw,
                "transformed_names": [
                    str(n) for n in suite.classifier_preprocessor.get_feature_names_out()
                ],
            },
        },
        "thresholds": {
            "q25_overvalued_log10": suite.q25_overvalued_log10,
            "q75_undervalued_log10": suite.q75_undervalued_log10,
            "oof_seasons": list(suite.oof_seasons),
            "oof_rows": suite.oof_rows,
        },
        "cluster_order": list(suite.cluster_order),
        "training_config": {
            "clean_manifest_sha256": clean_sha256,
            "transform_manifest_sha256": transform_sha256,
            "window_days": cfg.window_days,
            "minutes_floor": cfg.minutes_floor,
            "empirical_bayes_m": cfg.empirical_bayes_m,
            "prior_grouping": cfg.prior_grouping,
            "season_month_start": cfg.season_month_start,
            "country_top_n": cfg.country_top_n,
            "country_groups": list(cfg.country_groups),
            "rows_per_split": rows_per_split,
            "models": {
                "kmeans": {
                    "estimator": "sklearn.cluster.KMeans",
                    "scaler": "sklearn.preprocessing.RobustScaler",
                    "n_clusters": specs.KMEANS_K,
                    "n_init": specs.KMEANS_N_INIT,
                    "max_iter": specs.KMEANS_MAX_ITER,
                    "random_state": specs.KMEANS_RANDOM_STATE,
                },
                "linear_regression": {"estimator": "sklearn.linear_model.LinearRegression"},
                "polynomial_regression": {
                    "estimator": "sklearn.linear_model.LinearRegression",
                    "degree": specs.POLY_DEGREE,
                    "interaction_only": specs.POLY_INTERACTION_ONLY,
                },
                "decision_tree": {
                    "estimator": "sklearn.tree.DecisionTreeClassifier",
                    "max_depth": specs.DT_MAX_DEPTH,
                    "min_samples_leaf": specs.DT_MIN_SAMPLES_LEAF,
                    "class_weight": "balanced",
                    "random_state": specs.CLASSIFIER_RANDOM_STATE,
                },
                "random_forest": {
                    "estimator": "sklearn.ensemble.RandomForestClassifier",
                    "n_estimators": specs.RF_N_ESTIMATORS,
                    "max_depth": specs.RF_MAX_DEPTH,
                    "min_samples_leaf": specs.RF_MIN_SAMPLES_LEAF,
                    "class_weight": "balanced",
                    "random_state": specs.CLASSIFIER_RANDOM_STATE,
                    "n_jobs_fit": -1,
                    "n_jobs_serving": 1,
                },
            },
        },
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    (bundle_dir / "manifest.json").write_bytes(manifest_bytes)
    digests["manifest.json"] = hashlib.sha256(manifest_bytes).hexdigest()
    load_model(run_id, expected_sha256=digests, artifacts_dir=staging)
    return digests
