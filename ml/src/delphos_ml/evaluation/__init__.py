"""Public facade for KDD model evaluation and replacements (`delphos_ml.evaluation`).

Input: none (re-export facade).
Output: `build_replacements`, `classify_pre_transfer_status`, `compute_scheme_metrics`,
`holm_bonferroni`, and `run_inefficiency_tests`.
Responsibility: expose the evaluation primitives consumed by `delphos_ml.pipeline.evaluate` and
`analysis/`.
"""

from __future__ import annotations

from delphos_ml.evaluation.holm import holm_bonferroni
from delphos_ml.evaluation.inefficiency import (
    classify_pre_transfer_status,
    run_inefficiency_tests,
)
from delphos_ml.evaluation.replacements import build_replacements
from delphos_ml.evaluation.scheme_metrics import compute_scheme_metrics

__all__ = [
    "build_replacements",
    "classify_pre_transfer_status",
    "compute_scheme_metrics",
    "holm_bonferroni",
    "run_inefficiency_tests",
]
