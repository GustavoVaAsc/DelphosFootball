"""The three provisional feature-set declarations, one per model family.

Input: the column names of the `transform` stage's row schema.
Output: the `FULL`, `POLY_REDUCED` and `CLUSTER` constants, re-exported by
`delphos_ml.features.feature_sets`.
Responsibility: declare what each model family consumes. Experiments E1, E2, E4 and E6
(docs/TRANSFORM_PLAN.md section 7) finalise the sets; until then every tuple here is
provisional and a change belongs in the experiment's decision record.

These are kept together rather than one module per set because each set is a single
constructor call: splitting them would add two import-only modules without shortening
anything.
"""

from __future__ import annotations

from delphos_ml.features.feature_sets.feature_set import FeatureSet

#: Linear regression, Random Forest and Decision Tree: the full candidate panel.
#: Raw production counts carry season volume, the shrunk per-90 rates carry efficiency
#: (E1 decides whether the rate columns earn their place alongside the raw counts).
FULL = FeatureSet(
    name="full",
    numeric=(
        "minutes",
        "apps",
        "starts",
        "starter_ratio",
        "captain_ratio",
        "goals",
        "assists",
        "yellow_cards",
        "red_cards",
        "age",
        "age_sq",
        "height_in_cm",
        "win_rate",
        "clean_sheet_rate",
        "goals_conceded_per_match",
        "uefa_share",
        "cup_share",
        "league_position",
    ),
    categorical=("foot", "position", "sub_position", "country_group", "league_id"),
    log1p=("minutes", "apps", "goals", "assists"),
    rates=("goals", "assists"),
)

#: Polynomial regression on about six features. `age`/`age_sq` span the age curve with
#: an explicit square, `minutes` is exposure, `goals`+`assists` are production and
#: `starter_ratio` is squad importance; `position` is the one role conditioner. `poly`
#: lists the columns E2 expands with degree-2 interaction terms (interaction-only, so
#: the expansion does not regenerate the `age_sq` column that `numeric` already carries).
POLY_REDUCED = FeatureSet(
    name="poly_reduced",
    numeric=("age", "age_sq", "minutes", "goals", "assists", "starter_ratio"),
    categorical=("position",),
    poly=("age", "minutes", "goals", "assists", "starter_ratio"),
)

#: K-Means: playing style and output only - no market value and no league, so clusters
#: group players by what they do on the pitch. The count columns enter only through the
#: Empirical-Bayes per-90 rates (raw counts would double the volume signal the rates
#: already shrink); `minutes`, `starter_ratio` and the competition shares are the style
#: context; the sub-position levels below 1% of the training rows collapse to `other`
#: before encoding so K-Means never weights a near-empty category (E4/E6 finalise).
CLUSTER = FeatureSet(
    name="cluster",
    numeric=("minutes", "starter_ratio", "uefa_share", "cup_share"),
    categorical=("sub_position",),
    rates=("goals", "assists", "yellow_cards", "red_cards"),
    collapse=(("sub_position", ("Left Midfield", "Right Midfield", "Second Striker")),),
)
