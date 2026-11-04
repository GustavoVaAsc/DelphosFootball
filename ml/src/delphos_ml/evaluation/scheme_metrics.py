"""Held-out split and expanding-window comparison across all five KDD models (§3.15).

Input: `player_seasons`, `player_predictions`, `clusters`, `LoadedArtifacts`, and transform config.
Output: `model_metrics` DataFrame with `scope`, `model`, `metric`, `value`, `se`, and `n_rows`.
Responsibility: assemble `cv_k_fold`, `validation`, and `test` metrics for Linear, Polynomial,
Decision Tree, Random Forest, and K-Means without recalibrating on `test`.
"""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score

from delphos_ml.artifacts import LoadedArtifacts
from delphos_ml.evaluation._expanding_cv import run_expanding_cv
from delphos_ml.evaluation._metrics import cls_metrics, reg_metrics
from delphos_ml.evaluation.specs import (
    MODEL_METRICS_COLUMNS,
    SILHOUETTE_RANDOM_STATE,
    SILHOUETTE_SAMPLE_MAX,
)
from delphos_ml.models.scoring import to_dense


def compute_scheme_metrics(
    player_seasons: pd.DataFrame,
    player_predictions: pd.DataFrame,
    clusters: pd.DataFrame,
    bundle: LoadedArtifacts,
    *,
    empirical_bayes_m: float,
    prior_grouping: str,
) -> pd.DataFrame:
    """Compute held-out (`validation`, `test`) and expanding-window CV metrics for all 5 models."""
    rows = run_expanding_cv(
        player_seasons[player_seasons["split"].isin(["train", "validation"])],
        m=empirical_bayes_m,
        prior_grouping=prior_grouping,
    )
    reg_cols = (
        ("linear_regression", "linear_log10_pred"),
        ("polynomial_regression", "poly_log10_pred"),
    )
    cls_cols = (
        ("decision_tree", "dt_undervalued_prob", "dt_undervalued_pred"),
        ("random_forest", "rf_undervalued_prob", "rf_undervalued_pred"),
    )
    for split_name in ("validation", "test"):
        sub_p = player_predictions[player_predictions["split"] == split_name]
        if sub_p.empty:
            continue
        n_r = int(len(sub_p))
        y_l = sub_p["log10_market_value"].to_numpy(dtype="float64")
        for m_name, col in reg_cols:
            for k, v in reg_metrics(y_l, sub_p[col].to_numpy(dtype="float64")).items():
                rows.append(
                    {
                        "scope": split_name,
                        "model": m_name,
                        "metric": k,
                        "value": v,
                        "se": None,
                        "n_rows": n_r,
                    }
                )
        y_c = sub_p["is_undervalued"].to_numpy(dtype="int64")
        for m_name, p_col, b_col in cls_cols:
            probs = sub_p[p_col].to_numpy(dtype="float64")
            preds = sub_p[b_col].to_numpy(dtype="int64")
            for k, v in cls_metrics(y_c, probs, preds).items():
                rows.append(
                    {
                        "scope": split_name,
                        "model": m_name,
                        "metric": k,
                        "value": v,
                        "se": None,
                        "n_rows": n_r,
                    }
                )

    aligned = (
        player_seasons.merge(
            clusters[["player_id", "season", "split", "cluster_id"]],
            on=["player_id", "season", "split"],
            validate="one_to_one",
        )
        .sort_values(["season", "player_id"])
        .reset_index(drop=True)
    )
    if len(aligned) != len(player_seasons):
        raise ValueError("key mismatch between player_seasons and clusters")

    for split_name in ("train", "validation", "test"):
        sub = aligned[aligned["split"] == split_name].reset_index(drop=True)
        if len(sub) < 4 or sub["cluster_id"].nunique() < 2:
            continue
        x_cl = to_dense(bundle.cluster_preprocessor.transform(sub))
        labels = sub["cluster_id"].to_numpy(dtype="int64")
        n_r = int(len(sub))
        sil = float(
            silhouette_score(
                x_cl,
                labels,
                sample_size=min(SILHOUETTE_SAMPLE_MAX, n_r),
                random_state=SILHOUETTE_RANDOM_STATE,
            )
        )
        counts = pd.Series(labels).value_counts(normalize=True)
        km_stats = {
            "silhouette": sil,
            "calinski_harabasz": float(calinski_harabasz_score(x_cl, labels)),
            "davies_bouldin": float(davies_bouldin_score(x_cl, labels)),
            "min_cluster_share": float(counts.min()),
        }
        for k, v in km_stats.items():
            rows.append(
                {
                    "scope": split_name,
                    "model": "kmeans",
                    "metric": k,
                    "value": v,
                    "se": None,
                    "n_rows": n_r,
                }
            )
    if not rows:
        return pd.DataFrame(columns=MODEL_METRICS_COLUMNS)
    return pd.DataFrame(rows)
