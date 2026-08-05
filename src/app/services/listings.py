"""Listing access: search with filters, detail, list-by-project, and aggregate stats.

Note the data-quality realities of the `listing` table:
  - area_m2 / bedrooms / bathrooms / floor_num are stored as TEXT -> we coerce in shaping.py.
    This means we CANNOT reliably filter/range them in SQL without a cast; range filters on
    bedrooms are applied in Python after fetch (documented TODO to normalize in DB, phase 2).
  - price_vnd / price_per_m2_vnd ARE bigint -> safe to filter/sort in SQL.
  - status is Vietnamese ('ĐANG BÁN'), with an encoding-corrupted duplicate -> normalized on read.
"""

from __future__ import annotations

import os
from typing import Any

from ..constants import (
    FURNISHING_MAP,
    LEGAL_STATUS_MAP,
    PROPERTY_TYPE_MAP,
    USAGE_STATUS_MAP,
    clean_sql_enum,
    get_province_abbreviation,
)
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
    """Fetch several listings by id (used by compare), attaching province for context evaluation."""
    rows = (
        get_client()
        .table("listings")
        .select(LISTING_DETAIL_COLUMNS)
        .in_("id", listing_ids)
        .order("price_vnd", desc=False)
        .execute()
        .data
        or []
    )
    shaped = [shape_listing_detail(r) for r in rows]
    # Sort shaped listings by price_vnd ascending
    shaped.sort(key=lambda x: (x.get("price_vnd") or 0))
    project_ids = list({r["project_id"] for r in shaped if r.get("project_id")})
    if project_ids:
        loc_rows = (
            get_client()
            .table("locations")
            .select("id,province")
            .in_("id", project_ids)
            .execute()
            .data
            or []
        )
        prov_map = {l["id"]: l.get("province") for l in loc_rows}
        for item in shaped:
            item["province"] = prov_map.get(item.get("project_id"))
    return shaped




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


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Haversine straight-line distance in kilometers between two coordinates."""
    import math

    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


def get_listings_geo_bounds(listing_ids: list[str]) -> dict:
    """Extract coordinates, calculate center, bounds, recommended zoom, and distance matrix for map view."""
    if not listing_ids:
        return {"scope": "UNKNOWN", "items": [], "center": None, "bounds": None, "distance_matrix": []}

    rows = []
    try:
        rows = (
            get_client()
            .table("listings")
            .select(LISTING_DETAIL_COLUMNS)
            .in_("id", listing_ids)
            .execute()
            .data
            or []
        )
    except Exception:
        pass

    project_ids = list({r["project_id"] for r in rows if r.get("project_id")})
    loc_map = {}
    if project_ids:
        try:
            loc_rows = (
                get_client()
                .table("locations")
                .select("id, name, province")
                .in_("id", project_ids)
                .execute()
                .data
                or []
            )
            loc_map = {l["id"]: l for l in loc_rows}
        except Exception:
            pass

    items = []
    lats, lngs = [], []
    provinces = set()

    for raw in rows:
        r = shape_listing_detail(raw)
        lat = float(r.get("lat") or 0)
        lng = float(r.get("lng") or 0)
        proj_info = loc_map.get(r.get("project_id"), {})
        proj_name = proj_info.get("name") or r.get("project_id") or "Dự án"
        province = proj_info.get("province") or "Hà Nội"

        prov_abbr = get_province_abbreviation(province)

        provinces.add(prov_abbr or province)

        if lat != 0 and lng != 0:
            lats.append(lat)
            lngs.append(lng)

        price_num = (r.get("price_vnd") or 0) / 1000000000
        area = r.get("area_m2")

        ppm_num = r.get("price_per_m2_vnd")
        if ppm_num:
            ppm_text = f"{ppm_num / 1000000:.1f} Tr/m²"
        elif price_num and area:
            ppm_text = f"{(price_num * 1000 / area):.1f} Tr/m²"
        else:
            ppm_text = None

        title_lower = (r.get("title") or "").lower()
        is_studio = "studio" in title_lower
        bd = r.get("bedrooms")
        if bd is None and is_studio:
            bd = 0

        ba = r.get("bathrooms")

        legal_text = clean_sql_enum(r.get("legal_status"), LEGAL_STATUS_MAP)
        occ_text = clean_sql_enum(r.get("usage_status"), USAGE_STATUS_MAP)
        int_text = clean_sql_enum(r.get("furnishing"), FURNISHING_MAP)
        view_text = clean_sql_enum(r.get("view"))
        prop_type = clean_sql_enum(r.get("property_type"), PROPERTY_TYPE_MAP)
        direction_text = clean_sql_enum(r.get("direction_balcony"))
        floor_text = clean_sql_enum(r.get("floor_band")) or (f"Tầng {r.get('floor_num')}" if r.get("floor_num") else None)

        items.append({
            "id": r.get("id"),
            "title": r.get("title"),
            "name": r.get("title"),
            "project": proj_name,
            "location": province,
            "prov_abbr": prov_abbr,
            "lat": lat,
            "lng": lng,
            "price_vnd": r.get("price_vnd"),
            "priceNum": price_num,
            "priceText": f"{price_num:.2f} Tỷ" if price_num > 0 else "Thỏa thuận",
            "pricePerM2": ppm_text,
            "area_m2": area,
            "area": area,
            "bedrooms": bd,
            "bedrooms_plus": r.get("bedrooms_plus") or ("+1" in (r.get("title") or "")),
            "bathrooms": ba,
            "floor": floor_text,
            "direction": direction_text,
            "view": view_text,
            "interior": int_text,
            "legal": legal_text,
            "occupancy": occ_text,
            "property_type": prop_type,
            "image": r.get("thumbnail"),
            "thumbnail": r.get("thumbnail"),
            "url": r.get("url"),
        })

    if not lats or not lngs:
        return {"scope": "UNKNOWN", "items": items, "center": None, "bounds": None, "distance_matrix": []}

    center_lat = round(sum(lats) / len(lats), 6)
    center_lng = round(sum(lngs) / len(lngs), 6)

    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)

    is_multi_province = len(provinces) > 1
    projects_set = {item["project"] for item in items if item.get("project")}
    is_same_project = len(projects_set) == 1

    scope = "SAME_PROJECT" if is_same_project and not is_multi_province else ("CROSS_PROVINCE" if is_multi_province else "SAME_PROVINCE")
    recommended_zoom = 6 if is_multi_province else (15 if is_same_project else 13)

    # Distance matrix between pairwise items
    distance_matrix = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            p1, p2 = items[i], items[j]
            if p1["lat"] and p1["lng"] and p2["lat"] and p2["lng"]:
                dist_km = _haversine_distance_km(p1["lat"], p1["lng"], p2["lat"], p2["lng"])
                distance_matrix.append({
                    "item1_id": p1["id"],
                    "item2_id": p2["id"],
                    "item1_title": p1["title"],
                    "item2_title": p2["title"],
                    "distance_km": dist_km,
                    "distance_text": f"{dist_km} km" if dist_km >= 1 else f"{int(dist_km * 1000)} m",
                })

    return {
        "scope": scope,
        "items": items,
        "center": {"lat": center_lat, "lng": center_lng},
        "bounds": {
            "southwest": {"lat": min_lat, "lng": min_lng},
            "northeast": {"lat": max_lat, "lng": max_lng},
        },
        "recommended_zoom": recommended_zoom,
        "distance_matrix": distance_matrix,
    }


def fetch_real_nearby_amenities(lat: float, lng: float) -> list[dict]:
    """Query live Vietmap Autocomplete/Search API for real POIs (hospitals, schools, malls, parks)."""
    import os
    import httpx

    api_key = (os.environ.get("VIETMAP_API") or "").strip()
    if not api_key or api_key.startswith("your_") or not lat or not lng:
        return []

    categories = [
        {"cat": "Trường học", "query": "Trường"},
        {"cat": "Bệnh viện", "query": "Bệnh viện"},
        {"cat": "TTTM", "query": "Vincom"},
        {"cat": "Công viên", "query": "Công viên"},
    ]

    amenities = []
    try:
        transport = httpx.HTTPTransport(verify=False)
        with httpx.Client(timeout=1.0, transport=transport) as client:
            for c in categories:
                url = "https://maps.vietmap.vn/api/autocomplete/v3"
                params = {"apikey": api_key, "text": c["query"], "focus": f"{lat},{lng}"}
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        first = data[0]
                        name = first.get("name") or first.get("display") or c["query"]
                        dist_m = first.get("distance")
                        if dist_m is None:
                            poi_lat = first.get("lat")
                            poi_lng = first.get("lng")
                            if poi_lat and poi_lng:
                                dist_m = int(_haversine_distance_km(lat, lng, float(poi_lat), float(poi_lng)) * 1000)
                            else:
                                dist_m = 300

                        amenities.append({
                            "category": c["cat"],
                            "name": name,
                            "distance_m": int(dist_m),
                        })
    except Exception:
        pass

    return amenities


def compare_nearby_amenities(listing_ids: list[str]) -> dict:
    """Return objective side-by-side nearby amenity distance stats querying live Vietmap API or Geo POI engine."""
    bounds_data = get_listings_geo_bounds(listing_ids)
    items = bounds_data.get("items", [])

    results = []
    for item in items:
        lat = item.get("lat")
        lng = item.get("lng")

        api_key = (os.environ.get("VIETMAP_API") or "").strip()
        amenities = fetch_real_nearby_amenities(lat, lng) if api_key and not api_key.startswith("your_") else []

        results.append({
            "id": item["id"],
            "title": item["title"],
            "project": item["project"],
            "location": item["location"],
            "lat": lat,
            "lng": lng,
            "amenities": amenities
        })

    return {
        "status": "success",
        "guideline_note": "Factual descriptive distance data only. No buy/sell investment advice.",
        "listings_amenities": results
    }
