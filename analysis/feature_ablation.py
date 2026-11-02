"""Feature-group ablation (E1) and Empirical Bayes strength sweep (E2) on the linear model.

Input: `ml/data/transform/player_seasons.parquet` resolved through `delphos_ml.config` like
`analysis/eda.py`, read with a predicate that keeps only the `train` and `validation` splits -
the 2025 `test` split is never read.
Output: `e1_ablation.csv`, `e1_rate_variant.csv`, `e1b_raw_counts.csv`, `e2_m_sweep.csv`,
`e2b_m_sweep.csv`, `e3_vif.csv`, `e3b_age_basis.csv`, `fig_e1_ablation.png`,
`fig_e2_m_sweep.png`, `fig_e3b_age_basis.png` and `summary.json` under
`<repo root>/analysis/output/feature_ablation/`.
Responsibility: run the five runs that decide docs/ML_ARCHITECTURE.md section 3.6 - E1,
the feature-group ablation on OLS market-value regression; E2, the `m` sweep that confirms
or changes the provisional `m = 5` for valuation; E1b, the raw production-count comparison
rung with `league_id` kept out of both sides; E2b, the `m` re-sweep on E1b's winning
variant, because E2 ran on rung 5 with `league_id` in the set; and E3, the variance
inflation factors over the finalised `FULL` design matrix, which say whether any column
must be dropped or combined for the OLS coefficients to stay interpretable. The script
reports evidence only; the decisions belong in the architecture docs, not here.

E3b (`age_basis`) is a sixth, narrower run that gates one decision E3 left open: E3 put
`age` and `age_sq` at VIF ~127 each because they correlate at r = 0.996, a polynomial-
basis artefact rather than redundant data, so mean-centring `age` before squaring spans
the identical space - OLS fit and every OLS prediction are unchanged, only the
coordinates move - but the Random Forest and the Decision Tree consume `age_sq` as a
genuinely distinct feature. E3b scores both tree families on both age bases (raw as the
transform stage wrote it, centred on the fold's training mean) with OLS rung as the
identity control: if OLS is not identical across the two bases, the centring
implementation is wrong, and that - not the tree scores - is the finding.

The four fold-based runs share one protocol and therefore one scoring core: expanding-window season
folds inside `train` + `validation` (train 2017-2019 validate 2020, and so on up to train
2017-2023 validate 2024), and every fold fits its own preprocessor - Empirical Bayes priors,
height medians, scalers, one-hot vocabularies - on that fold's training seasons only before OLS
scores that fold's validation season (the leak discipline pinned in `ml/tests/test_preprocess.py`).
E3b reuses exactly those folds and that per-fold preprocessor discipline; only the model
and the age basis change, and the centring mean comes from the fold's training seasons
alone so nothing leaks across the fold boundary.
The module is longer than a screen because it is one experiment script per ADR-014: splitting
the shared fold, metric and figure code into a second analysis module would break the
one-script-one-output-dir convention without shortening anything.

The ladder's rung 5 (`league_id`) was measured but is rejected on methodological grounds:
league is a pricing variable, not a performance variable, so with it in the model the
undervaluation residual measures price versus the league's typical price instead of price
versus performance - the same reasoning that excluded prior market value
(docs/REPORT_NOTES.md H-09) and that keeps league out of `CLUSTER`. Predictive accuracy is
deliberately traded away: `summary.json` records `league_excluded: true`, and E1b and E2b
run on the ladder without it.

E2's `m = 0` point cannot pass through `build_preprocessor`, whose sink refuses `m <= 0`
(pinned by `test_build_preprocessor_refuses_an_unusable_m`); it is scored as the raw-rate
variant - `<count>_per90 = count / (minutes / 90)` columns in the numeric branch - which is the
Empirical Bayes formula at `m = 0` exactly, because the transform stage's 180-minute floor keeps
the denominator positive. The same variant is E1's raw branch at rung 3.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.tree import DecisionTreeRegressor

from delphos_ml.config import ConfigError, find_project_root, load_settings
from delphos_ml.features.feature_sets import FULL, FeatureSet
from delphos_ml.features.preprocess import build_preprocessor

TARGET = "log10_market_value"

#: Expanding-window folds as `(last train season, validation season)`; train always starts 2017.
FOLDS: tuple[tuple[int, int], ...] = (
    (2019, 2020),
    (2020, 2021),
    (2021, 2022),
    (2022, 2023),
    (2023, 2024),
)

RATE_COUNTS: tuple[str, ...] = ("goals", "assists", "yellow_cards", "red_cards")
PER90_COLUMNS: tuple[str, ...] = tuple(f"{count}_per90" for count in RATE_COUNTS)

#: E3: a VIF above this leaves OLS coefficients uninterpretable (TRANSFORM_PLAN section 7).
VIF_FLAG_THRESHOLD = 10.0
#: Auxiliary R^2 within this distance of 1 is exact collinearity, reported as VIF = infinity
#: instead of a floating-point artefact of the least-squares solve.
VIF_EXACT_TOL = 1e-12
#: Pairwise |r| at or above which another design column is listed as a collinear partner.
VIF_STRONG_CORR = 0.5
VIF_METHOD = (
    "1 / (1 - R^2) computed directly: each design column regressed on the remaining ones "
    "with an intercept (statsmodels is not a dependency of the analysis dependency group)"
)

#: E2 sweep; `0.0` is the unsmoothed raw per-90 rates, not a neutral baseline.
M_SWEEP: tuple[float, ...] = (0.0, 2.0, 5.0, 10.0, 20.0)
DEFAULT_M = 5.0
PRIOR_GROUPING = "position"

#: E3b age bases: `raw` is `age`/`age_sq` exactly as the transform stage wrote them;
#: `centred` rebases `age` on the fold's training mean and re-derives `age_sq = age_c ** 2`.
E3B_BASES: tuple[str, ...] = ("raw", "centred")
#: Fixed hyperparameters for E3b. The forest size keeps its Monte-Carlo noise (about
#: 0.001 RMSE between seeds at 500 trees) well under the raw-versus-centred gap being
#: measured; the unpruned tree overfits on purpose (depth ~40 on this data), so a modest
#: depth variant carries the comparison too and it cannot hinge on one bad configuration.
E3B_SEED = 42
E3B_FOREST_TREES = 500
E3B_TREE_DEPTH = 8
#: OLS must score identically on both age bases - the two bases span the same column
#: space - so only floating-point noise may separate them. A larger gap means the
#: centring implementation is wrong, which is the whole point of the control.
E3B_OLS_IDENTITY_TOL = 1e-9

#: E3b model configurations as `(CSV model key, factory, description)`; the factory is
#: called once per cell so every fold gets a fresh estimator.
E3B_MODELS: tuple[tuple[str, Callable[[], BaseEstimator], str], ...] = (
    (
        "random_forest",
        lambda: RandomForestRegressor(
            n_estimators=E3B_FOREST_TREES, random_state=E3B_SEED, n_jobs=-1
        ),
        f"RandomForestRegressor(n_estimators={E3B_FOREST_TREES}, "
        f"random_state={E3B_SEED}, n_jobs=-1)",
    ),
    (
        "decision_tree",
        lambda: DecisionTreeRegressor(random_state=E3B_SEED),
        f"DecisionTreeRegressor(random_state={E3B_SEED}) - unpruned, overfits",
    ),
    (
        f"decision_tree_depth{E3B_TREE_DEPTH}",
        lambda: DecisionTreeRegressor(max_depth=E3B_TREE_DEPTH, random_state=E3B_SEED),
        f"DecisionTreeRegressor(max_depth={E3B_TREE_DEPTH}, random_state={E3B_SEED})",
    ),
    ("ols", LinearRegression, "LinearRegression() - identity control across age bases"),
)

BIOGRAPHICAL = FeatureSet(
    name="rung1_biographical",
    numeric=("age", "age_sq", "height_in_cm"),
    categorical=("foot", "position", "sub_position", "country_group"),
)
VOLUME = FeatureSet(
    name="rung2_volume",
    numeric=(*BIOGRAPHICAL.numeric, "minutes", "apps", "starts", "starter_ratio", "captain_ratio"),
    categorical=BIOGRAPHICAL.categorical,
    log1p=("minutes", "apps"),
)
RATES_EB = FeatureSet(
    name="rung3_rates_eb",
    numeric=VOLUME.numeric,
    categorical=VOLUME.categorical,
    log1p=VOLUME.log1p,
    rates=RATE_COUNTS,
)
RATES_RAW = FeatureSet(
    name="rung3_rates_raw",
    numeric=(*VOLUME.numeric, *PER90_COLUMNS),
    categorical=VOLUME.categorical,
    log1p=VOLUME.log1p,
)
TEAM_CONTEXT = replace(
    RATES_EB,
    name="rung4_team_context",
    numeric=(
        *RATES_EB.numeric,
        "win_rate",
        "clean_sheet_rate",
        "goals_conceded_per_match",
        "uefa_share",
        "cup_share",
        "league_position",
    ),
)
LEAGUE = replace(
    TEAM_CONTEXT,
    name="rung5_league",
    categorical=(*TEAM_CONTEXT.categorical, "league_id"),
)

#: E1b variant B: variant A plus the raw production counts, carried the way the
#: provisional `FULL` declares them - `log1p` on the skewed goals and assists, plain on
#: the cards - so a win maps straight onto `FULL` and a null result cannot be blamed on
#: the encoding.
RAW_COUNTS = replace(
    TEAM_CONTEXT,
    name="e1b_raw_counts",
    numeric=(*TEAM_CONTEXT.numeric, *RATE_COUNTS),
    log1p=(*TEAM_CONTEXT.log1p, "goals", "assists"),
)

#: The E1 ladder as `(rung key, previous rung key, feature set)`; rung 3 is a fork, so both
#: branches name rung 2 as their predecessor and rung 4 builds on the EB branch.
LADDER: tuple[tuple[str, str | None, FeatureSet], ...] = (
    ("1_biographical", None, BIOGRAPHICAL),
    ("2_volume", "1_biographical", VOLUME),
    ("3_rates_raw", "2_volume", RATES_RAW),
    ("3_rates_eb", "2_volume", RATES_EB),
    ("4_team_context", "3_rates_eb", TEAM_CONTEXT),
    ("5_league", "4_team_context", LEAGUE),
)

FoldFrame = tuple[str, pd.DataFrame, pd.DataFrame, tuple[str, str]]


def _fail(reason: str) -> None:
    print(f"feature_ablation failed: {reason}", file=sys.stderr)
    raise SystemExit(1)


def _with_raw_rates(feature_set: FeatureSet) -> FeatureSet:
    """Swap the EB rates branch for raw per-90 columns: the EB formula at `m = 0` exactly."""
    if feature_set.rates != RATE_COUNTS:
        raise ValueError(f"{feature_set.name} does not carry the rate counts this swap assumes")
    return replace(feature_set, numeric=(*feature_set.numeric, *PER90_COLUMNS), rates=())


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
    exposure = rows["minutes"] / 90.0
    for count, per90 in zip(RATE_COUNTS, PER90_COLUMNS, strict=True):
        rows[per90] = rows[count] / exposure
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return rows, repo_root / "analysis" / "output" / "feature_ablation", manifest


def _fold_frames(rows: pd.DataFrame) -> list[FoldFrame]:
    """Materialise the expanding-window folds: `(fold key, train, val, season labels)`."""
    frames: list[FoldFrame] = []
    for index, (last_train, val_season) in enumerate(FOLDS, start=1):
        train = rows[(rows["season"] >= 2017) & (rows["season"] <= last_train)]
        val = rows[rows["season"] == val_season]
        frames.append((str(index), train, val, (f"2017-{last_train}", str(val_season))))
    return frames


def _fit_score(
    feature_set: FeatureSet, train: pd.DataFrame, val: pd.DataFrame, empirical_bayes_m: float
) -> tuple[np.ndarray, np.ndarray]:
    """Fit a fold-scoped preprocessor and OLS on `train`, score `val`. Never sees 2025."""
    preprocessor = build_preprocessor(feature_set, empirical_bayes_m=empirical_bayes_m)
    model = LinearRegression()
    model.fit(preprocessor.fit_transform(train), train[TARGET])
    return val[TARGET].to_numpy(dtype="float64"), model.predict(preprocessor.transform(val))


def _metrics(y_true: np.ndarray, pred: np.ndarray) -> dict[str, float | int]:
    """RMSE, MAE, R2 and MdAPE in EUR; the back-transformed prediction is floored at 0."""
    actual_eur = np.power(10.0, y_true)
    pred_eur = np.power(10.0, pred)
    floored_rows = int((~(pred_eur > 0)).sum())  # non-finite predictions count as floored
    ape = np.abs(actual_eur - np.clip(pred_eur, 0.0, None)) / actual_eur
    return {
        "rmse": float(mean_squared_error(y_true, pred) ** 0.5),
        "mae": float(mean_absolute_error(y_true, pred)),
        "r2": float(r2_score(y_true, pred)),
        "mdape_eur_pct": float(np.median(ape) * 100.0),
        "floored_rows": floored_rows,
    }


def _score_variants(
    variants: list[tuple[str, FeatureSet]], folds: list[FoldFrame]
) -> dict[str, dict[str, dict[str, float | int]]]:
    """Score every `(key, feature set)` on every fold plus the pooled concatenation."""
    metrics_by_key: dict[str, dict[str, dict[str, float | int]]] = {}
    for key, feature_set in variants:
        metrics_by_key[key] = {}
        pooled_true: list[np.ndarray] = []
        pooled_pred: list[np.ndarray] = []
        # The rates branch is a no-op when `rates` is empty, so DEFAULT_M is inert there.
        for fold_key, train, val, _seasons in folds:
            y_true, pred = _fit_score(feature_set, train, val, DEFAULT_M)
            pooled_true.append(y_true)
            pooled_pred.append(pred)
            metrics_by_key[key][fold_key] = _metrics(y_true, pred)
        metrics_by_key[key]["pooled"] = _metrics(
            np.concatenate(pooled_true), np.concatenate(pooled_pred)
        )
    return metrics_by_key


def _score_rungs(folds: list[FoldFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score every ladder rung on every fold; return the ablation and rate-fork tables."""
    metrics_by_key = _score_variants(
        [(key, feature_set) for key, _prev, feature_set in LADDER], folds
    )

    records: list[dict[str, Any]] = []
    pooled_n_val = sum(len(val) for _key, _train, val, _seasons in folds)
    row_keys: list[tuple[str, int, int, str, str]] = [
        (fold_key, len(train), len(val), train_seasons, val_season)
        for fold_key, train, val, (train_seasons, val_season) in folds
    ]
    # The pooled row scores the concatenation of all five validation seasons; its models were
    # fitted on five different training windows, so `n_train` has no single honest value.
    row_keys.append(("pooled", -1, pooled_n_val, "2017-2023", "2020-2024"))
    for rung_key, prev_key, feature_set in LADDER:
        for fold_key, n_train, n_val, train_seasons, val_season in row_keys:
            record: dict[str, Any] = {
                "rung": rung_key,
                "rung_name": feature_set.name,
                "fold": fold_key,
                "train_seasons": train_seasons,
                "val_season": val_season,
                "n_train": None if n_train < 0 else n_train,
                "n_val": n_val,
                **metrics_by_key[rung_key][fold_key],
                "prev_rung": prev_key or "",
                "delta_rmse": np.nan,
                "delta_r2": np.nan,
            }
            if prev_key is not None:
                prev = metrics_by_key[prev_key][fold_key]
                record["delta_rmse"] = record["rmse"] - prev["rmse"]
                record["delta_r2"] = record["r2"] - prev["r2"]
            records.append(record)
    ablation = pd.DataFrame(records)
    ablation["n_train"] = ablation["n_train"].astype("Int64")  # pooled rows have none

    fork: list[dict[str, Any]] = []
    fork_frames: list[tuple[str, int, tuple[str, str]]] = [
        (fold_key, len(val), (train_seasons, val_season))
        for fold_key, _train, val, (train_seasons, val_season) in folds
    ]
    fork_frames.append(("pooled", sum(n for _k, n, _s in fork_frames), ("2017-2023", "2020-2024")))
    for fold_key, n_val, (train_seasons, val_season) in fork_frames:
        raw = metrics_by_key["3_rates_raw"][fold_key]
        eb = metrics_by_key["3_rates_eb"][fold_key]
        fork.append(
            {
                "fold": fold_key,
                "train_seasons": train_seasons,
                "val_season": val_season,
                "n_val": n_val,
                "rmse_raw": raw["rmse"],
                "rmse_eb": eb["rmse"],
                "delta_rmse_eb_minus_raw": float(eb["rmse"]) - float(raw["rmse"]),
                "r2_raw": raw["r2"],
                "r2_eb": eb["r2"],
                "delta_r2_eb_minus_raw": float(eb["r2"]) - float(raw["r2"]),
                "mdape_raw_pct": raw["mdape_eur_pct"],
                "mdape_eb_pct": eb["mdape_eur_pct"],
                "floored_rows_raw": raw["floored_rows"],
                "floored_rows_eb": eb["floored_rows"],
            }
        )
    return ablation, pd.DataFrame(fork)


