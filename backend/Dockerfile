FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app/backend

# Copy backend project files
COPY backend/pyproject.toml backend/README.md ./

# Install dependencies
RUN uv sync --no-dev

# Copy source code
COPY backend/src ./src

# Expose API port
EXPOSE 8000

# Start Uvicorn web server
CMD ["uv", "run", "uvicorn", "delphos_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

