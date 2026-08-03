"""Listing access: search with filters, detail, list-by-project, and aggregate stats.

Note the data-quality realities of the `listings` table (see docs/SCHEMA.md):
  - area_m2 / bedrooms / bathrooms / floor_num are proper numeric columns in the current DB, but
    shaping.py still coerces them defensively — earlier snapshots stored them as TEXT.
  - price_vnd / price_per_m2_vnd are bigint -> safe to filter/sort in SQL.
  - status is Vietnamese ('ĐANG BÁN') and clean; normalize_status stays as a guard.

TODO(student): now that bedrooms is a real int, move that filter from Python into SQL
(`q.eq("bedrooms", n)`) and drop the limit*3 over-fetch in search_listings.
"""

from __future__ import annotations

from ..db import get_client
from ..shaping import (
    LISTING_CARD_COLUMNS,
    LISTING_DETAIL_COLUMNS,
    shape_listing_card,
    shape_listing_detail,
    to_int,
)


def search_listings(
    project_id: str | None,
    property_type: str | None,
    province: str | None,
    min_price_vnd: int | None,
    max_price_vnd: int | None,
    bedrooms: int | None,
    limit: int,
) -> list[dict]:
    """Filtered listing search. SQL-side filters for the reliable columns; bedrooms in Python."""
    q = get_client().table("listings").select(LISTING_CARD_COLUMNS)
    if project_id:
        q = q.eq("project_id", project_id)
    if property_type:
        q = q.eq("property_type", property_type)
    if min_price_vnd is not None:
        q = q.gte("price_vnd", min_price_vnd)
    if max_price_vnd is not None:
        q = q.lte("price_vnd", max_price_vnd)
    # NOTE: `province` is not a column on listing; resolve to project_ids upstream if needed.
    # Over-fetch a little when we must post-filter bedrooms so `limit` still holds after filtering.
    fetch = limit * 3 if bedrooms is not None else limit
    rows = q.order("price_vnd", desc=False).limit(fetch).execute().data or []
    cards = [shape_listing_card(r) for r in rows]
    if bedrooms is not None:
        cards = [c for c in cards if c["bedrooms"] == bedrooms]
    return cards[:limit]


def get_listing(listing_id: str) -> dict | None:
    rows = (
        get_client()
        .table("listings")
        .select(LISTING_DETAIL_COLUMNS)
        .eq("id", listing_id)
        .limit(1)
        .execute()
        .data
    )
    return shape_listing_detail(rows[0]) if rows else None


def list_by_project(project_id: str, limit: int) -> list[dict]:
    rows = (
        get_client()
        .table("listings")
        .select(LISTING_CARD_COLUMNS)
        .eq("project_id", project_id)
        .order("price_vnd", desc=False)
        .limit(limit)
        .execute()
        .data
        or []
    )
    return [shape_listing_card(r) for r in rows]


def get_many(listing_ids: list[str]) -> list[dict]:
    """Fetch several listings by id (used by compare)."""
    rows = (
        get_client()
        .table("listings")
        .select(LISTING_DETAIL_COLUMNS)
        .in_("id", listing_ids)
        .execute()
        .data
        or []
    )
    return [shape_listing_detail(r) for r in rows]


def project_price_stats(project_id: str) -> dict:
    """Aggregate price/area stats for one project (computed in Python over the project's rows).

    TODO(student, phase 2): move this to a Postgres RPC (avg/percentile over price_vnd) so we
    don't pull every row; keeps latency within the PRD's <3s budget at scale.
    """
    rows = (
        get_client()
        .table("listings")
        .select("price_vnd,price_per_m2_vnd,area_m2,property_type,bedrooms")
        .eq("project_id", project_id)
        .execute()
        .data
        or []
    )
    prices = [r["price_vnd"] for r in rows if r.get("price_vnd") is not None]
    ppm2 = [r["price_per_m2_vnd"] for r in rows if r.get("price_per_m2_vnd") is not None]
    beds = [b for b in (to_int(r.get("bedrooms")) for r in rows) if b is not None]
    ptypes: dict[str, int] = {}
    for r in rows:
        pt = r.get("property_type") or "unknown"
        ptypes[pt] = ptypes.get(pt, 0) + 1

    def _avg(xs: list[int]) -> float | None:
        return round(sum(xs) / len(xs)) if xs else None

    return {
        "project_id": project_id,
        "count": len(rows),
        "price_vnd": {
            "min": min(prices) if prices else None,
            "max": max(prices) if prices else None,
            "avg": _avg(prices),
        },
        "price_per_m2_vnd": {
            "min": min(ppm2) if ppm2 else None,
            "max": max(ppm2) if ppm2 else None,
            "avg": _avg(ppm2),
        },
        "bedrooms_range": {"min": min(beds) if beds else None, "max": max(beds) if beds else None},
        "by_property_type": ptypes,
    }


def map_points(project_id: str | None, limit: int) -> list[dict]:
    """Lightweight lat/lng points for the map view (US5)."""
    q = (
        get_client()
        .table("listings")
        .select("id,title,property_type,price_vnd,lat,lng")
        .not_.is_("lat", "null")
        .not_.is_("lng", "null")
    )
    if project_id:
        q = q.eq("project_id", project_id)
    rows = q.limit(limit).execute().data or []
    return [
        {
            "id": r["id"],
            "title": r.get("title"),
            "property_type": r.get("property_type"),
            "price_vnd": r.get("price_vnd"),
            "lat": r["lat"],
            "lng": r["lng"],
        }
        for r in rows
    ]
