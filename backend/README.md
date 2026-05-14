# Celonis CI — Backend

Python 3.11+ service built on FastAPI, LangGraph, and Supabase.
Project context, architecture, and conventions live in the root project guide.

## Setup

```bash
# from the backend/ directory
uv sync
cp ../.env.example ../.env   # then fill in keys
```

## Run

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is then available at <http://localhost:8000>.

- `GET /` — service identity
- `GET /health` — liveness probe

## Lint, type-check, test

```bash
uv run ruff check .
uv run ruff format .
uv run mypy app
uv run pytest
```

## OneDrive + uv hard-link workaround

This repo lives in a OneDrive-synced folder. OneDrive's reparse points block
uv's default hard-linking strategy, producing `Failed to hard-link files`
warnings during `uv sync` and `uv add`. We force copy mode instead.

`backend/.env` sets `UV_LINK_MODE=copy`, which uv reads automatically.

If you want this set globally for your Windows user (so it also applies in
fresh shells outside this repo), run **once** in PowerShell:

```powershell
[Environment]::SetEnvironmentVariable("UV_LINK_MODE", "copy", "User")
```

Restart your terminal afterwards. Verify with `echo $env:UV_LINK_MODE`.

## Layout

```
app/
  api/              FastAPI routes
  agents/           Capability workflows (LangGraph subgraphs)
  orchestration/    Chat orchestrator + workflow engines
  synthesis/        Correlation, critic, writer
  ingestion/        Source connectors (news, financial, ...)
  rag/              Retrieval logic (self-query, hybrid search)
  llm/              LLM provider abstraction
  prompts/          Centralised prompt templates
  models/           Pydantic schemas
tests/
  unit/
  integration/
scripts/            One-off and operational scripts
```
