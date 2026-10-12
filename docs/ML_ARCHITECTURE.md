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

Skeleton — content pending. The [Definition checklist](#3-definition-checklist) below is the agenda: each item must be decided and written here before this document is considered complete. Until then, ARCHITECTURE.md's black-box treatment of the pipeline stands, but the acceptance obligations it states (notably the statistical inefficiency demonstration) are not deferred.

## 3. Definition checklist

Each item names what must be decided and why it matters.

### 3.1 Undervalued/overvalued label definition

- **Decide:** the threshold rule (e.g. a residual percentile) that labels a player undervalued or overvalued, and out-of-fold label derivation — labels derived from regression residuals must be generated on held-out folds.
- **Why it matters:** leakage through in-fold labels would inflate the valuation-status findings the app surfaces and the grader evaluates.

### 3.2 Target transform and polynomial scope

- **Decide:** the log(market_value) regression strategy (transform, back-transform, error scale), and the reduced feature set for the polynomial model with its degree chosen by cross-validation; justify the polynomial model against the linear baseline.
- **Why it matters:** drives prediction quality and the residual statistics every downstream output (labels, inefficiency analysis, replacements economics) is built on.

### 3.3 Temporal leakage policy

- **Decide:** point-in-time discipline for transfer and valuation history — which columns are known at prediction time, and how splits respect time.
- **Why it matters:** Transfermarkt snapshots span multiple seasons; look-ahead bias would invalidate the undervaluation claims.

### 3.4 Statistical inefficiency demonstration

- **Decide:** which hypothesis test(s) are run, the reported statistic and significance, and the population they cover — transfer-fee vs predicted-value residuals.
- **Why it matters:** this accepts the responsibility stated in ARCHITECTURE.md: the pipeline `evaluate` stage emits the `inefficiency_analysis` output and the notebooks carry the demonstration; minimal acceptance is at least one hypothesis test with reported statistic and significance, presented in the notebooks and summarized in the app.

### 3.5 Replacements algorithm

- **Decide:** the "elite asset" definition/threshold, the athletic-equivalence similarity metric (cluster membership vs feature-space distance; which features and weights), and the ranking and tie-break rules.
- **Why it matters:** implements the `GET /players/{id}/replacements` contract from ARCHITECTURE.md — candidates are computed at publish, ranked, capped at 3 per target, and "at least 3" is guaranteed only when 3+ qualifying candidates exist.

### 3.6 K-Means specifics

- **Decide:** the feature set and scaling, k selection (elbow/silhouette), and cluster validation and stability checks.
- **Why it matters:** cluster assignments feed the archetype explorer and the replacement-similarity metric.

### 3.7 Artifact manifest contents

- **Decide:** the exact fields of `manifest.json` and of the training-config reference — beyond the fixed contract items in ARCHITECTURE.md (ordered feature names, sklearn and `delphos_ml` versions, dataset snapshot hash, training-config reference): what the training config records and in what format.
- **Why it matters:** the manifest is how `delphos_ml.load_model()` enforces the artifact contract (version refusal) and how a run is reproduced.

### 3.8 LLM call parameters

- **Decide:** model/quant selection, timeouts, concurrency limits, context budget and assembly rules (chat history cap, metrics injection caps), and mid-stream failure semantics.
- **Why it matters:** the backend enforces these limits verbatim and degrades `/reports/*` and `/chat` on LLM outage per ARCHITECTURE.md; mid-stream failure semantics define what a streamed reply does when the LLM dies after headers were sent.

### 3.9 Live inference semantics

- **Decide:** the what-if input schema (synthetic player profile fields) and the batch-vs-live equivalence guarantee (what "equivalent to a batch row" means and how it is checked).
- **Why it matters:** implements the `POST /players/what-if` endpoint from ARCHITECTURE.md, which must return the same values the batch path would for the same inputs.

### 3.10 Evaluation and cross-validation plan

- **Decide:** metrics (e.g. R2/RMSE/MAE on the transformed target), the CV scheme, and the baseline-vs-actual comparison of the data-mining schemes (course expectation, docs/CONTEXT.md:63).
- **Why it matters:** this is the graded evidence that the chosen models earn their place; it feeds the notebooks and the evaluate stage.

### 3.11 Notebook and pipeline lockstep

- **Decide:** how notebooks mirror `delphos_ml` code (which notebook covers which pipeline stage) and which notebook carries the statistical inefficiency demonstration.
- **Why it matters:** the grader evaluates a Jupyter mirror of the algorithms alongside the app; drift between notebooks and pipeline code would show.

### 3.12 Dataset snapshot

- **Decide:** which Kaggle dump version is canonical, how the snapshot hash is computed and recorded, and the refresh policy.
- **Why it matters:** the snapshot hash goes into every manifest, and reproducibility of published results depends on it.

### 3.13 Publish outputs (ML side)

- **Decide:** the exact row schemas for predictions, clusters, replacements, and the inefficiency-analysis output the evaluate stage emits — columns, keys, and dtypes, all carrying `model_run_id`.
- **Why it matters:** these rows are bulk-loaded in one transaction by the publish/activation protocol in ARCHITECTURE.md; the API reads them filtered on the active run.

## 4. See also

- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — software architecture: responsibilities, contracts, and where each contract defers substance to this document.
- [docs/CONTEXT.md](CONTEXT.md) — project charter: objectives, KDD strategy, modeling methodology, expectations.
