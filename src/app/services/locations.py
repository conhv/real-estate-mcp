"""Location hierarchy access.

`locations` is a self-referential tree keyed by text ids:
  level='project'  -> root nodes (57 of them), parent_id is NULL, project_id is NULL
  level='cluster'  -> optional mid layer, parent_id -> project
  level='building' -> leaf, parent_id -> cluster/project, project_id -> its project

Listings reference locations by `project_id` / `building_id` / `location_id` (all text).
"""

from __future__ import annotations

import unicodedata

from ..db import get_client
from ..shaping import shape_location

# Only the columns shape_location actually keeps. `select("*")` would also pull the three jsonb
# columns (sources, source_refs, attrs) on every search just to throw them away.
LOCATION_COLUMNS = "id,level,name,province,district,parent_id,project_id,lat,lng"

# LIKE wildcards and the quote/escape chars used by PostgREST's filter syntax. Vietnamese place
# names never contain these, and PostgREST offers no way to escape them inside an `or=(...)`
# group, so the only safe option is to drop them from user input.
_UNSAFE_IN_FILTER = str.maketrans({"%": None, "_": None, '"': None, "\\": None})


def _sanitize(value: str) -> str:
    """Strip characters that would be read as wildcards or break the filter syntax."""
    return value.translate(_UNSAFE_IN_FILTER).strip()


def _fold_accents(value: str) -> str:
    """Fold Vietnamese accents and case, to match against `locations.name_norm`.

    'Hải Vân' -> 'hai van'. `đ`/`Đ` have no combining-mark decomposition, so map them first.
    """
    value = value.replace("Đ", "D").replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower()


def search_projects(query: str | None, province: str | None, limit: int) -> list[dict]:
    """Search project nodes by name and/or province, best match first.

    Delegates to the `search_projects_fuzzy` Postgres function (see migrations/), which matches
    on three levels and ranks by trigram score:
      1. `name ILIKE %q%`            — accented input, as typed
      2. `name_norm ILIKE %folded%`  — accent-folded input ("chung cu" finds "Chung cư ...")
      3. `word_similarity >= 0.55`   — typos ("vinhoms" finds "Vinhomes ...")

    Filtering happens entirely in SQL, so `limit` never silently drops matches the way a
    post-fetch Python filter would. Requires the `pg_trgm` extension.

    Known gap: `name_norm` also drops generic words ("Khu", "The"), so a query containing one
    matches only via the `name` branch.
    """
    rows = (
        get_client()
        .rpc(
            "search_projects_fuzzy",
            {
                "q": _sanitize(query) if query else "",
                "q_folded": _fold_accents(_sanitize(query)) if query else "",
                "lim": limit,
                "prov": _sanitize(province) if province else None,
            },
        )
        .execute()
        .data
        or []
    )
    return [shape_location(r) for r in rows]


def get_location(location_id: str) -> dict | None:
    rows = (
        get_client()
        .table("locations")
        .select(LOCATION_COLUMNS)
        .eq("id", location_id)
        .limit(1)
        .execute()
        .data
    )
    return shape_location(rows[0]) if rows else None


def list_children(parent_id: str, level: str | None, limit: int) -> list[dict]:
    """List child nodes (clusters/buildings) of a project or cluster, sorted by name."""
    q = get_client().table("locations").select(LOCATION_COLUMNS).eq("parent_id", parent_id)
    if level:
        q = q.eq("level", level)
    rows = q.order("name").limit(limit).execute().data or []
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
