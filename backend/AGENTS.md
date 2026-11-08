# DelphosFootball Backend Guide

## Table of contents

1. [What this component is](#1-what-this-component-is)
2. [Dev commands](#2-dev-commands)
3. [Layout](#3-layout)
4. [Database & role rules](#4-database--role-rules)

---

## 1. What this component is

`backend/` is the FastAPI REST service for DelphosFootball. It serves player profiles, valuation predictions, and precomputed tactical replacements to the Flutter client, connecting to PostgreSQL as `delphos_app_user`.

## 2. Dev commands

Run every uv command from `backend/`:

| Task | Command |
| --- | --- |
| Install dependencies | `uv sync` |
| Start dev server | `uv run uvicorn delphos_backend.main:app --reload --port 8000` |
| Run tests | `uv run pytest` |
| Check linter | `uv run ruff check .` |
| Format code | `uv run ruff format .` |

## 3. Layout

```
backend/
├── src/delphos_backend/
│   ├── core/           # Configuration, lifecycle, and connection pool
│   ├── api/            # Route controllers grouped by resource (health, players, clusters, reports)
│   ├── schemas/        # Pydantic request/response models
│   ├── repositories/   # SQL queries against PostgreSQL schemas
│   ├── services/       # Local LLM context assembly and OpenAI-compatible HTTP client
│   └── main.py         # FastAPI application factory
├── tests/              # Pytest test suite using httpx.AsyncClient
├── Dockerfile          # Production container build
└── pyproject.toml      # uv package definition
```

## 4. Database & role rules

- The backend connects exclusively as `delphos_app_user` (ADR-002).
- It has read-only `SELECT` access to `analytics.*` and full CRUD access to `app.*`.
- Active model runs are resolved dynamically via `SELECT model_run_id FROM analytics.model_runs WHERE status = 'active'`.
- All database interactions use parameterized queries through `psycopg_pool.AsyncConnectionPool` to prevent SQL injection.
- Modules must not exceed roughly 130 lines without being split (`AGENTS.md` §4).

