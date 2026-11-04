"""E5: OLS residual diagnostics comparing `log10(market_value)` against raw EUR target.

Input: `ml/data/transform/player_seasons.parquet` and `_transform.json` resolved through
`delphos_ml.config`, read with a predicate keeping only `train` and `validation` (`2017..2024`;
the `2025` `test` split is never read).
Output: `e5_target_comparison.csv`, `e5_quantile_residuals.csv`, `fig_e5_residual_diagnostics.png`,
and `summary.json` under `<repo root>/analysis/output/residual_diagnostics/`.
Responsibility: execute experiment E5 (docs/TRANSFORM_PLAN.md section 7) over the five expanding-
window folds (`validate 2020..2024`) on the finalised `FULL` feature set, contrasting OLS fitted on
`log10_market_value` against OLS fitted directly on `market_value_eur = 10 ** log10_market_value`
via the Breusch-Pagan Lagrange Multiplier heteroscedasticity test, skewness/kurtosis, impossible
negative EUR predictions, and error profiles across market-value quartiles. Placed in its own
single-responsibility script rather than `poly_degree.py` so E4 stays untouched (AGENTS.md §4).
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
import pyarrow as pa
from feature_ablation import FOLDS, TARGET, _fold_frames
from scipy import stats
from sklearn.linear_model import LinearRegression

from delphos_ml.config import ConfigError, find_project_root, load_settings
from delphos_ml.features.feature_sets import FULL
from delphos_ml.features.preprocess import build_preprocessor
from delphos_ml.models import validate_transform_manifest
from delphos_ml.models.scoring import to_dense


def _fail(reason: str) -> None:
    print(f"residual_diagnostics failed: {reason}", file=sys.stderr)
    raise SystemExit(1)


def _load_rows() -> tuple[pd.DataFrame, Path, dict[str, Any]]:
    try:
        settings = load_settings()
    except ConfigError as exc:
        _fail(str(exc))
    project_root = find_project_root()
    repo_root = project_root.parent if project_root is not None else Path.cwd()
    ps_path = settings.data_dir / "transform" / "player_seasons.parquet"
    man_path = settings.data_dir / "transform" / "_transform.json"
    if not ps_path.is_file() or not man_path.is_file():
        _fail(f"missing transform outputs under {settings.data_dir / 'transform'}")
    try:
        rows = pd.read_parquet(ps_path, filters=[("split", "in", ["train", "validation"])])
        manifest = json.loads(man_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, pa.ArrowException) as exc:
        _fail(f"could not read transform outputs: {exc}")
    if set(rows["split"].unique()) != {"train", "validation"} or int(rows["season"].max()) > 2024:
        _fail("unexpected split or post-2024 season reached E5")
    return rows, repo_root / "analysis" / "output" / "residual_diagnostics", manifest


def _breusch_pagan(residuals: np.ndarray, design_matrix: np.ndarray) -> dict[str, float | int]:
    """Studentized Koenker-Bassett / Breusch-Pagan LM test of `e^2` on `design_matrix`."""
    n_rows = int(len(residuals))
    u = residuals**2
    u_centered = u - u.mean()
    denom = float(np.dot(u_centered, u_centered))
    if denom <= 0.0:
        return {"lm_stat": 0.0, "df": 1, "p_value": 1.0, "aux_r2": 0.0}
    aux = LinearRegression().fit(design_matrix, u)
    u_hat = aux.predict(design_matrix) - u.mean()
    r2_aux = float(np.clip(np.dot(u_hat, u_hat) / denom, 0.0, 1.0))
    # Slope degrees of freedom excluding constant intercept / spanning redundancy.
    df = max(1, int(np.linalg.matrix_rank(design_matrix - design_matrix.mean(axis=0))))
    lm_stat = float(n_rows * r2_aux)
    p_val = float(stats.chi2.sf(lm_stat, df))
    return {"lm_stat": lm_stat, "df": df, "p_value": p_val, "aux_r2": r2_aux}


def _white_fitted_bp(residuals: np.ndarray, y_hat: np.ndarray) -> dict[str, float]:
    """2-df Breusch-Pagan / White special-case LM test of `e^2` on `[y_hat, y_hat^2]`."""
    z = (y_hat - y_hat.mean()) / (y_hat.std(ddof=1) or 1.0)
    basis = np.column_stack([z, z**2])
    res = _breusch_pagan(residuals, basis)
    return {
        "fitted_lm_stat": float(res["lm_stat"]),
        "fitted_p_value": float(res["p_value"]),
        "fitted_aux_r2": float(res["aux_r2"]),
    }


def main() -> None:
    rows, out_dir, manifest = _load_rows()
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        cfg = validate_transform_manifest(manifest)
    except ValueError as exc:
        _fail(str(exc))

    folds = _fold_frames(rows)
    log_true_all, log_pred_all = [], []
    eur_true_all, eur_pred_raw_all = [], []
    x_val_blocks = []

    for _fold_key, tr_df, val_df, _seasons in folds:
        prep = build_preprocessor(
            FULL, empirical_bayes_m=cfg.empirical_bayes_m, prior_grouping=cfg.prior_grouping
        )
        x_tr = to_dense(prep.fit_transform(tr_df))
        x_val = to_dense(prep.transform(val_df))

        y_tr_log = tr_df[TARGET].to_numpy(dtype="float64")
        y_val_log = val_df[TARGET].to_numpy(dtype="float64")
        y_tr_eur = np.power(10.0, y_tr_log)
        y_val_eur = np.power(10.0, y_val_log)

        ols_log = LinearRegression().fit(x_tr, y_tr_log)
        ols_eur = LinearRegression().fit(x_tr, y_tr_eur)

        log_true_all.append(y_val_log)
        log_pred_all.append(ols_log.predict(x_val))
        eur_true_all.append(y_val_eur)
        eur_pred_raw_all.append(ols_eur.predict(x_val))
        x_val_blocks.append(x_val)

    y_log = np.concatenate(log_true_all)
    pred_log = np.concatenate(log_pred_all)
    y_eur = np.concatenate(eur_true_all)
    pred_eur_from_log = np.power(10.0, pred_log)
    pred_eur_raw = np.concatenate(eur_pred_raw_all)
    x_pooled = np.vstack(x_val_blocks)

    res_log = y_log - pred_log
    res_eur_raw = y_eur - pred_eur_raw

    bp_log = _breusch_pagan(res_log, x_pooled)
    bp_eur = _breusch_pagan(res_eur_raw, x_pooled)
    wbp_log = _white_fitted_bp(res_log, pred_log)
    wbp_eur = _white_fitted_bp(res_eur_raw, pred_eur_raw)

    ape_from_log = np.abs(y_eur - pred_eur_from_log) / y_eur
    ape_from_raw = np.abs(y_eur - np.maximum(0.0, pred_eur_raw)) / y_eur

    comp_rows = [
        {
            "target_model": "log10_ols_on_full",
            "n_pooled_val": int(len(y_log)),
            "bp_lm_stat": bp_log["lm_stat"],
            "bp_df": bp_log["df"],
            "bp_p_value": bp_log["p_value"],
            "bp_aux_r2": bp_log["aux_r2"],
            **wbp_log,
            "residual_skewness": float(stats.skew(res_log)),
            "residual_excess_kurtosis": float(stats.kurtosis(res_log)),
            "negative_eur_predictions": 0,
            "negative_eur_share": 0.0,
            "mdape_eur": float(np.median(ape_from_log)),
            "rmse_eur": float(np.sqrt(np.mean((y_eur - pred_eur_from_log) ** 2))),
        },
        {
            "target_model": "raw_eur_ols_on_full",
            "n_pooled_val": int(len(y_eur)),
            "bp_lm_stat": bp_eur["lm_stat"],
            "bp_df": bp_eur["df"],
            "bp_p_value": bp_eur["p_value"],
            "bp_aux_r2": bp_eur["aux_r2"],
            **wbp_eur,
            "residual_skewness": float(stats.skew(res_eur_raw)),
            "residual_excess_kurtosis": float(stats.kurtosis(res_eur_raw)),
            "negative_eur_predictions": int((pred_eur_raw <= 0.0).sum()),
            "negative_eur_share": float((pred_eur_raw <= 0.0).mean()),
            "mdape_eur": float(np.median(ape_from_raw)),
            "rmse_eur": float(np.sqrt(np.mean((y_eur - np.maximum(0.0, pred_eur_raw)) ** 2))),
        },
    ]
    comp_df = pd.DataFrame(comp_rows)
    comp_df.to_csv(out_dir / "e5_target_comparison.csv", index=False)

    q_edges = np.percentile(y_eur, [0, 25, 50, 75, 100])
    q_labels = ("Q1 (lowest 25%)", "Q2 (25-50%)", "Q3 (50-75%)", "Q4 (top 25%)")
    bins = np.digitize(y_eur, q_edges[1:-1], right=True)
    q_rows = []
    for q_idx, label in enumerate(q_labels):
        mask = bins == q_idx
        if not mask.any():
            continue
        q_rows.append(
            {
                "value_quartile": label,
                "n_rows": int(mask.sum()),
                "min_eur": float(y_eur[mask].min()),
                "max_eur": float(y_eur[mask].max()),
                "log10_ols_rmse_log10": float(np.sqrt(np.mean(res_log[mask] ** 2))),
                "log10_ols_iqr_log10": float(np.subtract(*np.percentile(res_log[mask], [75, 25]))),
                "log10_ols_mdape_eur": float(np.median(ape_from_log[mask])),
                "raw_eur_ols_mdape_eur": float(np.median(ape_from_raw[mask])),
                "raw_eur_ols_negative_share": float((pred_eur_raw[mask] <= 0.0).mean()),
            }
        )
    q_df = pd.DataFrame(q_rows)
    q_df.to_csv(out_dir / "e5_quantile_residuals.csv", index=False)

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.2), constrained_layout=True)
    rng = np.random.default_rng(20261103)
    sample_idx = rng.choice(len(y_log), size=min(4000, len(y_log)), replace=False)

    axes[0, 0].scatter(pred_log[sample_idx], res_log[sample_idx], s=6, alpha=0.25, color="#1b6ca8")
    axes[0, 0].axhline(0.0, color="#d1495b", ls="--", lw=1.2)
    axes[0, 0].set_xlabel("Predicted log10(EUR)")
    axes[0, 0].set_ylabel("Residual (actual - pred log10)")
    axes[0, 0].set_title(f"log10 OLS: BP R²={bp_log['aux_r2']:.3f}, skew={stats.skew(res_log):.2f}")

    axes[0, 1].scatter(
        pred_eur_raw[sample_idx] / 1e6,
        res_eur_raw[sample_idx] / 1e6,
        s=6,
        alpha=0.25,
        color="#c8553d",
    )
    axes[0, 1].axhline(0.0, color="black", ls="--", lw=1.2)
    axes[0, 1].axvline(0.0, color="#d1495b", ls=":", lw=1.2, label="0 EUR boundary")
    axes[0, 1].set_xlabel("Predicted raw EUR (millions)")
    axes[0, 1].set_ylabel("Residual EUR (millions)")
    axes[0, 1].set_title(
        f"Raw EUR OLS: BP R²={bp_eur['aux_r2']:.3f}, skew={stats.skew(res_eur_raw):.2f}"
    )
    axes[0, 1].legend(loc="upper left")

    stats.probplot(res_log, dist="norm", plot=axes[1, 0])
    axes[1, 0].set_title("Normal Q-Q plot of log10 OLS residuals")

    x_pos = np.arange(len(q_labels))
    axes[1, 1].bar(x_pos - 0.18, q_df["log10_ols_mdape_eur"], width=0.35, label="log10 OLS")
    axes[1, 1].bar(x_pos + 0.18, q_df["raw_eur_ols_mdape_eur"], width=0.35, label="Raw EUR OLS")
    axes[1, 1].set_xticks(x_pos, ["Q1", "Q2", "Q3", "Q4"])
    axes[1, 1].set_ylabel("MdAPE (EUR)")
    axes[1, 1].set_title("MdAPE across actual market-value quartiles")
    axes[1, 1].legend()

    fig.savefig(out_dir / "fig_e5_residual_diagnostics.png", dpi=180)
    plt.close(fig)

    summary = {
        "dataset_version": manifest.get("version"),
        "splits_read": ["train", "validation"],
        "test_split_read": False,
        "folds_pooled_rows": int(len(y_log)),
        "folds": [f"{s_tr}->{s_val}" for s_tr, s_val in FOLDS],
        "comparison": comp_rows,
        "by_value_quartile": q_rows,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(comp_df.to_string(index=False))
    print("\nQuartile breakdown:")
    print(q_df.to_string(index=False))


if __name__ == "__main__":
    main()
