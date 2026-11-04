"""Unit tests for the fitted preprocessor: shrunk rates, grouped imputation, centring, leak guard.

The leak guard is the central assertion of docs/TRANSFORM_PLAN.md section 2: changing
only the validation rows and refitting on the training rows must leave every fitted
parameter (priors, medians, scaler moments, one-hot vocabularies) identical, because
nothing learned from data may cross the split. Fixtures are small synthetic frames
shaped like the `transform` stage's row schema.

This module is well past the ~130-line ceiling and is deliberately not split: the tests
read as one argument about a single object, and cutting them into per-estimator files
would scatter the leak guard away from the transformers it constrains.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

from delphos_ml.features.feature_sets import CLUSTER, FULL, POLY_REDUCED
from delphos_ml.features.preprocess import (
    CenteredPolynomial,
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


def test_centered_polynomial_matches_hand_computed_values() -> None:
    frame = pd.DataFrame({"age": [20.0, 30.0, 40.0], "age_sq": [400.0, 900.0, 1600.0]})
    transformer = CenteredPolynomial().fit(frame)
    assert transformer.center_ == pytest.approx(30.0)
    transformed = transformer.transform(frame)
    assert list(transformed.columns) == ["age", "age_sq"]
    expected = np.array([[-10.0, 0.0, 10.0], [100.0, 0.0, 100.0]]).T
    np.testing.assert_allclose(transformed.to_numpy(), expected)
    # The same two columns as a plain ndarray: no names, so the pair in order.
    unnamed = transformer.transform(frame.to_numpy())
    np.testing.assert_allclose(np.asarray(unnamed), expected)


def test_centered_polynomial_transform_before_fit_raises() -> None:
    frame = pd.DataFrame({"age": [25.0], "age_sq": [625.0]})
    with pytest.raises(ValueError, match="not fitted"):
        CenteredPolynomial().transform(frame)


def test_centered_polynomial_feature_names_out_is_the_pair() -> None:
    frame = pd.DataFrame({"age": [25.0, 30.0], "age_sq": [625.0, 900.0]})
    transformer = CenteredPolynomial().fit(frame)
    names = transformer.get_feature_names_out()
    assert len(names) == 2
    assert list(names) == ["age", "age_sq"]


def test_centered_polynomial_survives_a_joblib_round_trip(tmp_path: Path) -> None:
    frame = pd.DataFrame({"age": [25.0, 30.0, 35.0], "age_sq": [625.0, 900.0, 1225.0]})
    transformer = CenteredPolynomial().fit(frame)
    before = transformer.transform(frame)
    path = tmp_path / "centered_polynomial.joblib"
    joblib.dump(transformer, path)
    loaded = joblib.load(path)
    assert loaded.center_ == transformer.center_
    np.testing.assert_allclose(loaded.transform(frame).to_numpy(), before.to_numpy())


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
        "center": numeric["center"].center_,
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


def test_leak_guard_validation_rows_do_not_change_the_centring_mean() -> None:
    """`center_` is a training statistic: only the rows `fit` receives may set it.

    The equality below is the weak half of the check — both arms fit the same training
    subset, so it holds for any implementation. The anchor that carries the weight is
    `center_ == 25.0`, and the last assertion shows the statistic does move when the
    training rows it receives actually differ.
    """
    train = _full_train()
    validation_a = pd.DataFrame([_full_row(split="validation", age=40.0, age_sq=1600.0)])
    validation_b = pd.DataFrame([_full_row(split="validation", age=18.0, age_sq=324.0)])
    frame_a = pd.concat([train, validation_a], ignore_index=True)
    frame_b = pd.concat([train, validation_b], ignore_index=True)
    assert not frame_a.equals(frame_b), "the two source frames must differ"
    fit_a = build_preprocessor(FULL).fit(frame_a[frame_a["split"] == "train"])
    fit_b = build_preprocessor(FULL).fit(frame_b[frame_b["split"] == "train"])
    center_a = fit_a.named_transformers_["numeric"]["center"].center_
    center_b = fit_b.named_transformers_["numeric"]["center"].center_
    assert center_a == center_b
    # The training rows are all 25 here; a leaked validation row would move the mean.
    assert center_a == pytest.approx(25.0)
    # And the statistic is genuinely fitted: different training rows give a different one.
    moved = build_preprocessor(FULL).fit(
        pd.concat([train, validation_a], ignore_index=True).assign(
            age=lambda d: d["age"].where(d["split"] != "train", 35.0),
            age_sq=lambda d: d["age_sq"].where(d["split"] != "train", 1225.0),
        )
    )
    assert moved.named_transformers_["numeric"]["center"].center_ != pytest.approx(25.0)


def test_build_preprocessor_full_replaces_the_age_pair_at_the_expected_width() -> None:
    """The centred pair must substitute the raw columns: same names, same count, no extras."""
    train = _full_train()
    preprocessor = build_preprocessor(FULL).fit(train)
    names = list(preprocessor.get_feature_names_out())
    numeric_names = [name for name in names if name.startswith("numeric__")]
    assert numeric_names == [f"numeric__{column}" for column in FULL.numeric]
    onehot = preprocessor.named_transformers_["categorical"]["onehot"]
    expected_width = (
        len(FULL.rates) + len(FULL.numeric) + sum(len(levels) for levels in onehot.categories_)
    )
    matrix = _dense(preprocessor.transform(train))
    assert matrix.shape == (len(train), expected_width)
    center = preprocessor.named_transformers_["numeric"]["center"]
    assert isinstance(center, CenteredPolynomial)
    assert center.center_ == pytest.approx(float(train["age"].mean()))


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


def test_build_preprocessor_honours_the_scaler_parameter() -> None:
    """E7's scaler switch must reach the numeric branch; the default must not move."""
    train = _full_train()
    default = build_preprocessor(FULL).fit(train)
    assert isinstance(default.named_transformers_["numeric"]["scale"], StandardScaler)

    robust = build_preprocessor(FULL, scaler=RobustScaler()).fit(train)
    robust_scaler = robust.named_transformers_["numeric"]["scale"]
    assert isinstance(robust_scaler, RobustScaler)
    # minutes is the first numeric column, so it indexes the scaler's fitted parameters.
    # Its training median is log1p(900) while its mean is not, so the centring constant
    # pins which estimator was fitted; the default row scales to a non-zero value.
    default_names = list(default.get_feature_names_out())
    robust_names = list(robust.get_feature_names_out())
    robust_numeric = [name for name in robust_names if name.startswith("numeric__")]
    assert robust_scaler.center_[robust_numeric.index("numeric__minutes")] == pytest.approx(
        np.log1p(900.0)
    )
    row = pd.DataFrame([_full_row()])
    robust_value = _dense(robust.transform(row))[0, robust_names.index("numeric__minutes")]
    default_value = _dense(default.transform(row))[0, default_names.index("numeric__minutes")]
    assert robust_value == pytest.approx(0.0)
    assert default_value != pytest.approx(0.0)

    # Passing the default explicitly must reproduce the default output exactly.
    explicit = build_preprocessor(FULL, scaler=StandardScaler()).fit(train)
    np.testing.assert_allclose(_dense(default.transform(train)), _dense(explicit.transform(train)))


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


