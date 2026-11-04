"""Public facade for model specifications and leak-free training (`delphos_ml.models`).

Input: none (re-export facade).
Output: `TrainedSuite`, `ValidatedTransformConfig`, `fit_and_score_all`, and
`validate_transform_manifest`.
Responsibility: expose the training primitives consumed by `delphos_ml.pipeline.train`.
"""

from __future__ import annotations

from delphos_ml.models.fitting import fit_and_score_all
from delphos_ml.models.specs import ValidatedTransformConfig, validate_transform_manifest
from delphos_ml.models.trained_suite import TrainedSuite

__all__ = [
    "TrainedSuite",
    "ValidatedTransformConfig",
    "fit_and_score_all",
    "validate_transform_manifest",
]
