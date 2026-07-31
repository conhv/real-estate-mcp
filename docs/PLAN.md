# Implementation Plan — Real Estate MCP

This plan turns the PRD (`docs/PRD_LeDuyHung.pdf`) into a buildable FastMCP server whose tools a
LangGraph agent will call later. It states the architecture, why the tools are shaped the way they
are, and a phased path from "tools work" to "agent deployed".

## 1. Where the MCP fits in the PRD architecture
The PRD's AI pipeline is:
`User → Guardrail → Intent Detection → Entity Extraction → Conversation Manager → **Tool Calling Layer** → Response Composer → UI`.

**This repo builds the Tool Calling Layer only** — the MCP server + its tools. The agent
(LangGraph supervisor, intent/entity/slot-filling, Langfuse tracing, SSE streaming, Redis session)
is a *separate* layer that will connect to this MCP server over HTTP and call these tools. Keeping
the tools in an MCP server (not hardcoded in the agent) is exactly the PRD's "MCP as tool protocol"
choice and lets us swap/redeploy the agent independently.

Boundary rule (from the PRD "Out of Scope"): tools return **descriptive data only** — no valuation,
no financing/mortgage math, no investment recommendation. Enforced in tool docstrings + server
instructions so the agent won't be tempted to synthesize advice.

## 2. Data model reality (see docs/SCHEMA.md)
Two useful tables: `locations` (project/cluster/building tree) and `listing` (1748 units). There is
**no projects table** (projects are `locations` rows) and **no RAG store yet**. Numeric listing
fields are text; `status` has an encoding bug. All of this is absorbed in `shaping.py` so tools
return clean typed JSON.

## 3. Design principles for the tools
1. **One MCP server, thin tools.** `@mcp.tool` functions validate input and shape output; all DB
   access is in `services/`. Business rules stay testable and out of the protocol layer.
2. **Tools map to User Stories.** Each tool names its US in the docstring so the agent (and the
   grader) can trace coverage.
3. **The docstring is the contract.** The agent selects tools purely from name + description +
   typed params. Write them for a model: say *what it does*, *when to use it*, *what it returns*.
4. **Project-first flow.** Almost every US requires knowing the project. Tools are ordered so the
   agent resolves the project (`search_projects`/`resolve_project`) before searching/among/booking.
5. **Return UI-action payloads, not prose, for CTAs.** Booking/consult tools return a *form spec*
   (fields depend on auth state) the frontend renders — matching the PRD "Action Triggering".
6. **No secrets in code**; service-role key from `.env`. Errors become `ToolError`, never leak DSNs.

## 4. Tool ↔ User Story coverage (phase 1, all implemented)
| Tool | User Story | Purpose |
|---|---|---|
| `search_projects` | US1 | find projects by name/province (quick-pick buttons) |
| `resolve_project` | US1/2.1/2.2/3 | slot-filling: is this text a known project? |
| `list_project_buildings` | US1 | drill into a project's buildings |
| `list_provinces` | US1 | offer location choices |
| `search_listings` | US1 | filtered unit search within a project |
| `get_listing` | US1 | listing detail page |
| `list_project_listings` | US1 | the "xem tất cả" list |
| `compare_listings` | US6 | side-by-side comparison of 2–4 units |
| `project_overview` | US4 | descriptive price/area/type stats per project |
| `map_listings` | US5 | lat/lng points for the map view |
| `start_visit_booking` | US2.1 | site-visit form spec (authed vs guest) |
| `start_consultation` | US2.2 | consultation form spec (authed vs guest) |
| `listing_cta_actions` | US1 | the CTA buttons + which tool each triggers |
| `answer_project_policy` | US3 | **phase 2, disabled** — policy/FAQ RAG w/ refusal guardrail |

## 5. Phasing
**Phase 1 — Tools over real data (this repo).** ✅ Server + 13 tools + schema/plan/todo docs +
skills. RAG intentionally skipped (stubbed + documented). Verified: server loads, all tools list.

**Phase 2 — Data quality + search quality.**
- Normalize numeric columns (generated columns or a cleaned view) so range filters run in SQL.
- Fuzzy Vietnamese search: `pg_trgm` + `unaccent` for `search_projects`.
- Move `project_overview` aggregation to a Postgres RPC (avoid pulling all rows).
- RAG (US3): install `vector`, create `documents` table, ingest policy/FAQ/legal, hybrid search
  (pgroonga/BM25 + vector) merged by RRF, rerank, and **enforce the similarity threshold refusal**
  (the PRD's hallucination<1% guardrail). Then enable `answer_project_policy`.
- Persist bookings/consultations (write path + `bookings` table) instead of only returning form specs.

**Phase 3 — Agent integration & deployment.**
- Run MCP over HTTP (`MCP_TRANSPORT=http`). LangGraph supervisor connects as an MCP client.
- Wire Langfuse tracing, Redis session/thread state, FastAPI+SSE streaming (all in the agent layer).
- Golden-dataset eval (RAGAS/DeepEval) in CI before release, per the PRD.

## 6. How to run / verify
```powershell
.\.venv\Scripts\python.exe -m pip install -e .
# list tools without a DB:
.\.venv\Scripts\python.exe -c "import asyncio; from app.server import mcp; print(len(asyncio.run(mcp.list_tools())))"
# run stdio server (needs .env with SUPABASE_SERVICE_ROLE_KEY):
.\.venv\Scripts\python.exe -m app
```

## 7. Success criteria mapping (PRD §VI)
The agent layer owns intent/entity accuracy and hallucination metrics; this layer supports them by
(a) making project/entity resolution a first-class tool (`resolve_project`) to raise entity accuracy,
and (b) providing the RAG refusal contract (phase 2) that keeps hallucination < 1%.
