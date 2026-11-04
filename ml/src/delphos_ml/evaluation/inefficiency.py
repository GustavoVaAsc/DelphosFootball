"""Statistical market-inefficiency hypothesis battery with Holm-Bonferroni correction (§3.12).

Input: `transfer_predictions` DataFrame from `train` and OOF quartile thresholds `(q25, q75)`.
Output: `inefficiency_analysis` DataFrame with raw and Holm-adjusted p-values and effect sizes.
Responsibility: test monetary inefficiency in paid transfers across `train_validation`, `test`, and
`all` scopes using paired parametric + non-parametric tests over `fee_minus_fair_log10`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from delphos_ml.evaluation._hypothesis_tests import (
    kruskal_rows,
    one_sample_rows,
    two_sample_rows,
)
from delphos_ml.evaluation.holm import holm_bonferroni
from delphos_ml.evaluation.specs import ALPHA, BIG5_LEAGUES, INEFFICIENCY_COLUMNS


def classify_pre_transfer_status(df: pd.DataFrame, *, q25: float, q75: float) -> np.ndarray:
    """Classify transfers into valuation status ('undervalued', 'fair', 'overvalued')."""
    if not {"linear_log10_pred", "pre_transfer_market_value"}.issubset(df.columns):
        raise ValueError("missing linear_log10_pred or pre_transfer_market_value in transfer frame")
    mv = df["pre_transfer_market_value"].to_numpy(dtype="float64")
    lin = df["linear_log10_pred"].to_numpy(dtype="float64")
    if not (np.isfinite(mv).all() and (mv > 0.0).all() and np.isfinite(lin).all()):
        raise ValueError("transfer frame requires positive market values and finite predictions")
    pre_res = lin - np.log10(mv)
    return np.where(pre_res >= q75, "undervalued", np.where(pre_res <= q25, "overvalued", "fair"))


def _run_scope_tests(scope: str, df: pd.DataFrame, q25: float, q75: float) -> list[dict[str, Any]]:
    gap = df["fee_minus_fair_log10"].to_numpy(dtype="float64")
    status = classify_pre_transfer_status(df, q25=q25, q75=q75)
    under, over = gap[status == "undervalued"], gap[status == "overvalued"]
    if "buyer_league_id" in df.columns:
        is_b5 = df["buyer_league_id"].isin(BIG5_LEAGUES).fillna(False).to_numpy()
    else:
        is_b5 = df["league_id"].isin(BIG5_LEAGUES).to_numpy()
    b5, nb5 = gap[is_b5], gap[~is_b5]
    cl_groups = [
        grp["fee_minus_fair_log10"].to_numpy(dtype="float64") for _, grp in df.groupby("cluster_id")
    ]
    rows = [
        *one_sample_rows(scope, gap),
        *two_sample_rows(scope, under, over),
        *kruskal_rows(scope, gap, b5, nb5, cl_groups),
    ]
    holm_p = holm_bonferroni(np.array([r["p_value"] for r in rows], dtype="float64"))
    for row, p_adj in zip(rows, holm_p, strict=True):
        row["p_value_holm"] = float(p_adj)
        row["alpha"] = ALPHA
        row["reject_null"] = bool(p_adj < ALPHA)
    return rows


def run_inefficiency_tests(
    transfer_predictions: pd.DataFrame, *, q25: float, q75: float
) -> pd.DataFrame:
    """Run the 6-test Holm-Bonferroni battery across `train_validation`, `test`, and `all`."""
    tv_mask = transfer_predictions["split"].isin(["train", "validation"])
    scopes = [
        ("train_validation", transfer_predictions[tv_mask]),
        ("test", transfer_predictions[transfer_predictions["split"] == "test"]),
        ("all", transfer_predictions),
    ]
    records: list[dict[str, Any]] = []
    for scope_name, frame in scopes:
        if len(frame) >= 2:
            records.extend(_run_scope_tests(scope_name, frame, q25, q75))
    if not records:
        return pd.DataFrame(columns=INEFFICIENCY_COLUMNS)
    return pd.DataFrame(records)
