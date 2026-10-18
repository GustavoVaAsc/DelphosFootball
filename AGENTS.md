# DelphosFootball agent instructions

## Table of contents

1. [What this project is](#1-what-this-project-is)
2. [Read first](#2-read-first)
3. [Team conventions](#3-team-conventions)
4. [Dev commands](#4-dev-commands)
5. [See also](#5-see-also)

---

## 1. What this project is

DelphosFootball is a data-mining course project that identifies economically undervalued football players from the "Football Data from Transfermarkt" Kaggle dataset. An offline Python pipeline trains the models (K-Means, linear and polynomial regression, Random Forest and Decision Tree classification) and publishes results to PostgreSQL. A FastAPI backend serves them to a Flutter app. Two students work on it jointly.

## 2. Read first

Read these in order. Each file owns one kind of fact, so change a fact in its owner and link to it from elsewhere.

1. [docs/CONTEXT.md](docs/CONTEXT.md): the draft proposal and the baseline. Objectives, KDD strategy, modeling methodology, expectations, and the baseline schedule. Do not rewrite its content; it is the baseline. Record deviations in WORK_PLAN.md.
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the software architecture. Components, contracts, data flow, deployment, and every architecture decision (ADRs in §10).
3. [docs/ML_ARCHITECTURE.md](docs/ML_ARCHITECTURE.md): the ML design checklist, ordered by pipeline stage. Decisions are recorded here as they are made.
4. [docs/WORK_PLAN.md](docs/WORK_PLAN.md): the schedule, actual progress, variances, and the decision log. Current status lives here, not in this file.

## 3. Team conventions

- Write everything in English: code, comments, docs, commit messages.
- Use Python scripts, never Jupyter notebooks.
- Give each script or stage one responsibility. Its module docstring states the input, the output, and the responsibility. A stage's `--help` text comes from its entry function's docstring.
- Pipeline stages exchange Parquet files under `data/<stage>/`. Only `publish` writes to the database (ADR-008).
- Ingest is a faithful text-only copy of the source (ADR-012). Typing and cleaning happen only in the `clean` stage.
- Analysis scripts live in `analysis/` and write to `analysis/output/` (ADR-009).
- The dataset comes from the Kaggle API at a pinned version (ADR-010). Never commit data, artifacts, model weights, or secrets.
- Configure the pipeline only through `DELPHOS_` environment variables or `.env`. Keep `.env.example` in sync with the table in ARCHITECTURE.md §9.
- Record every decision in the owning doc in the same change: ADRs in ARCHITECTURE.md §10, ML decisions in ML_ARCHITECTURE.md §3, schedule and variances in WORK_PLAN.md.
- Follow the delivery priority in ADR-007 when scope is tight.
- Use Conventional Commits and branch names of the form `type/part-of-project/what-you-are-doing`, for example `feat/backend/player-search`.
- Update this file whenever a convention or command changes.

## 4. Dev commands

Run these from the repo root. Python 3.13 is pinned in `.python-version`, and `uv.lock` is the only lockfile.

| Command | Purpose |
| --- | --- |
| `uv sync` | Install the workspace and the `dev` group into `.venv` |
| `uv run delphos-pipeline --help` | List the pipeline stages |
| `uv run delphos-pipeline ingest` | Download the pinned Kaggle dataset into `data/ingest/` |
| `uv run pytest` | Run the tests |
| `uv run ruff check` | Lint |
| `uv run ruff format --check` | Check formatting; `uv run ruff format` fixes it |

`ingest` needs about 1 GiB of free RAM and about 1.1 GB of disk (the kagglehub cache plus `data/ingest/`).

## 5. See also

- [README.md](README.md)
- [docs/CONTEXT.md](docs/CONTEXT.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/ML_ARCHITECTURE.md](docs/ML_ARCHITECTURE.md)
- [docs/WORK_PLAN.md](docs/WORK_PLAN.md)
- [.env.example](.env.example): the configuration variables and their defaults.
