# DelphosFootball

## Table of contents

1. [What this project is](#1-what-this-project-is)
2. [Quickstart](#2-quickstart)
3. [Repository layout](#3-repository-layout)
4. [Documentation](#4-documentation)
5. [See also](#5-see-also)
6. [License](#6-license)

---

## 1. What this project is

DelphosFootball is a data-mining course project that identifies economically undervalued football players from the "Football Data from Transfermarkt" Kaggle dataset. An offline Python pipeline trains the models (K-Means, linear and polynomial regression, Random Forest and Decision Tree classification) and publishes results to PostgreSQL. A FastAPI backend serves them to a Flutter app. Two students work on it jointly.

## 2. Quickstart

You need [Docker](https://www.docker.com/) and [uv](https://docs.astral.sh/uv/) (installs Python 3.13 if needed).

### Database and migrations

Start the PostgreSQL 16 container and apply the Alembic schema migrations (`analytics` and `app` schemas):

```bash
docker compose up -d
```

### ML Pipeline (train and publish)

Run these from `ml/`:

```bash
cd ml
uv sync --all-groups
uv run pytest
uv run delphos-pipeline all
uv run delphos-pipeline publish
```

`delphos-pipeline all` runs `ingest`, `clean`, `transform`, `train`, and `evaluate` sequentially. `delphos-pipeline publish` promotes the model bundle to `artifacts/<model_run_id>/` and bulk-loads the active run into the PostgreSQL `analytics` schema.

To override default settings, copy `.env.example` to `.env` at the repo root.

### Backend API

Run these from `backend/`:

```bash
cd backend
uv sync
uv run pytest
uv run uvicorn delphos_backend.main:app --reload --port 8000
```

Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

## 3. Repository layout

Each root file sits where its tool looks for it, so none of them can move into a subfolder.

| Path | What it is | Why it lives there |
| --- | --- | --- |
| `.env.example` | The configuration keys documented for every component. Copy it to `.env` at the repo root (gitignored). | It is the global key list for all components, and the repo root is the documented `.env` location. |
| `.gitignore` | Files Git leaves out: secrets, generated outputs, virtual environments. | Git reads it from the repo root. |
| `docker-compose.yml` | Multi-container definition for PostgreSQL 16 (`delphos-db`) and automated schema migration service (`delphos-migrate`). | Docker Compose anchors on the repo root. |
| `AGENTS.md` | Shared instructions for any AI coding agent. | Agent tools discover it only at the repo root. |
| `README.md` | This file. | It is the entry point of the repository. |
| `analysis/` | Plain Python analysis scripts (`analysis/eda.py`, `analysis/inefficiency_analysis.py`, `analysis/model_comparison.py`) that write tables and figures to gitignored `analysis/output/` ([ADR-009](docs/ARCHITECTURE.md#adr-009-analysis-scripts-over-jupyter-notebooks), [ADR-014](docs/ARCHITECTURE.md#adr-014-analysis-scripts-run-in-the-ml-uv-project-through-a-dependency-group)). | Kept outside `ml/src/` because analysis scripts answer report questions and are not part of the deployable package. |
| `artifacts/` | Staged and active versioned model bundles (`artifacts/<model_run_id>/`) with verified SHA-256 integrity and metadata ([ADR-006](docs/ARCHITECTURE.md#adr-006-file-based-model-artifacts-over-an-external-registry)). | Persisted storage for trained model weights and preprocessor pipelines. |
| `backend/` | The `delphos_backend` uv project: FastAPI service serving player valuations, tactical replacements, and cluster profiles from PostgreSQL ([ADR-002](docs/ARCHITECTURE.md#adr-002-fastapi-backend-over-monolithic-frameworks), [ADR-013](docs/ARCHITECTURE.md#adr-013-per-component-uv-projects-over-a-root-uv-workspace)). | Independent component with its own dependencies, Dockerfile, and test suite. |
| `docs/` | The project documents; see [Documentation](#4-documentation). | One folder keeps the architecture, ML decisions, and reports together. |
| `migrations/` | Alembic migration environment and version scripts (`0001` to `0003`) defining schemas `analytics` and `app`. | Database schema evolution decoupled from application and pipeline code. |
| `ml/` | The `delphos_ml` uv project: pipeline stages under `ml/src/`, unit tests in `ml/tests/`, stage outputs in `ml/data/<stage>/` (gitignored), and its own `pyproject.toml` and `uv.lock`. | Independent Python component for data ingest, cleaning, feature transformation, training, evaluation, and publishing. |

Planned: `frontend/` (Flutter mobile client, scheduled for Week 7) and `llms/models/` (local GGUF weights for AI scouting reports). See [Repository layout](docs/ARCHITECTURE.md#repository-layout) in ARCHITECTURE.md for what each will hold.

## 4. Documentation

Read the documents in this order. Each owns one kind of fact.

1. [docs/CONTEXT.md](docs/CONTEXT.md): the draft proposal and baseline. Objectives, KDD strategy, modeling methodology, and the baseline schedule.
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the software architecture. Components, contracts, data flow, deployment, and the ADRs.
3. [docs/ML_ARCHITECTURE.md](docs/ML_ARCHITECTURE.md): the ML design checklist, ordered by pipeline stage, with decisions recorded as they are made.
4. [docs/WORK_PLAN.md](docs/WORK_PLAN.md): the schedule, actual progress, variances, and the decision log. Current status lives there.
5. [docs/REPORT_NOTES.md](docs/REPORT_NOTES.md): empirical findings, data difficulties, and methodological trade-offs written in Spanish for the final report.
6. [docs/TRANSFORM_PLAN.md](docs/TRANSFORM_PLAN.md): the working plan and experiment log for the completed `transform` stage.

AI agents also read [AGENTS.md](AGENTS.md) for global team conventions, [ml/AGENTS.md](ml/AGENTS.md) for the ML component's dev commands, and [backend/AGENTS.md](backend/AGENTS.md) for the backend service conventions.

## 5. See also

- [AGENTS.md](AGENTS.md)
- [ml/AGENTS.md](ml/AGENTS.md)
- [backend/AGENTS.md](backend/AGENTS.md)
- [docs/WORK_PLAN.md](docs/WORK_PLAN.md)
- [docs/REPORT_NOTES.md](docs/REPORT_NOTES.md)
- [docs/TRANSFORM_PLAN.md](docs/TRANSFORM_PLAN.md)
- [.env.example](.env.example)

## 6. License

This project is under the BSD 3-Clause license. See [LICENSE](LICENSE) for the full text.
