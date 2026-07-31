"""Project / location tools (US1, and the 'clarify project' step across US1/2.1/2.2/3)."""

from __future__ import annotations

from fastmcp import FastMCP

from ..services import locations as svc


def register(mcp: FastMCP) -> None:
    @mcp.tool
    def search_projects(
        query: str | None = None,
        province: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search real-estate PROJECTS by name and/or province.

        Use when the user names or hints at a project ("Vinhomes", "Amber Riverside") or asks for
        projects in a place ("chung cư ở Hà Nội"). This is the entry point for US1 and for the
        "clarify which project" step in booking/consulting/policy flows.

        Args:
            query: free-text project name fragment (Vietnamese ok), e.g. "vinhomes". Optional.
            province: province filter, e.g. "Hà Nội". Optional.
            limit: max projects to return (default 10).

        Returns: list of project nodes, each {id, level, name, province, district, lat, lng}.
        Show up to 3 as quick-pick buttons; if more, offer "xem tất cả".
        """
        return svc.search_projects(query=query, province=province, limit=limit)

    @mcp.tool
    def resolve_project(text: str) -> dict:
        """Decide whether a user's free text refers to a known project, for slot-filling.

        Use to check if what the user typed/clicked is actually a project name before proceeding.
        Returns {"matched": bool, "project": {...}|None, "candidates": [...]}.
        - Exactly one strong match -> matched=true with that project.
        - Several possible -> matched=false with candidates to disambiguate (ask the user).
        - None -> matched=false, empty candidates (treat as not a project name).
        """
        candidates = svc.search_projects(query=text, province=None, limit=5)
        if len(candidates) == 1:
            return {"matched": True, "project": candidates[0], "candidates": []}
        return {"matched": False, "project": None, "candidates": candidates}

    @mcp.tool
    def list_project_buildings(project_id: str, limit: int = 50) -> list[dict]:
        """List the buildings/clusters that belong to a project.

        Use after a project is chosen, to let the user narrow to a specific tower/building.
        Args: project_id like "oh:amber-riverside". Returns child location nodes.
        """
        return svc.list_children(parent_id=project_id, level=None, limit=limit)

    @mcp.tool
    def list_provinces() -> list[str]:
        """List provinces that have at least one project. Use to offer location choices to the user."""
        return svc.list_provinces()
