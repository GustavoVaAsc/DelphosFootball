"""E6/E7: the K-Means cluster-count sweep and the scaler comparison behind the archetypes.

Input: `ml/data/transform/player_seasons.parquet` (dataset v679) resolved through
`delphos_ml.config` like `analysis/feature_ablation.py`, read with a predicate that keeps
only the `train` and `validation` splits - the 2025 `test` split is never read.
Output: `e6_k_sweep.csv`, `e6_decision.csv`, `e6_cluster_profiles.csv`,
`e7_scaler_comparison.csv`, `e7_decision.csv`, `fig_e6_internal.png`,
`fig_e6_stability.png`, `fig_e7_scaler_silhouette.png` and `summary.json` under
`<repo root>/analysis/output/kmeans_selection/`.
Responsibility: run experiment E6 of docs/ML_ARCHITECTURE.md section 3.8 (the procedure is
docs/TRANSFORM_PLAN.md section 6): fit the `CLUSTER` feature space and one K-Means per `k`
on the training split only, sweep `k = 2..15`, score four internal metrics and two
stability measures, then apply the section-6 decision rule verbatim; and run E7, the same
sweep under `StandardScaler` and `RobustScaler`, which decides the open scaler question of
section 3.8 - the standard side reproduces E6, the robust side is the counterfactual. The
script reports evidence only; recording the chosen `k` and scaler in the architecture docs
is a separate step. Like `feature_ablation.py` this is one experiment script per ADR-014,
and it stays one module because every stage feeds the single decision table - splitting it
would break the one-script-one-output-dir convention without shortening anything.

Protocol notes:

- The preprocessor (Empirical Bayes priors, medians, scaler moments, one-hot
  vocabularies) is fitted on `train` only, and every K-Means sees training rows only; the
  2024 validation season is touched by the temporal stability check alone, where the
  training centroids assign its rows and a K-Means fitted directly on 2024 provides the
  comparison labels.
- The elbow is the maximum-curvature point on the min-max normalised inertia curve: the
  kneedle implementation (`kneed`) is not a dependency of the ml project, so the plan's
  documented fallback applies.
- The silhouette is computed on one fixed 10,000-row sample shared by every `k`, so the
  curve's shape reflects `k` and not sample noise (the full computation is O(n^2)).
- Bootstrap stability compares two refits only on the training rows both resamples
  contain (adjusted Rand on the intersection, as in Hubert and Arabie); comparing the
  assignments of two different row sets is not well defined.
- E7 varies exactly one thing per side: the numeric branch's scaler. Both sides share the
  folds, the silhouette sample, the K-Means hyper-parameters, the `random_state`, and the
  bootstrap resamples (`default_rng([RANDOM_STATE, k])`), so a difference between the two
  sweeps is attributable to the scaler alone.
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
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.preprocessing import RobustScaler, StandardScaler

from delphos_ml.config import ConfigError, find_project_root, load_settings
from delphos_ml.features.feature_sets import CLUSTER
from delphos_ml.features.preprocess import build_preprocessor

RANDOM_STATE = 20261101
N_INIT = 20
MAX_ITER = 500
K_VALUES: tuple[int, ...] = tuple(range(2, 16))
SILHOUETTE_SAMPLE = 10_000
N_BOOTSTRAP = 20

#: The decision rule's gates (docs/TRANSFORM_PLAN.md section 6).
CANDIDATE_K_MIN = 3
SILHOUETTE_REL_TOL = 0.05
SILHOUETTE_MIN = 0.25
MIN_CLUSTER_SHARE = 0.03
TEMPORAL_ARI_MIN = 0.5
BOOTSTRAP_ARI_MIN = 0.8

EMPIRICAL_BAYES_M = 5.0
PRIOR_GROUPING = "position"

RATE_COUNTS: tuple[str, ...] = ("goals", "assists", "yellow_cards", "red_cards")
PER90_COLUMNS: tuple[str, ...] = tuple(f"{count}_per90" for count in RATE_COUNTS)
PROFILE_MEANS: tuple[str, ...] = (
    "minutes",
    "starter_ratio",
    "uefa_share",
    "cup_share",
    *PER90_COLUMNS,
)


def _fail(reason: str) -> None:
    print(f"kmeans_selection failed: {reason}", file=sys.stderr)
    raise SystemExit(1)


def _load_rows() -> tuple[pd.DataFrame, pd.DataFrame, Path, dict[str, Any]]:
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
    train = rows[rows["split"] == "train"]
    validation = rows[rows["split"] == "validation"]
    if not 2017 <= int(train["season"].min()) or int(train["season"].max()) > 2023:
        raise ValueError(f"unexpected train seasons {sorted(train['season'].unique())}")
    if sorted(validation["season"].unique()) != [2024]:
        raise ValueError(f"unexpected validation seasons {sorted(validation['season'].unique())}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return train, validation, repo_root / "analysis" / "output" / "kmeans_selection", manifest


def _fit(X: np.ndarray, k: int, seed: int = RANDOM_STATE) -> KMeans:
    """Fit one K-Means with the sweep's shared hyper-parameters."""
    return KMeans(
        n_clusters=k, init="k-means++", n_init=N_INIT, random_state=seed, max_iter=MAX_ITER
    ).fit(X)


