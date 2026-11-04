"""Holm-Bonferroni step-down family-wise error rate adjustment (§3.12).

Input: 1-D NumPy array of raw two-sided p-values in `[0, 1]`.
Output: 1-D NumPy array of Holm-Bonferroni adjusted p-values in `[0, 1]`.
Responsibility: enforce monotone step-down FWER control across correlated hypothesis families.
"""

from __future__ import annotations

import numpy as np


def holm_bonferroni(p_values: np.ndarray) -> np.ndarray:
    """Compute step-down Holm-Bonferroni adjusted p-values preserving input order."""
    arr = np.asarray(p_values, dtype="float64")
    m = len(arr)
    if m == 0:
        return np.array([], dtype="float64")
    clean = np.where(np.isfinite(arr), np.clip(arr, 0.0, 1.0), 1.0)
    order = np.argsort(clean, kind="mergesort")
    adjusted = np.empty(m, dtype="float64")
    running_max = 0.0
    for rank_idx, orig_idx in enumerate(order):
        candidate = min(1.0, float(clean[orig_idx]) * float(m - rank_idx))
        running_max = max(running_max, candidate)
        adjusted[orig_idx] = running_max
    return adjusted
