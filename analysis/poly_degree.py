"""E4: the polynomial degree on `POLY_REDUCED`, chosen with the one-standard-error rule.

Input: `ml/data/transform/player_seasons.parquet` resolved through `delphos_ml.config`
like `analysis/eda.py`, read with a predicate that keeps only the `train` and
`validation` splits - the 2025 `test` split is never read - plus the transform manifest
`_transform.json` for the dataset version and settings. The expanding-window fold
construction and the metric definitions are imported from `analysis/feature_ablation.py`
so this experiment cannot drift off the E1/E2 protocol.
Output: `e4_poly_degree.csv`, `e4_one_se_summary.csv`, `fig_e4_poly_degree.png` and
`summary.json` under `<repo root>/analysis/output/poly_degree/`.
Responsibility: run E4, which decides docs/ML_ARCHITECTURE.md section 3.7 - the
polynomial degree, and whether any polynomial variant beats the degree-1 linear baseline
on the reduced set. Four variants are scored on the five expanding-window folds, every
fold refitting its own preprocessor on its training seasons only before the expansion
and the OLS fit, and the selection is the simplest variant whose mean fold RMSE lies
within one standard error of the best (docs/TRANSFORM_PLAN.md section 7). The script
reports evidence only; the decision belongs in the architecture docs, not here.

`PolynomialFeatures` runs on the preprocessor's scaled `poly` columns only - five of the
six numeric columns - so `age_sq` passes through untouched and no squared term is
regenerated; `position` is one-hot encoded upstream and also passes through. The module
stays longer than the ~130-line guide for the same reason `feature_ablation.py` does:
ADR-014 gives each experiment script its own output directory, so E4's scoring loop,
tables, figure and summary cannot move into a second analysis module without breaking
that convention, and everything genuinely shareable (folds, metrics) is imported from
`feature_ablation.py` rather than duplicated.
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
from feature_ablation import DEFAULT_M, FOLDS, TARGET, FoldFrame, _fold_frames, _metrics
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

from delphos_ml.config import ConfigError, find_project_root, load_settings
from delphos_ml.features.feature_sets import POLY_REDUCED
from delphos_ml.features.preprocess import build_preprocessor

#: E4 variants as `(key, degree, interaction_only)`. The tuple order is also the
#: complexity order the one-SE rule walks: simplest first, so `degree2_interaction`
#: (5 linear + 10 products) ranks simpler than `degree2_full` (adds 5 squares).
VARIANTS: tuple[tuple[str, int, bool], ...] = (
    ("degree1", 1, False),
    ("degree2_interaction", 2, True),
    ("degree2_full", 2, False),
    ("degree3_full", 3, False),
)

#: Figure tick labels, keyed by variant.
LABELS: dict[str, str] = {
    "degree1": "degree 1\n(linear)",
    "degree2_interaction": "degree 2\ninteraction",
    "degree2_full": "degree 2\nfull",
    "degree3_full": "degree 3\nfull",
}

MetricsByFold = dict[str, dict[str, float | int]]


def _fail(reason: str) -> None:
    print(f"poly_degree failed: {reason}", file=sys.stderr)
    raise SystemExit(1)


def _load_rows() -> tuple[pd.DataFrame, Path, dict[str, Any]]:
    """Read the transform rows (train + validation only), the manifest, and the paths."""
    try:
        settings = load_settings()
    except ConfigError as exc:
        _fail(str(exc))
    project_root = find_project_root()
    repo_root = project_root.parent if project_root is not None else Path.cwd()
    parquet_path = settings.data_dir / "transform" / "player_seasons.parquet"
    manifest_path = settings.data_dir / "transform" / "_transform.json"
    if not parquet_path.is_file():
        _fail(f"missing {parquet_path}; run `uv run delphos-pipeline transform` from ml/ first")
    rows = pd.read_parquet(parquet_path, filters=[("split", "in", ["train", "validation"])])
    if set(rows["split"].unique()) != {"train", "validation"} or rows["season"].max() > 2024:
        raise ValueError("the test split or a post-2024 season reached the analysis frame")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return rows, repo_root / "analysis" / "output" / "poly_degree", manifest


def _dense(matrix: Any) -> np.ndarray:
    """Return the design matrix as a dense ndarray (the one-hot branch may be sparse)."""
    return matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix)


def _splice(matrix: np.ndarray, poly_indices: list[int], block: np.ndarray) -> np.ndarray:
    """Replace the `poly` columns with their expansion, keeping every other column."""
    keep = [index for index in range(matrix.shape[1]) if index not in poly_indices]
    return np.hstack([matrix[:, keep], block])


def _fit_score(
    degree: int, interaction_only: bool, train: pd.DataFrame, val: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    """Fit a fold-scoped preprocessor and OLS on `train`, expand, score `val`.

    Never sees 2025: `train` and `val` come from the shared expanding-window folds.
    At degree 1 no expansion runs, so the variant is the plain linear baseline.
    """
    preprocessor = build_preprocessor(POLY_REDUCED, empirical_bayes_m=DEFAULT_M)
    x_train = _dense(preprocessor.fit_transform(train))
    x_val = _dense(preprocessor.transform(val))
    if degree > 1:
        names = list(preprocessor.get_feature_names_out())
        poly_indices = [names.index(f"numeric__{column}") for column in POLY_REDUCED.poly]
        expansion = PolynomialFeatures(
            degree=degree, interaction_only=interaction_only, include_bias=False
        )
        x_train = _splice(x_train, poly_indices, expansion.fit_transform(x_train[:, poly_indices]))
        x_val = _splice(x_val, poly_indices, expansion.transform(x_val[:, poly_indices]))
    model = LinearRegression()
    model.fit(x_train, train[TARGET])
    return val[TARGET].to_numpy(dtype="float64"), model.predict(x_val)


def _score_variant(degree: int, interaction_only: bool, folds: list[FoldFrame]) -> MetricsByFold:
    """Score one variant on every fold plus the pooled concatenation of the folds."""
    metrics: MetricsByFold = {}
    pooled_true: list[np.ndarray] = []
    pooled_pred: list[np.ndarray] = []
    for fold_key, train, val, _seasons in folds:
        y_true, pred = _fit_score(degree, interaction_only, train, val)
        pooled_true.append(y_true)
        pooled_pred.append(pred)
        metrics[fold_key] = _metrics(y_true, pred)
    metrics["pooled"] = _metrics(np.concatenate(pooled_true), np.concatenate(pooled_pred))
    return metrics


def _expansion_terms(degree: int, interaction_only: bool) -> int | None:
    """Columns `PolynomialFeatures` produces over the `poly` block; None at degree 1."""
    if degree == 1:
        return None
    probe = PolynomialFeatures(degree=degree, interaction_only=interaction_only, include_bias=False)
    probe.fit(np.zeros((1, len(POLY_REDUCED.poly))))
    return int(probe.n_output_features_)


def _means_and_ses(scores: dict[str, MetricsByFold]) -> tuple[dict[str, float], dict[str, float]]:
    """Mean and standard error of the five fold RMSEs for every variant.

    The standard error is the sample standard deviation (ddof=1) of the five fold
    RMSEs divided by sqrt(5); the one-SE rule in docs/TRANSFORM_PLAN.md section 7
    reads it off these numbers.
    """
    fold_keys = [str(index) for index in range(1, len(FOLDS) + 1)]
    means: dict[str, float] = {}
    ses: dict[str, float] = {}
    for key, _degree, _interaction_only in VARIANTS:
        fold_rmses = np.array([scores[key][fold_key]["rmse"] for fold_key in fold_keys])
        means[key] = float(fold_rmses.mean())
        ses[key] = float(fold_rmses.std(ddof=1) / np.sqrt(len(fold_rmses)))
    return means, ses


def _select_one_se(means: dict[str, float], ses: dict[str, float]) -> dict[str, Any]:
    """Apply the one-SE rule: simplest variant within one SE of the best mean RMSE."""
    best_key = min((key for key, _degree, _flag in VARIANTS), key=lambda key: means[key])
    threshold = means[best_key] + ses[best_key]
    within = [key for key, _degree, _flag in VARIANTS if means[key] <= threshold]
    return {
        "best_variant": best_key,
        "best_mean_rmse": means[best_key],
        "best_rmse_se": ses[best_key],
        "one_se_threshold": threshold,
        "selected_variant": within[0],
        "within_one_se": within,
    }


def _variant_table(
    scores: dict[str, MetricsByFold],
    folds: list[FoldFrame],
    means: dict[str, float],
    ses: dict[str, float],
) -> pd.DataFrame:
    """One row per variant x fold plus pooled, carrying the variant's mean and SE."""
    pooled_n_val = sum(len(val) for _key, _train, val, _seasons in folds)
    records: list[dict[str, Any]] = []
    for key, degree, interaction_only in VARIANTS:
        rows: list[tuple[str, int, int, str, str, dict[str, float | int]]] = [
            (fold_key, len(train), len(val), train_seasons, val_season, scores[key][fold_key])
            for fold_key, train, val, (train_seasons, val_season) in folds
        ]
        # The pooled row scores the concatenation of all five validation seasons; its models
        # were fitted on five different training windows, so `n_train` has no honest value.
        rows.append(("pooled", -1, pooled_n_val, "2017-2023", "2020-2024", scores[key]["pooled"]))
        for fold_key, n_train, n_val, train_seasons, val_season, metrics in rows:
            records.append(
                {
                    "variant": key,
                    "degree": degree,
                    "interaction_only": interaction_only,
                    "fold": fold_key,
                    "train_seasons": train_seasons,
                    "val_season": val_season,
                    "n_train": None if n_train < 0 else n_train,
                    "n_val": n_val,
                    **metrics,
                    "mean_rmse": means[key],
                    "rmse_se": ses[key],
                }
            )
    table = pd.DataFrame(records)
    table["n_train"] = table["n_train"].astype("Int64")  # pooled rows have none
    return table


