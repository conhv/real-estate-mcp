# Real Estate MCP

A [FastMCP](https://gofastmcp.com) server that exposes real-estate market-intelligence tools over
the Model Context Protocol (MCP), backed by Supabase Postgres. Built so a LangGraph/agent layer can
call these tools later (see `docs/PRD_LeDuyHung.pdf`).

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env   # then fill in SUPABASE_SERVICE_ROLE_KEY
.\.venv\Scripts\python.exe -m app        # stdio (local MCP clients)
```

For agent deployment over HTTP, set `MCP_TRANSPORT=http` in `.env` and run the same command; the
agent connects to `http://<host>:<port>/mcp`.

## Layout

```
src/app/
  server.py        # the single `mcp` instance + main()
  config.py        # env-based config (no secrets in code)
  db.py            # cached Supabase client
  shaping.py       # row -> agent-facing dict (coerces text-typed numbers, fixes status mojibake)
  services/        # all DB access (locations, listings)
  tools/           # @mcp.tool definitions grouped by user story (thin wrappers over services)
```

## Docs
- `docs/SCHEMA.md` — the real database schema + gotchas.
- `docs/PLAN.md` — architecture, approach, and phased implementation strategy.
- `docs/TOOLS_TODO.md` — the student-facing implementation checklist (what to build, per tool).

## Skills (for Claude Code)
- `.claude/skills/fastmcp` — how to build/run/test FastMCP tools here.
- `.claude/skills/supabase-access` — the Supabase client/query pattern used by the tools.
