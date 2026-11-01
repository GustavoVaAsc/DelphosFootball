"""Position-grouped median imputation for the numeric features of a `FeatureSet`.

Input: a numeric DataFrame that also carries the grouping column (`position`).
Output: the same numeric columns, missing values replaced by the training-split median
of the row's group, falling back to the pooled training median for a group unseen in
training.
Responsibility: impute `height_in_cm` - `SimpleImputer` cannot group, and a goalkeeper's
median height is not an outfield player's. Fitted on the training split only, so the
medians serialized with the artifact are training statistics.
Requires DataFrame input: it selects its columns by name, like every sub-transformer of
the preprocessor's `ColumnTransformer`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted

DEFAULT_GROUP_COLUMN = "position"


class GroupMedianImputer(BaseEstimator, TransformerMixin):
    """Impute each received value column with the training median of its group.

    `fit` stores `group_medians_` (one training median series per value column, keyed by
    `group_column`) and `global_medians_` (the pooled training median per value column);
    `transform` fills a missing value with its group median and falls back to the global
    median when the group was unseen at fit time. A real estimator: `get_params` /
    `set_params` and the trailing-underscore attributes survive a joblib round trip into
    the model artifacts.
    """

    def __init__(self, group_column: str = DEFAULT_GROUP_COLUMN) -> None:
        self.group_column = group_column

    def fit(self, X: pd.DataFrame, y: object = None) -> GroupMedianImputer:
        """Learn the per-group and pooled medians from `X` (training rows only)."""
        if self.group_column not in X.columns:
            raise ValueError(
                f"{type(self).__name__} is missing the grouping column {self.group_column!r}"
            )
        self.value_columns_ = tuple(column for column in X.columns if column != self.group_column)
        groups = X[self.group_column]
        self.group_medians_: dict[str, pd.Series] = {}
        self.global_medians_: dict[str, float] = {}
        for column in self.value_columns_:
            values = X[column].astype("float64")
            self.group_medians_[column] = values.groupby(groups, sort=False).median()
            self.global_medians_[column] = float(values.dropna().median())
        return self

    def transform(self, X: pd.DataFrame, y: object = None) -> pd.DataFrame:
        """Fill missing values with the group median, then the pooled median."""
        check_is_fitted(self)
        if not self.value_columns_:
            return pd.DataFrame(index=X.index)
        missing = [
            column
            for column in (*self.value_columns_, self.group_column)
            if column not in X.columns
        ]
        if missing:
            raise ValueError(
                f"{type(self).__name__} is missing required columns: {', '.join(missing)}"
            )
        groups = X[self.group_column]
        imputed: dict[str, pd.Series] = {}
        for column in self.value_columns_:
            values = X[column].astype("float64")
            group_fill = groups.map(self.group_medians_[column])
            imputed[column] = values.fillna(group_fill).fillna(self.global_medians_[column])
        return pd.DataFrame(imputed, index=X.index)

    def get_feature_names_out(self, input_features: object = None) -> np.ndarray:
        """The value columns, in fit-time order; the grouping column is not an output."""
        del input_features
        return np.asarray(self.value_columns_, dtype=object)
