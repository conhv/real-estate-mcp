"""Listing access: search with filters, detail, list-by-project, and aggregate stats.

Note the data-quality realities of the `listings` table (see docs/SCHEMA.md):
  - area_m2 / bedrooms / bathrooms / floor_num are proper numeric columns in the current DB, but
    shaping.py still coerces them defensively — earlier snapshots stored them as TEXT.
  - price_vnd / price_per_m2_vnd are bigint -> safe to filter/sort in SQL.
  - status has one non-null value ('ĐANG BÁN', 1091 rows) and is NULL on the other 1264, so it
    means "listed for sale" or "unknown" — never "sold". normalize_status stays as a guard.
  - NULL rates over all 2355 rows: bathrooms 23%, view 22%, legal_status 12%, building_id 10%,
    bedrooms 6%, area_m2 6%, price_vnd 1%. Filtering on a column silently drops its NULL rows.

Counts here are from the whole table. Don't read them off a `.limit(1000)` sample: PostgREST
returns the first 1000 rows in physical order, which is one crawl block and badly skewed —
floor_band looked 100% NULL that way while it is really only 46% NULL.
"""

from __future__ import annotations

from postgrest.exceptions import APIError

from ..db import get_client
from ..shaping import (
    LISTING_CARD_COLUMNS,
    LISTING_DETAIL_COLUMNS,
    shape_listing_card,
    shape_listing_detail,
    to_float,
    to_int,
)


def search_listings(
    project_id: str | None,
    building_id: str | None,
    property_type: str | None,
    min_price_vnd: int | None,
    max_price_vnd: int | None,
    bedrooms: int | None,
    limit: int,
) -> list[dict]:
    """Filtered listing search, cheapest first. Every filter runs in SQL.

    `bedrooms` used to be filtered in Python over `limit * 3` fetched rows, which silently
    under-returned: Vinhomes Grand Park has 587 listings, and sorted by price the first
    2-bedroom sits at index 144, so `bedrooms=2, limit=10` fetched the cheapest 30 rows,
    matched none of them and answered "no listings" over 251 real matches. Any post-fetch
    filter has this failure mode — over-fetching by a constant factor only moves the cliff.

    There is no `province` filter: `listings` has no province column. Resolve a province to
    project ids via `locations` first (see the phase-2 `search_listings_by_province` item).
    """
    q = get_client().table("listings_full").select(LISTING_CARD_COLUMNS)
    if project_id:
        q = q.eq("project_id", project_id)
    if building_id:
        q = q.eq("building_id", building_id)
    if property_type:
        q = q.eq("property_type", property_type)
    if bedrooms is not None:
        q = q.eq("bedrooms", bedrooms)
    if min_price_vnd is not None:
        q = q.gte("price_vnd", min_price_vnd)
    if max_price_vnd is not None:
        q = q.lte("price_vnd", max_price_vnd)
    # `id` breaks price ties so repeating a search returns the same cards (see list_by_project).
    rows = q.order("price_vnd", desc=False).order("id", desc=False).limit(limit).execute().data
    return [shape_listing_card(r) for r in rows or []]


def get_listing(listing_id: str) -> dict | None:
    rows = (
        get_client()
        .table("listings_full")
        .select(LISTING_DETAIL_COLUMNS)
        .eq("id", listing_id)
        .limit(1)
        .execute()
        .data
    )
    return shape_listing_detail(rows[0]) if rows else None


