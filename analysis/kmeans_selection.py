"""E6: the K-Means cluster-count sweep that decides the `k` of the player archetypes.

Input: `ml/data/transform/player_seasons.parquet` (dataset v679) resolved through
`delphos_ml.config` like `analysis/feature_ablation.py`, read with a predicate that keeps
only the `train` and `validation` splits - the 2025 `test` split is never read.
Output: `e6_k_sweep.csv`, `e6_decision.csv`, `e6_cluster_profiles.csv`,
`fig_e6_internal.png`, `fig_e6_stability.png` and `summary.json` under
`<repo root>/analysis/output/kmeans_selection/`.
Responsibility: run experiment E6 of docs/ML_ARCHITECTURE.md section 3.8 (the procedure is
docs/TRANSFORM_PLAN.md section 6): fit the `CLUSTER` feature space and one K-Means per `k`
on the training split only, sweep `k = 2..15`, score four internal metrics and two
stability measures, then apply the section-6 decision rule verbatim. The script reports
evidence only; recording the chosen `k` in the architecture docs is a separate step. Like
`feature_ablation.py` this is one experiment script per ADR-014, and it stays one module
because every stage feeds the single decision table - splitting it would break the
one-script-one-output-dir convention without shortening anything.

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
    """Run the E6 sweep and the decision rule, then write every output artefact."""
    train, validation, out_dir, manifest = _load_rows()
    out_dir.mkdir(parents=True, exist_ok=True)
    pre = build_preprocessor(
        CLUSTER, empirical_bayes_m=EMPIRICAL_BAYES_M, prior_grouping=PRIOR_GROUPING
    )
    X_train = pre.fit_transform(train)
    X_val = pre.transform(validation)
    sample_index = np.random.default_rng(RANDOM_STATE).choice(
        len(X_train), size=min(SILHOUETTE_SAMPLE, len(X_train)), replace=False
    )

    records = [_sweep_k(X_train, X_val, k, sample_index) for k in K_VALUES]
    sweep = pd.DataFrame(records)
    elbow_k = _elbow_k(sweep["inertia"].to_numpy())
    decision, trace = _decide(sweep, elbow_k)
    profile_k = trace["selected_k"] if trace["selected_k"] is not None else elbow_k
    profile_source = (
        "selected k"
        if trace["selected_k"] is not None
        else ("elbow k (no candidate passed the rule)")
    )
    profiles = _profiles(train, pre, _fit(X_train, profile_k))

    sweep.to_csv(out_dir / "e6_k_sweep.csv", index=False)
    decision.to_csv(out_dir / "e6_decision.csv", index=False)
    profiles.to_csv(out_dir / "e6_cluster_profiles.csv", index=False)
    figures = _render_figures(out_dir, sweep, elbow_k)

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
        "outputs": [
            "e6_k_sweep.csv",
            "e6_decision.csv",
            "e6_cluster_profiles.csv",
            *figures,
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
    print(f"\nOutputs written to {out_dir}")
    return summary


def main() -> None:
    summary = run()
    selected = summary["selected_k"]
    print(
        "K-Means selection completed: "
        + (f"selected k = {selected}" if selected is not None else "no k selected by the rule")
        + f" (elbow k = {summary['elbow_k']}, candidates {summary['candidate_set'] or 'none'})"
    )


if __name__ == "__main__":
    main()
