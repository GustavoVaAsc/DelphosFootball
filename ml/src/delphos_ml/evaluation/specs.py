"""Frozen statistical and replacement-ranking constants for `delphos_ml.evaluation` (§3.12–§3.15).

Input: none (declarative constants).
Output: significance level, Big-5 league IDs, replacement percentiles, and CV constants.
Responsibility: centralize every evaluation threshold agreed in `docs/ML_ARCHITECTURE.md` §3.12,
§3.13, and §3.15; grouped together because constants alone do not warrant separate modules.
"""

from __future__ import annotations

ALPHA = 0.05
BIG5_LEAGUES: frozenset[str] = frozenset({"GB1", "ES1", "IT1", "L1", "FR1"})

ELITE_PERCENTILE = 75.0
DISTANCE_PERCENTILE = 25.0
COST_CEILING_RATIO = 0.80
TOP_K_REPLACEMENTS = 3

MIN_CV_ANCHOR_SEASONS = 3
SILHOUETTE_SAMPLE_MAX = 5000
SILHOUETTE_RANDOM_STATE = 42

INEFFICIENCY_COLUMNS: tuple[str, ...] = (
    "scope",
    "test_id",
    "hypothesis",
    "statistic_name",
    "statistic",
    "p_value",
    "p_value_holm",
    "alpha",
    "reject_null",
    "n_primary",
    "n_secondary",
    "effect_size_name",
    "effect_size",
    "primary_median_log10",
    "secondary_median_log10",
    "median_eur_ratio",
)

TARGET_COLUMNS: tuple[str, ...] = (
    "player_id",
    "season",
    "position",
    "cluster_id",
    "market_value_eur",
    "elite_mv_threshold_eur",
    "is_elite_asset",
    "distance_ceiling",
    "qualifying_count",
    "shortfall_reason",
)

REPLACEMENT_COLUMNS: tuple[str, ...] = (
    "target_player_id",
    "season",
    "rank",
    "candidate_player_id",
    "cluster_id",
    "position",
    "euclidean_distance",
    "similarity_score",
    "target_market_value_eur",
    "candidate_market_value_eur",
    "cost_savings_eur",
    "cost_ratio",
    "candidate_fair_value_eur",
    "candidate_residual_log10",
    "candidate_valuation_status",
    "target_is_elite_asset",
)

MODEL_METRICS_COLUMNS: tuple[str, ...] = (
    "scope",
    "model",
    "metric",
    "value",
    "se",
    "n_rows",
)
