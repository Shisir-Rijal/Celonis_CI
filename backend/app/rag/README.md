# RAG Store

Single-corpus vector + keyword store backed by Supabase Postgres with pgvector.

## Applying the migration

### Prerequisites

1. A Supabase project (free tier works).
2. `pgvector` extension enabled:
   - Supabase Dashboard → **Database → Extensions → Search for "vector" → Enable**.

### Apply via Supabase SQL Editor

1. Open the Supabase Dashboard for your project.
2. Go to **SQL Editor → New query**.
3. Paste the contents of `backend/scripts/migrations/001_chunks.sql`.
4. Click **Run**.

The migration is idempotent (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`)
— safe to run again on an already-migrated project.

### Apply via psql (optional)

```bash
psql "$DATABASE_URL" -f backend/scripts/migrations/001_chunks.sql
```

Where `DATABASE_URL` is the direct Postgres connection string from
Supabase Dashboard → **Settings → Database → Connection string (URI)**.

## Environment variables

Add these to `.env` (see `.env.example`):

```
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
```

The backend uses the **service-role key** for all write operations
(bypasses Row Level Security). The anon key is reserved for future
client-side access once RLS policies are set up.

## Module layout

| File | Purpose |
|---|---|
| `supabase_client.py` | Module-level `Client` via `get_supabase()`, created once |
| `repository.py` | `insert_chunk`, `insert_chunks`, `get_chunk_by_id` |

## Running the integration smoke test

```bash
# Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env
uv run pytest backend/tests/integration/test_supabase_smoke.py -v -m integration
```

The test inserts one row and reads it back. It is excluded from the default
`pytest` run to keep CI clean when no Supabase project is available.
