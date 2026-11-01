"""The three provisional feature-set declarations, one per model family.

Input: the column names of the `transform` stage's row schema.
Output: the `FULL`, `POLY_REDUCED` and `CLUSTER` constants, re-exported by
`delphos_ml.features.feature_sets`.
Responsibility: declare what each model family consumes. E1, E2 and E1b/E2b finalised
`FULL`; `POLY_REDUCED` and `CLUSTER` stay provisional until E4 and E6
(docs/TRANSFORM_PLAN.md section 7) close them, and a change belongs in the experiment's
decision record.

These are kept together rather than one module per set because each set is a single
constructor call: splitting them would add two import-only modules without shortening
anything.
"""

from __future__ import annotations

from delphos_ml.features.feature_sets.feature_set import FeatureSet

#: Linear regression, Random Forest and Decision Tree. Finalised by E1 and E2
#: (docs/TRANSFORM_PLAN.md section 7): every group in the ladder earned its place except
#: `league_id`, which is excluded deliberately. It was the single largest gain in the
#: ladder (R^2 0.578 -> 0.810), but it is a pricing variable rather than a performance
#: one, so including it would make the undervaluation residual measure "price versus the
#: league's typical price" instead of "price versus performance" - the reasoning that
#: already excludes prior market value (REPORT_NOTES.md H-09) and league from CLUSTER.
#: Raw production counts are excluded too: E1b measured them alongside the rates at a
#: 0.05% RMSE gain, which does not pay for four more columns. The four counts enter only
#: through the Empirical-Bayes per-90 rates.
FULL = FeatureSet(
    name="full",
    numeric=(
        "minutes",
        "apps",
        "starts",
        "starter_ratio",
        "captain_ratio",
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
    categorical=("foot", "position", "sub_position", "country_group"),
    log1p=("minutes", "apps"),
    rates=("goals", "assists", "yellow_cards", "red_cards"),
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
