# DelphosFootball ML Architecture

## Table of contents

1. [Purpose](#1-purpose)
2. [Status](#2-status)
3. [Definition checklist](#3-definition-checklist)
4. [See also](#4-see-also)

---

## 1. Purpose

This document owns ML algorithm design and all ML substance deferred from [docs/ARCHITECTURE.md](ARCHITECTURE.md): the KDD pipeline's internal design — feature engineering, model selection, evaluation, statistical methodology — plus the LLM model/limits/parameters. ARCHITECTURE.md states general responsibilities and software contracts; where a contract references ML substance (thresholds, metrics, parameters, test selection, schema details of ML outputs), it is defined here.

## 2. Status

In progress. The [Definition checklist](#3-definition-checklist) below is the agenda: each item must be decided and written here before this document is considered complete. As of 2026-10-29, 5 of 18 items are decided (3.1 to 3.5). The checklist is ordered by pipeline stage, and each item names the week it is needed by, except the items gated on delivery priorities 3 and 4 (schedule in [docs/WORK_PLAN.md](WORK_PLAN.md)). Until the remaining items are decided, ARCHITECTURE.md's black-box treatment of the pipeline stands, and the acceptance obligations it states (notably the statistical inefficiency demonstration) are not deferred.

## 3. Definition checklist

Each item names what must be decided, why it matters, and the week and stage that need it.

### 3.1 Dataset snapshot

- **Decide:** which Kaggle dataset version is pinned through the Kaggle API, how the snapshot hash is computed and recorded, and the refresh policy (bumping the pinned version).
- **Decision (2026-10-17):** the pinned dataset is `davidcariboo/player-scores` at version 679. On 2026-10-17, Kaggle's dataset metadata reported `currentVersionNumber = 679` (last updated 2026-09-05). The dataset description says updates are paused and the data is current to 2026-07-06: no games after 2026-07-06, no appearances after 2026-06-28, no player valuations after 2026-06-12, and no 2026/27 squads. Ingest records the snapshot in `ml/data/ingest/_snapshot.json` with the fields `dataset`, `version`, `handle`, `ingested_at` (the UTC start time of the run in ISO 8601 with `Z`; the files may come from kagglehub's cache), `snapshot_sha256`, `tool_versions` (`kagglehub`, `pyarrow`), and `tables`, keyed by table name, each with `source_file`, `parquet_file`, `sha256`, `rows`, `columns`, and `column_names` (in source order). `snapshot_sha256` is built as follows: for each source CSV, one line made of the lowercase hex SHA-256 of the file bytes, two spaces, the file name relative to the dataset root (`/` separators), and `\n`; sort the lines by file name in Unicode code-point order, join them, encode as UTF-8, and take the SHA-256. The hash depends only on file names and contents. For version 679 it is `94f42930f5d50d76f5226f64bd2b9e4c70552e110ad28743b5edce4041c8b1c1`. To refresh, change `DEFAULT_KAGGLE_DATASET_VERSION` in `ml/src/delphos_ml/config.py` or set `DELPHOS_KAGGLE_DATASET_VERSION`, as a deliberate commit. A full ingest of version 679 peaks at 703 MiB of memory, so at least 1 GiB of free RAM is recommended. It uses about 873 MiB of disk for the kagglehub cache (`~/.cache/kagglehub`) and about 228 MiB for `ml/data/ingest/`. A cached run takes about 10 s and the first download about 33 s.
- **Why it matters:** the dataset version and snapshot hash go into every manifest, and reproducibility of published results depends on it.
- **Needed by:** week 3 (ingest).

### 3.2 Data scope and attribute selection

- **Decide:** which dataset tables and columns enter the pipeline, and the population filters (competitions, seasons, minimum minutes played, how goalkeepers are handled).
- **Inputs known so far:** version 679 has 12 tables (rows / columns): appearances 1,894,350 / 13; club_games 177,916 / 11; clubs 796 / 17; competitions 65 / 11; countries 124 / 8; game_events 1,274,469 / 11; game_lineups 3,179,016 / 10; games 88,958 / 23; national_teams 124 / 17; player_valuations 656,301 / 6; players 50,149 / 26; transfers 175,165 / 10. That is 7,497,433 rows, about 220 MiB of Parquet from 873 MiB of source CSV.
- **Decision (2026-10-28):**
  1. **Included and excluded tables:** 9 of the 12 tables enter `clean`: `appearances`, `club_games`, `clubs`, `competitions`, `game_lineups`, `games`, `player_valuations`, `players`, and `transfers`. Three tables are excluded: `countries` and `national_teams` (the country and confederation fields needed downstream already live on `competitions` and `players`, and `national_teams` is a static 2026 snapshot with 100% null `coach_name`), and `game_events` (of its 1,274,469 rows, 49.54% are `Substitutions` with 93,157 empty descriptions, 29.95% are `Cards` already counted in `appearances`, and 1.07% are `Shootout` tiebreaker kicks that do not count as official match goals; within the remaining 247,803 `Goals` rows, 6,729 are own goals, 15,387 games fall outside `appearances` coverage, and isolating the 21,898 penalty goals, 8.84% of goal events, requires substring matching across 8,931 free-text `description` variants and would add a penalty-breakdown input to live what-if scoring. Penalty-taker inflation on `goals` is recorded as a known limitation in [docs/REPORT_NOTES.md](REPORT_NOTES.md)).
  2. **Competitions filter:** `competitions` has 65 rows and 31 `type == 'domestic_league'` rows, 17 of which (`BRA1`, `ARG1`, `MLS1`, `JAP1`, `PL1`, `MEX1`, `TS1`, `RO1`, `C1`, `SER1`, `SE1`, `SA1`, `A1`, `NO1`, `KR1`, `RSK1`, `AUS1`) were added in 2024 to 2025 with `0` rows in `appearances`. Valuation rows are restricted to clubs in the closed set of **14 European first-tier domestic leagues with full `appearances` coverage**: `IT1`, `ES1`, `GB1`, `FR1`, `TR1`, `L1`, `NL1`, `PO1`, `BE1`, `RU1`, `GR1`, `SC1`, `UKR1`, and `DK1` (30.91 and 30.90 appearances per game in 2024 and 2025). Trailing club performance aggregates appearances and lineups across all tracked club competitions: those 14 domestic leagues, domestic cups (`type == 'domestic_cup'`), domestic super cups and playoffs, and UEFA club competitions (`type == 'international_cup'` or `sub_type` prefixed with `uefa_`, noting that `UCOL` main-stage games carry 0 `appearances` rows in v679). `national_team_competition` rows are excluded.
  3. **Season window:** seasons `2017` through `2025` (`2017/18` to `2025/26`), assigning any date to season start year `year` when `month >= 7` and `year - 1` otherwise (97.82% agreement with `games.season`). Starting in `2017` keeps the post-2017 transfer-fee regime, guarantees complete `game_lineups` density (`>= 34.61` rows per game since `2013`), and gives every `2017` row a full 365-day lookback.
  4. **Position exclusion filter:** exclude `players.position == 'Goalkeeper'` (5,828 players and 72,205 valuation rows; active goalkeepers average 0.00014 goals/90 and 0.00273 assists/90, and no table records saves, shots faced, or goals prevented) and `players.position == 'Missing'` (586 players). Retain `Defender`, `Midfield`, and `Attack` (failing fast if any unexpected `position` token appears). `clean` drops `Goalkeeper` and `Missing` rows directly on `players`, whereas all 65 `competitions`, pre-`2017` match rows needed for lookbacks, and all `656,300` positive `player_valuations` rows remain in `ml/data/clean/` for `transform` to filter at join and window time.
  5. **Minimum minutes and Empirical Bayes smoothing:** require `>= 180` trailing 365-day minutes (`47,359` player-seasons across `14,692` distinct players), avoiding the 30.1% sample loss of a `900`-minute cutoff (`33,113` rows) that drops emerging squad players. To stabilize noisy per-90 rates on low-minute rows without discarding them, `transform` applies Empirical Bayes pad-90s shrinkage `r_hat = (count + m * prior_pos) / ((minutes / 90) + m)` with `m = 5` (450 minutes of positional prior fit on `train` seasons only, which cuts next-season `G+A/90` RMSE by 42.4%, from `0.3143` to `0.1809`, across `2,378` low-to-regular transitions) alongside unsmoothed volume features (`minutes_played`, `starter_ratio`).
- **Why it matters:** it defines what every later stage sees. The exploratory analysis (`analysis/eda.py`) produced the evidence and closes the baseline's data-selection phase ([docs/CONTEXT.md](CONTEXT.md) §3, phase 2).
- **Needed by:** week 3 (exploratory analysis).

### 3.3 Unit of analysis

- **Decide:** what one row represents, for example a player at a valuation date with performance aggregated over a fixed window before that date, and the window length.
- **Decision (2026-10-28):** **Option A (end-of-season player-season snapshot)** is adopted for modeling and publishing. One row is a `(player_id, season)` pair anchored on the player's latest `player_valuations.date` (`as_of_date`) within that July 1 to June 30 season, with target `market_value_in_eur` at `as_of_date` and performance features from `appearances`, `club_games`, and `game_lineups` aggregated over the trailing 365-day window `[as_of_date - 365 days, as_of_date]`. Across seasons `2017` to `2025` in the 14 covered European leagues, Option A produces `107,456` outfield snapshots before the minutes floor and `47,359` rows (`14,692` players) at `>= 180` minutes. Option B (keeping all `235,594` raw valuation updates in `2017` to `2025`) is rejected because 30.86% of `(player_id, season)` pairs receive 3 to 6 updates within the same season, overweighting star and recently transferred players and introducing serial autocorrelation across consecutive snapshots. For the separate market-inefficiency dataset (§3.12), one row is a paid outfield transfer in `transfers` (`transfer_fee > 0`, seasons `2017` to `2025`, involving at least one club in the 14 covered leagues, with pre-transfer valuation and `>= 180` minutes in `[transfer_date - 365 days, transfer_date - 1 day]`; `5,325` rows).
- **Why it matters:** the target, the features, the temporal-leakage policy, and every published row depend on it.
- **Needed by:** week 4 (clean, transform).

### 3.4 Temporal leakage policy

- **Decide:** point-in-time discipline for transfer and valuation history — which columns are known at prediction time, and how splits respect time.
- **Decision (2026-10-28, refined 2026-10-29):**
  1. **Banned static snapshot columns:** every mutable 2026-snapshot field on `players` (`current_club_id`, `current_club_name`, `current_club_domestic_competition_id`, `contract_expiration_date`, `market_value_in_eur`, `highest_market_value_in_eur`, `international_caps`, `international_goals`, `current_national_team_id`, `agent_name`, `last_season`), `appearances.player_current_club_id` (static 2026 club alongside point-in-time `player_club_id`), and every squad-aggregate or scraper column on `clubs` (`total_market_value`, `squad_size`, `average_age`, `foreigners_number`, `foreigners_percentage`, `national_team_players`, `net_transfer_record`, `coach_name`, `last_season`, `filename`) is forbidden as a model feature and physically dropped in `clean` before writing `ml/data/clean/`. Across `347,548` historical valuation rows (`2017` to `2023`), `players.current_club_id` disagrees with the point-in-time club on 47.47% of rows, `players.highest_market_value_in_eur` exceeds point-in-time market value on 88.49%, and non-null `players.contract_expiration_date` falls in 2025 or later on 71.84%.
  2. **Allowed point-in-time sources:** club and domestic competition at `as_of_date` come only from `player_valuations.current_club_id` and `player_valuations.player_club_domestic_competition_id` (`clubs` is joined only for static `name` and `club_code` display metadata). Only biographical fields come from `players`: `player_id`, `name`, `date_of_birth` (used to compute `age = (as_of_date - date_of_birth) / 365.25`), `position`, `sub_position`, `foot`, `height_in_cm`, and `country_of_citizenship`.
  3. **Window inequalities:** valuation rows aggregate match records in `[as_of_date - 365 days, as_of_date]`; transfer-evaluation rows aggregate match records in `[transfer_date - 365 days, transfer_date - 1 day]` (`game_date < transfer_date`) so appearances after joining the buying club never leak into pre-transfer features.
  4. **Chronological splits:** `train` covers seasons `2017` to `2023`, `validation` is season `2024`, and `test` is season `2025` (expanding-window season folds inside `train + validation` are used for cross-validation in §3.15). Random row-level splits and player-mixed temporal splits into future seasons are forbidden. Every learned statistic (Empirical Bayes positional priors, median height imputers, scalers, K-Means centroids, and supervised estimators) is fit strictly on the training split.
- **Why it matters:** Transfermarkt snapshots span multiple seasons; look-ahead bias would invalidate the undervaluation claims.
- **Needed by:** week 4 (clean, transform).

### 3.5 Data cleaning policy

- **Decide:** the rules for missing values (including when a zero is a real value and when it means missing), outliers, duplicates, and noise: what is dropped, imputed, or capped, and which stage applies each rule.
- **Inputs known so far:** the ingest output is all text (every column is Arrow `string`), so `clean` owns all typing ([ADR-012](ARCHITECTURE.md#adr-012-ingest-stores-source-columns-as-text-typing-happens-in-clean)). The faithful copy of version 679 shows six things. (1) `game_lineups.number` is text, and 25,698 rows hold "-". (2) `clubs.total_market_value` (796 of 796 rows) and `national_teams.coach_name` (124 of 124) are entirely null. (3) `transfers.transfer_fee` and `transfers.market_value_in_eur` use the "700000.000" form, while `players.market_value_in_eur` has no decimals ("1000000"); `clean` must parse both. (4) Empty strings are distinct from null: `game_events.description` has 93,157 and `game_lineups.position` has 3. (5) Nulls per table: appearances 2, club_games 104,884, clubs 1,287, competitions 39, countries 0, game_events 1,730,113, game_lineups 0, games 81,774, national_teams 137, player_valuations 92,973, players 199,373, transfers 129,686. (6) There are no blank lines, CRLF line endings, multi-line values, BOM, or duplicate headers.
- **Decision (2026-10-28, refined 2026-10-29):**
  1. **Explicit schema casting in `clean`:** keep non-integer identifiers as non-null `string` (`appearances.appearance_id` formatted as `"<game_id>_<player_id>"`, `game_lineups.game_lineups_id` as a 32-character hex digest, and competition codes `competition_id`, `domestic_competition_id`, and `player_club_domestic_competition_id` such as `"IT1"` or `"CL"`); cast numeric entity IDs (`game_id`, `player_id`, `club_id`, `player_club_id`, `opponent_id`, `home_club_id`, `away_club_id`, `from_club_id`, `to_club_id`, `current_club_id`) to `int64` (nullable `int64` on optional integer columns such as `number`, `country_id`, `total_clubs`, `stadium_seats`, `attendance`, `height_in_cm`, and league table positions); cast match counts (`minutes_played`, `goals`, `assists`, `yellow_cards`, `red_cards`, `own_goals`, `opponent_goals`, `home_club_goals`, `away_club_goals`, `season`) to `int64` and binary flags (`is_win`, `team_captain`) to `bool`; parse EUR amounts (`player_valuations.market_value_in_eur`, `transfers.transfer_fee`, `transfers.market_value_in_eur`, handling both integer strings and `"700000.000"` decimal strings) to `float64`; slice all date/timestamp strings to their leading 10 characters (`YYYY-MM-DD`) before parsing to `date32` so `players.date_of_birth` (`"YYYY-MM-DD HH:MM:SS"`) parses identically to date-only tables.
  2. **Whitespace, sentinels, and zeros vs. nulls:** strip leading and trailing Unicode whitespace on every string column first (affecting `44,493` trailing `\xa0` non-breaking-space cells in `players.city_of_birth`, `39,104` retained non-sentinel outfield cells, plus `4` in `game_lineups.player_name`), then map empty strings `""` (`3` rows in `game_lineups.position`), `"-"` in `game_lineups.number` (`25,698` rows) and `players.city_of_birth` (`127` raw `"-\xa0\xa0"` cells, `99` on retained outfield rows), and `"-1"` in `competitions.country_id` (`12` international competitions whose `country_name` is null) to null. Preserve `"0"` and `"0.000"` as real numeric zero on match statistics (`goals`, `assists`, `yellow_cards`, `red_cards`, `own_goals`, `opponent_goals`, `is_win`, `team_captain`), where zero means the event did not happen. On `transfers.transfer_fee`, keep `0.0` (`96,085` free transfers and loans) distinct from null (`61,526` undisclosed fees), and filter to `transfer_fee > 0` when building the paid-transfer sample.
  3. **Duplicate check, outlier rules, and `_clean.json` manifest in `clean`:** assert zero duplicate primary keys across all 9 included tables before row filtering (exit 1 if violated); drop `player_valuations` rows with null or `<= 0` `market_value_in_eur` (`1` row in v679, `656,301` to `656,300`); drop `players` rows with null `date_of_birth` (`49` rows) or `position` in `{'Goalkeeper', 'Missing'}` (`6,414` rows, `6,449` unique rows dropped across their union, leaving `43,700` outfield players); drop `appearances` rows with `minutes_played <= 0` (`3` rows, `1,894,350` to `1,894,347`) and cap `minutes_played > 120` at `120` (`3` rows from extra-time stoppage entry overshoot); convert implausible `players.height_in_cm <= 0` or `< 140` (`13` rows, leaving valid heights in `[154, 206]` cm; `112` total nulled cells on retained `players` together with the `99` `city_of_birth` sentinels) to null rather than dropping the player. Across v679, `clean` writes `9` typed Parquet tables (`6,216,263` rows from `6,222,716` input rows, `25,825` nulled cells, about `165` MiB) plus `ml/data/clean/_clean.json` recording `dataset`, `version`, `source_snapshot_sha256`, `cleaned_at` (ISO 8601 UTC with `Z`), `tool_versions` (`pandas`, `pyarrow`), `excluded_tables`, and `tables` keyed by table name (`parquet_file`, `input_rows`, `output_rows`, `dropped_rows`, `capped_rows`, `nulled_cells`, `stripped_cells`, `dropped_columns`, `columns`, and `dtypes`).
  4. **Stage boundary for imputation and error loss:** `clean` writes typed, row-filtered Parquet tables to `ml/data/clean/` without cross-row statistical imputation so train/val/test separation cannot leak. Missing `height_in_cm` (`3,519` retained outfield players after outlier nulling; `4,378` across all `50,149` raw players) is imputed by positional median and missing `foot` (`4,310` retained outfield players; `5,893` across all raw players) is mapped to `"unknown"` inside `transform` and the fitted `sklearn` preprocessor using `train` rows only. To stay aligned with the ordinary-least-squares linear and polynomial specification in [docs/CONTEXT.md](CONTEXT.md) §4, regression models optimize squared error (`MSE` / `RMSE`) on `log10(market_value_in_eur)`, with `MAE` on the log scale and `MdAPE` in EUR reported alongside `RMSE` and `R^2`.
- **Why it matters:** [docs/CONTEXT.md](CONTEXT.md) §3 phase 3 commits to exhaustive treatment of nulls, outliers, and noise, and undocumented rules cannot be defended.
- **Needed by:** week 4 (clean, transform).

### 3.6 Feature engineering

- **Decide:** the derived attributes (for example per-90-minute rates, age from date of birth, remaining contract length), the categorical encoding (for example position), and the scaling, with the fitted transformers stored in the artifact preprocessor.
- **Decided so far (2026-10-31):** the player's market value from any earlier valuation (for example the previous season's `player_valuations.market_value_in_eur`) is excluded from every feature set. It is point-in-time safe under §3.4, but it would make the regression reproduce the prior valuation, so the residual would measure the change in valuation instead of the gap between performance and price that §3.9, §3.10, and §3.12 rely on. The lower regression `R^2` is an accepted cost ([docs/REPORT_NOTES.md](REPORT_NOTES.md) H-09).
- **Decided (2026-10-31):** the Empirical Bayes prior of the per-90 rate features is grouped by `position` (`Defender`, `Midfield`, `Attack`), not by `sub_position`. Three of the twelve `sub_position` groups hold fewer than `5,500` n90 of exposure in the training seasons, which makes their priors estimates from a handful of events, and the `sub_position` labels drift between seasons. `sub_position` stays in the model sets as a categorical feature, where the training split estimates the offsets, and it is subject to the VIF check of E3. The rate features travel from `transform` to `train` as counts and minutes; the prior, the imputers and the scalers are fitted on the training split only, and the parameters that both stages must agree on (`window_days`, `minutes_floor`, `empirical_bayes_m`, `prior_grouping`) are recorded in the `transform` manifest so `train` reads them instead of hard-coding them. The rest of §3.6 stays open until the experiments in [docs/TRANSFORM_PLAN.md](TRANSFORM_PLAN.md) §7 run.
- **Why it matters:** [docs/CONTEXT.md](CONTEXT.md) §3 phase 4 requires it, and the preprocessor is part of the ARCHITECTURE.md artifact contract, so batch and live scoring apply identical transforms.
- **Needed by:** week 4 (clean, transform).

### 3.7 Target transform and polynomial scope

- **Decide:** the log(market_value) regression strategy (transform, back-transform, error scale), and the reduced feature set for the polynomial model with its degree chosen by cross-validation; justify the polynomial model against the linear baseline.
- **Why it matters:** drives prediction quality and the residual statistics every downstream output (labels, inefficiency analysis, replacements economics) is built on.
- **Needed by:** week 4 (target transform) and week 5 (polynomial degree).

### 3.8 K-Means specifics

- **Decide:** the feature set and scaling, k selection (elbow/silhouette), and cluster validation and stability checks.
- **Decided (2026-10-31):** the cluster feature set excludes market value and league, and includes the Empirical Bayes per-90 rates, `starter_ratio`, minutes, card rates, competition mix and `sub_position`, with the `sub_position` levels below `1%` of the training rows collapsed into `other`. `k` is chosen by the rule in [docs/TRANSFORM_PLAN.md](TRANSFORM_PLAN.md) §6: candidates are the `k` whose silhouette is within 5% of the maximum, at least `0.25` in absolute terms, with no cluster below about 3% of rows, that pass the stability checks (temporal ARI >= 0.5 against a K-Means fitted on the validation season, and mean bootstrap ARI >= 0.8 computed on the intersection of resampled rows); among the candidates the elbow candidate wins if present, otherwise the largest `k`. The smallest candidate is excluded on purpose, because silhouette peaks at small `k` and "within 5% of the maximum" would otherwise resolve to `k = 2`. The chosen `k` is written here as a constant and `train` does not re-select it. The scaler (`StandardScaler` against `RobustScaler`) and the cluster feature set are still open until E6 and E7 run.
- **Why it matters:** cluster assignments feed the archetype explorer and the replacement-similarity metric.
- **Needed by:** week 4 (feature set and scaling) and week 5 (k selection).

### 3.9 Undervalued/overvalued label definition

- **Decide:** the threshold rule (e.g. a residual percentile) that labels a player undervalued or overvalued, and out-of-fold label derivation — labels derived from regression residuals must be generated on held-out folds.
- **Why it matters:** leakage through in-fold labels would inflate the valuation-status findings the app surfaces and the grader evaluates.
- **Needed by:** week 5 (train).

### 3.10 Classification model design

- **Decide:** the features, class-imbalance handling, hyperparameter search, and metrics for the Random Forest and Decision Tree classifiers, and how they use the labels from 3.9.
- **Why it matters:** [docs/CONTEXT.md](CONTEXT.md) §4.1 commits to testing both, and the label rule alone defines neither the model nor how the two are compared.
- **Needed by:** week 5 (train).

### 3.11 Artifact manifest contents

- **Decide:** the exact fields of `manifest.json` and of the training-config reference — beyond the fixed contract items in ARCHITECTURE.md (ordered feature names, sklearn and `delphos_ml` versions, pinned Kaggle dataset version and snapshot hash, training-config reference): what the training config records and in what format.
- **Why it matters:** the manifest is how `delphos_ml.load_model()` enforces the artifact contract (version refusal) and how a run is reproduced.
- **Needed by:** week 5 (train).

### 3.12 Statistical inefficiency demonstration

- **Decide:** which hypothesis test(s) are run, the reported statistic and significance, and the population they cover — transfer-fee vs predicted-value residuals.
- **Why it matters:** this accepts the responsibility stated in ARCHITECTURE.md: the pipeline `evaluate` stage emits the `inefficiency_analysis` output and the analysis scripts present the demonstration; minimal acceptance is at least one hypothesis test with reported statistic and significance, presented by the analysis scripts and summarized in the app.
- **Needed by:** week 6 (evaluate: inefficiency analysis).

### 3.13 Replacements algorithm

- **Decide:** the "elite asset" definition/threshold, the athletic-equivalence similarity metric (cluster membership vs feature-space distance; which features and weights), and the ranking and tie-break rules.
- **Why it matters:** implements the `GET /players/{id}/replacements` contract from ARCHITECTURE.md — candidates are computed at publish and ranked, with up to 3 per target: exactly 3 when 3+ qualifying candidates exist, otherwise fewer with an explicit "no qualifying replacement" reason, never padded.
- **Needed by:** week 6 (evaluate/publish: replacements).

### 3.14 Publish outputs, ML side

- **Decide:** the exact row schemas for the curated player data (ADR-008), predictions, clusters, replacements, and the inefficiency-analysis output the evaluate stage emits — columns, keys, and dtypes, all carrying `model_run_id`.
- **Why it matters:** these rows are bulk-loaded in one transaction by the publish/activation protocol in ARCHITECTURE.md; the API reads them filtered on the active run.
- **Needed by:** week 6 (publish).

### 3.15 Evaluation and cross-validation plan

- **Decide:** metrics (e.g. R2/RMSE/MAE on the transformed target), the CV scheme, and the comparison of data-mining schemes ([docs/CONTEXT.md](CONTEXT.md) §6, week 7).
- **Why it matters:** this is the graded evidence that the chosen models earn their place; it feeds the evaluate stage and the analysis scripts.
- **Needed by:** week 7 (evaluate).

### 3.16 Analysis outputs for the final report

- **Decide:** which analysis script produces which figure or table, which report section uses it, and how scripts reuse `delphos_ml` and the pipeline's Parquet outputs instead of re-implementing algorithms.
- **Why it matters:** the report must show the same numbers the pipeline published, and re-implemented analysis code drifts.
- **Needed by:** week 7 (evaluate).

### 3.17 Live inference semantics

- **Decide:** the what-if input schema (synthetic player profile fields) and the batch-vs-live equivalence guarantee (what "equivalent to a batch row" means and how it is checked).
- **Why it matters:** implements the `POST /players/what-if` endpoint from ARCHITECTURE.md, which must return the same values the batch path would for the same inputs.
- **Needed by:** only if delivery priority 3 (what-if, ARCHITECTURE.md ADR-007) is reached; no week assigned.

### 3.18 LLM call parameters

- **Decide:** model/quant selection, timeouts, concurrency limits, context budget and assembly rules (chat history cap, metrics injection caps), and mid-stream failure semantics.
- **Why it matters:** the backend enforces these limits verbatim and degrades `/reports/*` and `/chat` on LLM outage per ARCHITECTURE.md; mid-stream failure semantics define what a streamed reply does when the LLM dies after headers were sent.
- **Needed by:** only if delivery priority 4 (LLM reports and chat, ARCHITECTURE.md ADR-007) is reached; no week assigned.

## 4. See also

- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — software architecture: responsibilities, contracts, and where each contract defers substance to this document.
- [docs/CONTEXT.md](CONTEXT.md) — project charter: objectives, KDD strategy, modeling methodology, expectations.
- [docs/WORK_PLAN.md](WORK_PLAN.md) — course schedule, actual progress, variances, and decision log.
- [docs/REPORT_NOTES.md](REPORT_NOTES.md) — empirical findings, data difficulties, and methodological trade-offs recorded in Spanish for the final report.