def _elbow_k(inertias: np.ndarray) -> int:
    """Return the maximum-curvature `k` on the min-max normalised inertia curve.

    `kneed`'s kneedle is unavailable in this project, so the documented fallback applies:
    normalise both axes to [0, 1], take the discrete curvature
    ``|y''| / (1 + y'^2)^{3/2}`` (first derivatives by central differences) and return the
    `k` where it peaks.
    """
    x = np.linspace(0.0, 1.0, len(inertias))
    y = (inertias - inertias.min()) / (inertias.max() - inertias.min())
    dy = np.gradient(y, x)
    d2y = np.gradient(dy, x)
    curvature = np.abs(d2y) / (1.0 + dy**2) ** 1.5
    return K_VALUES[int(np.argmax(curvature))]


def _bootstrap_aris(X: np.ndarray, k: int) -> np.ndarray:
    """Refit on `N_BOOTSTRAP` resamples; ARI for each of the C(20,2) pairs on shared rows."""
    n_rows = X.shape[0]
    rng = np.random.default_rng([RANDOM_STATE, k])
    resamples = [np.unique(rng.integers(0, n_rows, size=n_rows)) for _ in range(N_BOOTSTRAP)]
    models = [_fit(X[index], k) for index in resamples]
    aris: list[float] = []
    for left in range(N_BOOTSTRAP):
        for right in range(left + 1, N_BOOTSTRAP):
            shared = np.intersect1d(resamples[left], resamples[right])
            aris.append(
                float(
                    adjusted_rand_score(
                        models[left].predict(X[shared]), models[right].predict(X[shared])
                    )
                )
            )
    return np.asarray(aris)


def _sweep_k(
    X_train: np.ndarray, X_val: np.ndarray, k: int, sample_index: np.ndarray
) -> dict[str, Any]:
    """Score one `k`: four internal metrics, both stability measures, and the size shares."""
    model = _fit(X_train, k)
    val_from_train = model.predict(X_val)
    temporal_ari = float(adjusted_rand_score(val_from_train, _fit(X_val, k).labels_))
    bootstrap = _bootstrap_aris(X_train, k)
    shares = np.bincount(model.labels_, minlength=k) / len(model.labels_)
    return {
        "k": k,
        "inertia": float(model.inertia_),
        "silhouette": float(silhouette_score(X_train[sample_index], model.labels_[sample_index])),
        "calinski_harabasz": float(calinski_harabasz_score(X_train, model.labels_)),
        "davies_bouldin": float(davies_bouldin_score(X_train, model.labels_)),
        "temporal_ari": temporal_ari,
        "bootstrap_ari_mean": float(bootstrap.mean()),
        "bootstrap_ari_std": float(bootstrap.std()),
        "min_cluster_share": float(shares.min()),
        **{
            f"share_{index + 1:02d}": (float(shares[index]) if index < k else np.nan)
            for index in range(max(K_VALUES))
        },
    }


