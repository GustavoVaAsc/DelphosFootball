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

Status as of 2026-10-17.

| Week | Dates | Baseline | Actual | Status |
| --- | --- | --- | --- | --- |
| W1 | Sep 30 – Oct 6 | Business understanding and data selection | Draft proposal handed in on 2026-09-30 (docs/CONTEXT.md). | Business understanding done |
| W2 | Oct 7 – Oct 13 | Business understanding and data selection | Software architecture and ML architecture skeleton written (commit a9be1cf, 2026-10-11). Python-only data-mining tooling approved by the professor (2026-10-12). Data selection not started. | Partial, data selection slipped (V-01) |
| W3 (in progress) | Oct 14 – Oct 20 | Data cleaning and transformation | Architecture decisions ADR-007 to ADR-010 recorded; ML checklist reordered by pipeline stage; repository .gitignore added; this work plan created. Data cleaning not started. | Behind (V-01) |
| W4 | Oct 21 – Oct 27 | Data cleaning and transformation | Not started. | Planned |
| W5 | Oct 28 – Nov 3 | Implementation of algorithms (K-means, Multiple Linear Regression, Polynomial Regression, and Random Forest/Decision Tree Classification) | Not started. | Planned |
| W6 | Nov 4 – Nov 10 | Implementation of algorithms (same as W5) | Not started. | Planned |
| W7 | Nov 11 – Nov 17 | Data interpretation and evaluation (Prediction Performance, Cross-validation, and Comparison of data mining schemes) | Not started. | Planned |
| W8 | Nov 18 – Nov 25 (09:00) | Comparison of results (Baseline vs. Actual) and final documentation (APA 7th edition format) | Not started. | Planned |

## 4. Variances and justification

### V-01: Software architecture before data work (week 2)

- **Baseline:** weeks 1–2 cover business understanding and data selection.
- **Actual:** the team wrote the software architecture and the ML architecture skeleton before any data work and committed them in week 2 (commit a9be1cf, 2026-10-11). Data selection did not start.
- **Justification:** the team wanted the whole system written down and planned before starting any data manipulation.
- **Impact:** data selection did not start in weeks 1–2. Data work is about 1.5 weeks behind baseline as of 2026-10-17. There is no code, no data access, and no exploratory data analysis yet.
- **Recovery:** see [Recovery plan](#6-recovery-plan).

## 5. Decision log

| Date | Decision | Reason | Recorded in |
| --- | --- | --- | --- |
| 2026-10-11 | Software architecture adopted | The whole system is written down and planned before any data manipulation | ARCHITECTURE.md ADR-001 to ADR-006 |
| 2026-10-12 | Python-only data-mining tooling (no visual tools such as Weka or Orange), approved by the professor; the Flutter app is unaffected | Approved by the professor | This document |
| 2026-10-17 | ADR-007: delivery priority under the course deadline | Delivery is on 2026-11-25, there is no code yet, and two people work jointly on one track while the architecture describes more than may fit | ARCHITECTURE.md ADR-007 |
| 2026-10-17 | ADR-008: Parquet files between pipeline stages; PostgreSQL only at publish | Keeping staging tables in `analytics` required PostgreSQL, roles, Alembic, and compose from day one for every stage | ARCHITECTURE.md ADR-008 |
| 2026-10-17 | ADR-009: analysis scripts over Jupyter notebooks | The team decided on plain Python scripts with no notebooks | ARCHITECTURE.md ADR-009 |
| 2026-10-17 | ADR-010: Kaggle API with a pinned dataset version over a manually downloaded snapshot | The manual download left the dataset version unrecorded and needed a manual step | ARCHITECTURE.md ADR-010 |

## 6. Recovery plan

As of 2026-10-17. Section numbers refer to [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md).

- **Rest of week 3 (Oct 17–20):** set up the Python environment and the `ml/` skeleton (dependency tool and Python version are decided first); build the ingest stage through the Kaggle API at a pinned version; write the exploratory analysis script; decide §3.1 and §3.2.
- **Week 4 (Oct 21–27):** decide §3.3 to §3.8; implement the clean and transform stages. Target: back on baseline by 2026-10-27.
- **Weeks 5–6:** train; decide §3.9 to §3.14; implement the evaluate outputs that publish loads (inefficiency analysis, replacements) and the publish stage (migration `0001`, the `analytics` tables, the single-transaction load).
- **Week 7:** evaluation and cross-validation (§3.15, §3.16); build the minimal demo (ADR-007 priority 2): FastAPI search, valuation, and replacements over the published `analytics` rows, plus the Flutter screens for them.
- **Week 8:** final report and the closing baseline-vs-actual comparison; priorities 3 and 4 only if the demo is done.

Under time pressure, scope is cut following ADR-007 in [docs/ARCHITECTURE.md](ARCHITECTURE.md).

## 7. See also

- [docs/CONTEXT.md](CONTEXT.md) — project charter and the baseline schedule (§6).
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — software architecture and the ADRs referenced here.
- [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) — ML definition checklist, ordered by pipeline stage.
