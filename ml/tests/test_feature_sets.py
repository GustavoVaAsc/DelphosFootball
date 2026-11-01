"""Unit tests for the `FeatureSet` declarations against the transform-stage schema.

The schema list is copied verbatim from the authoritative row schema the `transform`
stage writes, so the declaration contract is testable without importing the pipeline
module. Experiments E1/E2/E4/E6 finalise the three sets; these tests pin the invariants
that hold whatever the experiments decide.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from delphos_ml.features.feature_sets import CLUSTER, FULL, POLY_REDUCED, FeatureSet

# The output schema of the `transform` stage, in schema order.
TRANSFORM_SCHEMA: tuple[str, ...] = (
    "player_id",
    "season",
    "as_of_date",
    "split",
    "club_id",
    "league_id",
    "minutes",
    "apps",
    "starts",
    "captain",
    "squad_inclusions",
    "goals",
    "assists",
    "yellow_cards",
    "red_cards",
    "win_flag",
    "clean_sheet_flag",
    "goals_conceded",
    "uefa_minutes",
    "starter_ratio",
    "captain_ratio",
    "win_rate",
    "clean_sheet_rate",
    "goals_conceded_per_match",
    "uefa_share",
    "cup_share",
    "league_position",
    "league_position_missing",
    "age",
    "age_sq",
    "height_in_cm",
    "foot",
    "position",
    "sub_position",
    "country_group",
    "log10_market_value",
)

ALL_SETS = (FULL, POLY_REDUCED, CLUSTER)


def test_feature_set_is_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        FULL.name = "other"
    with pytest.raises(FrozenInstanceError):
        FULL.collapse = ()


def test_collapse_is_immutable_and_the_declaration_stays_hashable() -> None:
    # The one field encoding a measured rarity decision must not be reassignable in place.
    with pytest.raises(TypeError):
        FULL.collapse["foot"] = ("left",)
    assert isinstance(hash(FULL), int)


@pytest.mark.parametrize("feature_set", ALL_SETS, ids=lambda feature_set: feature_set.name)
def test_every_declared_column_is_in_the_transform_schema(feature_set: FeatureSet) -> None:
    declared = feature_set.columns()
    assert declared, f"{feature_set.name} declares no columns"
    unknown = [column for column in declared if column not in TRANSFORM_SCHEMA]
    assert unknown == [], f"{feature_set.name} declares columns outside the schema: {unknown}"


@pytest.mark.parametrize("feature_set", ALL_SETS, ids=lambda feature_set: feature_set.name)
def test_log1p_columns_are_numeric(feature_set: FeatureSet) -> None:
    assert set(feature_set.log1p) <= set(feature_set.numeric)


@pytest.mark.parametrize("feature_set", ALL_SETS, ids=lambda feature_set: feature_set.name)
def test_no_column_is_declared_as_both_numeric_and_categorical(feature_set: FeatureSet) -> None:
    assert set(feature_set.numeric).isdisjoint(feature_set.categorical)


def test_full_and_cluster_carry_no_market_value_feature() -> None:
    for feature_set in (FULL, CLUSTER):
        leaked = [column for column in feature_set.columns() if "market_value" in column]
        assert leaked == [], f"{feature_set.name} declares market-value features: {leaked}"


def test_cluster_carries_no_league_feature() -> None:
    leaked = [column for column in CLUSTER.columns() if column.startswith("league")]
    assert leaked == [], f"CLUSTER declares league features: {leaked}"


def test_cluster_collapses_rare_sub_position_levels() -> None:
    assert {column for column, _levels in CLUSTER.collapse} <= set(CLUSTER.categorical)
    assert dict(CLUSTER.collapse)["sub_position"] == (
        "Left Midfield",
        "Right Midfield",
        "Second Striker",
    )


def test_only_cluster_declares_collapse() -> None:
    assert FULL.collapse == ()
    assert POLY_REDUCED.collapse == ()
    assert CLUSTER.collapse != ()
