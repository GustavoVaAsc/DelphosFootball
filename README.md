# DelphosFootball

## Table of contents

1. [What this project is](#1-what-this-project-is)
2. [Quickstart](#2-quickstart)
3. [Repository layout](#3-repository-layout)
4. [Documentation](#4-documentation)
5. [See also](#5-see-also)

---

## 1. What this project is

DelphosFootball is a data-mining course project that identifies economically undervalued football players from the "Football Data from Transfermarkt" Kaggle dataset. An offline Python pipeline trains the models (K-Means, linear and polynomial regression, Random Forest and Decision Tree classification) and publishes results to PostgreSQL. A FastAPI backend serves them to a Flutter app. Two students work on it jointly.

## 2. Quickstart

Run these from the repo root. You need [uv](https://docs.astral.sh/uv/); it installs Python 3.13 if the machine lacks it. No Kaggle credentials are needed.

```
uv sync
uv run pytest
uv run delphos-pipeline --help
uv run delphos-pipeline ingest
```

The first `ingest` needs about 1 GiB of free RAM and about 1.1 GB of disk: about 873 MiB for the kagglehub cache plus about 228 MiB in `data/ingest/`.

To override a default setting, copy `.env.example` to `.env` and uncomment the line you want.

## 3. Repository layout

Each root file sits where its tool looks for it, so none of them can move into a subfolder.

| Path | What it is | Why it lives there |
| --- | --- | --- |
| `.env.example` | The documented configuration keys. Copy it to `.env` (gitignored). | The pipeline reads `.env` from the repo root. |
| `.gitignore` | Files Git leaves out: secrets, generated outputs, virtual environments. | Git reads it from the repo root. |
| `.python-version` | Pins Python 3.13 for uv. | uv looks for it at the project root. |
| `AGENTS.md` | Shared instructions for any AI coding agent. | Agent tools discover it only at the repo root. |
| `README.md` | This file. | It is the entry point of the repository. |
| `pyproject.toml` | The uv workspace root, plus the pytest and ruff configuration. | It must be the common parent of every Python component. |
| `uv.lock` | The single lockfile for all Python components ([ADR-011](docs/ARCHITECTURE.md#adr-011-python-tooling-with-a-uv-workspace)). | uv expects it beside the workspace root, and the pipeline uses it to locate the repo root. |
| `docs/` | The project documents; see [Documentation](#4-documentation). | One folder keeps the documents together. |
| `ml/` | The `delphos_ml` package and the pipeline stages, with tests in `ml/tests/`. | It is a workspace member, listed in the root `pyproject.toml`. |
| `data/` | Generated stage outputs (gitignored). | Stages write to `data/<stage>/` under the repo root. |

Planned, not yet created: `analysis/`, `backend/`, `frontend/`, `migrations/`, `artifacts/`, and `llms/models/`. See [Repository layout](docs/ARCHITECTURE.md#repository-layout) in ARCHITECTURE.md for what each will hold.

## 4. Documentation

Read the documents in this order. Each owns one kind of fact.

1. [docs/CONTEXT.md](docs/CONTEXT.md): the draft proposal and baseline. Objectives, KDD strategy, modeling methodology, and the baseline schedule.
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the software architecture. Components, contracts, data flow, deployment, and the ADRs.
3. [docs/ML_ARCHITECTURE.md](docs/ML_ARCHITECTURE.md): the ML design checklist, ordered by pipeline stage, with decisions recorded as they are made.
4. [docs/WORK_PLAN.md](docs/WORK_PLAN.md): the schedule, actual progress, variances, and the decision log. Current status lives there.

AI agents also read [AGENTS.md](AGENTS.md), which holds the team conventions and dev commands.

## 5. See also

- [AGENTS.md](AGENTS.md)
- [docs/WORK_PLAN.md](docs/WORK_PLAN.md)
- [.env.example](.env.example)
