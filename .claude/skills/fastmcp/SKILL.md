---
name: fastmcp
description: Use when building, editing, or running a FastMCP server in this project — defining MCP tools/resources/prompts, wiring the Supabase-backed real-estate tools, choosing stdio vs HTTP transport, testing tools in-process, or preparing the server for agent deployment. Triggers on FastMCP, @mcp.tool, @mcp.resource, MCP server, "add a tool", "run the mcp server".
---

# FastMCP (v3.x) in this project

FastMCP is the framework used to expose the Real Estate Market Intelligence tools over the
Model Context Protocol (MCP), so a LangGraph/agent layer can call them later. Installed version
is **fastmcp 3.4.5** in `.venv`. Always run Python through `.venv/Scripts/python.exe`.

## Golden rules
1. **One server instance** lives in `src/app/server.py` as `mcp = FastMCP("real-estate-mcp")`.
2. **Every tool has a full docstring + typed signature.** The LLM/agent chooses tools from these,
   so the description and parameter types ARE the contract. Write them for a model, not a human.
3. **Tools return JSON-serializable data** (dicts / lists / pydantic models), never raw DB rows or
   ORM objects. Shape the output deliberately — the agent reads exactly what you return.
4. **No secrets in code.** Read Supabase URL/keys from env via `python-dotenv` (`.env`, gitignored).
5. **Keep tools thin.** Business logic (search, ranking, DB access) goes in `src/app/`
   modules; the `@mcp.tool` function just validates input, calls the module, shapes the output.

## Minimal server shape (matches installed API)
```python
from fastmcp import FastMCP, Context

mcp = FastMCP(
    name="real-estate-mcp",
    instructions="Tools for searching and analyzing Vietnamese real-estate projects & properties.",
)

@mcp.tool
def search_projects(query: str, province: str | None = None, limit: int = 10) -> list[dict]:
    """Search real-estate projects by name/keyword, optionally filtered by province.

    Use when the user names or hints at a project ("Vinhomes", "chung cư ở Hà Nội").
    Returns up to `limit` projects, each with id, name, province, developer.
    """
    ...  # call into a module, return a list of plain dicts

if __name__ == "__main__":
    mcp.run()  # stdio by default
```

## Decorators (the whole surface you need here)
- `@mcp.tool` — an action the agent can invoke. Sync or `async def`. Type every parameter; use
  `X | None = None` for optional filters. The docstring is the tool description shown to the model.
- `@mcp.resource("scheme://path")` — read-only data the agent can *read* by URI (e.g. a project's
  full policy document `realestate://project/{id}/policy`). Use for RAG-style context fetch.
- `@mcp.prompt` — a reusable prompt template. Rarely needed for this project; prefer tools.

## Context (for progress / logging / sampling)
Add `ctx: Context` as the last parameter of a tool to access `await ctx.info(...)`,
`await ctx.report_progress(...)`, etc. FastMCP injects it — the agent does NOT pass it.
```python
@mcp.tool
async def reindex_docs(project_id: str, ctx: Context) -> dict:
    await ctx.info(f"Re-indexing {project_id}")
    ...
```

## Transports & running
- **Development / editor MCP client:** stdio. `mcp.run()` or `.venv/Scripts/fastmcp run src/app/server.py`.
- **Agent deployment (HTTP):** `mcp.run(transport="http", host="0.0.0.0", port=8000)`.
  This is the target for "deploy agent later" — the agent connects to the HTTP MCP endpoint.
- Never print to stdout in stdio mode (it corrupts the protocol). Use `ctx.info`/logging to stderr.

## Testing a tool WITHOUT a full client
FastMCP lets you call tools in-process — use this in `tests/`:
```python
import asyncio
from app.server import mcp
result = asyncio.run(mcp.call_tool("search_projects", {"query": "Vinhomes"}))
```
Or list what's registered: `asyncio.run(mcp.list_tools())`. Prefer this over spinning up a client.

## Checklist before saying a tool is done
- [ ] Typed signature, `| None = None` for optionals, sensible `limit` default.
- [ ] Docstring: 1 line what it does + when to use it + what it returns.
- [ ] Returns plain JSON-serializable data, shaped for an agent (no leaking DB internals).
- [ ] DB access delegated to a module; env-based Supabase client; errors handled, no stack traces leak.
- [ ] Registered on the single `mcp` instance and appears in `mcp.list_tools()`.

## References
- Official docs: https://gofastmcp.com (see `/servers/tools`, `/servers/resources`, `/deployment`).
- This project's tool spec & TODOs: `docs/PLAN.md` and `docs/TOOLS_TODO.md`.
- Supabase access rules: the `supabase` skill in this repo.
