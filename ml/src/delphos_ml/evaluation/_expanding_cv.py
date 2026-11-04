"""Expanding-window cross-validation runner for supervised valuation models (§3.15).

Input: pre-`test` `player_seasons` frame (`train` + `validation`) and transform hyperparameters.
Output: fold-averaged CV summary rows with standard errors (`se`).
Responsibility: refit preprocessors, OOF quartile thresholds, and supervised estimators inside each
chronological fold so CV means and standard errors are free of lookahead leakage. Folds and model
fits stay in this single module to guarantee chronological isolation without partial state leakage.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeClassifier

from delphos_ml.evaluation._metrics import cls_metrics, reg_metrics
from delphos_ml.evaluation.specs import MIN_CV_ANCHOR_SEASONS
from delphos_ml.features.feature_sets import FULL, POLY_REDUCED
from delphos_ml.features.preprocess import build_preprocessor
from delphos_ml.models import specs as mspecs
from delphos_ml.models.scoring import TARGET, to_dense


def _oof_residuals(
    tr: pd.DataFrame, *, m: float, prior_grouping: str
) -> tuple[pd.DataFrame, np.ndarray]:
    tr_seasons = sorted(int(s) for s in tr["season"].unique())
    parts, preds = [], []
    for s_in in tr_seasons[1:]:
        p_in = tr[tr["season"] < s_in].reset_index(drop=True)
        c_in = tr[tr["season"] == s_in].reset_index(drop=True)
        ip = build_preprocessor(FULL, empirical_bayes_m=m, prior_grouping=prior_grouping)
        io = LinearRegression().fit(
            to_dense(ip.fit_transform(p_in)), p_in[TARGET].to_numpy(dtype="float64")
        )
        parts.append(c_in)
        preds.append(io.predict(to_dense(ip.transform(c_in))))
    oof_df = pd.concat(parts, axis=0, ignore_index=True)
    return oof_df, np.concatenate(preds) - oof_df[TARGET].to_numpy(dtype="float64")


def run_expanding_cv(
    pre_test: pd.DataFrame, *, m: float, prior_grouping: str
) -> list[dict[str, Any]]:
    """Run expanding-window season folds over `train + validation` and return mean/SE rows."""
    seasons = sorted(int(s) for s in pre_test["season"].unique())
    start_idx = MIN_CV_ANCHOR_SEASONS if len(seasons) > MIN_CV_ANCHOR_SEASONS else 2
    val_seasons = seasons[start_idx:]
    if not val_seasons:
        return []

    per_model: dict[str, list[dict[str, float]]] = {
        "linear_regression": [],
        "polynomial_regression": [],
        "decision_tree": [],
        "random_forest": [],
    }
    n_pooled = 0
    for val_s in val_seasons:
        tr = pre_test[pre_test["season"] < val_s].reset_index(drop=True)
        va = pre_test[pre_test["season"] == val_s].reset_index(drop=True)
        n_pooled += len(va)
        y_tr, y_va = tr[TARGET].to_numpy(dtype="float64"), va[TARGET].to_numpy(dtype="float64")
        fp = build_preprocessor(FULL, empirical_bayes_m=m, prior_grouping=prior_grouping)
        va_lin = (
            LinearRegression()
            .fit(to_dense(fp.fit_transform(tr)), y_tr)
            .predict(to_dense(fp.transform(va)))
        )
        per_model["linear_regression"].append(reg_metrics(y_va, va_lin))

        pp = build_preprocessor(
            POLY_REDUCED,
            empirical_bayes_m=m,
            prior_grouping=prior_grouping,
            poly_degree=mspecs.POLY_DEGREE,
            poly_interaction_only=mspecs.POLY_INTERACTION_ONLY,
        )
        va_poly = (
            LinearRegression()
            .fit(to_dense(pp.fit_transform(tr)), y_tr)
            .predict(to_dense(pp.transform(va)))
        )
        per_model["polynomial_regression"].append(reg_metrics(y_va, va_poly))

        oof_df, oof_res = _oof_residuals(tr, m=m, prior_grouping=prior_grouping)
        q75_f = float(np.percentile(oof_res, mspecs.Q75_PERCENTILE))
        y_oof = (oof_res >= q75_f).astype(np.int64)
        y_va_cls = ((va_lin - y_va) >= q75_f).astype(np.int64)
        if len(np.unique(y_oof)) < 2:
            raise ValueError("chronological CV OOF residuals collapsed to a single class")
        cp = build_preprocessor(FULL, empirical_bayes_m=m, prior_grouping=prior_grouping)
        x_oof, x_va_c = to_dense(cp.fit_transform(oof_df)), to_dense(cp.transform(va))
        dt = DecisionTreeClassifier(
            max_depth=mspecs.DT_MAX_DEPTH,
            min_samples_leaf=mspecs.DT_MIN_SAMPLES_LEAF,
            class_weight="balanced",
            random_state=mspecs.CLASSIFIER_RANDOM_STATE,
        ).fit(x_oof, y_oof)
        rf = RandomForestClassifier(
            n_estimators=mspecs.RF_N_ESTIMATORS,
            max_depth=mspecs.RF_MAX_DEPTH,
            min_samples_leaf=mspecs.RF_MIN_SAMPLES_LEAF,
            class_weight="balanced",
            random_state=mspecs.CLASSIFIER_RANDOM_STATE,
            n_jobs=-1,
        ).fit(x_oof, y_oof)
        per_model["decision_tree"].append(
            cls_metrics(y_va_cls, dt.predict_proba(x_va_c)[:, 1], dt.predict(x_va_c))
        )
        per_model["random_forest"].append(
            cls_metrics(y_va_cls, rf.predict_proba(x_va_c)[:, 1], rf.predict(x_va_c))
        )

    rows: list[dict[str, Any]] = []
    scope = f"cv_{len(val_seasons)}fold"
    for model_name, fold_dicts in per_model.items():
        for metric_name in fold_dicts[0] if fold_dicts else ():
            vals = np.array([d[metric_name] for d in fold_dicts], dtype="float64")
            se = float(vals.std(ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0
            rows.append(
                {
                    "scope": scope,
                    "model": model_name,
                    "metric": metric_name,
                    "value": float(vals.mean()),
                    "se": se,
                    "n_rows": n_pooled,
                }
            )
    return rows
