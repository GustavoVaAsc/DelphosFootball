"""Assemble the fitted preprocessor for a `FeatureSet`.

Input: a `FeatureSet` declaration (docs/TRANSFORM_PLAN.md section 3) plus the optional
`empirical_bayes_m` and `prior_grouping` parameters the transform manifest records, so
`train` passes the manifest's values instead of the transformer's hard-coded ones.
Output: a scikit-learn `ColumnTransformer` with three branches: (1) the Empirical-Bayes
per-90 rates over the set's `rates` counts, (2) numerics imputed - `height_in_cm` with
the position-grouped median, the rest with the plain training median - then log1p'd
where the set declares it and standard-scaled, (3) categoricals rare-level-collapsed
where the set declares it, imputed with `"unknown"` and one-hot encoded with unknown
levels ignored.
Responsibility: wire the fitted layer of docs/TRANSFORM_PLAN.md section 2. Every learned
statistic (priors, medians, scaler moments, one-hot vocabularies) is fitted inside the
returned estimator on whatever rows `fit` receives, so `train` fits it on the training
split only and batch and live scoring apply identical transforms. The two stateless
helpers below stay in this module: they hold no fitted state, are only meaningful wired
into this exact pipeline, and both are module-level functions so the fitted pipeline
pickles - a file each would wrap one expression.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from delphos_ml.features.feature_sets import FeatureSet
from delphos_ml.features.preprocess.empirical_bayes_rates import (
    DEFAULT_GROUP_COLUMN,
    DEFAULT_M,
    DEFAULT_MINUTES_COLUMN,
    EmpiricalBayesRates,
)
from delphos_ml.features.preprocess.group_median_imputer import GroupMedianImputer

#: Numeric columns imputed with the position-grouped median instead of the plain one.
GROUP_MEDIAN_COLUMNS = frozenset({"height_in_cm"})

Branch = tuple[str, BaseEstimator, list[str]]


def _log1p_values(values: np.ndarray, indices: tuple[int, ...]) -> np.ndarray:
    """Return `values` with the columns at `indices` replaced by their log1p."""
    out = np.array(values, dtype="float64", copy=True)
    for index in indices:
        out[:, index] = np.log1p(out[:, index])
    return out


def _collapse_levels(frame: pd.DataFrame, mapping: dict[str, tuple[str, ...]]) -> np.ndarray:
    """Replace the rare levels of `mapping`'s columns with `"other"` before encoding."""
    if not hasattr(frame, "columns"):
        raise ValueError(
            "the rare-level collapse selects columns by name and requires DataFrame input"
        )
    out = frame.copy()
    for column, levels in mapping.items():
        out[column] = out[column].where(~out[column].isin(levels), "other")
    return out.to_numpy(dtype=object, na_value=np.nan)


def _imputation_transformers(feature_set: FeatureSet) -> list[Branch]:
    """Chunk `feature_set.numeric` into order-preserving runs of equal imputation.

    Consecutive plain-median columns share one `SimpleImputer`; a grouped column such
    as `height_in_cm` gets its own `GroupMedianImputer` between the runs, so the
    branch's output order stays the declared order and the names route correctly.
    """
    transformers: list[Branch] = []
    run: list[str] = []
    for column in feature_set.numeric:
        if column in GROUP_MEDIAN_COLUMNS:
            if run:
                transformers.append(
                    (f"median_{len(transformers)}", SimpleImputer(strategy="median"), run)
                )
                run = []
            transformers.append(("grouped", GroupMedianImputer(), [DEFAULT_GROUP_COLUMN, column]))
        else:
            run.append(column)
    if run:
        transformers.append((f"median_{len(transformers)}", SimpleImputer(strategy="median"), run))
    return transformers


def build_preprocessor(
    feature_set: FeatureSet,
    *,
    empirical_bayes_m: float = DEFAULT_M,
    prior_grouping: str = DEFAULT_GROUP_COLUMN,
) -> ColumnTransformer:
    """Return the three-branch ColumnTransformer this feature set consumes.

    Fitted on the training split by `train` and serialized with the model artifact;
    every branch is a real estimator, so `get_params` / `set_params` and the fitted
    trailing-underscore attributes survive a joblib round trip to the serving backend.
    `empirical_bayes_m` and `prior_grouping` default to the shared Empirical Bayes
    constants; `train` passes the values `_transform.json` records so the fitted
    preprocessor cannot drift from the rows' manifest.
    """
    rates = tuple(feature_set.rates)
    rates_branch = EmpiricalBayesRates(
        count_columns=rates, m=empirical_bayes_m, group_column=prior_grouping
    )
    rates_columns = [prior_grouping, DEFAULT_MINUTES_COLUMN, *rates] if rates else []
    branches: list[Branch] = [("empirical_bayes", rates_branch, rates_columns)]

    numeric_columns = list(feature_set.numeric)
    log1p_indices = tuple(numeric_columns.index(column) for column in feature_set.log1p)
    impute = ColumnTransformer(
        _imputation_transformers(feature_set), verbose_feature_names_out=False
    )
    numeric_steps: list[tuple[str, BaseEstimator]] = [("impute", impute)]
    if log1p_indices:
        log1p = FunctionTransformer(
            _log1p_values, kw_args={"indices": log1p_indices}, feature_names_out="one-to-one"
        )
        numeric_steps.append(("log1p", log1p))
    numeric_steps.append(("scale", StandardScaler()))
    if any(column in GROUP_MEDIAN_COLUMNS for column in numeric_columns):
        numeric_columns.append(DEFAULT_GROUP_COLUMN)
    branches.append(("numeric", Pipeline(numeric_steps), numeric_columns))

    categorical_steps: list[tuple[str, BaseEstimator]] = []
    if feature_set.collapse:
        collapse = FunctionTransformer(
            _collapse_levels,
            kw_args={"mapping": dict(feature_set.collapse)},
            feature_names_out="one-to-one",
        )
        categorical_steps.append(("collapse", collapse))
    categorical_steps.append(("impute", SimpleImputer(strategy="constant", fill_value="unknown")))
    categorical_steps.append(("onehot", OneHotEncoder(handle_unknown="ignore")))
    branches.append(("categorical", Pipeline(categorical_steps), list(feature_set.categorical)))

    return ColumnTransformer(transformers=branches)