def _one_se_table(
    means: dict[str, float],
    ses: dict[str, float],
    pooled: dict[str, float],
    selection: dict[str, Any],
) -> pd.DataFrame:
    """One row per variant: means, SEs, the threshold, and the in-band/selected flags."""
    records: list[dict[str, Any]] = []
    for key, degree, interaction_only in VARIANTS:
        records.append(
            {
                "variant": key,
                "degree": degree,
                "interaction_only": interaction_only,
                "expansion_terms": _expansion_terms(degree, interaction_only),
                "mean_rmse": means[key],
                "rmse_se": ses[key],
                "pooled_rmse": pooled[key],
                "best_variant": selection["best_variant"],
                "best_mean_rmse": selection["best_mean_rmse"],
                "one_se_threshold": selection["one_se_threshold"],
                "within_one_se": key in selection["within_one_se"],
                "selected": key == selection["selected_variant"],
            }
        )
    table = pd.DataFrame(records)
    table["expansion_terms"] = table["expansion_terms"].astype("Int64")  # degree 1 has none
    return table


def _render_figure(
    out_dir: Path,
    table: pd.DataFrame,
    means: dict[str, float],
    ses: dict[str, float],
    selection: dict[str, Any],
) -> str:
    """Write the RMSE-vs-variant figure with the one-SE band and the selection marked."""
    keys = [key for key, _degree, _flag in VARIANTS]
    positions = list(range(len(keys)))
    fold_keys = [str(index) for index in range(1, len(FOLDS) + 1)]
    fig, axis = plt.subplots(figsize=(7.2, 4.4), constrained_layout=True)
    for fold_key in fold_keys:
        fold_rows = table[table["fold"] == fold_key].set_index("variant").loc[keys]
        axis.plot(positions, fold_rows["rmse"], color="steelblue", alpha=0.35, lw=1)
    pooled = table[table["fold"] == "pooled"].set_index("variant").loc[keys]
    axis.plot(positions, pooled["rmse"], "s--", color="grey", lw=1.5, label="pooled")
    axis.errorbar(
        positions,
        [means[key] for key in keys],
        yerr=[ses[key] for key in keys],
        fmt="o-",
        color="navy",
        lw=2,
        capsize=4,
        label="mean fold RMSE ± 1 SE",
    )
    axis.axhspan(
        selection["best_mean_rmse"],
        selection["one_se_threshold"],
        color="lightgreen",
        alpha=0.35,
        label="one-SE band",
    )
    axis.axvline(
        keys.index(selection["selected_variant"]),
        color="crimson",
        ls="--",
        lw=1.5,
        label=f"selected: {selection['selected_variant']}",
    )
    axis.set_xticks(positions, [LABELS[key] for key in keys])
    axis.set_ylabel("RMSE (log10 EUR)")
    axis.set_title("E4: polynomial degree on POLY_REDUCED")
    axis.legend()
    name = "fig_e4_poly_degree.png"
    fig.savefig(out_dir / name, dpi=240)
    plt.close(fig)
    return name