def test_build_preprocessor_refuses_a_scaler_outside_the_allowlist() -> None:
    # A forged manifest must not be able to substitute an arbitrary estimator class.
    with pytest.raises(ValueError, match="scaler must be one of"):
        build_preprocessor(FULL, scaler=object())
    with pytest.raises(ValueError, match="scaler must be one of"):
        build_preprocessor(FULL, scaler=MinMaxScaler())


def test_centered_polynomial_refuses_a_non_finite_center() -> None:
    # An empty or all-null age column must fail at fit time, not ship NaN predictions.
    empty = pd.DataFrame({"age": [], "age_sq": []})
    with pytest.raises(ValueError, match="center_ must be finite"):
        CenteredPolynomial().fit(empty)
    all_null = pd.DataFrame({"age": [float("nan"), float("nan")], "age_sq": [float("nan")] * 2})
    with pytest.raises(ValueError, match="center_ must be finite"):
        CenteredPolynomial().fit(all_null)


def test_centered_polynomial_transform_uses_the_stored_center_not_the_batch_mean() -> None:
    # The live-scoring failure mode is re-centring on whatever batch arrives at transform
    # time. Fit on one spread of ages, transform a far-away row, and pin the stored centre.
    fitted = CenteredPolynomial().fit(
        pd.DataFrame({"age": [20.0, 30.0, 40.0], "age_sq": [400.0, 900.0, 1600.0]})
    )
    assert fitted.center_ == pytest.approx(30.0)

    out = fitted.transform(pd.DataFrame({"age": [100.0], "age_sq": [10000.0]}))
    assert float(np.asarray(out)[0][0]) == pytest.approx(70.0)
    assert float(np.asarray(out)[0][1]) == pytest.approx(4900.0)


