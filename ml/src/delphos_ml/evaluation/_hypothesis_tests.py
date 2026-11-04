"""Parametric and non-parametric statistical test row builders for §3.12.

Input: 1-D `fee_minus_fair_log10` arrays for one-sample, two-sample, and k-sample hypotheses.
Output: unadjusted test result dicts ready for Holm-Bonferroni correction.
Responsibility: encapsulate scipy test calls and standardized effect sizes (`cohen_d`,
`matched_rank_biserial`, `rank_biserial`, `epsilon_squared`). The three small paired helpers
(`one_sample_rows`, `two_sample_rows`, `kruskal_rows`) share `_row` and stay together under
the 130-line convention.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats


def _has_variation(groups: list[np.ndarray]) -> bool:
    all_vals = np.concatenate(groups)
    return len(all_vals) > 0 and bool(np.ptp(all_vals) > 0)


def _row(
    meta: tuple[str, str, str],
    stat: tuple[str, float, float],
    counts: tuple[int, int | None],
    effect: tuple[str, float],
    medians: tuple[float, float | None, float],
) -> dict[str, Any]:
    return {
        "scope": meta[0],
        "test_id": meta[1],
        "hypothesis": meta[2],
        "statistic_name": stat[0],
        "statistic": float(stat[1]) if np.isfinite(stat[1]) else 0.0,
        "p_value": float(stat[2]) if np.isfinite(stat[2]) else 1.0,
        "n_primary": int(counts[0]),
        "n_secondary": int(counts[1]) if counts[1] is not None else None,
        "effect_size_name": effect[0],
        "effect_size": float(effect[1]),
        "primary_median_log10": float(medians[0]),
        "secondary_median_log10": float(medians[1]) if medians[1] is not None else None,
        "median_eur_ratio": float(medians[2]),
    }


def one_sample_rows(scope: str, gap: np.ndarray) -> list[dict[str, Any]]:
    """Build 1-sample t-test and Wilcoxon signed-rank rows against `0.0`."""
    med, ratio = float(np.median(gap)), float(10.0 ** np.median(gap))
    sd = float(gap.std(ddof=1)) if len(gap) > 1 else 0.0
    t1 = stats.ttest_1samp(gap, 0.0) if len(gap) >= 2 and sd > 0 else (0.0, 1.0)
    d1 = float(gap.mean() / sd) if sd > 0 else 0.0
    nz = gap[gap != 0.0]
    w1 = stats.wilcoxon(nz) if len(nz) >= 2 and np.ptp(nz) > 0 else (0.0, 1.0)
    if len(nz) > 0:
        ranks = stats.rankdata(np.abs(nz))
        rb = float((ranks[nz > 0].sum() - ranks[nz < 0].sum()) / (len(nz) * (len(nz) + 1) / 2.0))
    else:
        rb = 0.0
    return [
        _row(
            (scope, "one_sample_t_fee_vs_fair", "mean(log10_fee - fair_log10) != 0"),
            ("t", t1[0], t1[1]),
            (len(gap), None),
            ("cohen_d", d1),
            (med, None, ratio),
        ),
        _row(
            (scope, "wilcoxon_fee_vs_fair", "median(log10_fee - fair_log10) != 0"),
            ("W", w1[0], w1[1]),
            (len(nz), None),
            ("matched_rank_biserial", rb),
            (med, None, ratio),
        ),
    ]


def two_sample_rows(scope: str, under: np.ndarray, over: np.ndarray) -> list[dict[str, Any]]:
    """Build Mann-Whitney U and Welch t-test rows comparing pre-transfer valuation regimes."""
    ok = len(under) >= 2 and len(over) >= 2 and (np.ptp(under) > 0 or np.ptp(over) > 0)
    mw = stats.mannwhitneyu(under, over, alternative="two-sided") if ok else (0.0, 1.0)
    rb = float((2.0 * float(mw[0])) / (len(under) * len(over)) - 1.0) if ok else 0.0
    wt = stats.ttest_ind(under, over, equal_var=False) if ok else (0.0, 1.0)
    psd = float(np.sqrt(0.5 * (under.var(ddof=1) + over.var(ddof=1)))) if ok else 0.0
    d_val = float((under.mean() - over.mean()) / psd) if psd > 0 else 0.0
    m1 = float(np.median(under)) if len(under) else 0.0
    m2 = float(np.median(over)) if len(over) else 0.0
    ratio = float(10.0 ** (m1 - m2)) if ok else 1.0
    return [
        _row(
            (
                scope,
                "mann_whitney_undervalued_vs_overvalued",
                "dist(fee_gap | undervalued) != dist(fee_gap | overvalued)",
            ),
            ("U", mw[0], mw[1]),
            (len(under), len(over)),
            ("rank_biserial", rb),
            (m1, m2, ratio),
        ),
        _row(
            (
                scope,
                "welch_t_undervalued_vs_overvalued",
                "mean(fee_gap | undervalued) != mean(fee_gap | overvalued)",
            ),
            ("welch_t", wt[0], wt[1]),
            (len(under), len(over)),
            ("cohen_d", d_val),
            (m1, m2, ratio),
        ),
    ]


def kruskal_rows(
    scope: str, gap: np.ndarray, b5: np.ndarray, nb5: np.ndarray, cl_groups: list[np.ndarray]
) -> list[dict[str, Any]]:
    """Build Kruskal-Wallis rows for buyer-league tier and tactical clusters."""
    ok_b5 = len(b5) >= 2 and len(nb5) >= 2 and _has_variation([b5, nb5])
    kw_b5 = stats.kruskal(b5, nb5) if ok_b5 else (0.0, 1.0)
    eps_b5 = float(kw_b5[0] / (len(gap) - 1)) if ok_b5 and len(gap) > 1 else 0.0
    mb5 = float(np.median(b5)) if len(b5) else 0.0
    mnb5 = float(np.median(nb5)) if len(nb5) else 0.0
    rb5 = float(10.0 ** (mb5 - mnb5)) if ok_b5 else 1.0

    valid_cl = [g for g in cl_groups if len(g) >= 2]
    n_cl = sum(len(g) for g in valid_cl)
    ok_cl = len(valid_cl) >= 2 and _has_variation(valid_cl)
    kw_cl = stats.kruskal(*valid_cl) if ok_cl else (0.0, 1.0)
    eps_cl = float(kw_cl[0] / (n_cl - 1)) if ok_cl and n_cl > 1 else 0.0
    mall = float(np.median(gap)) if len(gap) else 0.0
    return [
        _row(
            (
                scope,
                "kruskal_big5_vs_non_big5",
                "dist(fee_gap | Big-5 buyer) != dist(fee_gap | non-Big-5 buyer)",
            ),
            ("H", kw_b5[0], kw_b5[1]),
            (len(b5), len(nb5)),
            ("epsilon_squared", eps_b5),
            (mb5, mnb5, rb5),
        ),
        _row(
            (
                scope,
                "kruskal_across_clusters",
                "dist(fee_gap) differs across K-Means tactical clusters",
            ),
            ("H", kw_cl[0], kw_cl[1]),
            (n_cl, None),
            ("epsilon_squared", eps_cl),
            (mall, None, float(10.0**mall)),
        ),
    ]
