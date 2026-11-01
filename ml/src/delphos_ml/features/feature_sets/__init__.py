"""Declarations of the ordered feature columns each model consumes.

Input: the column names of the `transform` stage's row schema.
Output: the `FeatureSet` dataclass and the provisional `FULL`, `POLY_REDUCED` and
`CLUSTER` declarations (docs/TRANSFORM_PLAN.md section 3, finalised by experiments
E1/E2/E4/E6).
Responsibility: re-export this concept's public surface; the implementations live in
`feature_set` and `presets` and this facade only imports from them.
"""

from delphos_ml.features.feature_sets.feature_set import FeatureSet
from delphos_ml.features.feature_sets.presets import CLUSTER, FULL, POLY_REDUCED

__all__ = ["CLUSTER", "FULL", "POLY_REDUCED", "FeatureSet"]
