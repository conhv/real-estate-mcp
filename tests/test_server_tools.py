"""No-DB tests for the server wiring: the right tools are registered with sane schemas.

These don't touch Supabase — they inspect the FastMCP server. They catch the common student
mistakes: forgot to register a tool, wrong tool name, missing docstring, untyped params.
"""

from __future__ import annotations

import pytest

EXPECTED_ENABLED_TOOLS = {
    # US1
    "search_projects", "resolve_project", "list_project_buildings", "list_provinces",
    "search_listings", "search_listings_by_province", "get_listing", "list_project_listings",
    "listing_cta_actions",
    # US6 / US4 / US5
    "compare_listings", "project_overview", "map_listings",
    # US5 Map commute tools (OpenStreetMap & OSRM)
    "calculate_commute_matrix",
    # US2.1 / US2.2
    "start_visit_booking", "start_consultation", "submit_booking",
}


async def test_all_expected_tools_registered(mcp_server):
    tools = await mcp_server.list_tools()
    names = {t.name for t in tools}
    missing = EXPECTED_ENABLED_TOOLS - names
    assert not missing, f"Tools not registered: {missing}"


async def test_no_unexpected_enabled_tools(mcp_server):
    """RAG (answer_project_policy) must stay DISABLED in phase 1."""
    tools = await mcp_server.list_tools()
    names = {t.name for t in tools}
    assert "answer_project_policy" not in names, "RAG tool should be disabled in phase 1"
    assert names == EXPECTED_ENABLED_TOOLS


async def test_every_tool_has_a_description(mcp_server):
    tools = await mcp_server.list_tools()
    undocumented = [t.name for t in tools if not (t.description or "").strip()]
    assert not undocumented, f"Tools missing a docstring/description: {undocumented}"


@pytest.mark.parametrize(
    "tool_name,required_param",
    [
        ("search_projects", "query"),
        ("get_listing", "listing_id"),
        ("compare_listings", "listing_ids"),
        ("calculate_commute_matrix", "origins"),
        ("project_overview", "project_id"),
        ("start_visit_booking", "project_id"),
    ],
)
async def test_tool_input_schema_has_param(mcp_server, tool_name, required_param):
    tool = await mcp_server.get_tool(tool_name)
    assert tool is not None, f"{tool_name} not found"
    props = (tool.parameters or {}).get("properties", {})
    assert required_param in props, f"{tool_name} missing param '{required_param}' in schema"
