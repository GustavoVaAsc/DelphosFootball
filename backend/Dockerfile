FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app/backend

# Copy backend project files
COPY backend/pyproject.toml backend/README.md ./

# Copy the delphos-domain path dependency to where backend/pyproject.toml's
# [tool.uv.sources] points (`../ml/src` -> `/app/ml/src`). It is dependency-free,
# so it adds nothing to the install tree beyond its own two modules.
COPY ml/src/pyproject.toml ../ml/src/
COPY ml/src/delphos_domain ../ml/src/delphos_domain

# Install dependencies
RUN uv sync --no-dev

# Copy source code
COPY backend/src ./src

# Expose API port
EXPOSE 8000

# Start Uvicorn web server
CMD ["uv", "run", "uvicorn", "delphos_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