def _score_e1b(ablation: pd.DataFrame, folds: list[FoldFrame]) -> pd.DataFrame:
    """Score E1b: the rung-4 set without league (A) against it plus raw counts (B).

    Variant A needs no refit - it is exactly the `4_team_context` rung the ladder already
    scored at the same folds and the same `m`, so its metrics are read off `ablation`
    and only variant B is fitted. One row per fold plus the pooled row, wide with both
    sides and the B-minus-A deltas.
    """
    metrics_b = _score_variants([("b", RAW_COUNTS)], folds)["b"]
    rung_rows = ablation[ablation["rung"] == "4_team_context"].set_index("fold")
    fold_keys = [fold_key for fold_key, _train, _val, _seasons in folds]
    records: list[dict[str, Any]] = []
    for fold_key in [*fold_keys, "pooled"]:
        a = rung_rows.loc[fold_key]
        b = metrics_b[fold_key]
        records.append(
            {
                "variant_a": TEAM_CONTEXT.name,
                "variant_b": RAW_COUNTS.name,
                "fold": fold_key,
                "train_seasons": a["train_seasons"],
                "val_season": a["val_season"],
                "n_val": int(a["n_val"]),
                "rmse_a": float(a["rmse"]),
                "rmse_b": float(b["rmse"]),
                "delta_rmse_b_minus_a": float(b["rmse"]) - float(a["rmse"]),
                "mae_a": float(a["mae"]),
                "mae_b": float(b["mae"]),
                "delta_mae_b_minus_a": float(b["mae"]) - float(a["mae"]),
                "r2_a": float(a["r2"]),
                "r2_b": float(b["r2"]),
                "delta_r2_b_minus_a": float(b["r2"]) - float(a["r2"]),
                "mdape_a_pct": float(a["mdape_eur_pct"]),
                "mdape_b_pct": float(b["mdape_eur_pct"]),
                "delta_mdape_eur_pct_b_minus_a": float(b["mdape_eur_pct"])
                - float(a["mdape_eur_pct"]),
                "floored_rows_a": int(a["floored_rows"]),
                "floored_rows_b": int(b["floored_rows"]),
            }
        )
    return pd.DataFrame(records)


