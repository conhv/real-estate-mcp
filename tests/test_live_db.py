"""Live-DB integration tests. AUTO-SKIPPED unless SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are set.

Run them once you've put credentials in .env:
    .venv/Scripts/python.exe -m pytest tests/test_live_db.py -v

These call the real tools end-to-end through the MCP server, proving your service/db layer works
against the actual Supabase data. They use the real sample ids from conftest.py.

`mcp.call_tool(name, args)` returns a ToolResult; `.structured_content` holds the tool's return value.
"""

from __future__ import annotations

from .conftest import needs_db


@needs_db
async def test_search_projects_finds_vinhomes(mcp_server, sample_project_name):
    res = await mcp_server.call_tool("search_projects", {"query": sample_project_name})
    projects = res.structured_content
    assert isinstance(projects, list) and projects, "expected at least one Vinhomes project"
    assert all(p["level"] == "project" for p in projects)


@needs_db
async def test_resolve_project(mcp_server, sample_project_name):
    res = await mcp_server.call_tool("resolve_project", {"text": sample_project_name})
    out = res.structured_content
    assert set(out) == {"matched", "project", "candidates"}


@needs_db
async def test_search_listings_in_project(mcp_server, sample_project_id):
    res = await mcp_server.call_tool(
        "search_listings", {"project_id": sample_project_id, "limit": 5}
    )
    cards = res.structured_content
    assert isinstance(cards, list) and cards
    assert len(cards) <= 5
    # types were coerced by shaping (price is int, area is float-or-none)
    assert all(isinstance(c["price_vnd"], (int, type(None))) for c in cards)


@needs_db
async def test_get_listing_detail(mcp_server, sample_listing_ids):
    res = await mcp_server.call_tool("get_listing", {"listing_id": sample_listing_ids[0]})
    listing = res.structured_content
    assert listing["id"] == sample_listing_ids[0]
    assert "images" in listing  # detail view


@needs_db
async def test_compare_listings(mcp_server, sample_listing_ids):
    res = await mcp_server.call_tool(
        "compare_listings", {"listing_ids": sample_listing_ids[:2]}
    )
    out = res.structured_content
    assert len(out["listings"]) == 2
    assert "fields" in out


@needs_db
async def test_project_overview_stats(mcp_server, sample_project_id):
    res = await mcp_server.call_tool("project_overview", {"project_id": sample_project_id})
    out = res.structured_content
    assert out["project"]["id"] == sample_project_id
    assert out["stats"]["count"] > 0
    assert "price_vnd" in out["stats"]


@needs_db
async def test_map_listings_have_coords(mcp_server, sample_project_id):
    res = await mcp_server.call_tool(
        "map_listings", {"project_id": sample_project_id, "limit": 10}
    )
    out = res.structured_content
    assert out["count"] == len(out["points"])
    assert all(p["lat"] is not None and p["lng"] is not None for p in out["points"])


@needs_db
async def test_booking_form_authed_vs_guest(mcp_server, sample_project_id):
    guest = (await mcp_server.call_tool(
        "start_visit_booking", {"project_id": sample_project_id, "is_authenticated": False}
    )).structured_content
    authed = (await mcp_server.call_tool(
        "start_visit_booking", {"project_id": sample_project_id, "is_authenticated": True}
    )).structured_content
    guest_fields = {f["name"] for f in guest["fields"]}
    authed_fields = {f["name"] for f in authed["fields"]}
    assert "phone" in guest_fields  # guest must give contact
    assert "phone" not in authed_fields  # authed is prefilled
