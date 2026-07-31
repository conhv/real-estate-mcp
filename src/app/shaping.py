"""Row -> agent-facing dict shaping.

The `listing` table stores several numeric fields as `text` (area_m2, bedrooms, bathrooms,
floor_num) and `status` has an encoding-corrupted variant. These helpers coerce raw rows into
clean, JSON-serializable dicts with the right types so the agent never sees DB noise.
Keep all "what the agent sees" decisions here, in one place.
"""

from __future__ import annotations

from typing import Any

# Columns selected for a compact listing card (used in search results / lists).
LISTING_CARD_COLUMNS = (
    "id,title,url,source,project_id,building_id,property_type,area_m2,bedrooms,bathrooms,"
    "price_vnd,price_per_m2_vnd,status,lat,lng,thumbnail"
)

# Columns for a full listing detail view.
LISTING_DETAIL_COLUMNS = (
    LISTING_CARD_COLUMNS
    + ",floor_num,floor_band,direction_balcony,view,legal_status,furnishing,usage_status,"
    "price_type,area_type,image_count,images,first_seen,last_seen,crawled_at"
)


def to_float(value: Any) -> float | None:
    """Coerce a text/number field to float, tolerating commas and stray whitespace."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
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
        "bedrooms": to_int(row.get("bedrooms")),
        "bathrooms": to_int(row.get("bathrooms")),
        "price_vnd": row.get("price_vnd"),
        "price_per_m2_vnd": row.get("price_per_m2_vnd"),
        "status": normalize_status(row.get("status")),
        "lat": row.get("lat"),
        "lng": row.get("lng"),
        "thumbnail": row.get("thumbnail"),
    }


def shape_listing_detail(row: dict[str, Any]) -> dict[str, Any]:
    """Full detail view for a single listing."""
    card = shape_listing_card(row)
    card.update(
        {
            "floor_num": to_int(row.get("floor_num")),
            "floor_band": row.get("floor_band"),
            "direction_balcony": row.get("direction_balcony"),
            "view": row.get("view"),
            "legal_status": row.get("legal_status"),
            "furnishing": row.get("furnishing"),
            "usage_status": row.get("usage_status"),
            "price_type": row.get("price_type"),
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
