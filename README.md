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

Run these from `ml/`. You need [uv](https://docs.astral.sh/uv/); it installs Python 3.13 if the machine lacks it. No Kaggle credentials are needed.

```
cd ml
uv sync
uv run pytest
uv run delphos-pipeline --help
uv run delphos-pipeline ingest
```

The first `ingest` needs about 1 GiB of free RAM and about 1.1 GB of disk: about 873 MiB for the kagglehub cache plus about 228 MiB in `ml/data/ingest/`.

To override a default setting, copy `.env.example` to `.env` at the repo root and uncomment the line you want. The pipeline walks up from the working directory and reads the first `.env` it finds, stopping after the repo root, which is the parent of the project root `ml/`, so a repo-root `.env` applies when you run from `ml/`; a `.env` above the repo root is never read.

## 3. Repository layout

Each root file sits where its tool looks for it, so none of them can move into a subfolder.

| Path | What it is | Why it lives there |
| --- | --- | --- |
| `.env.example` | The configuration keys documented for every component. Copy it to `.env` at the repo root (gitignored). | It is the global key list for all components, and the repo root is the documented `.env` location. |
| `.gitignore` | Files Git leaves out: secrets, generated outputs, virtual environments. | Git reads it from the repo root. |
| `ml/.python-version` | Pins Python 3.13 for uv. | uv reads it in the component's own uv project, `ml/`. |
| `AGENTS.md` | Shared instructions for any AI coding agent. | Agent tools discover it only at the repo root. |
| `README.md` | This file. | It is the entry point of the repository. |
| `ml/pyproject.toml` | The uv project for `delphos_ml`: project metadata, the dev dependency group, and the pytest and ruff configuration. | Each Python component owns its own uv project ([ADR-013](docs/ARCHITECTURE.md#adr-013-per-component-uv-projects-over-a-root-uv-workspace)). |
| `ml/uv.lock` | The lockfile of the `ml/` component ([ADR-013](docs/ARCHITECTURE.md#adr-013-per-component-uv-projects-over-a-root-uv-workspace)). | uv writes it beside its project, and the pipeline anchors a relative `DELPHOS_DATA_DIR` on the nearest `uv.lock`. |
| `docs/` | The project documents; see [Documentation](#4-documentation). | One folder keeps the documents together. |
| `ml/` | The `delphos_ml` uv project: the package and pipeline stages under `ml/src/`, tests in `ml/tests/`, stage outputs in `ml/data/<stage>/` (gitignored), and its own `pyproject.toml`, `uv.lock`, and `.python-version`. | It is the only Python component today; `backend/` gets its own uv project and lockfile when it lands (ADR-013). |

Planned, not yet created: `analysis/`, `backend/`, `frontend/`, `migrations/`, `artifacts/`, and `llms/models/`. See [Repository layout](docs/ARCHITECTURE.md#repository-layout) in ARCHITECTURE.md for what each will hold.

## 4. Documentation

Read the documents in this order. Each owns one kind of fact.

1. [docs/CONTEXT.md](docs/CONTEXT.md): the draft proposal and baseline. Objectives, KDD strategy, modeling methodology, and the baseline schedule.
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the software architecture. Components, contracts, data flow, deployment, and the ADRs.
3. [docs/ML_ARCHITECTURE.md](docs/ML_ARCHITECTURE.md): the ML design checklist, ordered by pipeline stage, with decisions recorded as they are made.
4. [docs/WORK_PLAN.md](docs/WORK_PLAN.md): the schedule, actual progress, variances, and the decision log. Current status lives there.

AI agents also read [AGENTS.md](AGENTS.md) for the global team conventions and [ml/AGENTS.md](ml/AGENTS.md) for the ML component's dev commands.

## 5. See also

- [AGENTS.md](AGENTS.md)
- [ml/AGENTS.md](ml/AGENTS.md)
- [docs/WORK_PLAN.md](docs/WORK_PLAN.md)
- [.env.example](.env.example)

## 6. License

This project is under the BSD 3-Clause license. See [LICENSE](LICENSE) for the full text.