def _decide(sweep: pd.DataFrame, elbow_k: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply the TRANSFORM_PLAN section-6 rule; return the decision table and the trace."""
    max_silhouette = float(sweep["silhouette"].max())
    table = sweep[sweep["k"] >= CANDIDATE_K_MIN].copy()
    table["silhouette_within_5pct_of_max"] = (
        table["silhouette"] >= (1.0 - SILHOUETTE_REL_TOL) * max_silhouette
    )
    table["silhouette_at_least_025"] = table["silhouette"] >= SILHOUETTE_MIN
    table["no_cluster_below_3pct"] = table["min_cluster_share"] >= MIN_CLUSTER_SHARE
    table["temporal_ari_pass"] = table["temporal_ari"] >= TEMPORAL_ARI_MIN
    table["bootstrap_ari_pass"] = table["bootstrap_ari_mean"] >= BOOTSTRAP_ARI_MIN
    gates = [
        "silhouette_within_5pct_of_max",
        "silhouette_at_least_025",
        "no_cluster_below_3pct",
        "temporal_ari_pass",
        "bootstrap_ari_pass",
    ]
    table["is_candidate"] = table[gates].all(axis=1)
    table["is_elbow"] = table["k"] == elbow_k
    candidates = [int(k) for k in table.loc[table["is_candidate"], "k"]]
    if not candidates:
        selected_k = None
        rule = (
            f"no k in {CANDIDATE_K_MIN}..{max(K_VALUES)} passes every gate (maximum sampled "
            f"silhouette {max_silhouette:.4f} against the {SILHOUETTE_MIN} floor), so the "
            "rule yields no selection"
        )
    elif elbow_k in candidates:
        selected_k = elbow_k
        rule = f"the elbow k={elbow_k} is in the candidate set -> selected k={selected_k}"
    else:
        selected_k = max(candidates)
        rule = (
            f"the elbow k={elbow_k} is not in the candidate set -> selected the largest "
            f"candidate k={selected_k}"
        )
    table["is_selected"] = table["k"] == selected_k
    table.insert(0, "candidate_set", ";".join(str(k) for k in candidates))
    table.insert(1, "elbow_k", elbow_k)
    table.insert(2, "selected_k", selected_k)
    table.insert(3, "rule", rule)
    return table, {"candidates": candidates, "selected_k": selected_k, "rule": rule}


def _sweep_scaler(
    label: str,
    scaler: StandardScaler | RobustScaler,
    train: pd.DataFrame,
    validation: pd.DataFrame,
    sample_index: np.ndarray,
) -> dict[str, Any]:
    """Fit one CLUSTER preprocessor under `scaler`, sweep `k`, apply the rule; log per `k`.

    Everything the sweep touches besides the scaler is shared: the folds, the silhouette
    sample, the K-Means hyper-parameters and the bootstrap resample seeds. The `label`
    prefix on each progress line keeps the background run's log readable per side.
    """
    print(
        f"E7: sweeping k = {min(K_VALUES)}..{max(K_VALUES)} with the {label} scaler",
        flush=True,
    )
    pre = build_preprocessor(
        CLUSTER,
        empirical_bayes_m=EMPIRICAL_BAYES_M,
        prior_grouping=PRIOR_GROUPING,
        scaler=scaler,
    )
    X_train = pre.fit_transform(train)
    X_val = pre.transform(validation)
    records: list[dict[str, Any]] = []
    for k in K_VALUES:
        record = _sweep_k(X_train, X_val, k, sample_index)
        print(
            f"  [{label}] k={k:2d} silhouette={record['silhouette']:.4f} "
            f"inertia={record['inertia']:.1f} temporal_ari={record['temporal_ari']:.3f} "
            f"bootstrap_ari={record['bootstrap_ari_mean']:.3f} "
            f"min_share={record['min_cluster_share']:.3f}",
            flush=True,
        )
        records.append(record)
    sweep = pd.DataFrame(records)
    elbow_k = _elbow_k(sweep["inertia"].to_numpy())
    decision, trace = _decide(sweep, elbow_k)
    return {
        "label": label,
        "scaler": type(scaler).__name__,
        "pre": pre,
        "X_train": X_train,
        "sweep": sweep,
        "elbow_k": elbow_k,
        "decision": decision,
        "trace": trace,
    }


def _e7_comparison(runs: list[dict[str, Any]]) -> pd.DataFrame:
    """One row per scaler x k: the two sweeps side by side."""
    frames = [run["sweep"].assign(scaler=run["label"]) for run in runs]
    comparison = pd.concat(frames, ignore_index=True)
    return comparison[["scaler", *[column for column in comparison if column != "scaler"]]]


def _e7_decisions(runs: list[dict[str, Any]]) -> pd.DataFrame:
    """One row per scaler: maxima, floor gap, candidate set, selection or explicit refusal."""
    records: list[dict[str, Any]] = []
    for run in runs:
        sweep, trace = run["sweep"], run["trace"]
        max_silhouette = float(sweep["silhouette"].max())
        selected_k = trace["selected_k"]
        records.append(
            {
                "scaler": run["label"],
                "max_silhouette": max_silhouette,
                "max_silhouette_k": int(sweep.loc[sweep["silhouette"].idxmax(), "k"]),
                "silhouette_floor": SILHOUETTE_MIN,
                "floor_reached": bool(max_silhouette >= SILHOUETTE_MIN),
                "gap_to_floor": float(SILHOUETTE_MIN - max_silhouette),
                "candidate_set": ";".join(str(k) for k in trace["candidates"]),
                "elbow_k": run["elbow_k"],
                "selected_k": selected_k,
                "outcome": "no selection" if selected_k is None else f"k={selected_k}",
                "rule": trace["rule"],
            }
        )
    frame = pd.DataFrame(records)
    # None and an int land in a float64 column, which would serialise k=3 as "3.0".
    frame["selected_k"] = frame["selected_k"].astype("Int64")
    return frame


def _e7_summary(runs: list[dict[str, Any]], decision_table: pd.DataFrame) -> dict[str, Any]:
    """The `summary.json` `e7` block: both maxima, the floor outcome, both selections."""
    scalers: dict[str, Any] = {}
    for run, (_index, row) in zip(runs, decision_table.iterrows(), strict=True):
        scalers[run["label"]] = {
            "scaler": run["scaler"],
            "max_silhouette": float(row["max_silhouette"]),
            "max_silhouette_k": int(row["max_silhouette_k"]),
            "floor_reached": bool(row["floor_reached"]),
            "gap_to_floor": float(row["gap_to_floor"]),
            "elbow_k": int(row["elbow_k"]),
            "candidate_set": [int(k) for k in str(row["candidate_set"]).split(";") if k],
            "selected_k": None if pd.isna(row["selected_k"]) else int(row["selected_k"]),
            "rule_trace": str(row["rule"]),
        }
    return {
        "experiment": "E7",
        "decides": "docs/ML_ARCHITECTURE.md section 3.8 (the cluster scaler)",
        "silhouette_floor": SILHOUETTE_MIN,
        "gap_to_floor_sign": "positive means the maximum sampled silhouette is below the floor",
        "scalers": scalers,
        "floor_reached_by": [label for label, entry in scalers.items() if entry["floor_reached"]],
    }


def _render_e7_figure(out_dir: Path, runs: list[dict[str, Any]]) -> list[str]:
    """Silhouette against `k` for both scalers with the 0.25 floor drawn."""
    fig, axis = plt.subplots(figsize=(7.2, 4.4), constrained_layout=True)
    for run in runs:
        axis.plot(
            run["sweep"]["k"],
            run["sweep"]["silhouette"],
            "o-",
            label=f"{run['label']} scaler",
        )
    axis.axhline(SILHOUETTE_MIN, color="grey", ls=":", lw=1.5, label=f"floor {SILHOUETTE_MIN}")
    axis.set_xlabel("k")
    axis.set_ylabel("silhouette (10k-row sample)")
    axis.set_title("E7: silhouette against k by scaler (train split only)")
    axis.legend()
    fig.savefig(out_dir / "fig_e7_scaler_silhouette.png", dpi=240)
    plt.close(fig)
    return ["fig_e7_scaler_silhouette.png"]


def _profiles(train: pd.DataFrame, pre: ColumnTransformer, model: KMeans) -> pd.DataFrame:
    """One centroid profile per cluster at `k`, in original units, on the training rows."""
    rates = pre.named_transformers_["empirical_bayes"].transform(train).reset_index(drop=True)
    frame = pd.concat([train.reset_index(drop=True), rates], axis=1)
    frame["cluster"] = model.labels_
    frame["sub_position"] = frame["sub_position"].where(
        ~frame["sub_position"].isin(dict(CLUSTER.collapse)["sub_position"]), "other"
    )
    profile = frame.groupby("cluster")[list(PROFILE_MEANS)].mean()
    counts = frame.groupby(["cluster", "sub_position"]).size().unstack(fill_value=0)
    profile["size"] = counts.sum(axis=1)
    profile["share"] = profile["size"] / len(frame)
    profile["sub_position_mode"] = counts.idxmax(axis=1)
    profile["sub_position_mode_share"] = counts.max(axis=1) / counts.sum(axis=1)
    return profile.reset_index()


def _render_figures(out_dir: Path, sweep: pd.DataFrame, elbow_k: int) -> list[str]:
    """Write the internal-metrics figure (elbow marked) and the stability figure."""
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    for axis, column, title in (
        (axes[0, 0], "inertia", "Inertia (elbow marked)"),
        (axes[0, 1], "silhouette", "Silhouette (10k-row sample)"),
        (axes[1, 0], "calinski_harabasz", "Calinski-Harabasz (higher is better)"),
        (axes[1, 1], "davies_bouldin", "Davies-Bouldin (lower is better)"),
    ):
        axis.plot(sweep["k"], sweep[column], "o-", color="navy")
        axis.set_title(title)
        axis.set_xlabel("k")
    axes[0, 0].axvline(elbow_k, color="crimson", ls="--", label=f"elbow k={elbow_k}")
    axes[0, 0].legend()
    max_silhouette = float(sweep["silhouette"].max())
    axes[0, 1].axhline(SILHOUETTE_MIN, color="grey", ls=":", label=f"floor {SILHOUETTE_MIN}")
    axes[0, 1].axhline(
        (1.0 - SILHOUETTE_REL_TOL) * max_silhouette,
        color="darkorange",
        ls=":",
        label="5% of max",
    )
    axes[0, 1].legend()
    fig.suptitle("E6: internal metrics against k (train split only)")
    fig.savefig(out_dir / "fig_e6_internal.png", dpi=240)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(7.2, 4.4), constrained_layout=True)
    axis.plot(sweep["k"], sweep["temporal_ari"], "o-", color="navy", label="temporal ARI")
    axis.plot(
        sweep["k"], sweep["bootstrap_ari_mean"], "s-", color="seagreen", label="bootstrap ARI"
    )
    axis.axhline(TEMPORAL_ARI_MIN, color="navy", ls="--", lw=1, label="temporal floor 0.5")
    axis.axhline(BOOTSTRAP_ARI_MIN, color="seagreen", ls="--", lw=1, label="bootstrap target 0.8")
    axis.set_xlabel("k")
    axis.set_ylabel("adjusted Rand index")
    axis.set_ylim(0.0, 1.0)
    axis.set_title("E6: stability against k")
    axis.legend()
    fig.savefig(out_dir / "fig_e6_stability.png", dpi=240)
    plt.close(fig)
    return ["fig_e6_internal.png", "fig_e6_stability.png"]


def run() -> dict[str, Any]:
    """Run the E6 sweep under both E7 scalers plus the decision rules, write every artefact."""
    train, validation, out_dir, manifest = _load_rows()
    out_dir.mkdir(parents=True, exist_ok=True)
    sample_index = np.random.default_rng(RANDOM_STATE).choice(
        len(train), size=min(SILHOUETTE_SAMPLE, len(train)), replace=False
    )
    runs = [
        _sweep_scaler(label, scaler, train, validation, sample_index)
        for label, scaler in (("standard", StandardScaler()), ("robust", RobustScaler()))
    ]
    # The E6 artefacts come from the standard side, which reproduces the original E6 run
    # byte for byte; the E7 artefacts compare both sides.
    standard = runs[0]
    sweep, elbow_k = standard["sweep"], standard["elbow_k"]
    decision, trace = standard["decision"], standard["trace"]
    profile_k = trace["selected_k"] if trace["selected_k"] is not None else elbow_k
    profile_source = (
        "selected k"
        if trace["selected_k"] is not None
        else ("elbow k (no candidate passed the rule)")
    )
    profiles = _profiles(train, standard["pre"], _fit(standard["X_train"], profile_k))

    sweep.to_csv(out_dir / "e6_k_sweep.csv", index=False)
    decision.to_csv(out_dir / "e6_decision.csv", index=False)
    profiles.to_csv(out_dir / "e6_cluster_profiles.csv", index=False)
    comparison = _e7_comparison(runs)
    e7_decisions = _e7_decisions(runs)
    comparison.to_csv(out_dir / "e7_scaler_comparison.csv", index=False)
    e7_decisions.to_csv(out_dir / "e7_decision.csv", index=False)
    figures = _render_figures(out_dir, sweep, elbow_k)
    e7_figures = _render_e7_figure(out_dir, runs)

    summary = {
        "experiment": "E6",
        "decides": "docs/ML_ARCHITECTURE.md section 3.8 (rule in docs/TRANSFORM_PLAN.md section 6)",
        "input": "data/transform/player_seasons.parquet",
        "dataset_version": manifest.get("version"),
        "splits": {
            "train": {"seasons": "2017-2023", "rows": len(train), "role": "fit + all metrics"},
            "validation": {
                "seasons": "2024",
                "rows": len(validation),
                "role": "temporal stability only",
            },
            "test": {
                "seasons": "2025",
                "read": False,
                "rows_per_manifest": manifest.get("rows_per_split", {}).get("test"),
            },
            "note": (
                "E6 uses the final expanding-window split of the feature_ablation fold "
                "protocol: preprocessor and K-Means fit on train only, the 2024 season "
                "never contributes a fitted statistic."
            ),
        },
        "feature_set": CLUSTER.name,
        "empirical_bayes_m": EMPIRICAL_BAYES_M,
        "prior_grouping": PRIOR_GROUPING,
        "random_state": RANDOM_STATE,
        "n_init": N_INIT,
        "max_iter": MAX_ITER,
        "silhouette_sample_size": int(sample_index.size),
        "bootstrap_resamples": N_BOOTSTRAP,
        "bootstrap_pairs_per_k": N_BOOTSTRAP * (N_BOOTSTRAP - 1) // 2,
        "elbow_method": (
            "maximum curvature on the min-max normalised inertia curve (kneedle via "
            "`kneed` is not a dependency of the ml project, so the documented fallback "
            "applies)"
        ),
        "max_silhouette": float(sweep["silhouette"].max()),
        "max_silhouette_k": int(sweep.loc[sweep["silhouette"].idxmax(), "k"]),
        "elbow_k": elbow_k,
        "candidate_set": trace["candidates"],
        "selected_k": trace["selected_k"],
        "rule_trace": trace["rule"],
        "profiles_at_k": profile_k,
        "profiles_source": profile_source,
        "e7": _e7_summary(runs, e7_decisions),
        "outputs": [
            "e6_k_sweep.csv",
            "e6_decision.csv",
            "e6_cluster_profiles.csv",
            "e7_scaler_comparison.csv",
            "e7_decision.csv",
            *figures,
            *e7_figures,
            "summary.json",
        ],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    columns = [
        "k",
        "silhouette",
        "temporal_ari",
        "bootstrap_ari_mean",
        "min_cluster_share",
        "calinski_harabasz",
        "davies_bouldin",
    ]
    print("E6 sweep (train split only):")
    print(sweep[columns].to_string(index=False, float_format=lambda value: f"{value:0.4f}"))
    print(f"\nelbow k = {elbow_k} ({summary['elbow_method']})")
    print(f"candidate set: {trace['candidates'] or 'empty'}")
    print(f"decision: {trace['rule']}")

    print("\nE7 scaler comparison (train split only):")
    print(
        e7_decisions[
            [
                "scaler",
                "max_silhouette",
                "max_silhouette_k",
                "floor_reached",
                "gap_to_floor",
                "candidate_set",
                "elbow_k",
                "selected_k",
            ]
        ].to_string(index=False, float_format=lambda value: f"{value:0.4f}")
    )
    for run in runs:
        print(f"  {run['label']}: {run['trace']['rule']}")
    print(f"\nOutputs written to {out_dir}")
    return summary


def main() -> None:
    summary = run()
    selected = summary["selected_k"]
    robust = summary["e7"]["scalers"]["robust"]
    floor_note = (
        f"robust max silhouette {robust['max_silhouette']:.4f} reaches the floor, "
        + (
            f"selected k = {robust['selected_k']}"
            if robust["selected_k"] is not None
            else "the rule still selects nothing"
        )
        if robust["floor_reached"]
        else f"robust max silhouette {robust['max_silhouette']:.4f} stays "
        f"{robust['gap_to_floor']:.4f} below the {SILHOUETTE_MIN} floor"
    )
    print(
        "K-Means selection completed: "
        + (f"selected k = {selected}" if selected is not None else "no k selected by the rule")
        + f" (elbow k = {summary['elbow_k']}, candidates {summary['candidate_set'] or 'none'}); "
        + f"E7: {floor_note}"
    )


if __name__ == "__main__":
    main()
