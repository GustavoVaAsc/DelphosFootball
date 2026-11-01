"""Feature-group ablation (E1) and Empirical Bayes strength sweep (E2) on the linear model.

Input: `ml/data/transform/player_seasons.parquet` resolved through `delphos_ml.config` like
`analysis/eda.py`, read with a predicate that keeps only the `train` and `validation` splits -
the 2025 `test` split is never read.
Output: `e1_ablation.csv`, `e1_rate_variant.csv`, `e2_m_sweep.csv`, `fig_e1_ablation.png`,
`fig_e2_m_sweep.png` and `summary.json` under `<repo root>/analysis/output/feature_ablation/`.
Responsibility: run the two experiments that decide docs/ML_ARCHITECTURE.md section 3.6 - E1,
the feature-group ablation on OLS market-value regression, and E2, the `m` sweep that confirms
or changes the provisional `m = 5` for valuation. The script reports evidence only; the
decisions belong in the architecture docs, not here.

Both experiments share one protocol and therefore one scoring core: expanding-window season
folds inside `train` + `validation` (train 2017-2019 validate 2020, and so on up to train
2017-2023 validate 2024), and every fold fits its own preprocessor - Empirical Bayes priors,
height medians, scalers, one-hot vocabularies - on that fold's training seasons only before OLS
scores that fold's validation season (the leak discipline pinned in `ml/tests/test_preprocess.py`).
The module is longer than a screen because it is one experiment script per ADR-014: splitting
the shared fold, metric and figure code into a second analysis module would break the
one-script-one-output-dir convention without shortening anything.

E2's `m = 0` point cannot pass through `build_preprocessor`, whose sink refuses `m <= 0`
(pinned by `test_build_preprocessor_refuses_an_unusable_m`); it is scored as the raw-rate
variant - `<count>_per90 = count / (minutes / 90)` columns in the numeric branch - which is the
Empirical Bayes formula at `m = 0` exactly, because the transform stage's 180-minute floor keeps
the denominator positive. The same variant is E1's raw branch at rung 3.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from delphos_ml.config import ConfigError, find_project_root, load_settings
from delphos_ml.features.feature_sets import FeatureSet
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

#: E2 sweep; `0.0` is the unsmoothed raw per-90 rates, not a neutral baseline.
M_SWEEP: tuple[float, ...] = (0.0, 2.0, 5.0, 10.0, 20.0)
DEFAULT_M = 5.0
PRIOR_GROUPING = "position"

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


def _score_rungs(folds: list[FoldFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score every ladder rung on every fold; return the ablation and rate-fork tables."""
    metrics_by_key: dict[str, dict[str, dict[str, float | int]]] = {}
    for rung_key, _prev, feature_set in LADDER:
        metrics_by_key[rung_key] = {}
        pooled_true: list[np.ndarray] = []
        pooled_pred: list[np.ndarray] = []
        # The rates branch is a no-op when `rates` is empty, so DEFAULT_M is inert there.
        for fold_key, train, val, _seasons in folds:
            y_true, pred = _fit_score(feature_set, train, val, DEFAULT_M)
            pooled_true.append(y_true)
            pooled_pred.append(pred)
            metrics_by_key[rung_key][fold_key] = _metrics(y_true, pred)
        metrics_by_key[rung_key]["pooled"] = _metrics(
            np.concatenate(pooled_true), np.concatenate(pooled_pred)
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


def _sweep_m(winning: FeatureSet, folds: list[FoldFrame]) -> pd.DataFrame:
    """Rescore the winning rung at each `m`; `m = 0` goes through the raw-rate variant."""
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


def _render_figures(out_dir: Path, ablation: pd.DataFrame, sweep: pd.DataFrame) -> list[str]:
    """Write the two figures; pooled metrics bold, per-fold metrics as thin context lines."""
    labels = [key for key, _prev, _set in LADDER]
    fold_keys = [str(i) for i in range(1, len(FOLDS) + 1)]
    pooled = ablation[ablation["fold"] == "pooled"].set_index("rung").loc[labels]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    for axis, metric, title in ((axes[0], "rmse", "RMSE (log10 EUR)"), (axes[1], "r2", "R$^2$")):
        for fold_key in fold_keys:
            fold_rows = ablation[ablation["fold"] == fold_key].set_index("rung").loc[labels]
            axis.plot(range(len(labels)), fold_rows[metric], color="steelblue", alpha=0.35, lw=1)
        axis.plot(range(len(labels)), pooled[metric], "o-", color="navy", lw=2, label="pooled")
        axis.set_xticks(range(len(labels)), labels, rotation=30, ha="right")
        axis.set_title(title)
        axis.legend()
    fig.suptitle("E1: feature-group ablation on the OLS market-value regression")
    fig.savefig(out_dir / "fig_e1_ablation.png", dpi=240)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(6.8, 4.2), constrained_layout=True)
    for fold_key in fold_keys:
        fold_rows = sweep[sweep["fold"] == fold_key]
        axis.plot(fold_rows["m"], fold_rows["rmse"], color="darkorange", alpha=0.35, lw=1)
    pooled_sweep = sweep[sweep["fold"] == "pooled"]
    axis.plot(pooled_sweep["m"], pooled_sweep["rmse"], "o-", color="navy", lw=2, label="pooled")
    axis.axvline(
        DEFAULT_M, color="crimson", ls="--", lw=1.5, label=f"m = {DEFAULT_M:g} (provisional)"
    )
    axis.set_xlabel("Empirical Bayes strength m (0 = raw per-90 rates)")
    axis.set_ylabel("RMSE (log10 EUR)")
    axis.set_title("E2: EB strength sweep on the winning rung")
    axis.legend()
    fig.savefig(out_dir / "fig_e2_m_sweep.png", dpi=240)
    plt.close(fig)
    return ["fig_e1_ablation.png", "fig_e2_m_sweep.png"]


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


def run() -> dict[str, Any]:
    """Run E1 and E2 and write the CSVs, figures and `summary.json`."""
    rows, out_dir, manifest = _load_rows()
    out_dir.mkdir(parents=True, exist_ok=True)
    folds = _fold_frames(rows)

    ablation, rate_variant = _score_rungs(folds)
    pooled_rows = ablation[ablation["fold"] == "pooled"]
    winning_key = str(pooled_rows.loc[pooled_rows["rmse"].idxmin(), "rung"])
    winning_set = next(feature_set for key, _prev, feature_set in LADDER if key == winning_key)
    sweep = _sweep_m(winning_set, folds)
    pooled_sweep = sweep[sweep["fold"] == "pooled"]

    ablation.to_csv(out_dir / "e1_ablation.csv", index=False)
    rate_variant.to_csv(out_dir / "e1_rate_variant.csv", index=False)
    sweep.to_csv(out_dir / "e2_m_sweep.csv", index=False)
    figures = _render_figures(out_dir, ablation, sweep)

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
        "settings": {
            "eb_m_default": DEFAULT_M,
            "prior_grouping": PRIOR_GROUPING,
            "m_sweep": list(M_SWEEP),
            "rate_counts": list(RATE_COUNTS),
        },
        "outputs": [
            "e1_ablation.csv",
            "e1_rate_variant.csv",
            "e2_m_sweep.csv",
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
    print("\nE2 pooled by m:")
    print(pooled_sweep[["m", "variant", "rmse"]].to_string(index=False))
    print(f"\nOutputs written to {out_dir}")
    return summary


def main() -> None:
    summary = run()
    print(f"Feature ablation completed: winning rung {summary['e1']['winning_rung']}")


if __name__ == "__main__":
    main()
