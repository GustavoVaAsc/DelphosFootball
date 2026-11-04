"""Regression and imbalanced binary classification metric helpers (§3.15).

Input: ground-truth and predicted `log10` valuations or binary undervaluation probabilities/labels.
Output: scalar metric dictionaries (`rmse_log10`, `mae_log10`, `r2_log10`, `mdape_eur`, `pr_auc`,
`roc_auc`, `f1`, `balanced_accuracy`, `precision`, `recall`).
Responsibility: share identical metric definitions across held-out splits and expanding-window CV.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)


def reg_metrics(y_log: np.ndarray, pred_log: np.ndarray) -> dict[str, float]:
    """Compute `log10` error metrics and EUR-scale MdAPE."""
    y_eur = np.power(10.0, y_log)
    pred_eur = np.maximum(0.0, np.power(10.0, pred_log))
    return {
        "rmse_log10": float(np.sqrt(mean_squared_error(y_log, pred_log))),
        "mae_log10": float(mean_absolute_error(y_log, pred_log)),
        "r2_log10": float(r2_score(y_log, pred_log)),
        "mdape_eur": float(np.median(np.abs(y_eur - pred_eur) / y_eur)),
    }


def cls_metrics(y_true: np.ndarray, prob: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    """Compute imbalanced binary classification metrics (`PR-AUC` primary)."""
    both = len(np.unique(y_true)) == 2
    return {
        "pr_auc": float(average_precision_score(y_true, prob)) if both else 0.0,
        "roc_auc": float(roc_auc_score(y_true, prob)) if both else 0.5,
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)) if both else 0.5,
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
    }
