# DelphosFootball Backend

FastAPI service serving outfield player valuations, tactical replacements, and cluster profiles from PostgreSQL (`analytics` schema) to the Flutter Web client.

## Quickstart

Run all commands from `backend/`. Requires [uv](https://docs.astral.sh/uv/) and a running PostgreSQL instance (via `docker compose up -d` at repository root).

```bash
cd backend
uv sync
uv run pytest
uv run uvicorn delphos_backend.main:app --reload --port 8000
```

Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

## Endpoints overview

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health/live` | Kubernetes liveness probe (checks process health) |
| `GET` | `/health/ready` | Readiness probe (verifies database connectivity and active model run) |
| `GET` | `/players` | Search and filter active outfield players (name, position, valuation status, cluster) |
| `GET` | `/players/{id}` | Full player profile, latest season stats, and tactical cluster mapping |
| `GET` | `/players/{id}/valuation` | Fair value prediction, actual market value, and valuation status badge |
| `GET` | `/players/{id}/replacements` | Precomputed top-3 cheaper tactical replacements with similarity and savings |
| `GET` | `/clusters` | Catalog of K-Means tactical clusters with centroids and descriptions |
| `POST` | `/reports/generate` | Generate (or return cached) AI scouting report for a player via local `llama.cpp` |
| `GET` | `/reports` | List persisted scouting reports for the active model run |
| `GET` | `/reports/{id}` | Retrieve a persisted scouting report by ID |

## Environment variables

Configured via environment variables or root `.env`:

| Variable | Default | Description |
| --- | --- | --- |
| `DELPHOS_BACKEND_PORT` | `8000` | Port to bind the FastAPI server |
| `DELPHOS_BACKEND_HOST` | `0.0.0.0` | Host interface |
| `DELPHOS_DATABASE_APP_URL` | `postgresql://delphos_app_user:delphos_app_pass@localhost:5432/delphos` | Database connection string |
| `DELPHOS_BACKEND_CORS_ORIGINS` | `*` | Allowed CORS origins for frontend client |
| `DELPHOS_DATABASE_POOL_MIN` | `2` | Minimum connection pool size |
| `DELPHOS_DATABASE_POOL_MAX` | `10` | Maximum connection pool size |
