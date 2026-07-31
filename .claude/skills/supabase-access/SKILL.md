---
name: supabase-access
description: Use when a FastMCP tool in this project needs to read/write the Supabase Postgres database — creating the Supabase client, querying projects/properties tables, running RPC/SQL for hybrid search, choosing anon vs service-role key, or handling RLS. Triggers on Supabase, supabase-py, "query the database", "get the client", pgvector, RPC, RLS in this repo. For broad Supabase product questions (Auth, Edge Functions, migrations) defer to the official `supabase:supabase` skill.
---

# Supabase access for this project

The real-estate data lives in a Supabase Postgres project (`etmrjxsxwsecvwvexvbq`).
FastMCP tools read it through the **supabase-py** client (installed: `supabase` 2.31 in `.venv`).
This skill covers the *access pattern* used by the MCP tools. For Supabase-product topics
(migrations, RLS design, Edge Functions, pgvector setup), use the official `supabase:supabase` skill.

## The one client, created once
Never construct a client per call. Put this in `src/app/db.py`:
```python
import os
from functools import lru_cache
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

@lru_cache(maxsize=1)
def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]  # server-side MCP → service role
    return create_client(url, key)
```
- **Key choice:** the MCP server runs server-side (trusted), so use the **service-role key** to
  bypass RLS for read tools. Keep it ONLY in `.env` (gitignored). Never expose it to the browser
  or embed it in agent prompts.
- `.env.example` documents required vars: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.

## Querying (PostgREST via supabase-py)
```python
from app.db import get_client

def fetch_projects(province: str | None, limit: int):
    q = get_client().table("projects").select("id,name,province,developer")
    if province:
        q = q.ilike("province", f"%{province}%")
    return q.limit(limit).execute().data   # .data is a list[dict] — return that
```
- Always `.select(...)` explicit columns — never `select("*")` in a tool (leaks internals, bloats tokens).
- `.execute().data` is the list of rows; return it (or a reshaped subset) directly.
- Use `.ilike` for fuzzy Vietnamese name matches, `.eq` for exact ids, `.in_()` for id lists.

## Hybrid / vector search → Postgres RPC
BM25 + vector + RRF + rerank (per PRD) belong in a **Postgres function**, called via RPC — not
reimplemented in Python. Define the SQL function in a migration, then:
```python
get_client().rpc("hybrid_search_properties",
                 {"query_text": q, "query_embedding": emb, "match_count": k}).execute().data
```
When writing/altering that SQL function, migrations, indexes, or RLS, **load the
`supabase:supabase-postgres-best-practices` skill first** — it has the rules for types, indexes,
pgvector, and function safety.

## Schema conventions (fill in after introspecting the live DB)
The two editor tabs in the task point at specific tables. Confirm exact names/columns by
introspecting (Supabase MCP `list_tables`, or `information_schema`) before writing tools.
Document the real schema in `docs/SCHEMA.md`. Expected core tables (verify!):
- `projects` — real-estate projects (id, name, province, developer, ...).
- `properties` / `units` — individual properties/apartments linked to a project.
- a documents/embeddings table for RAG (policies, FAQ, legal) with a `pgvector` column.

## Do / Don't
- DO shape rows for the agent; DO handle "no rows" as an empty list, not an error.
- DO wrap DB errors and return a clean `{"error": "..."}` or raise a `ToolError` — never leak DSNs/keys.
- DON'T put SQL string-building for user input into f-strings; use PostgREST filters or parameterized RPC.
- DON'T call the DB from inside the `@mcp.tool` body directly — go through a `db.py`/service module.

## References
- supabase-py docs: https://supabase.com/docs/reference/python
- Live schema introspection: use the Supabase MCP server (authenticate via the plugin) or `docs/SCHEMA.md`.
- Postgres/RLS/pgvector rules: `supabase:supabase-postgres-best-practices` skill.