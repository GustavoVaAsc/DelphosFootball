"""Unit tests for the fitted preprocessor: shrunk rates, grouped imputation, leak guard.

The leak guard is the central assertion of docs/TRANSFORM_PLAN.md section 2: changing
only the validation rows and refitting on the training rows must leave every fitted
parameter (priors, medians, scaler moments, one-hot vocabularies) identical, because
nothing learned from data may cross the split. Fixtures are small synthetic frames
shaped like the `transform` stage's row schema.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from delphos_ml.features.feature_sets import CLUSTER, FULL, POLY_REDUCED
from delphos_ml.features.preprocess import (
    EmpiricalBayesRates,
    GroupMedianImputer,
    build_preprocessor,
)
from delphos_ml.features.preprocess.empirical_bayes_rates import DEFAULT_GROUP_COLUMN, DEFAULT_M


def _dense(matrix: object) -> np.ndarray:
    """Dense array from either sparse or dense preprocessor output."""
    toarray = getattr(matrix, "toarray", None)
    return toarray() if toarray is not None else np.asarray(matrix)


def _full_row(**overrides: object) -> dict[str, object]:
    """One row carrying every column `FULL` declares (plus the `split` marker)."""
    row: dict[str, object] = {
        "split": "train",
        "minutes": 900.0,
        "apps": 10.0,
        "starts": 8.0,
        "starter_ratio": 0.8,
        "captain_ratio": 0.1,
        "goals": 2.0,
        "assists": 1.0,
        "yellow_cards": 3.0,
        "red_cards": 0.0,
        "age": 25.0,
        "age_sq": 625.0,
        "height_in_cm": 180.0,
        "win_rate": 0.5,
        "clean_sheet_rate": 0.4,
        "goals_conceded_per_match": 1.2,
        "uefa_share": 0.22,
        "cup_share": 0.1,
        "league_position": 4.0,
        "foot": "right",
        "position": "Midfield",
        "sub_position": "Central Midfield",
        "country_group": "Brazil",
        "league_id": "GB1",
    }
    row.update(overrides)
    return row


def _full_train() -> pd.DataFrame:
    """Training rows covering every position, two feet, and missing height/position data."""
    return pd.DataFrame(
        [
            _full_row(
                position="Defender",
                sub_position="Centre-Back",
                height_in_cm=182.0,
                country_group="Spain",
                league_id="ES1",
                minutes=1800.0,
                goals=6.0,
            ),
            _full_row(
                position="Defender",
                sub_position="Left-Back",
                foot="left",
                height_in_cm=184.0,
                country_group="Spain",
                league_id="ES1",
                minutes=2000.0,
                apps=22.0,
                starts=20.0,
            ),
            _full_row(
                position="Midfield",
                height_in_cm=178.0,
                country_group="Brazil",
                league_id="BR1",
                league_position=3.0,
            ),
            _full_row(
                position="Attack",
                sub_position="Striker",
                height_in_cm=180.0,
                country_group="France",
                league_id="FR1",
                league_position=None,
            ),
            _full_row(
                position="Attack",
                sub_position="Second Striker",
                foot="left",
                height_in_cm=None,
                country_group="France",
                league_id="FR1",
                minutes=600.0,
            ),
        ]
    )


def _cluster_row(**overrides: object) -> dict[str, object]:
    """One row carrying every column `CLUSTER` declares."""
    row: dict[str, object] = {
        "minutes": 900.0,
        "starter_ratio": 0.8,
        "uefa_share": 0.2,
        "cup_share": 0.1,
        "position": "Midfield",
        "sub_position": "Central Midfield",
        "goals": 9.0,
        "assists": 3.0,
        "yellow_cards": 5.0,
        "red_cards": 0.0,
    }
    row.update(overrides)
    return row


def test_empirical_bayes_rates_match_hand_computed_values() -> None:
    frame = pd.DataFrame(
        {
            "position": ["Defender", "Defender", "Midfield"],
            "sub_position": ["Centre-Back", "Left-Back", "Central Midfield"],
            "minutes": [900.0, 1800.0, 900.0],
            "goals": [5.0, 7.0, 9.0],
        }
    )
    rates = EmpiricalBayesRates(count_columns=("goals",), m=5.0).fit(frame)
    # priors: Defender 12 goals / 30 n90 = 0.4, Midfield 9 / 10 = 0.9
    priors = rates.group_priors_["goals"]
    assert priors["Defender"] == pytest.approx(12.0 / 30.0)
    assert priors["Midfield"] == pytest.approx(9.0 / 10.0)
    out = rates.transform(frame)
    assert list(out.columns) == ["goals_per90"]
    expected = np.array(
        [
            (5.0 + 5.0 * 0.4) / (10.0 + 5.0),  # 7/15
            (7.0 + 5.0 * 0.4) / (20.0 + 5.0),  # 9/25
            (9.0 + 5.0 * 0.9) / (10.0 + 5.0),  # 14/15
        ]
    )
    np.testing.assert_allclose(out["goals_per90"].to_numpy(), expected)


def test_priors_are_grouped_by_position_only() -> None:
    frame = pd.DataFrame(
        {
            "position": ["Defender", "Defender", "Midfield"],
            "sub_position": ["Centre-Back", "Left-Back", "Central Midfield"],
            "minutes": [900.0, 1800.0, 900.0],
            "goals": [5.0, 7.0, 9.0],
        }
    )
    rates = EmpiricalBayesRates(count_columns=("goals",)).fit(frame)
    # one prior per position; sub_position never keys a prior, so the two Defender
    # rows that differ only in sub_position share the 0.4 prior (asserted above)
    assert list(rates.group_priors_["goals"].index) == ["Defender", "Midfield"]


def test_unseen_position_falls_back_to_pooled_prior() -> None:
    train = pd.DataFrame(
        {
            "position": ["Defender", "Midfield"],
            "sub_position": ["Centre-Back", "Central Midfield"],
            "minutes": [900.0, 1800.0],
            "goals": [5.0, 9.0],
        }
    )
    rates = EmpiricalBayesRates(count_columns=("goals",)).fit(train)
    row = pd.DataFrame(
        {"position": ["Attack"], "sub_position": ["Striker"], "minutes": [900.0], "goals": [4.0]}
    )
    out = rates.transform(row)
    pooled = 14.0 / 30.0
    np.testing.assert_allclose(out["goals_per90"].to_numpy(), [(4.0 + 5.0 * pooled) / (10.0 + 5.0)])


def test_empirical_bayes_rates_get_and_set_params() -> None:
    rates = EmpiricalBayesRates()
    assert rates.get_params() == {
        "count_columns": ("goals", "assists", "yellow_cards", "red_cards"),
        "m": 5.0,
        "group_column": "position",
        "minutes_column": "minutes",
    }
    rates.set_params(m=10.0, count_columns=("goals",))
    frame = pd.DataFrame(
        {
            "position": ["Defender"],
            "sub_position": ["Centre-Back"],
            "minutes": [900.0],
            "goals": [5.0],
        }
    )
    out = rates.fit(frame).transform(frame)
    # prior = 5 / 10 n90 = 0.5; (5 + 10 * 0.5) / (10 + 10) = 10 / 20
    np.testing.assert_allclose(out["goals_per90"].to_numpy(), [0.5])


def test_group_median_imputer_uses_training_median_per_position() -> None:
    train = pd.DataFrame(
        {
            "position": ["Defender", "Defender", "Defender", "Midfield", "Midfield", "Midfield"],
            "height_in_cm": [180.0, 182.0, np.nan, 175.0, 177.0, 179.0],
        }
    )
    imputer = GroupMedianImputer().fit(train)
    assert imputer.get_params() == {"group_column": "position"}
    assert imputer.group_medians_["height_in_cm"]["Defender"] == 181.0
    assert imputer.group_medians_["height_in_cm"]["Midfield"] == 177.0
    out = imputer.transform(
        pd.DataFrame({"position": ["Defender", "Midfield"], "height_in_cm": [np.nan, np.nan]})
    )
    assert out["height_in_cm"].tolist() == [181.0, 177.0]


def test_group_median_imputer_falls_back_to_global_median_for_unseen_position() -> None:
    train = pd.DataFrame(
        {
            "position": ["Defender", "Defender", "Defender", "Midfield", "Midfield", "Midfield"],
            "height_in_cm": [180.0, 182.0, np.nan, 175.0, 177.0, 179.0],
        }
    )
    imputer = GroupMedianImputer().fit(train)
    out = imputer.transform(pd.DataFrame({"position": ["Goalkeeper"], "height_in_cm": [np.nan]}))
    # pooled training median of 175, 177, 179, 180, 182
    assert out["height_in_cm"].tolist() == [179.0]


def test_build_preprocessor_exposes_the_three_branches() -> None:
    preprocessor = build_preprocessor(FULL)
    assert [name for name, _, _ in preprocessor.transformers] == [
        "empirical_bayes",
        "numeric",
        "categorical",
    ]


def _fit_parameters(preprocessor: object) -> dict[str, object]:
    """Every fitted parameter the leak guard compares, as plain Python data."""
    named = preprocessor.named_transformers_
    empirical_bayes = named["empirical_bayes"]
    numeric = named["numeric"]
    impute = numeric["impute"]
    grouped = impute.named_transformers_["grouped"]
    onehot = named["categorical"]["onehot"]
    return {
        "group_priors": {
            column: series.to_dict() for column, series in empirical_bayes.group_priors_.items()
        },
        "global_priors": dict(empirical_bayes.global_priors_),
        "group_medians": {
            column: series.to_dict() for column, series in grouped.group_medians_.items()
        },
        "global_medians": dict(grouped.global_medians_),
        "median_statistics": {
            name: step.statistics_.tolist()
            for name, step in impute.named_transformers_.items()
            if hasattr(step, "statistics_")
        },
        "scaler_mean": numeric["scale"].mean_.tolist(),
        "scaler_scale": numeric["scale"].scale_.tolist(),
        "onehot_categories": [list(categories) for categories in onehot.categories_],
    }


def test_leak_guard_changed_validation_rows_do_not_change_fitted_parameters() -> None:
    """The most important test: fit sees training rows only, whatever else changes."""
    train = _full_train()
    validation_a = pd.DataFrame(
        [
            _full_row(split="validation", position="Midfield", height_in_cm=176.0),
            _full_row(split="validation", position="Attack", foot="left", height_in_cm=181.0),
        ]
    )
    validation_b = pd.DataFrame(
        [
            _full_row(
                split="validation",
                position="Defender",
                sub_position="Sweeper",
                foot="left",
                height_in_cm=190.0,
                minutes=2400.0,
                goals=1.0,
                apps=30.0,
                league_position=11.0,
                country_group="Germany",
                league_id="DE1",
            ),
            _full_row(
                split="validation",
                position="Attack",
                sub_position="Striker",
                height_in_cm=170.0,
                minutes=100.0,
                goals=12.0,
                country_group="Portugal",
                league_id="PT1",
            ),
        ]
    )
    frame_a = pd.concat([train, validation_a], ignore_index=True)
    frame_b = pd.concat([train, validation_b], ignore_index=True)
    assert not frame_a.equals(frame_b), "the two source frames must differ"
    preprocessor_a = build_preprocessor(FULL).fit(frame_a[frame_a["split"] == "train"])
    preprocessor_b = build_preprocessor(FULL).fit(frame_b[frame_b["split"] == "train"])
    parameters_a = _fit_parameters(preprocessor_a)
    parameters_b = _fit_parameters(preprocessor_b)
    assert parameters_a["group_priors"], "the guard must compare non-empty priors"
    assert parameters_a == parameters_b


def test_numeric_branch_applies_log1p_before_scaling() -> None:
    train = _full_train()
    preprocessor = build_preprocessor(FULL).fit(train)
    names = list(preprocessor.get_feature_names_out())
    numeric_names = [name for name in names if name.startswith("numeric__")]
    scaler = preprocessor.named_transformers_["numeric"]["scale"]
    scaler_index = numeric_names.index("numeric__minutes")
    row = pd.DataFrame([_full_row(minutes=900.0)])
    transformed = _dense(preprocessor.transform(row))
    # minutes is declared in FULL.log1p, so the scaler must see log1p(minutes)
    expected = (np.log1p(900.0) - scaler.mean_[scaler_index]) / scaler.scale_[scaler_index]
    assert transformed[0, names.index("numeric__minutes")] == pytest.approx(expected)


def test_unknown_categories_encode_as_all_zeros() -> None:
    preprocessor = build_preprocessor(FULL).fit(_full_train())
    row = pd.DataFrame(
        [
            _full_row(
                split="validation",
                foot="both",
                position="Goalkeeper",
                sub_position="Sweeper",
                country_group="Atlantis",
                league_id="XX99",
                height_in_cm=None,
                league_position=None,
            )
        ]
    )
    transformed = _dense(preprocessor.transform(row))
    names = list(preprocessor.get_feature_names_out())
    categorical = [i for i, name in enumerate(names) if name.startswith("categorical__")]
    assert categorical, "FULL must have a categorical block"
    np.testing.assert_allclose(transformed[0, categorical], 0.0)
    numeric = [i for i, name in enumerate(names) if name.startswith("numeric__")]
    assert np.isfinite(transformed[0, numeric]).all(), "missing height/position still imputes"


def test_cluster_collapses_rare_levels_before_one_hot() -> None:
    train = pd.DataFrame(
        [
            _cluster_row(),
            _cluster_row(position="Defender", sub_position="Centre-Back", minutes=1800.0),
            _cluster_row(position="Attack", sub_position="Striker", minutes=450.0, goals=7.0),
            _cluster_row(sub_position="Left Midfield", minutes=1200.0, goals=2.0),
        ]
    )
    preprocessor = build_preprocessor(CLUSTER).fit(train)
    categories = list(preprocessor.named_transformers_["categorical"]["onehot"].categories_[0])
    assert "other" in categories
    assert "Left Midfield" not in categories
    names = list(preprocessor.get_feature_names_out())
    assert "empirical_bayes__goals_per90" in names
    assert "numeric__minutes" in names
    matrix = _dense(preprocessor.transform(train))
    assert matrix.shape == (len(train), len(names))
    assert np.isfinite(matrix).all()


def test_poly_reduced_preprocessor_has_no_rate_columns() -> None:
    frame = pd.DataFrame(
        [
            {
                "age": 25.0,
                "age_sq": 625.0,
                "minutes": 900.0,
                "goals": 2.0,
                "assists": 1.0,
                "starter_ratio": 0.8,
                "position": "Midfield",
            }
        ]
    )
    preprocessor = build_preprocessor(POLY_REDUCED).fit(frame)
    names = list(preprocessor.get_feature_names_out())
    assert names
    assert not any(name.startswith("empirical_bayes__") for name in names)
    assert _dense(preprocessor.transform(frame)).shape == (1, len(names))


def test_build_preprocessor_passes_manifest_parameters_into_the_eb_transformer() -> None:
    """`train` must be able to feed `_transform.json`'s values through to the transformer."""
    fitted = build_preprocessor(FULL, empirical_bayes_m=7.5, prior_grouping="sub_position").fit(
        _full_train()
    )
    rates = fitted.named_transformers_["empirical_bayes"]
    assert rates.m == 7.5
    assert rates.group_column == "sub_position"


