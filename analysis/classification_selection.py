"""E8: out-of-fold valuation-label thresholds and classifier hyperparameter selection.

Input: `ml/data/transform/player_seasons.parquet` resolved through `delphos_ml.config`,
read with a predicate keeping only `train` and `validation` splits (`season <= 2024`) -
the 2025 `test` split is never read - plus `_transform.json` for dataset provenance and
Empirical Bayes parameters.
Output: `e8_oof_thresholds.csv`, `e8_dt_grid.csv`, `e8_rf_grid.csv`,
`e8_selected_comparison.csv`, `e8_feature_importance.csv`, `fig_e8_classifier_cv.png` and
`summary.json` under `<repo root>/analysis/output/classification_selection/`.
Responsibility: run experiment E8, which provides the empirical evidence closing
docs/ML_ARCHITECTURE.md sections 3.9 and 3.10: (1) measure the chronological out-of-fold
(OOF) OLS residual distribution `r = log10(fair_value) - log10(market_value)` across
`train` seasons `2018..2023` (`31,714` rows, each season predicted strictly from
`2017..s-1`) and its Q1/Q3 thresholds; and (2) tune `DecisionTreeClassifier` and
`RandomForestClassifier` (`class_weight="balanced"`) on `FULL` across the five
expanding-window folds (`validate 2020..2024`), recomputing fold-internal OOF residuals,
fold-internal Q3 thresholds and fold-scoped preprocessors inside every fold so no future
season leaks into any threshold, transformer or label. Selection uses mean fold PR-AUC
with the one-standard-error rule favoring simpler trees (smaller `max_depth`, larger
`min_samples_leaf`). Like `poly_degree.py` and `kmeans_selection.py`, this standalone
analysis script stays in one module per ADR-014 so all E8 outputs share one script-owned
directory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.tree import DecisionTreeClassifier, export_text

from delphos_ml.config import ConfigError, find_project_root, load_settings
from delphos_ml.features.feature_sets import FULL
from delphos_ml.features.preprocess import build_preprocessor
from delphos_ml.models import validate_transform_manifest

TARGET = "log10_market_value"
RANDOM_STATE = 20261103
RF_TREES = 300

#: Outer expanding-window validation seasons, matching E1 and E4 (`2020..2024`).
OUTER_VAL_SEASONS: tuple[int, ...] = (2020, 2021, 2022, 2023, 2024)

#: Decision Tree candidates ordered simplest-first (smaller depth, larger leaf floor)
#: so the one-SE rule deterministically picks the most parsimonious tree in the band.
DT_CANDIDATES: tuple[tuple[str, int | None, int], ...] = (
    *(
        (f"dt_d{depth}_l{leaf}", depth, leaf)
        for depth in (3, 4, 5, 6, 8, 10)
        for leaf in (100, 50, 25, 10)
    ),
    ("dt_unpruned_l50", None, 50),
    ("dt_unpruned_l25", None, 25),
    ("dt_unpruned_l10", None, 10),
    ("dt_unpruned_l1", None, 1),
)

#: Random Forest candidates ordered simplest-first (smaller depth, larger leaf floor).
RF_CANDIDATES: tuple[tuple[str, int | None, int], ...] = (
    *(
        (f"rf_d{depth}_l{leaf}", depth, leaf)
        for depth in (6, 8, 10, 14)
        for leaf in (50, 25, 10, 5)
    ),
    ("rf_unpruned_l50", None, 50),
    ("rf_unpruned_l25", None, 25),
    ("rf_unpruned_l10", None, 10),
    ("rf_unpruned_l5", None, 5),
)


def _fail(reason: str) -> None:
    print(f"classification_selection failed: {reason}", file=sys.stderr)
    raise SystemExit(1)


def _dense(matrix: Any) -> np.ndarray:
    return matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix)


def _load_rows() -> tuple[pd.DataFrame, Path, dict[str, Any]]:
    try:
        settings = load_settings()
    except ConfigError as exc:
        _fail(str(exc))
    project_root = find_project_root()
    repo_root = project_root.parent if project_root is not None else Path.cwd()
    parquet_path = settings.data_dir / "transform" / "player_seasons.parquet"
    manifest_path = settings.data_dir / "transform" / "_transform.json"
    if not parquet_path.is_file() or not manifest_path.is_file():
        _fail(f"missing {parquet_path}; run `uv run delphos-pipeline transform` from ml/ first")
    rows = pd.read_parquet(parquet_path, filters=[("split", "in", ["train", "validation"])])
    if set(rows["split"].unique()) != {"train", "validation"} or int(rows["season"].max()) > 2024:
        raise ValueError("the test split or a post-2024 season reached the analysis frame")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return rows, repo_root / "analysis" / "output" / "classification_selection", manifest


def _chronological_oof_residuals(
    frame: pd.DataFrame, *, max_season: int, m: float, prior_grouping: str
) -> pd.DataFrame:
    """Compute strict chronological OOF OLS residuals for seasons `2018..max_season`.

    Each season `s` is scored by a preprocessor + LinearRegression fitted strictly on
    `2017..s-1`. Season `2017` has no earlier season and is never emitted here.
    """
    pieces: list[pd.DataFrame] = []
    for season in range(2018, max_season + 1):
        past = frame[frame["season"] < season]
        current = frame[frame["season"] == season].copy()
        preprocessor = build_preprocessor(FULL, empirical_bayes_m=m, prior_grouping=prior_grouping)
        x_past = _dense(preprocessor.fit_transform(past))
        x_cur = _dense(preprocessor.transform(current))
        ols = LinearRegression()
        ols.fit(x_past, past[TARGET].to_numpy(dtype="float64"))
        pred = ols.predict(x_cur)
        current["predicted_log10_value"] = pred
        current["residual_log10"] = pred - current[TARGET].to_numpy(dtype="float64")
        pieces.append(current)
    return pd.concat(pieces, ignore_index=True)


def _heldout_residuals(
    train_frame: pd.DataFrame, val_frame: pd.DataFrame, *, m: float, prior_grouping: str
) -> pd.DataFrame:
    """Fit preprocessor + OLS on `train_frame` and compute residuals on `val_frame`."""
    preprocessor = build_preprocessor(FULL, empirical_bayes_m=m, prior_grouping=prior_grouping)
    x_train = _dense(preprocessor.fit_transform(train_frame))
    x_val = _dense(preprocessor.transform(val_frame))
    ols = LinearRegression()
    ols.fit(x_train, train_frame[TARGET].to_numpy(dtype="float64"))
    out = val_frame.copy()
    pred = ols.predict(x_val)
    out["predicted_log10_value"] = pred
    out["residual_log10"] = pred - out[TARGET].to_numpy(dtype="float64")
    return out


def _prepare_outer_folds(
    rows: pd.DataFrame, *, m: float, prior_grouping: str
) -> list[dict[str, Any]]:
    """Precompute leak-free design matrices and binary OOF/held-out labels per outer fold."""
    prepared: list[dict[str, Any]] = []
    for val_season in OUTER_VAL_SEASONS:
        cls_train = _chronological_oof_residuals(
            rows[rows["season"] < val_season],
            max_season=val_season - 1,
            m=m,
            prior_grouping=prior_grouping,
        )
        q25, q75 = np.percentile(
            cls_train["residual_log10"].to_numpy(dtype="float64"), [25.0, 75.0]
        )
        val_scored = _heldout_residuals(
            rows[rows["season"] < val_season],
            rows[rows["season"] == val_season],
            m=m,
            prior_grouping=prior_grouping,
        )
        cls_prep = build_preprocessor(FULL, empirical_bayes_m=m, prior_grouping=prior_grouping)
        x_train = _dense(cls_prep.fit_transform(cls_train))
        x_val = _dense(cls_prep.transform(val_scored))
        y_train = (cls_train["residual_log10"].to_numpy(dtype="float64") >= q75).astype(np.int64)
        y_val = (val_scored["residual_log10"].to_numpy(dtype="float64") >= q75).astype(np.int64)
        prepared.append(
            {
                "val_season": val_season,
                "train_rows": int(len(cls_train)),
                "val_rows": int(len(val_scored)),
                "q25": float(q25),
                "q75": float(q75),
                "val_pos_rate": float(y_val.mean()),
                "x_train": x_train,
                "y_train": y_train,
                "x_val": x_val,
                "y_val": y_val,
            }
        )
    return prepared


def _score_binary(
    y_true: np.ndarray, prob_pos: np.ndarray, pred_label: np.ndarray
) -> dict[str, float]:
    return {
        "pr_auc": float(average_precision_score(y_true, prob_pos)),
        "roc_auc": float(roc_auc_score(y_true, prob_pos)),
        "f1": float(f1_score(y_true, pred_label, zero_division=0)),
        "precision": float(precision_score(y_true, pred_label, zero_division=0)),
        "recall": float(recall_score(y_true, pred_label, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred_label)),
    }


def _evaluate_grid(
    candidates: tuple[tuple[str, int | None, int], ...],
    folds: list[dict[str, Any]],
    *,
    family: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for key, max_depth, min_samples_leaf in candidates:
        fold_metrics: list[dict[str, float]] = []
        for fold in folds:
            estimator: BaseEstimator
            if family == "decision_tree":
                estimator = DecisionTreeClassifier(
                    max_depth=max_depth,
                    min_samples_leaf=min_samples_leaf,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                )
            else:
                estimator = RandomForestClassifier(
                    n_estimators=RF_TREES,
                    max_depth=max_depth,
                    min_samples_leaf=min_samples_leaf,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                )
            estimator.fit(fold["x_train"], fold["y_train"])
            prob = estimator.predict_proba(fold["x_val"])[:, 1]
            pred = estimator.predict(fold["x_val"])
            fold_metrics.append(_score_binary(fold["y_val"], prob, pred))

        pr_aucs = np.array([m["pr_auc"] for m in fold_metrics], dtype="float64")
        roc_aucs = np.array([m["roc_auc"] for m in fold_metrics], dtype="float64")
        f1s = np.array([m["f1"] for m in fold_metrics], dtype="float64")
        bal_accs = np.array([m["balanced_accuracy"] for m in fold_metrics], dtype="float64")
        precs = np.array([m["precision"] for m in fold_metrics], dtype="float64")
        recs = np.array([m["recall"] for m in fold_metrics], dtype="float64")
        records.append(
            {
                "key": key,
                "family": family,
                "max_depth": -1 if max_depth is None else max_depth,
                "min_samples_leaf": min_samples_leaf,
                "mean_pr_auc": float(pr_aucs.mean()),
                "se_pr_auc": float(pr_aucs.std(ddof=1) / np.sqrt(len(pr_aucs))),
                "mean_roc_auc": float(roc_aucs.mean()),
                "mean_f1": float(f1s.mean()),
                "mean_precision": float(precs.mean()),
                "mean_recall": float(recs.mean()),
                "mean_balanced_accuracy": float(bal_accs.mean()),
                **{
                    f"pr_auc_{folds[i]['val_season']}": float(pr_aucs[i]) for i in range(len(folds))
                },
            }
        )

    grid_df = pd.DataFrame(records)
    best_idx = int(grid_df["mean_pr_auc"].idxmax())
    best_row = grid_df.iloc[best_idx]
    threshold = float(best_row["mean_pr_auc"] - best_row["se_pr_auc"])
    within = grid_df[grid_df["mean_pr_auc"] >= threshold]
    chosen_row = within.iloc[0]
    selection = {
        "best_key": str(best_row["key"]),
        "best_mean_pr_auc": float(best_row["mean_pr_auc"]),
        "best_se_pr_auc": float(best_row["se_pr_auc"]),
        "one_se_floor": threshold,
        "within_one_se": [str(k) for k in within["key"].tolist()],
        "selected_key": str(chosen_row["key"]),
        "selected_max_depth": None
        if int(chosen_row["max_depth"]) == -1
        else int(chosen_row["max_depth"]),
        "selected_min_samples_leaf": int(chosen_row["min_samples_leaf"]),
        "selected_mean_pr_auc": float(chosen_row["mean_pr_auc"]),
        "selected_mean_roc_auc": float(chosen_row["mean_roc_auc"]),
        "selected_mean_f1": float(chosen_row["mean_f1"]),
        "selected_mean_precision": float(chosen_row["mean_precision"]),
        "selected_mean_recall": float(chosen_row["mean_recall"]),
        "selected_mean_balanced_accuracy": float(chosen_row["mean_balanced_accuracy"]),
    }
    return grid_df, selection


def _plot_cv(
    dt_df: pd.DataFrame,
    rf_df: pd.DataFrame,
    dt_sel: dict[str, Any],
    rf_sel: dict[str, Any],
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, df, sel, title in (
        (axes[0], dt_df, dt_sel, "DecisionTreeClassifier (FULL)"),
        (axes[1], rf_df, rf_sel, "RandomForestClassifier (FULL, 300 trees)"),
    ):
        top = df.sort_values("mean_pr_auc", ascending=False).head(10).iloc[::-1]
        colors = ["#1b6ca8" if k == sel["selected_key"] else "#8da9c4" for k in top["key"]]
        ax.barh(top["key"], top["mean_pr_auc"], xerr=top["se_pr_auc"], color=colors, capsize=3)
        ax.axvline(
            sel["one_se_floor"], color="#d1495b", linestyle="--", linewidth=1.2, label="1-SE floor"
        )
        ax.set_xlabel("5-fold expanding-window PR-AUC")
        ax.set_title(title)
        ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def main() -> None:
    rows, out_dir, manifest = _load_rows()
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        cfg = validate_transform_manifest(manifest)
    except ValueError as exc:
        _fail(str(exc))
    m = cfg.empirical_bayes_m
    prior_grouping = cfg.prior_grouping

    train_rows = rows[rows["split"] == "train"]
    val_rows = rows[rows["split"] == "validation"]
    oof_train = _chronological_oof_residuals(
        train_rows, max_season=2023, m=m, prior_grouping=prior_grouping
    )
    oof_res = oof_train["residual_log10"].to_numpy(dtype="float64")
    q25, q50, q75 = np.percentile(oof_res, [25.0, 50.0, 75.0])
    val_2024 = _heldout_residuals(train_rows, val_rows, m=m, prior_grouping=prior_grouping)
    val_res = val_2024["residual_log10"].to_numpy(dtype="float64")

    threshold_rows: list[dict[str, Any]] = []
    for season, grp in oof_train.groupby("season"):
        r = grp["residual_log10"].to_numpy(dtype="float64")
        threshold_rows.append(
            {
                "scope": f"train_oof_{season}",
                "rows": int(len(r)),
                "mean_residual": float(r.mean()),
                "std_residual": float(r.std(ddof=1)),
                "share_undervalued": float((r >= q75).mean()),
                "share_fair": float(((r > q25) & (r < q75)).mean()),
                "share_overvalued": float((r <= q25).mean()),
            }
        )
    threshold_rows.append(
        {
            "scope": "train_oof_pooled_2018_2023",
            "rows": int(len(oof_res)),
            "mean_residual": float(oof_res.mean()),
            "std_residual": float(oof_res.std(ddof=1)),
            "share_undervalued": float((oof_res >= q75).mean()),
            "share_fair": float(((oof_res > q25) & (oof_res < q75)).mean()),
            "share_overvalued": float((oof_res <= q25).mean()),
        }
    )
    threshold_rows.append(
        {
            "scope": "validation_2024_heldout",
            "rows": int(len(val_res)),
            "mean_residual": float(val_res.mean()),
            "std_residual": float(val_res.std(ddof=1)),
            "share_undervalued": float((val_res >= q75).mean()),
            "share_fair": float(((val_res > q25) & (val_res < q75)).mean()),
            "share_overvalued": float((val_res <= q25).mean()),
        }
    )
    pd.DataFrame(threshold_rows).to_csv(out_dir / "e8_oof_thresholds.csv", index=False)

    folds = _prepare_outer_folds(rows, m=m, prior_grouping=prior_grouping)
    dt_df, dt_sel = _evaluate_grid(DT_CANDIDATES, folds, family="decision_tree")
    rf_df, rf_sel = _evaluate_grid(RF_CANDIDATES, folds, family="random_forest")
    dt_df.to_csv(out_dir / "e8_dt_grid.csv", index=False)
    rf_df.to_csv(out_dir / "e8_rf_grid.csv", index=False)

    naive_pr_auc = float(np.mean([f["val_pos_rate"] for f in folds]))
    comp_df = pd.DataFrame(
        [
            {
                "model": "naive_prevalence_baseline",
                "selected_key": "constant_prior",
                "mean_pr_auc": naive_pr_auc,
                "mean_roc_auc": 0.5,
                "mean_f1": 0.0,
                "mean_precision": 0.0,
                "mean_recall": 0.0,
                "mean_balanced_accuracy": 0.5,
            },
            {
                "model": "decision_tree_selected",
                "selected_key": dt_sel["selected_key"],
                "mean_pr_auc": dt_sel["selected_mean_pr_auc"],
                "mean_roc_auc": dt_sel["selected_mean_roc_auc"],
                "mean_f1": dt_sel["selected_mean_f1"],
                "mean_precision": dt_sel["selected_mean_precision"],
                "mean_recall": dt_sel["selected_mean_recall"],
                "mean_balanced_accuracy": dt_sel["selected_mean_balanced_accuracy"],
            },
            {
                "model": "random_forest_selected",
                "selected_key": rf_sel["selected_key"],
                "mean_pr_auc": rf_sel["selected_mean_pr_auc"],
                "mean_roc_auc": rf_sel["selected_mean_roc_auc"],
                "mean_f1": rf_sel["selected_mean_f1"],
                "mean_precision": rf_sel["selected_mean_precision"],
                "mean_recall": rf_sel["selected_mean_recall"],
                "mean_balanced_accuracy": rf_sel["selected_mean_balanced_accuracy"],
            },
        ]
    )
    comp_df.to_csv(out_dir / "e8_selected_comparison.csv", index=False)

    # Fit selected classifiers on full train OOF (2018..2023) to inspect feature importances
    # and score held-out validation 2024 once.
    full_prep = build_preprocessor(FULL, empirical_bayes_m=m, prior_grouping=prior_grouping)
    x_tr_full = _dense(full_prep.fit_transform(oof_train))
    x_va_full = _dense(full_prep.transform(val_2024))
    y_tr_full = (oof_res >= q75).astype(np.int64)
    y_va_full = (val_res >= q75).astype(np.int64)
    feature_names = [str(name) for name in full_prep.get_feature_names_out()]

    dt_final = DecisionTreeClassifier(
        max_depth=dt_sel["selected_max_depth"],
        min_samples_leaf=dt_sel["selected_min_samples_leaf"],
        class_weight="balanced",
        random_state=RANDOM_STATE,
    )
    rf_final = RandomForestClassifier(
        n_estimators=RF_TREES,
        max_depth=rf_sel["selected_max_depth"],
        min_samples_leaf=rf_sel["selected_min_samples_leaf"],
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    dt_final.fit(x_tr_full, y_tr_full)
    rf_final.fit(x_tr_full, y_tr_full)

    val2024_dt = _score_binary(
        y_va_full, dt_final.predict_proba(x_va_full)[:, 1], dt_final.predict(x_va_full)
    )
    val2024_rf = _score_binary(
        y_va_full, rf_final.predict_proba(x_va_full)[:, 1], rf_final.predict(x_va_full)
    )

    imp_df = pd.DataFrame(
        {
            "feature": feature_names,
            "rf_importance": rf_final.feature_importances_,
            "dt_importance": dt_final.feature_importances_,
        }
    ).sort_values("rf_importance", ascending=False)
    imp_df.to_csv(out_dir / "e8_feature_importance.csv", index=False)

    _plot_cv(dt_df, rf_df, dt_sel, rf_sel, out_dir / "fig_e8_classifier_cv.png")

    summary = {
        "dataset": manifest["dataset"],
        "version": manifest["version"],
        "test_split_touched": False,
        "oof_train_rows": int(len(oof_res)),
        "anchor_2017_rows_excluded_from_oof": int((train_rows["season"] == 2017).sum()),
        "thresholds_log10": {
            "q25_overvalued_ceiling": float(q25),
            "q50_median": float(q50),
            "q75_undervalued_floor": float(q75),
        },
        "thresholds_eur_ratio_fair_over_market": {
            "q25_ratio": float(10.0**q25),
            "q50_ratio": float(10.0**q50),
            "q75_ratio": float(10.0**q75),
        },
        "validation_2024_label_shares": {
            "undervalued": float((val_res >= q75).mean()),
            "fair": float(((val_res > q25) & (val_res < q75)).mean()),
            "overvalued": float((val_res <= q25).mean()),
        },
        "naive_cv_pr_auc": naive_pr_auc,
        "decision_tree_selection": dt_sel,
        "random_forest_selection": rf_sel,
        "validation_2024_scores": {
            "decision_tree": val2024_dt,
            "random_forest": val2024_rf,
        },
        "top_10_rf_features": imp_df.head(10).to_dict(orient="records"),
        "dt_top_rules": export_text(dt_final, feature_names=feature_names, max_depth=3),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote E8 outputs to {out_dir}")


if __name__ == "__main__":
    main()
