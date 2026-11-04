"""Cross-scheme model comparison and replacement-economics report artifacts (§3.13, §3.15, §3.16).

Input: `ml/data/evaluate/` (`model_metrics.parquet`, `replacement_targets.parquet`,
`replacements.parquet`, `_evaluate.json`), `ml/data/train/` (`_train.json`, `clusters.parquet`),
and `ml/data/transform/player_seasons.parquet`.
Output: `regression_comparison.csv`, `classification_comparison.csv`, `clustering_diagnostics.csv`,
`cluster_profiles.csv`, `replacement_economics.csv`, `fig_scheme_comparison.png`, and `summary.json`
under `<repo root>/analysis/output/model_comparison/`.
Responsibility: assemble the §3.15 5-model evaluation tables and §3.13 replacement-coverage summary
directly from `evaluate` Parquet outputs without re-implementing pipeline algorithms (ADR-009).
"""

from __future__ import annotations

import hashlib
import hmac
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

from delphos_ml.config import ConfigError, find_project_root, load_settings


def _fail(reason: str) -> None:
    print(f"model_comparison failed: {reason}", file=sys.stderr)
    raise SystemExit(1)


def _load_inputs() -> tuple[dict[str, pd.DataFrame], dict[str, Any], Path]:
    try:
        settings = load_settings()
    except ConfigError as exc:
        _fail(str(exc))
    project_root = find_project_root()
    repo_root = project_root.parent if project_root is not None else Path.cwd()
    ev_dir = settings.data_dir / "evaluate"
    tr_dir = settings.data_dir / "train"
    tf_dir = settings.data_dir / "transform"
    req = (
        ev_dir / "_evaluate.json",
        ev_dir / "model_metrics.parquet",
        ev_dir / "replacement_targets.parquet",
        ev_dir / "replacements.parquet",
        tr_dir / "_train.json",
        tr_dir / "clusters.parquet",
        tf_dir / "_transform.json",
        tf_dir / "player_seasons.parquet",
    )
    for path in req:
        if not path.is_file():
            _fail(f"missing {path}; run `delphos-pipeline evaluate` first")

    try:
        eval_man = json.loads((ev_dir / "_evaluate.json").read_text(encoding="utf-8"))
        train_bytes = (tr_dir / "_train.json").read_bytes()
        tf_bytes = (tf_dir / "_transform.json").read_bytes()
        train_man = json.loads(train_bytes.decode("utf-8"))
        tf_man = json.loads(tf_bytes.decode("utf-8"))
        tr_sha = hashlib.sha256(train_bytes).hexdigest()
        tf_sha = hashlib.sha256(tf_bytes).hexdigest()
        if not hmac.compare_digest(tr_sha, str(eval_man.get("train_manifest_sha256", ""))):
            _fail("_evaluate.json train_manifest_sha256 mismatch; rerun evaluate")
        if not hmac.compare_digest(tf_sha, str(eval_man.get("transform_manifest_sha256", ""))):
            _fail("_evaluate.json transform_manifest_sha256 mismatch; rerun evaluate")

        frames = {
            "metrics": pd.read_parquet(ev_dir / "model_metrics.parquet"),
            "targets": pd.read_parquet(ev_dir / "replacement_targets.parquet"),
            "replacements": pd.read_parquet(ev_dir / "replacements.parquet"),
            "clusters": pd.read_parquet(tr_dir / "clusters.parquet"),
            "player_seasons": pd.read_parquet(tf_dir / "player_seasons.parquet"),
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, pa.ArrowException) as exc:
        _fail(f"could not read inputs: {exc}")

    ev_t = eval_man.get("tables", {})
    tr_t = train_man.get("tables", {})
    tf_t = tf_man.get("tables", {})
    for name, tbl, man_t in (
        ("model_metrics", frames["metrics"], ev_t),
        ("replacement_targets", frames["targets"], ev_t),
        ("replacements", frames["replacements"], ev_t),
        ("clusters", frames["clusters"], tr_t),
        ("player_seasons", frames["player_seasons"], tf_t),
    ):
        if name in man_t and len(tbl) != man_t[name].get("rows"):
            _fail(f"{name}.parquet row count mismatch against upstream manifest")

    return frames, eval_man, repo_root / "analysis" / "output" / "model_comparison"


