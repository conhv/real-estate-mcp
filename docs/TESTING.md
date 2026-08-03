# Testing Guide (for students)

You can test in **two levels**. Start with level 1 — it needs no database.

## Level 1 — No database (run this first, always)
Proves your shaping logic and tool wiring are correct. No Supabase needed.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests/test_shaping.py tests/test_server_tools.py -v
```
Expected: all pass. These check:
- `test_shaping.py` — text→number coercion, the `status` mojibake fix, card/location shaping.
- `test_server_tools.py` — the 13 expected tools are registered, RAG stays disabled, every tool has
  a description, key params exist in the input schema.

If you add a tool, add its name to `EXPECTED_ENABLED_TOOLS` in `tests/test_server_tools.py`.

## Level 2 — Live database (integration)
Proves the tools actually query Supabase. **Auto-skipped** until you provide credentials.

1. `Copy-Item .env.example .env` and fill in `SUPABASE_SERVICE_ROLE_KEY`
   (Dashboard → Project Settings → API → `service_role`). The MCP server is server-side and needs
   the service-role key because **RLS is enabled** — an anon key returns 0 rows.
2. Run:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_live_db.py -v
   ```
Expected: the 8 integration tests pass against real data.

### "I ran a tool and got 0 rows / an error — is it my code or the DB?"
Decision tree:
- **0 rows everywhere, even `list_provinces`** → almost certainly the key. You used the anon key, or
  RLS is blocking. Use the **service-role** key.
- **`ConfigError: SUPABASE_URL not set`** → you didn't create `.env` or didn't fill it.
- **0 rows for one project id** → the id may be wrong. Valid sample ids are in `tests/conftest.py`
  (`vhm:vinhomes-ocean-park`, listing `oh:TOFMRB`). Or re-introspect via the Supabase MCP.
- **`ToolError: Unknown property_type ...`** → you passed a type not in the allowed list; see
  `tools/listings.py > PROPERTY_TYPES`.

## Testing a single tool interactively (no pytest)
```python
import asyncio
from app.server import mcp
res = asyncio.run(mcp.call_tool("search_listings", {"project_id": "vhm:vinhomes-ocean-park", "limit": 3}))
print(res.structured_content)   # FastMCP 3.x: NOT `.data`
```
`ToolResult` has `content`, `structured_content`, `meta`, `is_error`. Tools that return a list are
wrapped as `{"result": [...]}`; tools that return a dict come through as-is. The tests use the
`tool_data()` helper in `conftest.py` to hide that difference.

## Windows note
If you see `UnicodeEncodeError` printing Vietnamese in the console, prefix with `PYTHONUTF8=1` (the
tests themselves are unaffected — this only bites raw `print()` in the terminal).

## When is a tool "done"?
See the **Definition of Done** checklist at the bottom of `docs/TOOLS_TODO.md`. In short: typed +
documented + thin + returns shaped JSON + `mcp.call_tool` returns correct data + appears in
`list_tools()`.