def list_by_project(project_id: str, limit: int, offset: int) -> dict:
    """One page of a project's listings, cheapest first, plus the total that page came from.

    Returns the total because this backs the "xem tất cả" view and the biggest projects hold
    far more than one page — Vinhomes Ocean Park has 685 listings, Grand Park 623, and 9 of
    the 57 projects exceed the default page of 50. Returning a bare list let the caller
    present 50 of 685 as if it were everything.

    `count="exact"` rides along on the same request, so the total costs no extra round trip.
    """
    try:
        res = _project_page(project_id, limit, offset)
    except APIError as exc:
        # PostgREST answers 416 for an offset past the last row, whether the window is set via
        # the Range header or ?offset=. Paging off the end is a normal thing for a caller to do
        # and its error text leaks row counts, so report an empty page instead.
        if exc.code != "PGRST103":
            raise
        return {
            "total": _project_total(project_id),
            "offset": offset,
            "count": 0,
            "has_more": False,
            "listings": [],
        }
    listings = [shape_listing_card(r) for r in res.data or []]
    return {
        "total": res.count,
        "offset": offset,
        "count": len(listings),
        "has_more": offset + len(listings) < (res.count or 0),
        "listings": listings,
    }


def _project_total(project_id: str) -> int:
    count = (
        get_client()
        .table("listings_full")
        .select("id", count="exact")
        .eq("project_id", project_id)
        .limit(1)
        .execute()
        .count
    )
    return count or 0


def _project_page(project_id: str, limit: int, offset: int):
    return (
        get_client()
        .table("listings_full")
        .select(LISTING_CARD_COLUMNS, count="exact")
        .eq("project_id", project_id)
        .order("price_vnd", desc=False)
        # `id` breaks price ties. Without it the sort is not a total order — Ocean Park has ten
        # duplicated prices in its 60 cheapest alone — and Postgres may order a tie group
        # differently per query, so page 2 can repeat or skip rows that page 1 already showed.
        .order("id", desc=False)
        .range(offset, offset + limit - 1)  # inclusive on both ends
        .execute()
    )


def get_listing_ref(listing_id: str) -> dict | None:
    """id + project_id only — enough to prove a listing exists and to route its CTAs.

    Deliberately not `get_listing`: that pulls the full detail row including the images array
    (up to 40 URLs) just to read one foreign key.
    """
    rows = (
        get_client()
        .table("listings_full")
        .select("id,project_id")
        .eq("id", listing_id)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def get_many(listing_ids: list[str]) -> list[dict]:
    """Fetch several listings by id (used by compare)."""
    rows = (
        get_client()
        .table("listings_full")
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
        .table("listings_full")
        .select("price_vnd,price_per_m2_vnd,area_m2,property_type,bedrooms")
        .eq("project_id", project_id)
        .execute()
        .data
        or []
    )
    prices = [r["price_vnd"] for r in rows if r.get("price_vnd") is not None]
    ppm2 = [r["price_per_m2_vnd"] for r in rows if r.get("price_per_m2_vnd") is not None]
    areas = [a for a in (to_float(r.get("area_m2")) for r in rows) if a is not None]
    beds = [b for b in (to_int(r.get("bedrooms")) for r in rows) if b is not None]
    ptypes: dict[str, int] = {}
    for r in rows:
        pt = r.get("property_type") or "unknown"
        ptypes[pt] = ptypes.get(pt, 0) + 1

    def _avg(xs: list[int | float]) -> float | None:
        return round(sum(xs) / len(xs), 2) if xs else None

    return {
        "project_id": project_id,
        "count": len(rows),
        "price_vnd": {
            "min": min(prices) if prices else None,
            "max": max(prices) if prices else None,
            "avg": round(_avg(prices)) if prices and _avg(prices) is not None else None,
        },
        "price_per_m2_vnd": {
            "min": min(ppm2) if ppm2 else None,
            "max": max(ppm2) if ppm2 else None,
            "avg": round(_avg(ppm2)) if ppm2 and _avg(ppm2) is not None else None,
        },
        "area_m2": {
            "min": min(areas) if areas else None,
            "max": max(areas) if areas else None,
            "avg": _avg(areas),
        },
        "bedrooms_range": {"min": min(beds) if beds else None, "max": max(beds) if beds else None},
        "by_property_type": ptypes,
    }


def map_points(project_id: str | None, limit: int) -> list[dict]:
    """Lightweight lat/lng points for the map view (US5)."""
    q = (
        get_client()
        .table("listings_full")
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

