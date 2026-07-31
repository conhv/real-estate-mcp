"""Location hierarchy access.

`locations` is a self-referential tree keyed by text ids:
  level='project'  -> root nodes (57 of them), parent_id is NULL, project_id is NULL
  level='cluster'  -> optional mid layer, parent_id -> project
  level='building' -> leaf, parent_id -> cluster/project, project_id -> its project

Listings reference locations by `project_id` / `building_id` / `location_id` (all text).
"""

from __future__ import annotations

from ..db import get_client
from ..shaping import shape_location


def search_projects(query: str | None, province: str | None, limit: int) -> list[dict]:
    """Fuzzy-search project nodes by name and/or province.

    TODO(student, phase 2): upgrade name matching from ilike to pg_trgm similarity + unaccent
    (both extensions are available) so 'vinhome' matches 'Vinhomes' and accents are optional.
    """
    q = get_client().table("locations").select("*").eq("level", "project")
    if query:
        q = q.ilike("name", f"%{query}%")
    if province:
        q = q.ilike("province", f"%{province}%")
    rows = q.limit(limit).execute().data or []
    return [shape_location(r) for r in rows]


def get_location(location_id: str) -> dict | None:
    rows = get_client().table("locations").select("*").eq("id", location_id).limit(1).execute().data
    return shape_location(rows[0]) if rows else None


def list_children(parent_id: str, level: str | None, limit: int) -> list[dict]:
    """List child nodes (clusters/buildings) of a project or cluster."""
    q = get_client().table("locations").select("*").eq("parent_id", parent_id)
    if level:
        q = q.eq("level", level)
    rows = q.limit(limit).execute().data or []
    return [shape_location(r) for r in rows]


def list_provinces() -> list[str]:
    """Distinct provinces that have at least one project node."""
    rows = (
        get_client()
        .table("locations")
        .select("province")
        .eq("level", "project")
        .execute()
        .data
        or []
    )
    provinces = {r["province"] for r in rows if r.get("province")}
    return sorted(provinces)