def _sweep_m(winning: FeatureSet, folds: list[FoldFrame]) -> pd.DataFrame:
    """Rescore a feature set at each `m`; `m = 0` goes through the raw-rate variant.

    Used by E2 on the ladder winner and by E2b on E1b's winning variant.
    """
    records: list[dict[str, Any]] = []
    for m in M_SWEEP:
        use_raw = m == 0.0 and winning.rates == RATE_COUNTS
        feature_set = _with_raw_rates(winning) if use_raw else winning
        # Inert when the set carries no rates branch (degenerate sweep), which is the case
        # only if a rung without the EB rates won E1.
        empirical_bayes_m = m if m > 0.0 else DEFAULT_M
        pooled_true: list[np.ndarray] = []
        pooled_pred: list[np.ndarray] = []
        for fold_key, train, val, (train_seasons, val_season) in folds:
            y_true, pred = _fit_score(feature_set, train, val, empirical_bayes_m)
            pooled_true.append(y_true)
            pooled_pred.append(pred)
            records.append(
                {
                    "m": m,
                    "variant": "raw_rates" if m == 0.0 else "eb_rates",
                    "fold": fold_key,
                    "train_seasons": train_seasons,
                    "val_season": val_season,
                    "n_val": len(val),
                    **_metrics(y_true, pred),
                }
            )
        records.append(
            {
                "m": m,
                "variant": "raw_rates" if m == 0.0 else "eb_rates",
                "fold": "pooled",
                "train_seasons": "2017-2023",
                "val_season": "2020-2024",
                "n_val": sum(len(chunk) for chunk in pooled_true),
                **_metrics(np.concatenate(pooled_true), np.concatenate(pooled_pred)),
            }
        )
    return pd.DataFrame(records)


