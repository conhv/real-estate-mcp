"""Live-DB integration tests. AUTO-SKIPPED unless SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are set.

Run them once you've put credentials in .env:
    .venv/Scripts/python.exe -m pytest tests/test_live_db.py -v

These call the real tools end-to-end through the MCP server, proving your service/db layer works
against the actual Supabase data. They use the real sample ids from conftest.py.

`mcp.call_tool(name, args)` returns a ToolResult; use `tool_data(res)` from conftest to read the
tool's return value out of it (see that helper for why `.structured_content` needs unwrapping).
"""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from .conftest import needs_db, tool_data


@needs_db
async def test_search_projects_finds_vinhomes(mcp_server, sample_project_name):
    res = await mcp_server.call_tool("search_projects", {"query": sample_project_name})
    projects = tool_data(res)
    assert isinstance(projects, list) and projects, "expected at least one Vinhomes project"
    assert all(p["level"] == "project" for p in projects)


@needs_db
async def test_search_projects_ignores_accents(mcp_server):
    """US1 acceptance: an unaccented query must find the same projects as the accented one.

    Matching runs against `locations.name_norm`, which is stored accent-folded. Guards the
    checklist example "chung cu" (which returned nothing while we only searched `name`).
    """
    for accented, plain in [("chung cư", "chung cu"), ("Phương Đông", "phuong dong")]:
        with_marks = tool_data(await mcp_server.call_tool("search_projects", {"query": accented}))
        without = tool_data(await mcp_server.call_tool("search_projects", {"query": plain}))
        assert without, f"unaccented query {plain!r} found nothing"
        assert {p["id"] for p in with_marks} == {p["id"] for p in without}


@needs_db
async def test_search_projects_order_is_deterministic(mcp_server):
    """`limit` must cut a stable prefix, not an arbitrary subset.

    Without ORDER BY, Postgres may return any 5 of the 57 projects, and a different 5 next
    time. Don't compare against Python's `sorted()` — Postgres orders by its own locale
    collation, which ranks e.g. "Happy Home" before "HH Linh Đàm"; the property that matters
    to callers is that the order is reproducible.
    """
    first = [p["id"] for p in tool_data(await mcp_server.call_tool("search_projects", {"limit": 5}))]
    wider = [p["id"] for p in tool_data(await mcp_server.call_tool("search_projects", {"limit": 20}))]
    assert len(first) == 5
    assert first == wider[:5], "limit returned a different slice on a wider query"


@needs_db
async def test_search_projects_survives_filter_metacharacters(mcp_server):
    """Characters with meaning in PostgREST's filter syntax must not break the request.

    A comma previously produced a "failed to parse logic tree" error rather than a result set.
    """
    for probe in ["a,b", "%", '"', "(x)"]:
        out = tool_data(await mcp_server.call_tool("search_projects", {"query": probe}))
        assert isinstance(out, list)


@needs_db
async def test_search_projects_tolerates_typos(mcp_server):
    """pg_trgm branch: a misspelt query still reaches the project (US1 "harden" item).

    Requires migrations/001_search_projects_fuzzy.sql. A "Could not find the function
    public.search_projects_fuzzy" error here means the migration has not been applied.
    """
    for typo in ["vinhoms", "vinhomse", "vin homes"]:
        out = tool_data(await mcp_server.call_tool("search_projects", {"query": typo}))
        assert any("Vinhomes" in p["name"] for p in out), f"{typo!r} found nothing"


@needs_db
async def test_search_projects_rejects_unrelated_queries(mcp_server):
    """The other half of the similarity threshold: fuzziness must not become "matches anything".

    Pairs with test_search_projects_tolerates_typos — lowering min_score far enough to pass that
    test while failing this one means the threshold is too loose.
    """
    for nonsense in ["xyzabc", "qqqqqq", "zzzzzzzz"]:
        out = tool_data(await mcp_server.call_tool("search_projects", {"query": nonsense}))
        assert out == [], f"{nonsense!r} matched {[p['name'] for p in out]}"


@needs_db
async def test_search_projects_ranks_best_match_first(mcp_server):
    """Results come back ordered by trigram score, so the exact name outranks its longer siblings."""
    out = tool_data(await mcp_server.call_tool("search_projects", {"query": "Vinhomes Ocean Park"}))
    assert out, "expected at least one Vinhomes Ocean Park project"
    assert out[0]["name"] == "Vinhomes Ocean Park"


@needs_db
async def test_search_projects_filters_province_in_sql(mcp_server):
    """`province` must narrow the query itself, not a page of results.

    If the filter ran in Python after LIMIT, a name+province search would return fewer rows than
    the same search capped at that many — silently dropping matches.
    """
    args = {"query": "Vinhomes", "province": "Hà Nội"}
    out = tool_data(await mcp_server.call_tool("search_projects", {**args, "limit": 100}))
    assert out, "expected Vinhomes projects in Hà Nội"
    assert all(p["province"] == "Hà Nội" for p in out)
    capped = tool_data(await mcp_server.call_tool("search_projects", {**args, "limit": 
