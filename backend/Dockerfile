# -----------------------------------------------------------------------
# Celonis CI — Backend container
# Optimised for Railway: uv for fast installs, $PORT injected at runtime.
# -----------------------------------------------------------------------

FROM python:3.11-slim

# uv binary — fetched from the official image so it is cached independently
# of the source layer and does not require pip or curl.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependency layer — copied separately so Docker cache is reused when only
# source files change.
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

# Application source
COPY app/ ./app/

# Railway injects PORT at runtime; default to 8000 for local docker runs.
CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
