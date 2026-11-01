"""The `FeatureSet` declaration: the ordered feature columns one model consumes.

Input: column names of the `transform` stage's row schema.
Output: the frozen `FeatureSet` dataclass, re-exported by `delphos_ml.features.feature_sets`.
Responsibility: define the declaration shape only; the concrete sets live in `presets.py`
and the fitted transforms that consume a set live in `delphos_ml.features.preprocess`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FeatureSet:
    """The ordered feature columns one model consumes, declared against the row schema.

    `numeric` and `categorical` name raw columns of the `transform` stage's output;
    `rates` names the count columns the preprocessor shrinks into positional per-90
    rates; `log1p` must be a subset of `numeric` (the skewed volumes); `poly` names the
    columns the polynomial model expands (the expansion itself is a `train` concern).
    `collapse` maps a categorical column to the rare levels that become `"other"`
    before encoding. Tuples keep the declaration order-stable for the artifact's
    recorded feature names; the frozen dataclass blocks assignment, though the dict in
    `collapse` keeps the instance unhashable.
    """

    name: str
    numeric: tuple[str, ...] = ()
    categorical: tuple[str, ...] = ()
    log1p: tuple[str, ...] = ()
    poly: tuple[str, ...] = ()
    rates: tuple[str, ...] = ()
    collapse: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def columns(self) -> tuple[str, ...]:
        """Every raw schema column this set declares, in declaration order, deduplicated."""
        seen: dict[str, None] = {}
        for column in (*self.numeric, *self.categorical, *self.rates, *self.poly, *self.collapse):
            seen.setdefault(column, None)
        return tuple(seen)
