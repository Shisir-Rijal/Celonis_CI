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

## Agents

### Research Agent

The Research Agent is the foundation for all other agents. It scrapes a comprehensive competitive profile for a given company domain once a day. All downstream agents read from this profile and pick the data relevant to their task.

#### State (`state.py`)

Each node has its own Pydantic model (e.g. `NewsData`, `FinancialData`). All node models are combined into `ResearchState` — a LangGraph `TypedDict` that is passed through the graph. It also tracks `completed_nodes` and `errors` (both use `operator.add` so parallel nodes can write safely).

For downstream use, `CompetitorProfile` is the clean output model. It is constructed from a finished `ResearchState` via `CompetitorProfile.from_state(state)` and requires a `domain` and optional `company_name`.
Within the CompanyProfile all necessary data of one competitor will be saved.

#### Nodes

All nodes run **in parallel** (see Graph section below). Each node writes only into its own slice of the state.

| Node | What it does |
|------|-------------|
| **Events** | Searches for events via Serper on the company website, Meetup, and Luma. Also runs a general Google + news search. GPT-4o-mini extracts structured event data (name, dates, location, speakers, sponsors, summary) from the scraped markdown. Results are split into `website_events`, `luma_events`, `meetup_events`, and `reported_events`. |
| **Financials** | Looks up the company's stock ticker via Finnhub. If publicly traded: fetches current price, daily change, 5-year monthly price history (via yfinance), and analyst buy/hold/sell ratings (via Serper + GPT-4o-mini extraction). Returns `on_stock_market: false` for private companies. |
| **News** | Aggregates articles from three sources: Finnhub (for listed companies), Serper news search with full-text scraping of the top 5 articles via Firecrawl, and the company's own newsroom/blog discovered via Serper and individually scraped. |
| **Newsletter** | Checks a local JSON file whether the company has already been subscribed to. If not, it finds the newsletter signup form on the company website via Serper + Firecrawl, fills it in (using `celonisdashboard@gmail.com`), and submits it. On every run it then fetches received newsletter emails from that Gmail inbox via the Gmail API. |
| **Positioning** | Scrapes three page types in parallel: the About/Mission/Vision/Values page, the Careers/Employer page, and the Blog listing. GPT-4o-mini extracts `purpose`, `vision`, `mission`, `company_values`, `employer_values`, `employer_positioning`, and full blog post content. |
| **SeoGeo** | Checks visibility for ~27 fixed industry keywords across two dimensions. **SEO**: queries Serper for each keyword and checks whether the competitor's domain appears in the top 50 Google results. **GEO**: asks GPT-4o-mini (and optionally Gemini) which companies are the leading providers for each keyword, checking whether the competitor is mentioned by name. |
| **Socials** | Fetches social profile links (LinkedIn, Twitter/X, Instagram, YouTube, TikTok, Facebook) via the Brandfetch API. For YouTube, additionally fetches channel stats (subscriber count, video count, description) and the 10 most recent videos with view/like/comment counts via the YouTube Data API. Also runs a YouTube keyword search for the company name. |
| **Visuals** | Maps up to 5 pages of the company website via Firecrawl. Extracts logos and primary colors from Brandfetch, secondary colors from CSS `<style>` blocks parsed by GPT-4o-mini, fonts from Brandfetch / Google Fonts links / CSS declarations (with a GPT-4o-mini fallback), plus all images and embedded video URLs found in HTML and markdown. |
| **Wording** *(pending)* | Planned node for scraping the company's language, tone, and copywriting style. |

#### Graph (`graph.py`)

All 8 active nodes are wired **directly from `START` to `END`** — there are no sequential dependencies between them. LangGraph executes them fully in parallel via `asyncio`.

```
START ──┬── events ──────┐
        ├── financials ──┤
        ├── news ─────── ┤
        ├── newsletter ──┤──▶ END
        ├── positioning ─┤
        ├── seogeo ───── ┤
        ├── socials ──── ┤
        └── visuals ─────┘
```

The compiled graph is exported as `app` and invoked with `await app.ainvoke(initial_state)`. After completion, `state["completed_nodes"]` lists every node that succeeded and `state["errors"]` collects any that failed, without stopping the rest.

#### Important to know

The Research Agent requires the following API keys and credentials. To get access, contact **Nadja Müller**.

| API / Service | Key / Credential | Used by |
|---|---|---|
| [Serper](https://serper.dev) | `SERPER_API_KEY` | Events, Financials, News, Newsletter, Positioning, SeoGeo |
| [Firecrawl](https://firecrawl.dev) | `FIRECRAWL_API_KEY` | Events, News, Newsletter, Positioning, Visuals |
| [OpenAI](https://platform.openai.com) | `OPENAI_API_KEY` | Events, Financials, News, Positioning, SeoGeo, Visuals |
| [Finnhub](https://finnhub.io) | `FINNHUB_API_KEY` | Financials, News |
| [Brandfetch](https://brandfetch.com) | `BRANDFETCH_API_KEY` | Socials, Visuals |
| [YouTube Data API v3](https://console.cloud.google.com) | `YOUTUBE_API_KEY` | Socials |
| [Gmail API](https://console.cloud.google.com) | `data/gmail_token.json` (OAuth token) | Newsletter |
| [Gemini](https://aistudio.google.com) | `GEMINI_API_KEY` | SeoGeo *(optional — GEO check via Gemini)* |

> `yfinance` (used in Financials for price history) pulls public data and requires no API key.