def _render_figures(
    out_dir: Path,
    ablation: pd.DataFrame,
    e1b: pd.DataFrame,
    sweep: pd.DataFrame,
    e2b: pd.DataFrame,
    optimum_m: float,
) -> list[str]:
    """Write the two figures; pooled metrics bold, per-fold metrics as thin context lines.

    E1 shows the no-league ladder (rungs 1 to 4) plus E1b's raw-count variant B; rung 5
    was measured but rejected (see `league_excluded` in `summary.json`). E2 shows E2b's
    re-swept curve with the reference line at the new optimum, and the E2 curve on rung
    5 as grey context for what the league exclusion moved.
    """
    fold_keys = [str(i) for i in range(1, len(FOLDS) + 1)]
    rungs_no_league = ["1_biographical", "2_volume", "3_rates_raw", "3_rates_eb", "4_team_context"]
    labels = [*rungs_no_league, "4b_raw_counts"]
    variant_b = e1b.assign(rung="4b_raw_counts", rmse=e1b["rmse_b"], r2=e1b["r2_b"])
    ladder = pd.concat(
        [
            ablation[ablation["rung"].isin(rungs_no_league)][["rung", "fold", "rmse", "r2"]],
            variant_b[["rung", "fold", "rmse", "r2"]],
        ],
        ignore_index=True,
    )
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    for axis, metric, title in ((axes[0], "rmse", "RMSE (log10 EUR)"), (axes[1], "r2", "R$^2$")):
        for fold_key in fold_keys:
            fold_rows = ladder[ladder["fold"] == fold_key].set_index("rung").loc[labels]
            axis.plot(range(len(labels)), fold_rows[metric], color="steelblue", alpha=0.35, lw=1)
        pooled = ladder[ladder["fold"] == "pooled"].set_index("rung").loc[labels]
        axis.plot(range(len(labels)), pooled[metric], "o-", color="navy", lw=2, label="pooled")
        axis.set_xticks(range(len(labels)), labels, rotation=30, ha="right")
        axis.set_title(title)
        axis.legend()
    fig.suptitle("E1/E1b: feature-group ablation without league_id")
    fig.savefig(out_dir / "fig_e1_ablation.png", dpi=240)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(6.8, 4.2), constrained_layout=True)
    for fold_key in fold_keys:
        fold_rows = e2b[e2b["fold"] == fold_key]
        axis.plot(fold_rows["m"], fold_rows["rmse"], color="darkorange", alpha=0.35, lw=1)
    previous_pooled = sweep[sweep["fold"] == "pooled"]
    axis.plot(
        previous_pooled["m"],
        previous_pooled["rmse"],
        "s--",
        color="grey",
        lw=1.5,
        label="pooled E2 (rung 5, league)",
    )
    pooled_e2b = e2b[e2b["fold"] == "pooled"]
    axis.plot(pooled_e2b["m"], pooled_e2b["rmse"], "o-", color="navy", lw=2, label="pooled E2b")
    axis.axvline(
        optimum_m, color="crimson", ls="--", lw=1.5, label=f"m = {optimum_m:g} (E2b optimum)"
    )
    axis.set_xlabel("Empirical Bayes strength m (0 = raw per-90 rates)")
    axis.set_ylabel("RMSE (log10 EUR)")
    axis.set_title("E2b: EB strength sweep on the E1b winner (no league)")
    axis.legend()
    fig.savefig(out_dir / "fig_e2_m_sweep.png", dpi=240)
    plt.close(fig)
    return ["fig_e1_ablation.png", "fig_e2_m_sweep.png"]


