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

Skeleton — content pending. The [Definition checklist](#3-definition-checklist) below is the agenda: each item must be decided and written here before this document is considered complete. The checklist is ordered by pipeline stage, and each item names the week it is needed by, except the items gated on delivery priorities 3 and 4 (schedule in [docs/WORK_PLAN.md](WORK_PLAN.md)). Until the items are decided, ARCHITECTURE.md's black-box treatment of the pipeline stands, but the acceptance obligations it states (notably the statistical inefficiency demonstration) are not deferred.

## 3. Definition checklist

Each item names what must be decided, why it matters, and the week and stage that need it.

### 3.1 Dataset snapshot

- **Decide:** which Kaggle dataset version is pinned through the Kaggle API, how the snapshot hash is computed and recorded, and the refresh policy (bumping the pinned version).
- **Why it matters:** the dataset version and snapshot hash go into every manifest, and reproducibility of published results depends on it.
- **Needed by:** week 3 (ingest).

### 3.2 Data scope and attribute selection

- **Decide:** which dataset tables and columns enter the pipeline, and the population filters (competitions, seasons, minimum minutes played, how goalkeepers are handled).
- **Why it matters:** it defines what every later stage sees. The week-3 exploratory analysis produces the evidence and closes the baseline's data-selection phase ([docs/CONTEXT.md](CONTEXT.md) §3, phase 2).
- **Needed by:** week 3 (exploratory analysis).

### 3.3 Unit of analysis

- **Decide:** what one row represents, for example a player at a valuation date with performance aggregated over a fixed window before that date, and the window length.
- **Why it matters:** the target, the features, the temporal-leakage policy, and every published row depend on it.
- **Needed by:** week 4 (clean, transform).

### 3.4 Temporal leakage policy

- **Decide:** point-in-time discipline for transfer and valuation history — which columns are known at prediction time, and how splits respect time.
- **Why it matters:** Transfermarkt snapshots span multiple seasons; look-ahead bias would invalidate the undervaluation claims.
- **Needed by:** week 4 (clean, transform).

### 3.5 Data cleaning policy

- **Decide:** the rules for missing values (including when a zero is a real value and when it means missing), outliers, duplicates, and noise: what is dropped, imputed, or capped, and which stage applies each rule.
- **Why it matters:** [docs/CONTEXT.md](CONTEXT.md) §3 phase 3 commits to exhaustive treatment of nulls, outliers, and noise, and undocumented rules cannot be defended.
- **Needed by:** week 4 (clean, transform).

### 3.6 Feature engineering

- **Decide:** the derived attributes (for example per-90-minute rates, age from date of birth, remaining contract length), the categorical encoding (for example position), and the scaling, with the fitted transformers stored in the artifact preprocessor.
- **Why it matters:** [docs/CONTEXT.md](CONTEXT.md) §3 phase 4 requires it, and the preprocessor is part of the ARCHITECTURE.md artifact contract, so batch and live scoring apply identical transforms.
- **Needed by:** week 4 (clean, transform).

### 3.7 Target transform and polynomial scope

- **Decide:** the log(market_value) regression strategy (transform, back-transform, error scale), and the reduced feature set for the polynomial model with its degree chosen by cross-validation; justify the polynomial model against the linear baseline.
- **Why it matters:** drives prediction quality and the residual statistics every downstream output (labels, inefficiency analysis, replacements economics) is built on.
- **Needed by:** week 4 (target transform) and week 5 (polynomial degree).

### 3.8 K-Means specifics

- **Decide:** the feature set and scaling, k selection (elbow/silhouette), and cluster validation and stability checks.
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
