# DelphosFootball agent instructions

## Table of contents

1. [What this project is](#1-what-this-project-is)
2. [Read first](#2-read-first)
3. [Per-scope guides](#3-per-scope-guides)
4. [Team conventions](#4-team-conventions)
5. [Dev commands](#5-dev-commands)
6. [See also](#6-see-also)

---

## 1. What this project is

DelphosFootball is a data-mining course project that identifies economically undervalued football players from the "Football Data from Transfermarkt" Kaggle dataset. An offline Python pipeline trains the models (K-Means, linear and polynomial regression, Random Forest and Decision Tree classification) and publishes results to PostgreSQL. A FastAPI backend serves them to a Flutter app. Two students work on it jointly.

## 2. Read first

Read these in order. Each file owns one kind of fact, so change a fact in its owner and link to it from elsewhere.

1. [docs/CONTEXT.md](docs/CONTEXT.md): the draft proposal and the baseline. Objectives, KDD strategy, modeling methodology, expectations, and the baseline schedule. Do not rewrite its content; it is the baseline. Record deviations in WORK_PLAN.md.
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the software architecture. Components, contracts, data flow, deployment, and every architecture decision (ADRs in §10).
3. [docs/ML_ARCHITECTURE.md](docs/ML_ARCHITECTURE.md): the ML design checklist, ordered by pipeline stage. Decisions are recorded here as they are made.
4. [docs/WORK_PLAN.md](docs/WORK_PLAN.md): the schedule, actual progress, variances, and the decision log. Current status lives here, not in this file.

## 3. Per-scope guides

This file is the global guide: conventions that hold everywhere in the repository. Component-specific commands and layout live in a guide beside each component:

- [ml/AGENTS.md](ml/AGENTS.md): the ML component in `ml/` (the `delphos_ml` package, the pipeline CLI, its tests, its stage outputs, and its dev commands).
- `backend/AGENTS.md` and `frontend/AGENTS.md`: added when those components land.

All uv commands run from `ml/`. Each Python component is its own uv project; there is no root workspace (ADR-013 in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).

## 4. Team conventions

- Write everything in English: code, comments, docs, commit messages.
- Use Python scripts, never Jupyter notebooks.
- Give each script or stage one responsibility. Its module docstring states the input, the output, and the responsibility. A stage's `--help` text comes from its entry function's docstring.
- Pipeline stages exchange Parquet files under `ml/data/<stage>/`. Only `publish` writes to the database (ADR-008).
- Ingest is a faithful text-only copy of the source (ADR-012). Typing and cleaning happen only in the `clean` stage.
- Analysis scripts live in `analysis/` and write to `analysis/output/` (ADR-009).
- The dataset comes from the Kaggle API at a pinned version (ADR-010). Never commit data, artifacts, model weights, or secrets.
- Configure the pipeline only through `DELPHOS_` environment variables or `.env`. [.env.example](.env.example) at the repo root is the global configuration-key list for every component; keep it in sync with the table in ARCHITECTURE.md §9.
- Record every decision in the owning doc in the same change: ADRs in ARCHITECTURE.md §10, ML decisions in ML_ARCHITECTURE.md §3, schedule and variances in WORK_PLAN.md.
- Follow the delivery priority in ADR-007 when scope is tight.
- Use Conventional Commits and branch names of the form `type/part-of-project/what-you-are-doing`, for example `feat/backend/player-search`.
- Update this file whenever a convention or command changes.

## 5. Dev commands

Run every uv command from `ml/`, not from the repo root; Python tooling is scoped per component. The command table lives in [ml/AGENTS.md](ml/AGENTS.md).

## 6. See also

- [README.md](README.md)
- [ml/AGENTS.md](ml/AGENTS.md): the ML component's dev commands, layout, and pipeline conventions.
- [docs/CONTEXT.md](docs/CONTEXT.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/ML_ARCHITECTURE.md](docs/ML_ARCHITECTURE.md)
- [docs/WORK_PLAN.md](docs/WORK_PLAN.md)
- [.env.example](.env.example): the global configuration variables and their defaults.
