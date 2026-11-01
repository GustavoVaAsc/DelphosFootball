"""Empirical-Bayes-shrunk per-90 rates for the count features of a `FeatureSet`.

Input: a DataFrame holding the count columns, the exposure column `minutes` and the
prior-grouping column `position` (the `transform` stage's row schema).
Output: one `<count>_per90` column per count: `(count + m * prior) / (minutes / 90 + m)`.
Responsibility: learn the positional priors on whatever split `fit` receives and apply
the shrinkage in `transform`. The grouping and `m` default to the values the `transform`
stage records in `_transform.json` (`prior_grouping = "position"`, `empirical_bayes_m = 5`);
`position` is used rather than `sub_position` because three of its twelve levels hold
fewer than 5,500 n90 of exposure, so their priors would come from a handful of events
(docs/TRANSFORM_PLAN.md section 3). Requires DataFrame input: like every sub-transformer
of the preprocessor's `ColumnTransformer`, it selects its columns by name.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted

DEFAULT_M = 5.0
DEFAULT_GROUP_COLUMN = "position"
DEFAULT_MINUTES_COLUMN = "minutes"
DEFAULT_COUNT_COLUMNS = ("goals", "assists", "yellow_cards", "red_cards")
_NINETY_MINUTES = 90.0


class EmpiricalBayesRates(BaseEstimator, TransformerMixin):
    """Shrink per-90 rates toward a prior estimated within each prior group.

    `fit` learns `prior = sum(count) / sum(minutes / 90)` per group of `group_column`
    (plus a pooled prior for groups unseen at fit time) and stores it as
    `group_priors_` / `global_priors_`. `transform` returns a frame of
    `<count>_per90 = (count + m * prior) / (n90 + m)`. A real estimator: `get_params` /
    `set_params` and the trailing-underscore attributes survive a joblib round trip
    into the model artifacts.
    """

    def __init__(
        self,
        count_columns: tuple[str, ...] = DEFAULT_COUNT_COLUMNS,
        m: float = DEFAULT_M,
        group_column: str = DEFAULT_GROUP_COLUMN,
        minutes_column: str = DEFAULT_MINUTES_COLUMN,
    ) -> None:
        self.count_columns = count_columns
        self.m = m
        self.group_column = group_column
        self.minutes_column = minutes_column

    def fit(self, X: pd.DataFrame, y: object = None) -> EmpiricalBayesRates:
        """Learn the per-group and pooled priors from `X` (training rows only)."""
        self.group_priors_: dict[str, pd.Series] = {}
        self.global_priors_: dict[str, float] = {}
        if not self.count_columns:
            return self
        self._require_columns(X)
        exposure = X[self.minutes_column].astype("float64") / _NINETY_MINUTES
        groups = X[self.group_column]
        exposure_by_group = exposure.groupby(groups, sort=False).sum()
        for column in self.count_columns:
            counts = X[column].astype("float64")
            by_group = counts.groupby(groups, sort=False).sum() / exposure_by_group
            self.group_priors_[column] = by_group.fillna(0.0)
            total_exposure = float(exposure.sum())
            self.global_priors_[column] = (
                float(counts.sum() / total_exposure) if total_exposure > 0.0 else 0.0
            )
        return self

    def transform(self, X: pd.DataFrame, y: object = None) -> pd.DataFrame:
        """Return the shrunk per-90 rates; groups unseen in training use the pooled prior."""
        check_is_fitted(self)
        if not self.count_columns:
            return pd.DataFrame(index=X.index)
        self._require_columns(X)
        exposure = X[self.minutes_column].astype("float64") / _NINETY_MINUTES
        groups = X[self.group_column]
        rates: dict[str, pd.Series] = {}
        for column in self.count_columns:
            prior = groups.map(self.group_priors_[column])
            prior = prior.fillna(self.global_priors_[column])
            rates[f"{column}_per90"] = (X[column].astype("float64") + self.m * prior) / (
                exposure + self.m
            )
        return pd.DataFrame(rates, index=X.index)

    def get_feature_names_out(self, input_features: object = None) -> np.ndarray:
        """The `<count>_per90` names, in `count_columns` order."""
        del input_features
        return np.asarray([f"{column}_per90" for column in self.count_columns], dtype=object)

    def _require_columns(self, X: pd.DataFrame) -> None:
        required = [self.group_column, self.minutes_column, *self.count_columns]
        missing = [column for column in required if column not in X.columns]
        if missing:
            raise ValueError(
                f"{type(self).__name__} is missing required columns: {', '.join(missing)}"
            )
