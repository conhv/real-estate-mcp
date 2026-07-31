"""Analytics & map tools (US4 overview, US5 map)."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..services import listings as listing_svc
from ..services import locations as loc_svc


def register(mcp: FastMCP) -> None:
    @mcp.tool
    def project_overview(project_id: str) -> dict:
        """Market overview for one project (US4): counts + price/area stats + property-type mix.

        Use when the user asks to analyze or summarize a project ("phân tích tổng quan").
        Returns {project, stats:{count, price_vnd:{min,max,avg}, price_per_m2_vnd:{...},
        bedrooms_range, by_property_type}}. Descriptive stats only — NOT valuation or investment
        advice (those are out of scope per the PRD). Raises if the project id is unknown.
        """
        project = loc_svc.get_location(project_id)
        if project is None or project.get("level") != "project":
            raise ToolError(f"'{project_id}' is not a known project id.")
        return {"project": project, "stats": listing_svc.project_price_stats(project_id)}

    @mcp.tool
    def map_listings(project_id: str | None = None, limit: int = 200) -> dict:
        """Geo points for the map view (US5): listings with lat/lng.

        Use for "xem bản đồ". Optionally scope to one project. Returns
        {"count": n, "points": [{id, title, property_type, price_vnd, lat, lng}]}.
        """
        points = listing_svc.map_points(project_id=project_id, limit=limit)
        return {"count": len(points), "points": points}
