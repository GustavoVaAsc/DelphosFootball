"""Settled model constants (ML_ARCHITECTURE.md sections 3.7-3.10) and manifest read-back checks.

Input: the parsed `_transform.json` dictionary read by `delphos_ml.pipeline.train`.
Output: validated transform parameters (`ValidatedTransformConfig`) or `ValueError`, plus the
settled hyperparameter constants consumed by `delphos_ml.models.fitting`.
Responsibility: centralize every fixed model hyperparameter chosen by E4, E6/E7, and E8 alongside
the sink/reader validation rules of docs/TRANSFORM_PLAN.md section 4 so `train` never trusts an
unvalidated `_transform.json`. Kept together in one module because the constants and the single
validation function define the parameter boundary entering `fitting`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

PRIOR_GROUPINGS: frozenset[str] = frozenset({"position", "sub_position"})

POLY_DEGREE = 2
POLY_INTERACTION_ONLY = False

KMEANS_K = 3
KMEANS_N_INIT = 20
KMEANS_MAX_ITER = 500
KMEANS_RANDOM_STATE = 20261101

CLASSIFIER_RANDOM_STATE = 20261103
DT_MAX_DEPTH = 10
DT_MIN_SAMPLES_LEAF = 100
RF_N_ESTIMATORS = 300
RF_MAX_DEPTH = 14
RF_MIN_SAMPLES_LEAF = 5

Q25_PERCENTILE = 25.0
Q75_PERCENTILE = 75.0


@dataclass(frozen=True)
class ValidatedTransformConfig:
    """Validated parameters read back from `_transform.json`."""

    window_days: int
    minutes_floor: int
    empirical_bayes_m: float
    prior_grouping: str
    season_month_start: int
    country_top_n: int
    country_groups: tuple[str, ...]


def _require_positive_int(mapping: Mapping[str, Any], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"_transform.json {key} must be a positive integer, got {value!r}")
    return value


def validate_transform_manifest(manifest: Mapping[str, Any]) -> ValidatedTransformConfig:
    """Validate `_transform.json` parameters per docs/TRANSFORM_PLAN.md section 4."""
    window_days = _require_positive_int(manifest, "window_days")
    minutes_floor = _require_positive_int(manifest, "minutes_floor")
    country_top_n = _require_positive_int(manifest, "country_top_n")

    season_month = manifest.get("season_month_start")
    if (
        isinstance(season_month, bool)
        or not isinstance(season_month, int)
        or not (1 <= season_month <= 12)
    ):
        raise ValueError(
            f"_transform.json season_month_start must be an integer in 1..12, got {season_month!r}"
        )

    m_val = manifest.get("empirical_bayes_m")
    if (
        isinstance(m_val, bool)
        or not isinstance(m_val, (int, float))
        or not math.isfinite(m_val)
        or m_val <= 0
    ):
        raise ValueError(
            f"_transform.json empirical_bayes_m must be positive and finite, got {m_val!r}"
        )

    grouping = manifest.get("prior_grouping")
    if not isinstance(grouping, str) or grouping not in PRIOR_GROUPINGS:
        raise ValueError(
            f"_transform.json prior_grouping must be in {sorted(PRIOR_GROUPINGS)}, got {grouping!r}"
        )

    groups = manifest.get("country_groups")
    if (
        not isinstance(groups, list)
        or len(groups) > country_top_n
        or not all(isinstance(item, str) and item and item != "other" for item in groups)
        or len(set(groups)) != len(groups)
    ):
        raise ValueError(
            f"_transform.json country_groups must be <= {country_top_n} unique non-'other' strings"
        )

    return ValidatedTransformConfig(
        window_days=window_days,
        minutes_floor=minutes_floor,
        empirical_bayes_m=float(m_val),
        prior_grouping=grouping,
        season_month_start=season_month,
        country_top_n=country_top_n,
        country_groups=tuple(groups),
    )