def _numeric_step_names(preprocessor: object) -> list[str]:
    """Step names of the numeric branch, read off the unfitted spec."""
    numeric = next(est for name, est, _cols in preprocessor.transformers if name == "numeric")
    return [name for name, _step in numeric.steps]


def test_build_preprocessor_can_skip_the_age_centring_for_before_after_comparisons() -> None:
    # A before/after comparison must be able to ask for the un-centred basis; with the step
    # always on, the "raw" arm would be centred twice and report a vacuous identity.
    assert "center" not in _numeric_step_names(build_preprocessor(FULL, center_age=False))
    assert "center" in _numeric_step_names(build_preprocessor(FULL, center_age=True))


def test_build_preprocessor_expands_poly_columns_and_round_trips_through_joblib(
    tmp_path: Path,
) -> None:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import PolynomialFeatures

    train = _full_train().assign(target=[5.8, 6.1, 6.4, 6.9, 6.2])
    poly_prep = build_preprocessor(POLY_REDUCED, poly_degree=2)
    x_poly = _dense(poly_prep.fit_transform(train))
    # 5 poly columns expanded at degree 2 without bias -> 5 linear + 15 quadratic/interaction = 20,
    # plus passthrough `age_sq` (1) and 3 `position` one-hot columns = 24 columns total.
    assert x_poly.shape == (len(train), 24)
    assert len(poly_prep.get_feature_names_out()) == 24

    # Reference OLS matching `analysis/poly_degree.py` E4 `degree2_full`.
    base_prep = build_preprocessor(POLY_REDUCED)
    x_base = _dense(base_prep.fit_transform(train))
    names = list(base_prep.get_feature_names_out())
    poly_idx = [names.index(f"numeric__{col}") for col in POLY_REDUCED.poly]
    keep_idx = [i for i in range(x_base.shape[1]) if i not in poly_idx]
    exp = PolynomialFeatures(degree=2, interaction_only=False, include_bias=False)
    x_ref = np.hstack([x_base[:, keep_idx], exp.fit_transform(x_base[:, poly_idx])])

    ols_poly = LinearRegression().fit(x_poly, train["target"])
    ols_ref = LinearRegression().fit(x_ref, train["target"])
    np.testing.assert_allclose(ols_poly.predict(x_poly), ols_ref.predict(x_ref), atol=1e-12)

    artifact_path = tmp_path / "poly_prep.joblib"
    joblib.dump(poly_prep, artifact_path)
    reloaded = joblib.load(artifact_path)
    np.testing.assert_allclose(_dense(reloaded.transform(train)), x_poly)


def test_build_preprocessor_refuses_invalid_poly_degree() -> None:
    with pytest.raises(ValueError, match="poly_degree"):
        build_preprocessor(POLY_REDUCED, poly_degree=0)
    with pytest.raises(ValueError, match="poly_degree"):
        build_preprocessor(POLY_REDUCED, poly_degree=True)
    with pytest.raises(ValueError, match="declares no poly columns"):
        build_preprocessor(FULL, poly_degree=2)