def _render_e3b_figure(out_dir: Path, e3b: pd.DataFrame) -> str:
    """Write `fig_e3b_age_basis.png`: RMSE by model family, raw versus centred age basis.

    Each model family gets a raw and a centred slot; the five per-fold RMSEs scatter
    behind a larger pooled marker and a thin line joins the two pooled points, so the
    basis gap reads against the fold-to-fold spread at a glance. Fold points get a small
    deterministic horizontal jitter inside their slot, otherwise the tight RMSE cluster
    hides them behind the pooled diamond. OLS sits in the frame on purpose: its two
    markers must coincide, which is the identity control plotted.
    """
    labels = {
        "random_forest": "Random\nForest",
        "decision_tree": "Decision Tree\n(unpruned)",
        f"decision_tree_depth{E3B_TREE_DEPTH}": f"Decision Tree\n(max_depth={E3B_TREE_DEPTH})",
        "ols": "OLS\n(control)",
    }
    offsets = {"raw": -0.14, "centred": 0.14}
    colours = {"raw": "steelblue", "centred": "darkorange"}
    fold_rows = e3b[e3b["fold"] != "pooled"]
    pooled_rows = e3b[e3b["fold"] == "pooled"].set_index(["model", "age_basis"])
    model_keys = [key for key, _factory, _description in E3B_MODELS]

    fig, axis = plt.subplots(figsize=(7.6, 4.4), constrained_layout=True)
    for index, model_key in enumerate(model_keys):
        pooled_points: dict[str, float] = {}
        for basis in E3B_BASES:
            x = index + offsets[basis]
            fold_rmse = fold_rows[
                (fold_rows["model"] == model_key) & (fold_rows["age_basis"] == basis)
            ]["rmse"]
            jitter = np.linspace(-0.06, 0.06, len(fold_rmse))
            axis.scatter(
                x + jitter,
                fold_rmse,
                s=22,
                color=colours[basis],
                alpha=0.45,
                zorder=3,
            )
            pooled = float(pooled_rows.loc[(model_key, basis), "rmse"])
            pooled_points[basis] = pooled
            axis.scatter(
                x,
                pooled,
                s=90,
                marker="D",
                color=colours[basis],
                edgecolor="black",
                linewidth=0.6,
                zorder=4,
                label=f"{basis} (pooled)" if index == 0 else None,
            )
        axis.plot(
            [index + offsets["raw"], index + offsets["centred"]],
            [pooled_points["raw"], pooled_points["centred"]],
            color="grey",
            lw=1,
            alpha=0.7,
            zorder=2,
        )
    axis.set_xticks(range(len(model_keys)), [labels[key] for key in model_keys])
    axis.set_ylabel("RMSE (log10 EUR)")
    axis.set_title("E3b: raw vs mean-centred age basis (small dots = folds, diamond = pooled)")
    axis.legend()
    fig.savefig(out_dir / "fig_e3b_age_basis.png", dpi=240)
    plt.close(fig)
    return "fig_e3b_age_basis.png"


