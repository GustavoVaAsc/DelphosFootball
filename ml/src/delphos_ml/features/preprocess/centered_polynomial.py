"""Mean-centred quadratic basis for the `age` / `age_sq` pair of a `FeatureSet`.

Input: the numeric columns of a set that declares both `age` and `age_sq` - a
DataFrame carrying them by name, or a two-column array in the same order.
Output: the same received columns with the pair replaced by `age - center_` and
`(age - center_) ** 2`; every other column passes through untouched, so the column
count in equals the column count out and the pipeline downstream is unaffected.
Responsibility: move the quadratic age basis off the raw origin. `fit` learns
`center_` - the mean of the `age` column over whatever rows it receives - and
`transform` rebuilds the square around that centre. The pair spans the identical
space, so the OLS fit and every OLS prediction are unchanged; only the coordinates
move, which clears the `age`/`age_sq` VIF artefact (E3) and leaves the OLS
coefficients individually interpretable. The centre is a training statistic, so
this estimator belongs to the fitted layer of docs/TRANSFORM_PLAN.md section 2 and
never the deterministic `transform` stage. Like `EmpiricalBayesRates` it selects
its columns by name when it receives a DataFrame; an unnamed array must carry
exactly the two columns, because it has no names to select by.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted

DEFAULT_AGE_COLUMN = "age"
DEFAULT_SQUARE_COLUMN = "age_sq"


class CenteredPolynomial(BaseEstimator, TransformerMixin):
    """Replace the received `age` / `age_sq` columns with their mean-centred basis.

    `fit` stores `center_`, the mean of the `age` column over the rows it received
    (missing values skipped, the plain pandas mean); `transform` substitutes
    `[age - center_, (age - center_) ** 2]` for the two input columns, same column
    count in, same column count out. A real estimator: `get_params` / `set_params`
    and the trailing-underscore attribute survive a joblib round trip into the
    model artifacts.
    """

    def __init__(
        self,
        age_column: str = DEFAULT_AGE_COLUMN,
        square_column: str = DEFAULT_SQUARE_COLUMN,
    ) -> None:
        self.age_column = age_column
        self.square_column = square_column

    def fit(self, X: pd.DataFrame | np.ndarray, y: object = None) -> CenteredPolynomial:
        """Learn the centre of the `age` column from `X` (training rows only).

        Raises `ValueError` when the mean is not finite, so a degenerate or all-null `age`
        column fails at fit time rather than shipping NaN valuations from a green pipeline.
        """
        age = self._as_pair(X)[:, 0]
        self.center_ = float(pd.Series(age, dtype="float64").mean())
        if not math.isfinite(self.center_):
            raise ValueError(f"center_ must be finite; {self.age_column!r} is empty or all-null")
        return self

    def transform(
        self, X: pd.DataFrame | np.ndarray, y: object = None
    ) -> pd.DataFrame | np.ndarray:
        """Substitute the centred pair for the two input columns; others pass through."""
        check_is_fitted(self)
        if hasattr(X, "columns"):
            self._require_columns(X)
            out = X.astype("float64")
            centered = out[self.age_column] - self.center_
            out[self.age_column] = centered
            out[self.square_column] = centered**2
            return out
        centered = self._as_pair(X)[:, 0] - self.center_
        return np.column_stack((centered, centered**2))

    def get_feature_names_out(self, input_features: object = None) -> np.ndarray:
        """The received names unchanged (the pair keeps its names), or the pair's own."""
        if input_features is not None:
            return np.asarray(input_features, dtype=object)
        return np.asarray([self.age_column, self.square_column], dtype=object)

    def _as_pair(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Return `[age, age_sq]` as a float array: selected by name from a frame."""
        if hasattr(X, "columns"):
            self._require_columns(X)
            return X[[self.age_column, self.square_column]].to_numpy(dtype="float64")
        array = np.asarray(X, dtype="float64")
        if array.ndim != 2 or array.shape[1] != 2:
            raise ValueError(
                f"{type(self).__name__} needs a DataFrame with named columns "
                f"{self.age_column!r} and {self.square_column!r} or an unnamed "
                f"two-column array, got shape {array.shape}"
            )
        return array

    def _require_columns(self, X: pd.DataFrame) -> None:
        missing = [
            column for column in (self.age_column, self.square_column) if column not in X.columns
        ]
        if missing:
            raise ValueError(
                f"{type(self).__name__} is missing required columns: {', '.join(missing)}"
            )
