# Transform stage and feature design plan

## Contents

1. [Purpose](#1-purpose)
2. [Design principle: deterministic stage, fitted preprocessor](#2-design-principle-deterministic-stage-fitted-preprocessor)
3. [Modules and classes](#3-modules-and-classes)
4. [Pipeline addition](#4-pipeline-addition)
5. [Candidate features](#5-candidate-features)
6. [K-Means: choosing k](#6-k-means-choosing-k)
7. [Experiments](#7-experiments)
8. [Order of work](#8-order-of-work)
9. [See also](#9-see-also)

---

## 1. Purpose

This plan covers step 1 of the week 5 recovery plan in [docs/WORK_PLAN.md](WORK_PLAN.md) §6: implement the `transform` stage and run the experiments that close [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) §3.6 (feature engineering), §3.7 (target transform and polynomial scope), and §3.8 (K-Means specifics). It is a working plan, not a decision record. Each decision it leads to is recorded in its owning doc when it is made.

## 2. Design principle: deterministic stage, fitted preprocessor

The work is split into two layers so that no statistic learned from the data can leak across splits, and so that batch scoring and live scoring apply identical transforms (artifact contract, [docs/ARCHITECTURE.md](ARCHITECTURE.md) §4.3).

| Layer | What it does | Where it lives | Learns from data? |
| --- | --- | --- | --- |
| `transform` stage | Builds the Option A player-season rows and the transfer-event rows, computes trailing-window raw counts, and assigns the split | `ml/data/transform/*.parquet` | No. Deterministic, no cross-row statistics |
| scikit-learn preprocessor | Empirical Bayes positional priors, positional median height imputation, `foot = "unknown"`, one-hot encoding, scaling | Fitted in `train` on the training split, serialized in `artifacts/<model_run_id>/` | Yes, training split only |

## 3. Modules and classes

Planned layout, implemented in steps 2 to 5 of §8. None of these modules exists yet at the time of writing.

```
ml/src/delphos_ml/
  pipeline/
    _staging.py      # atomic staging-and-swap helpers, extracted from clean.py
    transform.py     # stage entry function: transform()
  features/
    windows.py       # TrailingWindowIndex
    snapshots.py     # season_of(), assign_split(), build_player_seasons(), build_transfer_events()
    feature_sets.py  # FeatureSet dataclass and the FULL, POLY_REDUCED, CLUSTER sets
    preprocess.py    # EmpiricalBayesRates, GroupMedianImputer, build_preprocessor()
```

- **`TrailingWindowIndex`** (`windows.py`): promotes `_build_window_index` and `_query_365d_window` from `analysis/eda.py` into the package. It keeps per-`(player_id, day)` prefix sums and answers window queries with `searchsorted`, in O(N log M) without per-player loops. One method, `query(pids, days, strict_before)`:
  - `strict_before=False`: window `(as_of_date - 365 days, as_of_date]`, half-open — the as-of day is included and a match exactly 365 days before it is not (valuation rows);
  - `strict_before=True`: window `[transfer_date - 365 days, transfer_date - 1 day]` (transfer rows).

  `analysis/eda.py` will import it instead of keeping its own copy (ADR-009).
- **`snapshots.py`**:
  - `season_of(date)`: season start year, `year` when `month >= 7`, otherwise `year - 1`.
  - `assign_split(season)`: `train` for 2017 to 2023, `validation` for 2024, `test` for 2025.
  - `build_player_seasons()`: latest valuation per `(player_id, season)` in the 14 covered leagues, seasons 2017 to 2025, outfield players only, `>= 180` trailing minutes (§3.2, §3.3).
  - `build_transfer_events()`: the paid-transfer dataset for §3.12 (`transfer_fee > 0`, about 5,325 rows in v679).
- **`FeatureSet`** (`feature_sets.py`): frozen dataclass with `numeric`, `categorical`, `log1p`, and `poly` column lists. Each model declares the set it consumes, and the artifact manifest (§3.11) records the ordered feature names from it.
  - `FULL`: linear regression, Random Forest, Decision Tree.
  - `POLY_REDUCED`: about six features for the polynomial model.
  - `CLUSTER`: playing-style features for K-Means.
- **`EmpiricalBayesRates(BaseEstimator, TransformerMixin)`** (`preprocess.py`):
  - `fit`: prior grouped by `position` (the three outfield groups `Defender`, `Midfield`, `Attack`), `prior_pos = sum(count) / sum(minutes / 90)` on the training split. Grouping by `sub_position` was rejected: three of its twelve groups hold fewer than `5,500` n90 of exposure (`Left Midfield` `4,101`, `Right Midfield` `5,429`, `Second Striker` `4,841`), so their priors come from a handful of events, and the labels drift between seasons. `sub_position` still enters the model sets as a categorical feature, where the training split estimates the offsets instead of a hand-set prior.
  - `transform`: `(count + m * prior_pos) / (minutes / 90 + m)` with `m = 5` (provisional until E2).
- **`GroupMedianImputer`** (`preprocess.py`): imputes `height_in_cm` with the training-split median of the player's position. `SimpleImputer` cannot group.
- **`build_preprocessor(feature_set)`** (`preprocess.py`): returns a `ColumnTransformer` with three branches:
  - Empirical Bayes rates;
  - numeric: impute, `log1p` on skewed volumes, then `StandardScaler`;
  - categorical: `OneHotEncoder(handle_unknown="ignore")`.

**New dependency:** `scikit-learn` 1.9.1 and `joblib` 1.6.0 are runtime dependencies of `ml/` as of 2026-10-31, together with `numpy` 2.5.4, `scipy` 1.18.1, `cloudpickle` 3.1.2 and `threadpoolctl` 3.7.0, which the serialized artifacts depend on. All six are in the alignment list in [docs/ARCHITECTURE.md](ARCHITECTURE.md) §4.3 (ADR-013), because `delphos_ml.load_model()` refuses to load an artifact whose recorded versions differ from the installed ones.

## 4. Pipeline addition

`uv run delphos-pipeline transform` reads `ml/data/clean/` and writes `ml/data/transform/` atomically, using the same staging-and-swap pattern as `clean`:

| File | Contents |
| --- | --- |
| `player_seasons.parquet` | IDs, `season`, `as_of_date`, `split`, point-in-time club and league, raw candidate features, target `log10_market_value` |
| `transfer_events.parquet` | The same feature schema plus `transfer_date`, `transfer_fee`, and the pre-transfer valuation |
| `_transform.json` | Input `_clean.json` hash, rows per split, window and minutes-floor parameters, the Empirical Bayes prior grouping and `m`, column list and dtypes |

`all` becomes `ingest`, `clean`, `transform`.

The transform manifest (`_transform.json`) carries every parameter that `train` would otherwise hard-code, so the fitted preprocessor and the stage that produced the rows cannot drift apart: `window_days` (`365`), `minutes_floor` (`180`), `empirical_bayes_m` (`5`), `prior_grouping` (`position`), `season_month_start` (`7`), and the per-split row counts. The fitted prior values themselves belong to the preprocessor artifact written by `train` ([docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) §3.11), not to this transform manifest.

**Acceptance.** The stage is accepted when its output row counts equal the population fixed in [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) §3.2 and §3.3, measured over `ml/data/clean/`: `107,395` outfield player-season snapshots before the minutes floor, `47,350` after it, `14,688` distinct players, and `5,325` paid transfer rows. Per-season and per-split counts go into `_transform.json`. A run whose counts disagree is a defect, not a variant. The exploratory analysis over `ml/data/ingest/` reports `107,456` / `47,359` / `14,692`, which is the same funnel measured before `clean` drops the `4` outfield players with null `date_of_birth` (§3.5).

**Tests**, with small synthetic fixtures, focused on the boundaries:

- a match on day 365 before `as_of_date` is included, one on day 366 is not;
- on a transfer row, a match on `transfer_date` itself is excluded;
- June 30 and July 1 fall in different seasons;
- a player-season with 179 trailing minutes is excluded, one with 180 is kept;
- no row aggregates a match dated after its `as_of_date`;
- goalkeepers and clubs outside the 14 covered leagues never appear.

## 5. Candidate features

`transform` writes every candidate below. The experiments in §7 decide which ones each `FeatureSet` keeps.

- **Volume:** `minutes`, `apps`, `starts` (from `game_lineups.type`), `starter_ratio`, `captain_ratio`.
- **Production counts:** `goals`, `assists`, `yellow_cards`, `red_cards`. Per-90 rates are computed by the preprocessor, not stored.
- **Team context** (from `club_games` and `games`): win rate, goal difference per match, league position at `as_of_date` plus a missing flag.
- **Competition mix:** share of minutes in UEFA competitions and in domestic cups.
- **Biographical:** `age` at `as_of_date` (and `age²` for the linear model), `height_in_cm`, `foot`, `position`, `sub_position`, `country_of_citizenship` grouped into top-N countries plus `other`.

In `CLUSTER`, `sub_position` is collapsed before encoding: the levels below `1%` of the training rows become `other` (the `Left Midfield`, `Right Midfield` and `Second Striker` groups are the ones this affects). One-hotting twelve groups into a K-Means feature space gives near-empty categories a distance weight no cluster can interpret.
- **League:** point-in-time `player_club_domestic_competition_id` (14 categories).

**Excluded:** the player's market value from a previous season. It is not a candidate feature (see [docs/REPORT_NOTES.md](REPORT_NOTES.md) H-09).

## 6. K-Means: choosing k

**Features (`CLUSTER`):** playing style and output only: Empirical Bayes per-90 rates, `starter_ratio`, minutes, card rates, competition mix, and `sub_position`. Market value and league stay out, so clusters group players that are similar on the pitch, and price comparisons happen within a cluster afterwards.

**Procedure:** fitted on the training split only, `k-means++`, `n_init=20`, fixed `random_state`.

1. Sweep `k = 2` to `15`.
2. Compute four internal metrics for each `k`:
   - inertia, with the elbow located by the kneedle method; the elbow is a constraint on the decision rule, not a reported side metric;
   - silhouette, on a sample of about 10,000 rows (the full computation is O(n²));
   - Calinski-Harabasz (higher is better);
   - Davies-Bouldin (lower is better).
3. Measure two kinds of stability:
   - temporal (primary): assign the 2024 validation rows with the training centroids and compare against a K-Means fitted directly on 2024, ARI over the same rows. The threshold is ARI >= 0.5.
   - bootstrap (secondary): 20 resamples of the training rows, refit on each resample, and compare assignments on the rows the two resamples share (adjusted Rand index on the intersection, as in Hubert and Arabie). Comparing the assignments of two different row sets is not well defined. The target is mean ARI >= 0.8.
4. Check interpretability: no cluster below about 3% of rows, and centroid profiles that can be named.
5. **Decision rule:** the candidates are the values of `k` in `3` to `15` whose silhouette is within 5% of the maximum, that have a silhouette of at least `0.25` in absolute terms, that have no cluster below about 3% of rows, and that pass both stability checks. From the candidates, take the elbow candidate if it is among them; otherwise take the largest `k` in the candidate set. The smallest candidate is not taken: silhouette peaks at small `k` by construction, so "smallest within 5% of the maximum" resolves to `k = 2` and yields archetypes that carry no information for the archetype explorer.

The chosen `k` will be written into §3.8 as a constant once E6 runs, and `train` will not re-select it on each run, to keep runs reproducible.

## 7. Experiments

Experiments are analysis scripts in `analysis/` (ADR-009, ADR-014). They read `ml/data/transform/` and write to `analysis/output/<script>/`. All of them use expanding-window season folds inside `train + validation` (train 2017 to 2019 and validate on 2020, and so on up to train 2017 to 2023 and validate on 2024). The 2025 test split is never touched.

Every fold fits its own preprocessor: the Empirical Bayes priors, the height imputers and the scalers are fitted on that fold's training seasons only, never on the whole training split, and the fold's validation season is scored through that fold's fitted transformer. Re-using one full-split preprocessor across folds would leak the validation season into the fitted statistics and invalidate every metric in this table.

`MdAPE` in EUR is computed after back-transforming with `10 ** log10_prediction`, floored at `0`; the number of rows the floor affects is reported alongside it.

| # | Experiment | Script | Decides | Metrics |
| --- | --- | --- | --- | --- |
| E1 | Feature-group ablation on the linear model: biographical, then + volume, then + per-90 raw vs Empirical Bayes, then + team context, then + league | `analysis/feature_ablation.py` | §3.6: which feature groups enter `FULL` | RMSE and MAE on `log10`, MdAPE in EUR, R² |
| E2 | Empirical Bayes strength `m` in {0, 2, 5, 10, 20} on the market-value regression | `analysis/feature_ablation.py` | §3.6: confirm `m = 5` for valuation (the EDA validated it for next-season output, not for value) | RMSE on `log10` |
| E3 | Multicollinearity (VIF) on the linear feature set | `analysis/feature_ablation.py` | §3.6: drop or combine redundant features so OLS coefficients stay interpretable | VIF < 10 |
| E4 | Polynomial degree in {1, 2, 3}, plus interaction-only, on `POLY_REDUCED` | `analysis/poly_degree.py` | §3.7: the degree, and whether polynomial beats linear | Cross-validated RMSE with the one-standard-error rule |
| E5 | Residual diagnostics, `log10` vs raw target: heteroscedasticity and residuals by value quantile | `analysis/poly_degree.py` | §3.7: evidence for the report on the already decided `log10` target | Residual plots, Breusch-Pagan test |
| E6 | `k` sweep with stability checks (§6) | `analysis/kmeans_selection.py` | §3.8: `k` | Inertia, silhouette, Calinski-Harabasz, Davies-Bouldin, ARI |
| E7 | `StandardScaler` vs `RobustScaler` for the cluster feature space | `analysis/kmeans_selection.py` | §3.8: the cluster scaler | Silhouette and ARI at the `k` from E6 |

The one-K-Means-per-position variant of E7 is out of scope for week 5 and is recorded as future work: it multiplies the models, breaks comparison across clusters, and contradicts the rationale in §6, where clusters are supposed to group players that are similar on the pitch.

**Order and scope.** The week-5 order is E1, E2, E4, E6: they decide the feature groups, the prior strength, the polynomial degree and `k`, which the `train` stage consumes. E3 (VIF), E5 (residual diagnostics) and E7 run later, as week-6 side work: VIF is a diagnostic over the chosen `FULL` set that can run alongside training, the residual diagnostics are report material rather than a decision blocker, and E7 is reduced to the scaler comparison. E3's outcome may still prune `FULL` before `train` freezes it.

Each result is recorded as a decision in [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) §3.6 to §3.8 and as a finding in [docs/REPORT_NOTES.md](REPORT_NOTES.md).

## 8. Order of work

Each step has a gate: the next step starts only when the gate passes.

| # | Step | Gate |
| --- | --- | --- |
| 0 | Toolchain: put `uv` on `PATH` and run `uv sync` in `ml/` | done: `uv` 0.12.0 on `PATH`, `uv run pytest` runs the suite (the two failures it reports predate this branch) |
| 1 | Add `scikit-learn` and `joblib` to `ml/pyproject.toml`, align their versions in [docs/ARCHITECTURE.md](ARCHITECTURE.md) §4.3 (§3) | done on 2026-10-31: `scikit-learn` 1.9.1, `joblib` 1.6.0, `numpy` 2.5.4, `scipy` 1.18.1, `cloudpickle` 3.1.2 and `threadpoolctl` 3.7.0 declared and aligned, lockfile updated, §4.3 alignment list and manifest fields extended |
| 2 | Implement `features/windows.py`; point `analysis/eda.py` at it and drop its private copy (§3) | `eda.py` re-runs and reproduces the recorded figures: `107,456`, `47,359`, `14,692`, `5,325`, the `42.4%` RMSE reduction from `m = 5` (`0.3143` to `0.1809`) over `2,378` transitions, the `97.82%` season agreement, and the `30.91` / `30.90` appearances per game |
| 3 | Extract `pipeline/_staging.py` from `clean.py`, parameterizing the staging prefix by stage name (§3) | `ml/tests/test_clean.py` unchanged and green |
| 4 | Implement `features/snapshots.py`, `pipeline/transform.py`, the CLI wiring and the tests from §4 | the six boundary tests green; the manifest matches the §4 spec |
| 5 | Implement `features/preprocess.py` and `features/feature_sets.py` with provisional sets (§3) | unit tests for the Empirical Bayes formula, the grouped imputer, and fold-scoped fitting |
| 6 | Run `ingest` to `clean` to `transform` on version `679` | row counts equal `47,350`, `14,688` and `5,325`; per-split counts as expected |
| 7 | Run E1, E2, E4 and E6 (§7) | decisions recorded in [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) §3.6 to §3.8, findings in [docs/REPORT_NOTES.md](REPORT_NOTES.md), progress in [docs/WORK_PLAN.md](WORK_PLAN.md) |
| 8 | Run E3, E5 and E7 as week-6 side work | E3's VIF outcome applied to `FULL` before `train` freezes it |

Step 2 moves code that produced every number quoted in the project documentation, so the gate is a diff of re-run outputs against the recorded figures, not a green test run.

## 9. See also

- [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md): §3.2 to §3.5 (decided inputs to this plan) and §3.6 to §3.8 (decided by it).
- [docs/ARCHITECTURE.md](ARCHITECTURE.md): the artifact contract (§4.3), ADR-009, ADR-013, ADR-014.
- [docs/WORK_PLAN.md](WORK_PLAN.md): the recovery plan this implements.
- [docs/REPORT_NOTES.md](REPORT_NOTES.md): findings and methodological decisions for the final report.
