# DelphosFootball Work Plan

## Table of contents

1. [Purpose](#1-purpose)
2. [Timeline](#2-timeline)
3. [Baseline vs. actual](#3-baseline-vs-actual)
4. [Variances and justification](#4-variances-and-justification)
5. [Decision log](#5-decision-log)
6. [Recovery plan](#6-recovery-plan)
7. [See also](#7-see-also)

---

## 1. Purpose

This document tracks the baseline schedule from [docs/CONTEXT.md](CONTEXT.md) §6 against actual progress, records every variance with its justification, and logs decisions. It is the source for the final report's baseline-vs-actual comparison. Update it every work session.

## 2. Timeline

The project runs 8 weeks, each from Wednesday to Tuesday, except that week 8 extends to the delivery deadline, Wednesday 2026-11-25 at 09:00. Week 1 starts on 2026-09-30, the day the draft proposal was handed in. Final delivery is 2026-11-25 at 09:00. The baseline content of each week is in [docs/CONTEXT.md](CONTEXT.md) §6.

| Week | Dates |
| --- | --- |
| W1 | Sep 30 – Oct 6 |
| W2 | Oct 7 – Oct 13 |
| W3 | Oct 14 – Oct 20 |
| W4 | Oct 21 – Oct 27 |
| W5 | Oct 28 – Nov 3 |
| W6 | Nov 4 – Nov 10 |
| W7 | Nov 11 – Nov 17 |
| W8 | Nov 18 – Nov 25 (09:00) |

The two team members work jointly on every task in shared sessions. There are no parallel tracks.

## 3. Baseline vs. actual

Status as of 2026-10-29.

| Week | Dates | Baseline | Actual | Status |
| --- | --- | --- | --- | --- |
| W1 | Sep 30 – Oct 6 | Business understanding and data selection | Project proposal delivered with the problem definition, objectives, KDD strategy, and baseline schedule. Data selection not started. | Business understanding done |
| W2 | Oct 7 – Oct 13 | Business understanding and data selection | Software architecture and ML design checklist defined, and Python-only data-mining stack approved by the professor. Data selection still pending. | Partial, data selection slipped (V-01) |
| W3 | Oct 14 – Oct 20 | Data cleaning and transformation | Python ML environment and the `ingest` pipeline stage built to download the pinned Transfermarkt dataset (version 679: 12 tables, 7,497,433 rows) into text-only Parquet tables. Exploratory data analysis, data cleaning, and transformation still pending. | Behind (V-01, V-02) |
| W4 | Oct 21 – Oct 27 | Data cleaning and transformation | No advances during this week. | Slipped (V-03) |
| W5 (in progress) | Oct 28 – Nov 3 | Implementation of algorithms (K-means, Multiple Linear Regression, Polynomial Regression, and Random Forest/Decision Tree Classification) | Exploratory data analysis completed on 2026-10-28 over the 12 ingested tables (summary tables and six diagnostic figures), closing data selection and setting the modeling population, end-of-season snapshot rule, temporal-leakage controls, and cleaning rules. Data cleaning completed on 2026-10-29: the `clean` pipeline stage and sequential `all` runner produce 9 typed Parquet tables (`6,216,263` rows from `6,222,716` input rows) with excluded tables and 22 static 2026 columns removed, Unicode whitespace and `"-"` / `"-1"` sentinels normalized, unique primary keys verified, and row-level outliers filtered. Feature transformation (`transform`) and algorithm implementation remain pending. | Behind (V-01, V-03) |
| W6 | Nov 4 – Nov 10 | Implementation of algorithms (same as W5) | Not started. | Planned |
| W7 | Nov 11 – Nov 17 | Data interpretation and evaluation (Prediction Performance, Cross-validation, and Comparison of data mining schemes) | Not started. | Planned |
| W8 | Nov 18 – Nov 25 (09:00) | Comparison of results (Baseline vs. Actual) and final documentation (APA 7th edition format) | Not started. | Planned |

## 4. Variances and justification

### V-01: Software architecture before data work (week 2)

- **Baseline:** weeks 1–2 cover business understanding and data selection.
- **Actual:** the team defined the software architecture and the ML design checklist in week 2 (2026-10-11) before starting any data work. Data selection did not start.
- **Justification:** the team wanted the whole system written down and planned before starting any data manipulation.
- **Impact:** data selection did not start in weeks 1–2. Data work is about 1.5 weeks behind baseline as of 2026-10-17. By the end of 2026-10-17 the Python environment and the ingest stage exist and the pinned dataset is accessible; the exploratory data analysis that closes data selection, and data cleaning, have not started.
- **Recovery:** see [Recovery plan](#6-recovery-plan).

### V-02: Root uv workspace dissolved; uv commands moved to `ml/`

- **Baseline:** Python tooling is one uv workspace at the repo root with a single shared `uv.lock`, and the documented dev commands run from the repo root (ADR-011).
- **Actual:** on 2026-10-18 the root workspace was dissolved. `ml/` became its own uv project, owning its `pyproject.toml`, `uv.lock`, and `.python-version`, and the documented dev commands run from `ml/` (ADR-013). ADR-011 is superseded but retained for history. `.env.example` stays at the repo root as the global configuration-key list.
- **Justification:** the root workspace was overhead for a single Python component, and scoping tooling per module was preferred.
- **Impact:** version alignment between `ml/` and the future `backend/` is now a manual pinning discipline instead of a lockfile guarantee (accepted risk, ADR-013). No schedule date moves.
- **Recovery:** none required; this is a tooling change with no schedule effect.

### V-03: No project progress during week 4 (Oct 21 – Oct 27)

- **Baseline:** week 4 completes data cleaning and transformation, and the 2026-10-17 recovery plan targeted finishing EDA plus `clean` and `transform` by 2026-10-27.
- **Actual:** no KDD or pipeline progress took place between 2026-10-19 and 2026-10-27. Exploratory data analysis started on 2026-10-28 at the opening of week 5.
- **Justification:** both team members had midterm exams and extra coursework across weeks 3 and 4. Gustavo also carried external work commitments, and Yordi competed in the Club America sports-analytics hackathon from Thursday 2026-10-16 to Thursday 2026-10-23; the professor was informed beforehand because the hackathon topic related directly to the course and Yordi consulted him on it.
- **Impact:** data cleaning, feature transformation, and algorithm implementation start one week later than the 2026-10-17 recovery plan assumed, putting the project roughly two weeks behind the original baseline entering week 5.
- **Recovery:** finish EDA and §3.2 to §3.5 on 2026-10-28, complete `clean` on 2026-10-29 and `transform` (§3.6 to §3.8) during the rest of week 5, concentrate model training and `publish` in week 6, and protect weeks 7 and 8 through the delivery priority in ADR-007. See [Recovery plan](#6-recovery-plan).

## 5. Decision log

| Date | Decision | Reason | Recorded in |
| --- | --- | --- | --- |
| 2026-10-11 | Software architecture adopted | The whole system is written down and planned before any data manipulation | ARCHITECTURE.md ADR-001 to ADR-006 |
| 2026-10-12 | Python-only data-mining tooling (no visual tools such as Weka or Orange), approved by the professor; the Flutter app is unaffected | Approved by the professor | This document |
| 2026-10-17 | ADR-007: delivery priority under the course deadline | Delivery is on 2026-11-25, there is no code yet, and two people work jointly on one track while the architecture describes more than may fit | ARCHITECTURE.md ADR-007 |
| 2026-10-17 | ADR-008: Parquet files between pipeline stages; PostgreSQL only at publish | Keeping staging tables in `analytics` required PostgreSQL, roles, Alembic, and compose from day one for every stage | ARCHITECTURE.md ADR-008 |
| 2026-10-17 | ADR-009: analysis scripts over Jupyter notebooks | The team decided on plain Python scripts with no notebooks | ARCHITECTURE.md ADR-009 |
| 2026-10-17 | ADR-010: Kaggle API with a pinned dataset version over a manually downloaded snapshot | The manual download left the dataset version unrecorded and needed a manual step | ARCHITECTURE.md ADR-010 |
| 2026-10-17 | ADR-011: Python tooling with a uv workspace | Section 11 listed the Python tooling as undecided, and the shared constraint set needed one lockfile | ARCHITECTURE.md ADR-011 |
| 2026-10-17 | ADR-012: ingest stores source columns as text; typing happens in clean | The first implementation inferred types and changed the source text, which the audit flagged | ARCHITECTURE.md ADR-012 |
| 2026-10-17 | Kaggle dataset version 679 pinned | Latest version on 2026-10-17; upstream updates are paused and the data is current to 2026-07-06 | ML_ARCHITECTURE.md §3.1 |
| 2026-10-18 | Per-component uv projects: the root uv workspace dissolved (ADR-013 supersedes ADR-011) | The root workspace was overhead for a single Python component, and scoping tooling per module was preferred | ARCHITECTURE.md ADR-013 |
| 2026-10-28 | ADR-014: analysis scripts run in the `ml/` uv project through an `analysis` dependency group (`matplotlib`, `scipy`, `seaborn`), and `pandas` joins `ml/` runtime dependencies | Keeps one lockfile and virtual environment for `ml/` and `analysis/`, preserves `ml/uv.lock` as the `DELPHOS_DATA_DIR` anchor, and keeps plotting packages out of the runtime `delphos_ml` wheel | ARCHITECTURE.md ADR-014, ml/pyproject.toml |
| 2026-10-28 | KDD data scope, unit of analysis, temporal-leakage rules, and cleaning policy decided from v679 EDA (`analysis/eda.py`) | Restricts population to the 14 European domestic leagues with `appearances` coverage (`2017` to `2025`, outfield players, `>= 180` min + Empirical Bayes `m = 5`), adopts Option A end-of-season snapshots, excludes `game_events` and static 2026 columns, sets chronological splits (`2017..2023` / `2024` / `2025`), and specifies `clean` typing and sentinel rules | ML_ARCHITECTURE.md §3.2 to §3.5, REPORT_NOTES.md |
| 2026-10-29 | `clean` stage and `all` CLI runner implemented; §3.4 and §3.5 refined from v679 schema validation | Keeps composite/hex/alphanumeric IDs (`appearance_id`, `game_lineups_id`, `competition_id`) as `string`, strips Unicode `\xa0` whitespace (`44,493` raw cells in `players.city_of_birth`), maps `"-"` in `players.city_of_birth` (`127` raw `"-\xa0\xa0"` cells) and `"-1"` in `competitions.country_id` (`12` rows) to null, and physically drops 22 static 2026 columns across `players`, `clubs`, and `appearances` when writing `ml/data/clean/` | ML_ARCHITECTURE.md §3.4 to §3.5, REPORT_NOTES.md |

## 6. Recovery plan

As of 2026-10-29. Section numbers refer to [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md).

- **Week 5 (Oct 28 – Nov 3):** exploratory data analysis, ADR-014, Spanish report notes, and KDD decisions §3.2 to §3.5 finished on 2026-10-28, and the `clean` pipeline stage plus `all` runner finished on 2026-10-29. Next: decide §3.6 to §3.8 and implement the `transform` stage with unit tests.
- **Week 6 (Nov 4 – Nov 10):** decide §3.9 to §3.14; implement `train`, `evaluate` (market-inefficiency tests and replacement rankings), and `publish` (migration `0001`, the `analytics` tables, and the single-transaction load).
- **Week 7 (Nov 11 – Nov 17):** cross-validation and model comparison (§3.15, §3.16); build the minimal demo (ADR-007 priority 2): FastAPI search, valuation, and replacements over the published `analytics` rows, plus the Flutter screens for them.
- **Week 8 (Nov 18 – Nov 25, 09:00):** final report in APA 7th edition format and the closing baseline-vs-actual comparison; ADR-007 priorities 3 and 4 only if priority 2 is complete.

Under time pressure, scope is cut following ADR-007 in [docs/ARCHITECTURE.md](ARCHITECTURE.md).

## 7. See also

- [docs/CONTEXT.md](CONTEXT.md) — project charter and the baseline schedule (§6).
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — software architecture and the ADRs referenced here.
- [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) — ML definition checklist, ordered by pipeline stage.
- [docs/REPORT_NOTES.md](REPORT_NOTES.md) — empirical findings and methodological memory in Spanish for the final report.
