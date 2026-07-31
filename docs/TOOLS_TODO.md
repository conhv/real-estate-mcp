# Tools — Student Implementation Checklist

This is the build list. Each tool has: the User Story it serves, its signature, what it must
return, and acceptance checks. The **scaffold is already in place** — for phase-1 tools your job is
to read the provided implementation, confirm it against the live DB, and check the boxes (or
improve). Phase-2 tools are yours to build from the spec.

**Ground rules (apply to every tool):**
- Tool = thin wrapper in `src/app/tools/`; DB logic in `src/app/services/`.
- Type every parameter; optionals as `X | None = None`; give `limit` a sane default.
- Docstring must say *what it does / when to use / what it returns* — the agent reads only that.
- Return JSON-serializable data shaped in `shaping.py`. Never return raw rows.
- Not-found / bad input → raise `fastmcp.exceptions.ToolError`. Never leak keys or stack traces.
- Verify against the real schema in `docs/SCHEMA.md`. Re-introspect with the Supabase MCP if unsure.

**How to test:** full guide in [TESTING.md](TESTING.md). Quick version — level-1 tests need no DB:
```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests/test_shaping.py tests/test_server_tools.py -v   # no DB
.\.venv\Scripts\python.exe -m pytest tests/test_live_db.py -v                              # needs .env
```
Or test one tool interactively:
```python
import asyncio
from app.server import mcp
print(asyncio.run(mcp.call_tool("search_projects", {"query": "Vinhomes"})).data)
```
Valid sample ids for testing are in `tests/conftest.py`.

---

## Phase 1 — implemented; verify & harden

### US1 — Search by project / province
- [ ] **`search_projects(query, province, limit)`** → list of project nodes.
  - Verify it returns 1–3 for a clear name and several for a partial (e.g. "chung cu").
  - Harden: switch `ilike` → `pg_trgm similarity` + `unaccent` so "vinhome"/"Vinhomes" and
    accent-insensitive queries match. (extensions available; see SCHEMA.md)
- [ ] **`resolve_project(text)`** → `{matched, project, candidates}`.
  - Exactly one match → `matched=true`; several → `matched=false` + candidates; none → empty.
- [ ] **`list_project_buildings(project_id, limit)`** → child location nodes.
- [ ] **`list_provinces()`** → sorted distinct provinces having a project.
- [ ] **`search_listings(project_id, property_type, min_price_vnd, max_price_vnd, bedrooms, limit)`**
  - Confirm price bounds filter in SQL; confirm `bedrooms` post-filter works (field is text!).
  - Confirm invalid `property_type` raises with the valid list.
- [ ] **`get_listing(listing_id)`** → full detail; raises if missing.
- [ ] **`list_project_listings(project_id, limit)`** → all units in a project ("xem tất cả").
- [ ] **`listing_cta_actions(listing_id)`** → the 4 CTA buttons + `next_tool` for each.
  - UI rule to enforce upstream: 1–3 results show cards+CTAs; >3 show "xem tất cả".

### US2.1 — Book a site visit
- [ ] **`start_visit_booking(project_id, is_authenticated)`** → form spec.
  - Guest form asks name/phone/email/time/note; authed form only time/note.
  - Raises if `project_id` isn't a real project.

### US2.2 — Buyer consultation
- [ ] **`start_consultation(project_id, is_authenticated)`** → form spec (same auth split).

### US4 — Project overview
- [ ] **`project_overview(project_id)`** → `{project, stats}` with count, price/price-per-m2 min/max/avg,
  bedrooms range, property-type mix. **Descriptive only** — no valuation/advice.

### US5 — Map
- [ ] **`map_listings(project_id, limit)`** → `{count, points:[{id,title,property_type,price_vnd,lat,lng}]}`.

### US6 — Compare
- [ ] **`compare_listings(listing_ids)`** → `{listings, fields}`; enforces 2–4 distinct ids;
  raises listing ids that don't exist.

---

## Phase 2 — build these (specs only; not implemented)

### US3 / RAG — Policy / FAQ / legal Q&A  ← the big one
File: `src/app/tools/rag.py` (tool `answer_project_policy` is defined but **disabled**).
The DB has **no documents table** and **pgvector is not installed** yet.

- [ ] **DB setup (migration):** `CREATE EXTENSION vector;` then a `documents` table:
      `(id, project_id, doc_type, source_url, chunk_index, content text, embedding vector(<dim>))`.
      Add an HNSW index on `embedding`. Load the `supabase:supabase-postgres-best-practices` skill
      before writing this migration.
- [ ] **Ingestion job:** fetch each project's policy/FAQ/legal/amenity docs → chunk → embed → insert.
      (Celery/Arq per PRD; can start as a script.)
- [ ] **Hybrid retrieval (Postgres RPC `hybrid_search_docs`):** BM25/full-text (pgroonga or
      tsvector) **+** vector search, merged with **RRF**, then **rerank** (cross-encoder).
- [ ] **Implement `answer_project_policy(project_id, question, doc_type)`** →
      `{answer, sources:[{doc_id, chunk, score}], confident}`.
- [ ] **Guardrail (mandatory):** if the top retrieval score is **below the threshold**, set
      `confident=false` and return the standard refusal offering a human advisor — do **not**
      fabricate. This is the PRD's hallucination<1% requirement (US3 explicitly requires the refusal).
- [ ] Enable the tool: remove the `mcp.disable(...)` line in `rag.py`.

### Booking persistence (upgrade US2.1/US2.2 from form-spec to real write)
- [ ] Create a `bookings` table `(id, project_id, kind, contact jsonb, preferred_time, note, created_at)`.
- [ ] Add **`submit_booking(kind, project_id, payload)`** tool that validates and inserts, returns
      a confirmation id. (This is a *write* — think about RLS and rate-limit before enabling.)

### Search-quality upgrades
- [ ] Normalize numeric listing columns (generated columns or a cleaned view) so `bedrooms`/`area_m2`
      range-filter in SQL, and drop the Python post-filter in `search_listings`.
- [ ] Add **`search_listings_by_province(province, ...)`**: resolve province → project ids via
      `locations`, then filter listings (recall: `listing` has no province column).
- [ ] Move `project_overview` stats to a Postgres RPC so it doesn't fetch every row.

### Optional (nice-to-have)
- [ ] **`nearby_listings(lat, lng, radius_m, limit)`** using `earthdistance`/`postgis`.
- [ ] Expose a **resource** `realestate://project/{id}` (read-only project profile) via `@mcp.resource`.

---

## Definition of Done (per tool)
- [ ] Typed signature + model-facing docstring (what/when/returns).
- [ ] DB access in a `services/` function; tool body is thin.
- [ ] Returns shaped JSON; errors are `ToolError`.
- [ ] `mcp.call_tool(...)` returns correct data against the live DB.
- [ ] Appears in `mcp.list_tools()` (or intentionally disabled with a comment saying why).
