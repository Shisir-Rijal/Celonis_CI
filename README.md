# Celonis CI

A multi-agent system for competitive intelligence and brand analysis,
built as a university project in collaboration with
Celonis. It tracks competitor activity across public data sources, analyses
it through specialised capability workflows, and surfaces correlations and
insights through a chat interface and autonomous scheduled workflows.

## Tech stack

**Backend** — Python 3.11+, FastAPI, LangGraph, LangChain, Pydantic,
Supabase (Postgres + pgvector), ARQ + Redis, FireCrawl, structlog.
Packaged with `uv`.

**Frontend** — Next.js 15 (App Router), TypeScript, Tailwind CSS,
TanStack Query, Recharts.

**Infra** — Supabase, Upstash Redis (planned), backend host TBD, Vercel
for the frontend.

## Repo structure

```
Celonis_CI/
├── backend/             FastAPI + LangGraph service (Python, uv)
│   ├── app/             api, agents, orchestration, synthesis,
│   │                    ingestion, rag, llm, prompts, models
│   ├── tests/           unit, integration
│   └── scripts/
├── frontend/            Next.js + TS + Tailwind
│   └── src/             app, components, lib
├── docs/                Architecture decisions and longer-form notes
└── .env.example         Environment variable template
```

## Setup

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20+.

```bash
git clone <repo-url> && cd Celonis_CI
cp .env.example .env           

# Backend
cd backend
uv sync

# Frontend
cd ../frontend
npm install
```

## Run locally

```bash
# Backend (from backend/)
uv run uvicorn app.main:app --reload --port 8000

# Frontend (from frontend/, separate terminal)
npm run dev
```

Backend: <http://localhost:8000>. Frontend: <http://localhost:3000>.

## Documentation

- `docs/architecture.md` — architecture decisions and notes
- Backend: see [`backend/README.md`](backend/README.md) for run, lint, test,
  and the OneDrive/`uv` hard-link workaround.