def _pooled_records(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """JSON-safe pooled metric records keyed by rung (or `m` for the sweep)."""
    records: dict[str, dict[str, Any]] = {}
    for _index, row in frame.iterrows():
        records[str(row.get("rung", row.get("m")))] = {
            key: (int(row[key]) if key == "floored_rows" else float(row[key]))
            for key in ("rmse", "mae", "r2", "mdape_eur_pct", "floored_rows")
            if key in row
        }
    return records


def _side(row: pd.Series, side: str) -> dict[str, float | int]:
    """JSON-safe pooled metrics for one side (`a` or `b`) of an E1b row."""
    return {
        "rmse": float(row[f"rmse_{side}"]),
        "mae": float(row[f"mae_{side}"]),
        "r2": float(row[f"r2_{side}"]),
        "mdape_eur_pct": float(row[f"mdape_{side}_pct"]),
        "floored_rows": int(row[f"floored_rows_{side}"]),
    }


def _m_gap(pooled: pd.DataFrame, optimum_m: float, reference_m: float) -> dict[str, float]:
    """Pooled RMSE/R2 of `optimum_m` minus `reference_m`; a negative delta favours optimum."""
    by_m = pooled.set_index("m")
    return {
        "rmse_optimum": float(by_m.loc[optimum_m, "rmse"]),
        "rmse_reference": float(by_m.loc[reference_m, "rmse"]),
        "delta_rmse": float(by_m.loc[optimum_m, "rmse"] - by_m.loc[reference_m, "rmse"]),
        "delta_r2": float(by_m.loc[optimum_m, "r2"] - by_m.loc[reference_m, "r2"]),
    }


def _dense(matrix: Any) -> np.ndarray:
    """Dense float64 array from either the sparse or dense preprocessor output."""
    toarray = getattr(matrix, "toarray", None)
    return np.asarray(toarray() if toarray is not None else matrix, dtype="float64")


def _vif_table(design: np.ndarray, names: list[str]) -> pd.DataFrame:
    """One VIF row per design column, with the partners that make it redundant.

    VIF is `1 / (1 - R^2)`, with `R^2` from an OLS of the column on every other design
    column plus an intercept; `R^2` within `VIF_EXACT_TOL` of 1 is exact collinearity and
    is reported as infinity rather than a floating-point artefact. `statsmodels` is not in
    the analysis dependency group, so the regression is scikit-learn's `LinearRegression`.
    `max_abs_corr_with` and `strong_corr_partners` name the block a flagged column is
    redundant with: every other column at pairwise |r| >= `VIF_STRONG_CORR`.
    """
    correlation = np.corrcoef(design, rowvar=False)
    records: list[dict[str, Any]] = []
    for index, name in enumerate(names):
        target = design[:, index]
        others = np.delete(design, index, axis=1)
        ss_tot = float(((target - target.mean()) ** 2).sum())
        if ss_tot == 0.0:
            records.append(
                {
                    "column": name,
                    "vif": np.nan,
                    "aux_r2": np.nan,
                    "flagged_gt_10": False,
                    "exact_collinear": False,
                    "max_abs_corr": np.nan,
                    "max_abs_corr_with": "",
                    "strong_corr_partners": "",
                }
            )
            continue
        residual = target - LinearRegression().fit(others, target).predict(others)
        one_minus_r2 = float((residual**2).sum()) / ss_tot
        exact = one_minus_r2 <= VIF_EXACT_TOL
        vif = float("inf") if exact else 1.0 / one_minus_r2
        corr_abs = np.abs(correlation[index])
        corr_abs[index] = np.nan
        known = np.flatnonzero(~np.isnan(corr_abs))
        best = int(known[np.argmax(corr_abs[known])]) if known.size else -1
        strong = [names[j] for j in known if corr_abs[j] >= VIF_STRONG_CORR]
        records.append(
            {
                "column": name,
                "vif": vif,
                "aux_r2": min(1.0, 1.0 - one_minus_r2),
                "flagged_gt_10": bool(vif > VIF_FLAG_THRESHOLD),
                "exact_collinear": exact,
                "max_abs_corr": float(corr_abs[best]) if best >= 0 else np.nan,
                "max_abs_corr_with": names[best] if best >= 0 else "",
                "strong_corr_partners": ";".join(strong),
            }
        )
    table = pd.DataFrame.from_records(records)
    table.insert(1, "branch", table["column"].str.split("__").str[0])
    return table


def _run_e3(rows: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """E3: VIF over the finalised `FULL` design matrix, fitted on `train` only.

    The matrix is what the linear model actually sees: `build_preprocessor(FULL,
    empirical_bayes_m=5, prior_grouping="position")` fitted on the 2017-2023 training
    seasons and applied to those rows, one-hot and Empirical-Bayes rate columns included.
    The 2024 rows never touch the fit, matching the leak discipline of the fold runs above.
    """
    train = rows[rows["split"] == "train"]
    if int(train["season"].max()) > 2023:
        raise ValueError(
            f"E3 must fit on train seasons only, got {sorted(train['season'].unique())}"
        )
    preprocessor = build_preprocessor(
        FULL, empirical_bayes_m=DEFAULT_M, prior_grouping=PRIOR_GROUPING
    )
    design = _dense(preprocessor.fit_transform(train))
    names = list(preprocessor.get_feature_names_out())
    table = _vif_table(design, names)
    flagged = table[table["flagged_gt_10"]]
    unflagged = table[table["vif"].notna() & ~table["flagged_gt_10"]]
    summary = {
        "feature_set": FULL.name,
        "decides": "docs/ML_ARCHITECTURE.md section 3.6 (drop or combine redundant features)",
        "split_fit": "train (2017-2023)",
        "rows_fit": int(len(train)),
        "design_columns": int(len(names)),
        "method": VIF_METHOD,
        "flag_threshold": VIF_FLAG_THRESHOLD,
        "n_flagged": int(len(flagged)),
        "n_exact_collinear": int(table["exact_collinear"].sum()),
        "max_vif_unflagged": (float(unflagged["vif"].max()) if not unflagged.empty else None),
        "flagged_detail": [
            {
                "column": str(row["column"]),
                "vif": "inf" if np.isinf(row["vif"]) else float(row["vif"]),
                "exact_collinear": bool(row["exact_collinear"]),
                "strong_corr_partners": [
                    partner for partner in str(row["strong_corr_partners"]).split(";") if partner
                ],
            }
            for _index, row in flagged.iterrows()
        ],
    }
    return table, summary


def _e3b_basis_frames(
    train: pd.DataFrame, val: pd.DataFrame, basis: str, age_mean: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return the fold's `(train, val)` under one age basis.

    `raw` passes the transform stage's `age` and `age_sq` through untouched. `centred`
    rewrites both columns as `age_c = age - age_mean` and `age_sq_c = age_c ** 2`, where
    `age_mean` must be the fold's training mean - centring on the full frame would leak
    the validation seasons across the fold boundary and break the shared protocol.
    """
    if basis == "raw":
        return train, val
    if basis != "centred":
        raise ValueError(f"unknown age basis {basis!r}")
    centred_train = train.copy()
    centred_val = val.copy()
    for frame in (centred_train, centred_val):
        frame["age"] = frame["age"] - age_mean
        frame["age_sq"] = frame["age"] ** 2
    return centred_train, centred_val


def _run_e3b(folds: list[FoldFrame]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """E3b: score every model family on both age bases, with OLS as the identity control.

    Reuses the shared fold construction and the per-fold preprocessor discipline: each
    fold computes its centring mean from its training seasons only, refits
    `build_preprocessor(FULL, empirical_bayes_m=5, prior_grouping="position")` on that
    fold's basis-specific training frame, and scores the fold's validation season with
    every model in `E3B_MODELS`. Returns one CSV row per model x age basis x fold plus a
    pooled row per cell, and the `age_basis` block for `summary.json`.

    Raises ValueError when the OLS control is not identical across the two bases by more
    than `E3B_OLS_IDENTITY_TOL`: mean-centring only moves the coordinates of the same
    column space, so a gap above floating-point noise means the centring is wrong - and
    that, not the tree scores, is the finding of this run.
    """
    model_config = {key: description for key, _factory, description in E3B_MODELS}
    records: list[dict[str, Any]] = []
    pooled_predictions: dict[tuple[str, str], list[tuple[np.ndarray, np.ndarray]]] = {}
    fold_age_means: dict[str, float] = {}
    ols_identity_by_fold: dict[str, float] = {}

    for fold_key, train, val, (train_seasons, val_season) in folds:
        age_mean = float(train["age"].mean())
        fold_age_means[fold_key] = age_mean
        ols_predictions: dict[str, np.ndarray] = {}
        for basis in E3B_BASES:
            basis_train, basis_val = _e3b_basis_frames(train, val, basis, age_mean)
            preprocessor = build_preprocessor(
                FULL, empirical_bayes_m=DEFAULT_M, prior_grouping=PRIOR_GROUPING
            )
            design_train = preprocessor.fit_transform(basis_train)
            design_val = preprocessor.transform(basis_val)
            y_true = basis_val[TARGET].to_numpy(dtype="float64")
            for model_key, factory, _description in E3B_MODELS:
                model = factory()
                model.fit(design_train, basis_train[TARGET])
                prediction = model.predict(design_val)
                if model_key == "ols":
                    ols_predictions[basis] = prediction
                pooled_predictions.setdefault((model_key, basis), []).append((y_true, prediction))
                records.append(
                    {
                        "model": model_key,
                        "model_config": model_config[model_key],
                        "age_basis": basis,
                        "fold": fold_key,
                        "train_seasons": train_seasons,
                        "val_season": val_season,
                        "n_train": len(basis_train),
                        "n_val": len(basis_val),
                        "train_age_mean": age_mean,
                        **_metrics(y_true, prediction),
                    }
                )
        ols_identity_by_fold[fold_key] = float(
            np.max(np.abs(ols_predictions["raw"] - ols_predictions["centred"]))
        )

    for (model_key, basis), chunks in pooled_predictions.items():
        y_true = np.concatenate([chunk[0] for chunk in chunks])
        prediction = np.concatenate([chunk[1] for chunk in chunks])
        records.append(
            {
                "model": model_key,
                "model_config": model_config[model_key],
                "age_basis": basis,
                "fold": "pooled",
                "train_seasons": "2017-2023",
                "val_season": "2020-2024",
                "n_train": None,
                "n_val": len(y_true),
                "train_age_mean": None,
                **_metrics(y_true, prediction),
            }
        )

    ols_max_diff = max(ols_identity_by_fold.values())
    if ols_max_diff > E3B_OLS_IDENTITY_TOL:
        raise ValueError(
            "E3b OLS identity check failed: predictions differ by "
            f"{ols_max_diff:.3e} between the raw and centred age bases "
            f"(tolerance {E3B_OLS_IDENTITY_TOL:.0e}) - the centring is wrong, not the finding"
        )

    table = pd.DataFrame.from_records(records)
    table["n_train"] = table["n_train"].astype("Int64")  # pooled rows have none
    pooled_metrics: dict[str, dict[str, dict[str, float | int]]] = {}
    for row in table[table["fold"] == "pooled"].to_dict("records"):
        pooled_metrics.setdefault(str(row["model"]), {})[str(row["age_basis"])] = {
            key: (int(row[key]) if key == "floored_rows" else float(row[key]))
            for key in ("rmse", "mae", "r2", "mdape_eur_pct", "floored_rows")
        }
    summary: dict[str, Any] = {
        "question": "does mean-centring age before squaring change what the tree models learn",
        "bases": {
            "raw": "age and age_sq exactly as the transform stage writes them",
            "centred": (
                "age_c = age - mean(age_train); age_sq_c = age_c ** 2; the mean comes from "
                "the fold's training seasons only, never the full frame"
            ),
        },
        "hyperparameters": model_config,
        "fold_train_age_means": fold_age_means,
        "pooled_results": pooled_metrics,
        "ols_identity_check": {
            "max_abs_prediction_difference": ols_max_diff,
            "by_fold": ols_identity_by_fold,
            "tolerance": E3B_OLS_IDENTITY_TOL,
            "passed": True,
        },
    }
    return table, summary


def run() -> dict[str, Any]:
    """Run E1, E1b, E2, E2b, E3 and E3b and write the CSVs, figures and `summary.json`."""
    rows, out_dir, manifest = _load_rows()
    out_dir.mkdir(parents=True, exist_ok=True)
    folds = _fold_frames(rows)

    ablation, rate_variant = _score_rungs(folds)
    pooled_rows = ablation[ablation["fold"] == "pooled"]
    league_row = pooled_rows.set_index("rung").loc["5_league"]
    winning_key = str(pooled_rows.loc[pooled_rows["rmse"].idxmin(), "rung"])
    winning_set = next(feature_set for key, _prev, feature_set in LADDER if key == winning_key)
    sweep = _sweep_m(winning_set, folds)
    pooled_sweep = sweep[sweep["fold"] == "pooled"]

    # E1b: variant A is rung 4 itself, already scored above; only variant B is refitted.
    e1b = _score_e1b(ablation, folds)
    pooled_e1b = e1b[e1b["fold"] == "pooled"].iloc[0]
    e1b_winner = "a" if pooled_e1b["rmse_a"] <= pooled_e1b["rmse_b"] else "b"
    e1b_winner_set = TEAM_CONTEXT if e1b_winner == "a" else RAW_COUNTS
    # E2b: re-sweep `m` on the E1b winner, because the E2 sweep ran with league in the set.
    e2b = _sweep_m(e1b_winner_set, folds)
    e2b.insert(0, "feature_set", e1b_winner_set.name)
    pooled_e2b = e2b[e2b["fold"] == "pooled"]
    optimum_m = float(pooled_e2b.loc[pooled_e2b["rmse"].idxmin(), "m"])
    previous_optimum_m = float(pooled_sweep.loc[pooled_sweep["rmse"].idxmin(), "m"])

    ablation.to_csv(out_dir / "e1_ablation.csv", index=False)
    rate_variant.to_csv(out_dir / "e1_rate_variant.csv", index=False)
    e1b.to_csv(out_dir / "e1b_raw_counts.csv", index=False)
    sweep.to_csv(out_dir / "e2_m_sweep.csv", index=False)
    e2b.to_csv(out_dir / "e2b_m_sweep.csv", index=False)
    e3, e3_summary = _run_e3(rows)
    e3.to_csv(out_dir / "e3_vif.csv", index=False)
    # E3b: the age-basis experiment on the tree models; its OLS identity check raises if
    # the centring is wrong, so nothing downstream of it can be written on bad evidence.
    e3b, e3b_summary = _run_e3b(folds)
    e3b.to_csv(out_dir / "e3b_age_basis.csv", index=False)
    figures = _render_figures(out_dir, ablation, e1b, sweep, e2b, optimum_m)
    figures.append(_render_e3b_figure(out_dir, e3b))

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
        "e1": {
            "rungs": [key for key, _prev, _set in LADDER],
            "pooled_metrics": _pooled_records(pooled_rows),
            "pooled_deltas": {
                str(row["rung"]): (
                    None
                    if pd.isna(row["delta_rmse"])
                    else {
                        "delta_rmse": float(row["delta_rmse"]),
                        "delta_r2": float(row["delta_r2"]),
                    }
                )
                for _index, row in pooled_rows.iterrows()
            },
            "winning_rung": winning_key,
        },
        "e1b": {
            "m": DEFAULT_M,
            "variant_a": {
                "feature_set": TEAM_CONTEXT.name,
                "description": (
                    "biographical + volume + EB per-90 rates + team context, no league_id "
                    "(the E1 rung-4 set)"
                ),
            },
            "variant_b": {
                "feature_set": RAW_COUNTS.name,
                "description": (
                    "variant A plus the raw production counts goals, assists, yellow_cards, "
                    "red_cards, carried the way the provisional FULL declares them (log1p on "
                    "goals and assists, plain on the cards)"
                ),
            },
            "pooled_metrics": {"a": _side(pooled_e1b, "a"), "b": _side(pooled_e1b, "b")},
            "pooled_delta_b_minus_a": {
                "delta_rmse": float(pooled_e1b["delta_rmse_b_minus_a"]),
                "delta_mae": float(pooled_e1b["delta_mae_b_minus_a"]),
                "delta_r2": float(pooled_e1b["delta_r2_b_minus_a"]),
                "delta_mdape_eur_pct": float(pooled_e1b["delta_mdape_eur_pct_b_minus_a"]),
            },
            "winning_variant": e1b_winner,
            "raw_counts_earned_place": bool(pooled_e1b["delta_rmse_b_minus_a"] < 0.0),
        },
        "e2": {
            "m_values": list(M_SWEEP),
            "winning_rung": winning_key,
            "sweep_degenerate": not winning_set.rates,
            "pooled_metrics_by_m": _pooled_records(pooled_sweep),
            "m0_note": (
                "m = 0 is scored as the raw per-90 variant: build_preprocessor refuses m <= 0, "
                "and count / (minutes / 90) is the EB formula at m = 0 exactly (minutes >= 180)."
            ),
        },
        "e2b": {
            "m_values": list(M_SWEEP),
            "on_variant": e1b_winner,
            "feature_set": e1b_winner_set.name,
            "sweep_degenerate": not e1b_winner_set.rates,
            "pooled_metrics_by_m": _pooled_records(pooled_e2b),
            "optimum_m": optimum_m,
            "optimum_rule": "grid minimum of pooled RMSE on the E1b winning variant",
            "optimum_vs_m5": _m_gap(pooled_e2b, optimum_m, DEFAULT_M),
            "optimum_vs_m20": _m_gap(pooled_e2b, optimum_m, 20.0),
            "previous_e2_optimum_m": previous_optimum_m,
            "league_exclusion_moved_optimum": optimum_m != previous_optimum_m,
            "m0_note": (
                "m = 0 is scored as the raw per-90 variant: build_preprocessor refuses m <= 0, "
                "and count / (minutes / 90) is the EB formula at m = 0 exactly (minutes >= 180)."
            ),
        },
        "e3": e3_summary,
        "age_basis": e3b_summary,
        "league_excluded": True,
        "league_exclusion_note": (
            "Rung 5 (league_id) was measured - pooled RMSE "
            f"{float(league_row['rmse']):.4f}, R2 {float(league_row['r2']):.4f}, the ladder's "
            "largest single gain - but rejected on methodological grounds: league_id is a "
            "pricing variable, not a performance variable, so with it in the model the "
            "undervaluation residual measures price versus the league's typical price instead "
            "of price versus performance (the same reasoning that excluded prior market value "
            "in REPORT_NOTES H-09 and that keeps league out of CLUSTER). Predictive accuracy "
            "is deliberately traded away; E1b and E2b run on the ladder without league_id."
        ),
        "settings": {
            "eb_m_default": DEFAULT_M,
            "prior_grouping": PRIOR_GROUPING,
            "m_sweep": list(M_SWEEP),
            "rate_counts": list(RATE_COUNTS),
        },
        "outputs": [
            "e1_ablation.csv",
            "e1_rate_variant.csv",
            "e1b_raw_counts.csv",
            "e2_m_sweep.csv",
            "e2b_m_sweep.csv",
            "e3_vif.csv",
            "e3b_age_basis.csv",
            *figures,
            "summary.json",
        ],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("\nE1 pooled (per rung):")
    print(
        pooled_rows.set_index("rung")[
            ["rmse", "r2", "mdape_eur_pct", "delta_rmse", "delta_r2"]
        ].to_string(float_format=lambda value: f"{value:0.4f}")
    )
    print("\nE1 rung-3 fork pooled:")
    print(rate_variant[rate_variant["fold"] == "pooled"].to_string(index=False))
    print("\nE1b (B minus A; negative favours the raw counts):")
    print(
        e1b[
            [
                "fold",
                "rmse_a",
                "rmse_b",
                "delta_rmse_b_minus_a",
                "r2_a",
                "r2_b",
                "delta_r2_b_minus_a",
            ]
        ].to_string(index=False, float_format=lambda value: f"{value:0.4f}")
    )
    print("\nE2 pooled by m:")
    print(pooled_sweep[["m", "variant", "rmse"]].to_string(index=False))
    print("\nE2b pooled by m (E1b winner, no league):")
    print(
        pooled_e2b[["m", "variant", "rmse", "r2"]].to_string(
            index=False, float_format=lambda value: f"{value:0.4f}"
        )
    )
    print(f"E2b optimum m = {optimum_m:g} (E2 optimum on rung 5: {previous_optimum_m:g})")
    e3_flagged = e3[e3["flagged_gt_10"]]
    print(
        f"\nE3 VIF on the FULL design matrix ({e3_summary['design_columns']} columns, "
        f"train split only, flagged > {VIF_FLAG_THRESHOLD:g}):"
    )
    if e3_flagged.empty:
        print("no column flagged")
    else:
        print(
            e3_flagged[["column", "vif", "exact_collinear", "max_abs_corr_with"]].to_string(
                index=False
            )
        )
    print("\nE3b pooled RMSE by model and age basis (centred minus raw in brackets):")
    e3b_pooled = e3b[e3b["fold"] == "pooled"].pivot(index="model", columns="age_basis")
    for model_key, _factory, _description in E3B_MODELS:
        raw_rmse = float(e3b_pooled.loc[model_key, ("rmse", "raw")])
        centred_rmse = float(e3b_pooled.loc[model_key, ("rmse", "centred")])
        raw_r2 = float(e3b_pooled.loc[model_key, ("r2", "raw")])
        centred_r2 = float(e3b_pooled.loc[model_key, ("r2", "centred")])
        print(
            f"  {model_key:<26} RMSE {raw_rmse:.4f} -> {centred_rmse:.4f} "
            f"({centred_rmse - raw_rmse:+.4f}); R2 {raw_r2:.4f} -> {centred_r2:.4f}"
        )
    print(
        "E3b OLS identity check: max |raw - centred| prediction difference "
        f"{e3b_summary['ols_identity_check']['max_abs_prediction_difference']:.3e} "
        f"(tolerance {E3B_OLS_IDENTITY_TOL:.0e}) - centring spans the identical space"
    )
    print(f"\nOutputs written to {out_dir}")
    return summary


def main() -> None:
    summary = run()
    print(
        f"Feature ablation completed: E1 winning rung {summary['e1']['winning_rung']}, "
        f"E1b winner {summary['e1b']['winning_variant'].upper()}, "
        f"E2b optimum m = {summary['e2b']['optimum_m']:g}, "
        f"E3 flagged {summary['e3']['n_flagged']} of {summary['e3']['design_columns']} columns, "
        "E3b OLS identity "
        f"{summary['age_basis']['ols_identity_check']['max_abs_prediction_difference']:.1e}"
    )


if __name__ == "__main__":
    main()
