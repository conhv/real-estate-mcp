"""Row -> agent-facing dict shaping.

The `listing` table stores several numeric fields as `text` (area_m2, bedrooms, bathrooms,
floor_num) and `status` has an encoding-corrupted variant. These helpers coerce raw rows into
clean, JSON-serializable dicts with the right types so the agent never sees DB noise.
Keep all "what the agent sees" decisions here, in one place.
"""

from __future__ import annotations

from typing import Any

# Columns selected for a compact listing card (used in search results / lists).
#
# `price_type` rides along with the price it qualifies: 1264 of 2355 rows price a unit by
# `estimate` (a figure the source computed) rather than `asking`, and a card showing price_vnd
# without it invites the agent to quote an estimate as the seller's price.
#
# `bedrooms_norm`/`has_flex_room` come from the `listings_clean` view (migrations/002), not from
# the base table. The raw `bedrooms` column is not selected at all: 139 rows it calls 1-bedroom
# are titled "Studio" and 126 more are shophouses carrying a placeholder 1.
LISTING_CARD_COLUMNS = (
    "id,title,url,source,project_id,building_id,property_type,area_m2,"
    "bedrooms_norm,has_flex_room,bathrooms,"
    "price_vnd,price_per_m2_vnd,price_type,status,lat,lng,thumbnail"
)

# Columns for a full listing detail view.
LISTING_DETAIL_COLUMNS = (
    LISTING_CARD_COLUMNS
    + ",floor_num,floor_band,direction_balcony,view,legal_status,furnishing,usage_status,"
    "area_type,image_count,images,first_seen,last_seen,crawled_at"
)


def to_float(value: Any) -> float | int | None:
    """Coerce a text/number field to float/int, omitting trailing .0 for whole numbers."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        return int(f) if f.is_integer() else round(f, 1)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        f = float(text)
        return int(f) if f.is_integer() else round(f, 1)
    except ValueError:
        return None


def to_int(value: Any) -> int | None:
    f = to_float(value)
    return int(f) if f is not None else None


def normalize_status(value: Any) -> str | None:
    """Fix the mojibake status value; return a clean label.

    The DB contains both a correctly-encoded 'ĐANG BÁN' and a corrupted byte-variant.
    Normalize by detecting the replacement char and mapping to the canonical label.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "�" in text or "ANG B" in text.upper():
        return "ĐANG BÁN"
    return text


def shape_listing_card(row: dict[str, Any]) -> dict[str, Any]:
    """Compact card for search results and lists."""
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "url": row.get("url"),
        "source": row.get("source"),
        "project_id": row.get("project_id"),
        "building_id": row.get("building_id"),
        "property_type": row.get("property_type"),
        "area_m2": to_float(row.get("area_m2")),
        # Derived in SQL from the listing title — see LISTING_CARD_COLUMNS above. None means the
        # title did not say, which is mostly shophouses and townhouses.
        "bedrooms": to_int(row.get("bedrooms_norm")),
        "has_flex_room": row.get("has_flex_room"),
        "bathrooms": to_int(row.get("bathrooms")),
        "price_vnd": row.get("price_vnd"),
        "price_per_m2_vnd": row.get("price_per_m2_vnd"),
        "price_type": row.get("price_type"),  # "asking" vs "estimate" — never drop this
        "status": normalize_status(row.get("status")),
        "lat": row.get("lat"),
        "lng": row.get("lng"),
        "thumbnail": row.get("thumbnail"),
    }


def shape_listing_detail(row: dict[str, Any]) -> dict[str, Any]:
    """Full detail view for a single listing."""
    card = shape_listing_card(row)
    if row.get("bedrooms_plus"):
        card["has_flex_room"] = True
    card.update(
        {
            "floor_num": to_int(row.get("floor_num")),
            "floor_band": row.get("floor_band"),
            "direction_balcony": row.get("direction_balcony"),
            "view": row.get("view"),
            "legal_status": row.get("legal_status"),
            "furnishing": row.get("furnishing"),
            "usage_status": row.get("usage_status"),
            "area_type": row.get("area_type"),
            "image_count": row.get("image_count"),
            "images": row.get("images") or [],
            "first_seen": row.get("first_seen"),
            "last_seen": row.get("last_seen"),
            "crawled_at": row.get("crawled_at"),
        }
    )
    return card


def shape_location(row: dict[str, Any]) -> dict[str, Any]:
    """A project/cluster/building node from the `locations` hierarchy."""
    return {
        "id": row.get("id"),
        "level": row.get("level"),
        "name": row.get("name"),
        "province": row.get("province"),
        "district": row.get("district"),
        "parent_id": row.get("parent_id"),
        "project_id": row.get("project_id"),
        "lat": row.get("lat"),
        "lng": row.get("lng"),
    }


def compute_comparison_insights(listings: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute context evaluation, deltas, and badges/highlights across compared listings."""
    if not listings:
        return {
            "context": {"same_project": True, "same_province": True, "projects": [], "provinces": []},
            "deltas": {},
            "highlights": {},
        }

    projects = sorted(list({l.get("project_id") for l in listings if l.get("project_id")}))
    provinces = sorted(list({l.get("province") for l in listings if l.get("province")}))

    same_project = len(projects) <= 1
    same_province = len(provinces) <= 1

    prices = [l["price_vnd"] for l in listings if l.get("price_vnd") is not None]
    price_per_m2s = [l["price_per_m2_vnd"] for l in listings if l.get("price_per_m2_vnd") is not None]
    areas = [l["area_m2"] for l in listings if l.get("area_m2") is not None]
    bedrooms = [l["bedrooms"] for l in listings if l.get("bedrooms") is not None]

    deltas = {
        "price_vnd": {
            "min": min(prices) if prices else None,
            "max": max(prices) if prices else None,
            "diff": (max(prices) - min(prices)) if len(prices) >= 2 else 0,
        },
        "price_per_m2_vnd": {
            "min": min(price_per_m2s) if price_per_m2s else None,
            "max": max(price_per_m2s) if price_per_m2s else None,
            "diff": (max(price_per_m2s) - min(price_per_m2s)) if len(price_per_m2s) >= 2 else 0,
        },
        "area_m2": {
            "min": min(areas) if areas else None,
            "max": max(areas) if areas else None,
            "diff": round(max(areas) - min(areas), 2) if len(areas) >= 2 else 0.0,
        },
    }

    highlights: dict[str, list[str]] = {l["id"]: [] for l in listings if l.get("id")}

    min_price = min(prices) if prices else None
    min_ppm2 = min(price_per_m2s) if price_per_m2s else None
    max_area = max(areas) if areas else None
    max_bed = max(bedrooms) if bedrooms else None

    for l in listings:
        lid = l.get("id")
        if not lid:
            continue
        if min_price is not None and l.get("price_vnd") == min_price:
            highlights[lid].append("cheapest_price")
        if min_ppm2 is not None and l.get("price_per_m2_vnd") == min_ppm2:
            highlights[lid].append("lowest_price_per_m2")
        if max_area is not None and l.get("area_m2") == max_area:
            highlights[lid].append("largest_area")
        if max_bed is not None and l.get("bedrooms") == max_bed:
            highlights[lid].append("most_bedrooms")

    return {
        "context": {
            "same_project": same_project,
            "same_province": same_province,
            "projects": projects,
            "provinces": provinces,
        },
        "deltas": deltas,
        "highlights": highlights,
    }