def run() -> dict[str, Any]:
    """Run E4 and write the CSVs, the figure and `summary.json`; return the summary."""
    rows, out_dir, manifest = _load_rows()
    out_dir.mkdir(parents=True, exist_ok=True)
    folds = _fold_frames(rows)

    scores = {
        key: _score_variant(degree, interaction_only, folds)
        for key, degree, interaction_only in VARIANTS
    }
    means, ses = _means_and_ses(scores)
    selection = _select_one_se(means, ses)
    pooled = {key: float(scores[key]["pooled"]["rmse"]) for key, _degree, _flag in VARIANTS}
    table = _variant_table(scores, folds, means, ses)
    one_se_table = _one_se_table(means, ses, pooled, selection)
    figure = _render_figure(out_dir, table, means, ses, selection)

    linear_mean, linear_pooled = means["degree1"], pooled["degree1"]
    poly_keys = [key for key, _degree, _flag in VARIANTS if key != "degree1"]
    best_poly = min(poly_keys, key=lambda key: means[key])
    selected = selection["selected_variant"]
    beats_linear = {
        "linear_variant": "degree1",
        "linear_mean_rmse": linear_mean,
        "linear_pooled_rmse": linear_pooled,
        "best_polynomial_variant": best_poly,
        "best_polynomial_mean_rmse": means[best_poly],
        "best_polynomial_pooled_rmse": pooled[best_poly],
        "delta_mean_rmse": means[best_poly] - linear_mean,
        "delta_pooled_rmse": pooled[best_poly] - linear_pooled,
        "beats_linear": bool(means[best_poly] < linear_mean),
        "selected_variant": selected,
        "selected_delta_mean_rmse": means[selected] - linear_mean,
    }

    table.to_csv(out_dir / "e4_poly_degree.csv", index=False)
    one_se_table.to_csv(out_dir / "e4_one_se_summary.csv", index=False)

    summary = {
        "input": "data/transform/player_seasons.parquet",
        "dataset_version": manifest.get("version"),
        "manifest_settings": {
            "window_days": manifest.get("window_days"),
            "minutes_floor": manifest.get("minutes_floor"),
            "empirical_bayes_m": manifest.get("empirical_bayes_m"),
            "prior_grouping": manifest.get("prior_grouping"),
        },
        "target": TARGET,
        "splits_read": ["train", "validation"],
        "test_split_read": False,
        "model": "sklearn.linear_model.LinearRegression",
        "feature_set": POLY_REDUCED.name,
        "numeric_columns": list(POLY_REDUCED.numeric),
        "poly_columns": list(POLY_REDUCED.poly),
        "expansion_note": (
            "PolynomialFeatures runs on the preprocessor's scaled poly columns only, with "
            "include_bias=False; age_sq and the one-hot position pass through unchanged."
        ),
        "row_counts": {
            "parquet_rows": manifest.get("tables", {}).get("player_seasons", {}).get("rows"),
            "rows_read": int(len(rows)),
            "rows_per_split_read": {
                str(split): int(count) for split, count in rows["split"].value_counts().items()
            },
            "folds": [
                {
                    "fold": fold_key,
                    "train_seasons": train_seasons,
                    "val_season": val_season,
                    "n_train": len(train),
                    "n_val": len(val),
                }
                for fold_key, train, val, (train_seasons, val_season) in folds
            ],
            "pooled_n_val": sum(len(val) for _key, _train, val, _seasons in folds),
        },
        "variants": [
            {
                "variant": key,
                "degree": degree,
                "expansion": (
                    None
                    if degree == 1
                    else {
                        "degree": degree,
                        "interaction_only": interaction_only,
                        "include_bias": False,
                        "terms": _expansion_terms(degree, interaction_only),
                    }
                ),
            }
            for key, degree, interaction_only in VARIANTS
        ],
        "standard_errors": {
            "definition": (
                "sample standard deviation (ddof=1) of the five fold RMSEs divided by sqrt(5)"
            ),
            "by_variant": {key: {"mean_rmse": means[key], "rmse_se": ses[key]} for key in means},
        },
        "one_se": {
            "rule": (
                "docs/TRANSFORM_PLAN.md section 7: simplest variant whose mean fold RMSE is "
                "within one standard error of the best"
            ),
            **selection,
        },
        "beats_linear_baseline": beats_linear,
        "metrics_by_variant": {
            key: {
                "folds": {
                    fold_key: scores[key][fold_key]
                    for fold_key in sorted(scores[key], key=lambda k: k == "pooled")
                },
                "pooled": scores[key]["pooled"],
            }
            for key in means
        },
        "floored_rows": {
            key: {fold_key: int(scores[key][fold_key]["floored_rows"]) for fold_key in scores[key]}
            for key in means
        },
        "outputs": [
            "e4_poly_degree.csv",
            "e4_one_se_summary.csv",
            figure,
            "summary.json",
        ],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("\nE4 mean fold RMSE by variant:")
    print(
        pd.DataFrame({"mean_rmse": means, "rmse_se": ses, "pooled_rmse": pooled}).to_string(
            float_format=lambda value: f"{value:0.4f}"
        )
    )
    print(
        f"\nOne-SE: best {selection['best_variant']} "
        f"(mean {selection['best_mean_rmse']:.4f} ± {selection['best_rmse_se']:.4f}), "
        f"threshold {selection['one_se_threshold']:.4f}, selected "
        f"{selection['selected_variant']}; within band: {selection['within_one_se']}"
    )
    print(
        f"Best polynomial ({best_poly}) vs linear: delta mean RMSE "
        f"{beats_linear['delta_mean_rmse']:+.4f}, delta pooled "
        f"{beats_linear['delta_pooled_rmse']:+.4f}; beats linear: "
        f"{beats_linear['beats_linear']}"
    )
    print(f"\nOutputs written to {out_dir}")
    return summary


def main() -> None:
    summary = run()
    print(
        f"E4 completed: selected {summary['one_se']['selected_variant']} under the one-SE rule "
        f"(best {summary['one_se']['best_variant']}); polynomial beats linear: "
        f"{summary['beats_linear_baseline']['beats_linear']}"
    )


if __name__ == "__main__":
    main()
