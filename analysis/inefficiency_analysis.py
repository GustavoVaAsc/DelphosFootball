"""Market-inefficiency report tables and figures from `evaluate` outputs (§3.12, §3.16).

Input: `ml/data/evaluate/inefficiency_analysis.parquet`, `_evaluate.json`, and
`ml/data/train/transfer_predictions.parquet`, `_train.json` resolved via `delphos_ml.config`.
Output: `hypothesis_tests.csv`, `subgroup_fee_gaps.csv`, `fig_inefficiency_distributions.png`,
and `summary.json` under `<repo root>/analysis/output/inefficiency_analysis/`.
Responsibility: present the §3.12 statistical demonstration without re-implementing hypothesis
tests or Holm-Bonferroni adjustments (ADR-009, ML_ARCHITECTURE.md §3.16), verifying manifest
provenance so report figures and tables match the published pipeline outputs verbatim.
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
from delphos_ml.evaluation import classify_pre_transfer_status
from delphos_ml.evaluation.specs import BIG5_LEAGUES


def _fail(reason: str) -> None:
    print(f"inefficiency_analysis failed: {reason}", file=sys.stderr)
    raise SystemExit(1)


def _load_validated_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], Path]:
    try:
        settings = load_settings()
    except ConfigError as exc:
        _fail(str(exc))
    project_root = find_project_root()
    repo_root = project_root.parent if project_root is not None else Path.cwd()
    eval_dir = settings.data_dir / "evaluate"
    train_dir = settings.data_dir / "train"
    tf_dir = settings.data_dir / "transform"
    req_files = (
        eval_dir / "_evaluate.json",
        eval_dir / "inefficiency_analysis.parquet",
        train_dir / "_train.json",
        train_dir / "transfer_predictions.parquet",
        tf_dir / "_transform.json",
    )
    for req in req_files:
        if not req.is_file():
            _fail(f"missing {req}; run `delphos-pipeline evaluate` first")

    try:
        eval_man = json.loads((eval_dir / "_evaluate.json").read_text(encoding="utf-8"))
        train_bytes = (train_dir / "_train.json").read_bytes()
        train_man = json.loads(train_bytes.decode("utf-8"))
        tf_bytes = (tf_dir / "_transform.json").read_bytes()
        tf_sha = hashlib.sha256(tf_bytes).hexdigest()
        actual_train_sha = hashlib.sha256(train_bytes).hexdigest()
        if not hmac.compare_digest(
            actual_train_sha, str(eval_man.get("train_manifest_sha256", ""))
        ):
            _fail("_evaluate.json train_manifest_sha256 does not match _train.json; rerun evaluate")
        if not hmac.compare_digest(tf_sha, str(eval_man.get("transform_manifest_sha256", ""))):
            _fail("_evaluate.json transform_manifest_sha256 mismatch; rerun evaluate")

        ineff_df = pd.read_parquet(eval_dir / "inefficiency_analysis.parquet")
        transfers_df = pd.read_parquet(train_dir / "transfer_predictions.parquet")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, pa.ArrowException) as exc:
        _fail(f"could not read inputs: {exc}")

    ev_tables = eval_man.get("tables", {})
    tr_tables = train_man.get("tables", {})
    if "inefficiency_analysis" in ev_tables and len(ineff_df) != ev_tables[
        "inefficiency_analysis"
    ].get("rows"):
        _fail("inefficiency_analysis.parquet row count mismatch against _evaluate.json")
    if "transfer_predictions" in tr_tables and len(transfers_df) != tr_tables[
        "transfer_predictions"
    ].get("rows"):
        _fail("transfer_predictions.parquet row count mismatch against _train.json")

    out_dir = repo_root / "analysis" / "output" / "inefficiency_analysis"
    return ineff_df, transfers_df, train_man, out_dir


def _subgroup_summary(df: pd.DataFrame, q25: float, q75: float) -> pd.DataFrame:
    work = df.copy()
    work["pre_valuation_status"] = classify_pre_transfer_status(work, q25=q25, q75=q75)
    if "buyer_league_id" in work.columns:
        is_b5 = work["buyer_league_id"].isin(BIG5_LEAGUES).fillna(False)
    else:
        is_b5 = work["league_id"].isin(BIG5_LEAGUES)
    work["buyer_tier"] = np.where(is_b5, "Big-5", "non-Big-5")

    slices: list[tuple[str, str, pd.DataFrame]] = [("overall", "all_transfers", work)]
    for sp in ("train", "validation", "test"):
        slices.append(("split", sp, work[work["split"] == sp]))
    for st in ("undervalued", "fair", "overvalued"):
        slices.append(("pre_valuation_status", st, work[work["pre_valuation_status"] == st]))
    for tier in ("Big-5", "non-Big-5"):
        slices.append(("buyer_tier", tier, work[work["buyer_tier"] == tier]))
    for cid in sorted(int(c) for c in work["cluster_id"].unique()):
        slices.append(("cluster_id", f"cluster_{cid}", work[work["cluster_id"] == cid]))

    rows: list[dict[str, Any]] = []
    for dim, level, sub in slices:
        if sub.empty:
            continue
        gap = sub["fee_minus_fair_log10"].to_numpy(dtype="float64")
        mv_gap = sub["fee_minus_mv_log10"].to_numpy(dtype="float64")
        q75_g, q25_g = np.percentile(gap, [75, 25])
        med_g = float(np.median(gap))
        rows.append(
            {
                "dimension": dim,
                "subgroup": level,
                "n_transfers": int(len(sub)),
                "mean_fee_minus_fair_log10": float(gap.mean()),
                "median_fee_minus_fair_log10": med_g,
                "iqr_fee_minus_fair_log10": float(q75_g - q25_g),
                "median_fee_to_fair_ratio": float(10.0**med_g),
                "median_fee_minus_mv_log10": float(np.median(mv_gap)),
                "overpaid_vs_fair_share": float((gap > 0.0).mean()),
            }
        )
    return pd.DataFrame(rows)


def _plot_distributions(df: pd.DataFrame, q25: float, q75: float, out_path: Path) -> None:
    status = classify_pre_transfer_status(df, q25=q25, q75=q75)
    if "buyer_league_id" in df.columns:
        is_b5 = df["buyer_league_id"].isin(BIG5_LEAGUES).fillna(False).to_numpy()
    else:
        is_b5 = df["league_id"].isin(BIG5_LEAGUES).to_numpy()
    gap = df["fee_minus_fair_log10"].to_numpy(dtype="float64")

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4), constrained_layout=True)

    axes[0].hist(gap, bins=48, color="#1b6ca8", alpha=0.78, edgecolor="white")
    axes[0].axvline(0.0, color="black", ls="--", lw=1.2, label="Fair value (0.0)")
    axes[0].axvline(
        float(np.median(gap)),
        color="#d1495b",
        lw=1.6,
        label=f"Median ({np.median(gap):+.3f})",
    )
    axes[0].set_xlabel("log10(transfer_fee) - fair_log10")
    axes[0].set_ylabel("Paid transfers")
    axes[0].set_title(f"A. Paid-transfer fee gap (n={len(gap):,})")
    axes[0].legend(fontsize=8.5)

    order_st = ("undervalued", "fair", "overvalued")
    data_st = [gap[status == label] for label in order_st]
    bp1 = axes[1].boxplot(data_st, tick_labels=order_st, patch_artist=True, showfliers=False)
    for patch, col in zip(bp1["boxes"], ("#2a9d8f", "#8d99ae", "#e76f51"), strict=True):
        patch.set_facecolor(col)
        patch.set_alpha(0.75)
    axes[1].axhline(0.0, color="black", ls="--", lw=1.0)
    axes[1].set_ylabel("log10(transfer_fee) - fair_log10")
    axes[1].set_title("B. Fee gap by pre-transfer status")

    tv = df["split"].isin(["train", "validation"]).to_numpy()
    te = (df["split"] == "test").to_numpy()
    groups_b5 = [gap[tv & is_b5], gap[tv & ~is_b5], gap[te & is_b5], gap[te & ~is_b5]]
    labels_b5 = ["Big-5\n(17-24)", "Other\n(17-24)", "Big-5\n(2025)", "Other\n(2025)"]
    bp2 = axes[2].boxplot(groups_b5, tick_labels=labels_b5, patch_artist=True, showfliers=False)
    for patch, col in zip(bp2["boxes"], ("#264653", "#a8dadc", "#264653", "#a8dadc"), strict=True):
        patch.set_facecolor(col)
        patch.set_alpha(0.8)
    axes[2].axhline(0.0, color="black", ls="--", lw=1.0)
    axes[2].set_ylabel("log10(transfer_fee) - fair_log10")
    axes[2].set_title("C. Buyer-league tier across splits")

    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    ineff_df, transfers_df, train_man, out_dir = _load_validated_inputs()
    out_dir.mkdir(parents=True, exist_ok=True)
    thresholds = train_man["thresholds"]
    q25 = float(thresholds["q25_overvalued_log10"])
    q75 = float(thresholds["q75_undervalued_log10"])

    ineff_df.to_csv(out_dir / "hypothesis_tests.csv", index=False)
    sub_df = _subgroup_summary(transfers_df, q25, q75)
    sub_df.to_csv(out_dir / "subgroup_fee_gaps.csv", index=False)
    _plot_distributions(transfers_df, q25, q75, out_dir / "fig_inefficiency_distributions.png")

    summary = {
        "dataset_version": train_man.get("version"),
        "n_paid_transfers": int(len(transfers_df)),
        "thresholds": {"q25_overvalued_log10": q25, "q75_undervalued_log10": q75},
        "hypothesis_tests": ineff_df.to_dict(orient="records"),
        "subgroups": sub_df.to_dict(orient="records"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(ineff_df[["scope", "test_id", "statistic", "p_value_holm", "reject_null"]].to_string())


if __name__ == "__main__":
    main()
