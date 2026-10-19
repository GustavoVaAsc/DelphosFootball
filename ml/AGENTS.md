# DelphosFootball ML component instructions

## Table of contents

1. [Scope](#1-scope)
2. [Layout](#2-layout)
3. [Dev commands](#3-dev-commands)
4. [Pipeline conventions](#4-pipeline-conventions)
5. [Configuration](#5-configuration)
6. [See also](#6-see-also)

---

## 1. Scope

This file covers `ml/` only: the `delphos_ml` package, the pipeline CLI, its tests, and its stage outputs. The global conventions (language, commits and branches, decision records, the `.env.example` key list) live in the [root AGENTS.md](../AGENTS.md); follow both when you work here.

## 2. Layout

| Path | What it is |
| --- | --- |
| `pyproject.toml` | The uv project: metadata, the `dev` dependency group, and the pytest and ruff configuration. |
| `uv.lock` | This component's lockfile (`ml/` is its own uv project, ADR-013). |
| `.python-version` | Pins Python 3.13 for uv. |
| `src/delphos_ml/` | The package; `pipeline/` holds one module per stage. |
| `tests/` | pytest unit tests for `delphos_ml`. |
| `data/<stage>/` | Stage outputs (gitignored). From the repo root this path is `ml/data/<stage>/`. |

## 3. Dev commands

Run these from `ml/`.

| Command | Purpose |
| --- | --- |
| `uv sync` | Install the project and the `dev` group into `ml/.venv` |
| `uv run delphos-pipeline --help` | List the pipeline stages |
| `uv run delphos-pipeline ingest` | Download the pinned Kaggle dataset into `ml/data/ingest/` |
| `uv run pytest` | Run the tests |
| `uv run ruff check` | Lint |
| `uv run ruff format --check` | Check formatting; `uv run ruff format` fixes it |

`ingest` needs about 1 GiB of free RAM and about 1.1 GB of disk (the kagglehub cache plus `ml/data/ingest/`).

## 4. Pipeline conventions

- One stage is one module with one entry function; the function's docstring is the command's `--help` text.
- A stage exits 0 on success and 1 on an expected failure, printing `<stage> failed: <reason>` to stderr.
- Stages exchange Parquet files under `data/<stage>/`; only `publish` writes to the database (ADR-008).
- Ingest is a faithful text-only copy of the source; typing and cleaning happen only in `clean` (ADR-012).

ADRs are in [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) §10; the ML design decisions are in [docs/ML_ARCHITECTURE.md](../docs/ML_ARCHITECTURE.md).

## 5. Configuration

Settings come from `DELPHOS_` environment variables; [.env.example](../.env.example) at the repo root documents every key and is also the documented location for a local `.env`. The pipeline walks up from the working directory and reads the first `.env` it finds, stopping after the repo root, which is the parent of the project root `ml/`, so a `.env` at the repo root applies when you run commands from `ml/`; a `.env` above the repo root is never read. A relative `DELPHOS_DATA_DIR` resolves against the project root, the nearest directory containing `uv.lock`, which is `ml/` here. Details: [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) §9.

## 6. See also

- [root AGENTS.md](../AGENTS.md): the global conventions.
- [README.md](../README.md): the entry point.
- [docs/ML_ARCHITECTURE.md](../docs/ML_ARCHITECTURE.md): the ML design checklist and its decisions.
- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md): the architecture and the ADRs.
- [.env.example](../.env.example): the configuration variables and their defaults.