def test_build_preprocessor_defaults_to_the_shared_eb_constants() -> None:
    default = build_preprocessor(FULL).fit(_full_train())
    rates = default.named_transformers_["empirical_bayes"]
    assert rates.m == DEFAULT_M
    assert rates.group_column == DEFAULT_GROUP_COLUMN


@pytest.mark.parametrize(
    "empirical_bayes_m",
    [0, -1, -0.5, float("nan"), float("inf"), float("-inf"), True, False, "5", None],
    ids=[
        "zero",
        "negative",
        "neg-fraction",
        "nan",
        "inf",
        "-inf",
        "true",
        "false",
        "string",
        "none",
    ],
)
def test_build_preprocessor_refuses_an_unusable_m(
    empirical_bayes_m: object,
) -> None:
    # A forged _transform.json must fail at the sink, not reach estimator construction.
    with pytest.raises(ValueError, match="empirical_bayes_m"):
        build_preprocessor(FULL, empirical_bayes_m=empirical_bayes_m)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "prior_grouping",
    ["market_value_in_eur", "player_id", "", "Position", "goals", None],
    ids=["target", "id", "empty", "wrong-case", "a-count", "none"],
)
def test_build_preprocessor_refuses_a_prior_grouping_outside_the_allowlist(
    prior_grouping: object,
) -> None:
    with pytest.raises(ValueError, match="prior_grouping"):
        build_preprocessor(FULL, prior_grouping=prior_grouping)  # type: ignore[arg-type]


def test_fitted_preprocessor_survives_a_joblib_round_trip(tmp_path: Path) -> None:
    train = _full_train()
    preprocessor = build_preprocessor(FULL).fit(train)
    before = _dense(preprocessor.transform(train))
    path = tmp_path / "preprocessor.joblib"
    joblib.dump(preprocessor, path)
    loaded = joblib.load(path)
    np.testing.assert_allclose(_dense(loaded.transform(train)), before)
