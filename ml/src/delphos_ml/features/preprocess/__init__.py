"""The fitted layer: the transformers `train` fits on the training split and serializes.

Input: transform-stage rows (a `FeatureSet` declaration selects which columns each
transformer consumes).
Output: `EmpiricalBayesRates`, `GroupMedianImputer` and `build_preprocessor`, the public
surface of the fitted preprocessor of docs/TRANSFORM_PLAN.md section 2.
Responsibility: re-export this concept's public surface; the implementations live in
`empirical_bayes_rates`, `group_median_imputer` and `build_preprocessor` and this facade
only imports from them.
"""

from delphos_ml.features.preprocess.build_preprocessor import build_preprocessor
from delphos_ml.features.preprocess.empirical_bayes_rates import EmpiricalBayesRates
from delphos_ml.features.preprocess.group_median_imputer import GroupMedianImputer

__all__ = ["EmpiricalBayesRates", "GroupMedianImputer", "build_preprocessor"]