def _cluster_profiles(ps: pd.DataFrame, cl: pd.DataFrame) -> pd.DataFrame:
    joined = ps.merge(cl, on=["player_id", "season", "split"], validate="one_to_one")
    n90 = np.maximum(joined["minutes"].to_numpy(dtype="float64") / 90.0, 1e-9)
    joined["raw_ga_per90"] = (joined["goals"] + joined["assists"]) / n90
    rows: list[dict[str, Any]] = []
    for cid, grp in joined.groupby("cluster_id"):
        pos_shares = grp["position"].value_counts(normalize=True)
        dom_pos = str(pos_shares.index[0])
        rows.append(
            {
                "cluster_id": int(cid),
                "n_rows_all": int(len(grp)),
                "share_all": float(len(grp) / len(joined)),
                "mean_raw_ga_per90": float(grp["raw_ga_per90"].mean()),
                "mean_minutes": float(grp["minutes"].mean()),
                "mean_starter_ratio": float(grp["starter_ratio"].mean()),
                "mean_uefa_share": float(grp["uefa_share"].mean()),
                "dominant_position": dom_pos,
                "dominant_position_share": float(pos_shares.iloc[0]),
            }
        )
    return pd.DataFrame(rows)


def _replacement_economics(targets: pd.DataFrame, repl: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    slices: list[tuple[str, pd.DataFrame]] = [
        ("all_active_players", targets),
        ("elite_assets_only", targets[targets["is_elite_asset"]]),
    ]
    for pos in sorted(targets["position"].astype(str).unique()):
        slices.append(
            (f"elite_{pos}", targets[targets["is_elite_asset"] & (targets["position"] == pos)])
        )

    for label, sub_t in slices:
        if sub_t.empty:
            continue
        sub_r = repl[repl["target_player_id"].isin(sub_t["player_id"])]
        rows.append(
            {
                "cohort": label,
                "n_targets": int(len(sub_t)),
                "share_with_3_replacements": float((sub_t["qualifying_count"] == 3).mean()),
                "share_with_at_least_1": float((sub_t["qualifying_count"] >= 1).mean()),
                "n_replacement_rows": int(len(sub_r)),
                "median_cost_savings_eur": float(sub_r["cost_savings_eur"].median())
                if len(sub_r)
                else 0.0,
                "median_discount_pct": float((1.0 - sub_r["cost_ratio"]).median() * 100.0)
                if len(sub_r)
                else 0.0,
                "median_similarity_score": float(sub_r["similarity_score"].median())
                if len(sub_r)
                else 0.0,
                "undervalued_candidate_share": float(
                    (sub_r["candidate_valuation_status"] == "undervalued").mean()
                )
                if len(sub_r)
                else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _plot_comparison(metrics: pd.DataFrame, repl: pd.DataFrame, out_path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11.8, 8.2), constrained_layout=True)
    cv_scopes = sorted(s for s in set(metrics["scope"]) if s.startswith("cv_"))
    scopes_sup = cv_scopes + [s for s in ("validation", "test") if s in set(metrics["scope"])]
    x = np.arange(len(scopes_sup))

    for idx, (m_name, label, col) in enumerate(
        (
            ("linear_regression", "Linear OLS (FULL)", "#1b6ca8"),
            ("polynomial_regression", "Poly deg-2 (POLY_REDUCED)", "#e76f51"),
        )
    ):
        sub = metrics[(metrics["model"] == m_name) & (metrics["metric"] == "rmse_log10")].set_index(
            "scope"
        )
        vals = [float(sub.loc[s, "value"]) for s in scopes_sup]
        ses = [0.0 if pd.isna(sub.loc[s, "se"]) else float(sub.loc[s, "se"]) for s in scopes_sup]
        axes[0, 0].bar(
            x + (idx - 0.5) * 0.34, vals, width=0.32, yerr=ses, capsize=4, label=label, color=col
        )
    axes[0, 0].set_xticks(x, scopes_sup)
    axes[0, 0].set_ylabel("RMSE on log10(EUR)")
    axes[0, 0].set_title("A. Regression RMSE (lower is better)")
    axes[0, 0].legend(fontsize=8.5)

    for idx, (m_name, label, col) in enumerate(
        (
            ("decision_tree", "Decision Tree (1-SE)", "#8d99ae"),
            ("random_forest", "Random Forest (1-SE)", "#2a9d8f"),
        )
    ):
        sub = metrics[(metrics["model"] == m_name) & (metrics["metric"] == "pr_auc")].set_index(
            "scope"
        )
        vals = [float(sub.loc[s, "value"]) for s in scopes_sup]
        ses = [0.0 if pd.isna(sub.loc[s, "se"]) else float(sub.loc[s, "se"]) for s in scopes_sup]
        axes[0, 1].bar(
            x + (idx - 0.5) * 0.34, vals, width=0.32, yerr=ses, capsize=4, label=label, color=col
        )
    axes[0, 1].set_xticks(x, scopes_sup)
    axes[0, 1].set_ylabel("PR-AUC (is_undervalued)")
    axes[0, 1].set_title("B. Classification PR-AUC (higher is better)")
    axes[0, 1].legend(fontsize=8.5)

    km = metrics[(metrics["model"] == "kmeans") & (metrics["metric"] == "silhouette")].set_index(
        "scope"
    )
    km_scopes = [s for s in ("train", "validation", "test") if s in km.index]
    axes[1, 0].bar(
        km_scopes, [float(km.loc[s, "value"]) for s in km_scopes], color="#264653", width=0.45
    )
    axes[1, 0].axhline(0.25, color="#d1495b", ls="--", lw=1.1, label="0.25 structure floor")
    axes[1, 0].set_ylabel("Sampled Silhouette (RobustScaler)")
    axes[1, 0].set_title("C. K-Means (k=3) silhouette across splits")
    axes[1, 0].legend(fontsize=8.5)

    elite_r = repl[repl["target_is_elite_asset"]]
    rng = np.random.default_rng(20261103)
    s_idx = (
        rng.choice(len(elite_r), size=min(2500, len(elite_r)), replace=False)
        if len(elite_r)
        else []
    )
    if len(s_idx):
        axes[1, 1].scatter(
            elite_r["similarity_score"].iloc[s_idx],
            (1.0 - elite_r["cost_ratio"].iloc[s_idx]) * 100.0,
            s=8,
            alpha=0.3,
            color="#2a9d8f",
        )
    axes[1, 1].axhline(20.0, color="#d1495b", ls="--", lw=1.1, label="20% min discount")
    axes[1, 1].set_xlabel("Athletic similarity score 1 / (1 + d)")
    axes[1, 1].set_ylabel("Market-value discount (%)")
    axes[1, 1].set_title("D. Elite-asset top-3 replacements (2025)")
    axes[1, 1].legend(fontsize=8.5)

    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    frames, eval_man, out_dir = _load_inputs()
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = frames["metrics"]

    reg_df = metrics[metrics["model"].isin(["linear_regression", "polynomial_regression"])].copy()
    cls_df = metrics[metrics["model"].isin(["decision_tree", "random_forest"])].copy()
    km_df = metrics[metrics["model"] == "kmeans"].copy()
    prof_df = _cluster_profiles(frames["player_seasons"], frames["clusters"])
    econ_df = _replacement_economics(frames["targets"], frames["replacements"])

    reg_df.to_csv(out_dir / "regression_comparison.csv", index=False)
    cls_df.to_csv(out_dir / "classification_comparison.csv", index=False)
    km_df.to_csv(out_dir / "clustering_diagnostics.csv", index=False)
    prof_df.to_csv(out_dir / "cluster_profiles.csv", index=False)
    econ_df.to_csv(out_dir / "replacement_economics.csv", index=False)
    _plot_comparison(metrics, frames["replacements"], out_dir / "fig_scheme_comparison.png")

    summary = {
        "dataset_version": eval_man.get("version"),
        "active_replacement_season": eval_man.get("active_replacement_season"),
        "replacement_coverage": eval_man.get("replacement_coverage"),
        "regression_metrics": reg_df.to_dict(orient="records"),
        "classification_metrics": cls_df.to_dict(orient="records"),
        "clustering_metrics": km_df.to_dict(orient="records"),
        "cluster_profiles": prof_df.to_dict(orient="records"),
        "replacement_economics": econ_df.to_dict(orient="records"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(metrics.to_string(index=False))
    print("\nReplacement economics:")
    print(econ_df.to_string(index=False))


if __name__ == "__main__":
    main()
