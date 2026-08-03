"""Listing tools (US1 results, US6 compare, listing detail)."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..services import listings as svc

# Known property types in the data (US1 filtering). Vietnamese slugs as stored.
PROPERTY_TYPES = (
    "can_ho",  # apartment (dominant)
    "lien_ke",  # townhouse
    "nha_pho",  # street house
    "shophouse",
    "thuong_mai_dich_vu",  # commercial/service
    "biet_thu_don_lap",  # detached villa
    "biet_thu_song_lap",  # semi-detached villa
    "biet_thu_tu_lap",  # quad villa
)


def register(mcp: FastMCP) -> None:
    @mcp.tool
    def search_listings(
        project_id: str | None = None,
        property_type: str | None = None,
        min_price_vnd: int | None = None,
        max_price_vnd: int | None = None,
        bedrooms: int | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search property LISTINGS with filters. Use after the project is known (US1 results).

        Args:
            project_id: restrict to one project, e.g. "oh:amber-riverside". Strongly recommended.
            property_type: one of can_ho, lien_ke, shophouse, thuong_mai_dich_vu,
                biet_thu_don_lap, biet_thu_song_lap, biet_thu_tu_lap.
            min_price_vnd / max_price_vnd: price bounds in VND (bigint).
            bedrooms: exact bedroom count.
            limit: max cards to return (default 10).

        Returns: list of listing cards {id, title, price_vnd, area_m2, bedrooms, property_type,
        status, lat, lng, thumbnail, ...}, sorted by price ascending.
        UI rule: 1-3 results -> show cards + CTAs; >3 -> show a "xem tất cả" button.
        """
        if property_type and property_type not in PROPERTY_TYPES:
            raise ToolError(
                f"Unknown property_type '{property_type}'. Valid: {', '.join(PROPERTY_TYPES)}."
            )
        return svc.search_listings(
            project_id=project_id,
            property_type=property_type,
            province=None,
            min_price_vnd=min_price_vnd,
            max_price_vnd=max_price_vnd,
            bedrooms=bedrooms,
            limit=limit,
        )

    @mcp.tool
    def get_listing(listing_id: str) -> dict:
        """Get the full detail of one listing (the detail page in US1). Raises if not found."""
        row = svc.get_listing(listing_id)
        if row is None:
            raise ToolError(f"No listing found with id '{listing_id}'.")
        return row

    @mcp.tool
    def list_project_listings(project_id: str, limit: int = 50) -> list[dict]:
        """List all listings in a project (the 'xem tất cả' view). Sorted by price ascending."""
        return svc.list_by_project(project_id=project_id, limit=limit)

    @mcp.tool
    def compare_listings(listing_ids: list[str]) -> dict:
        """Compare 2-4 listings side by side (US6).

        Use when the user wants to compare specific units. Pass their ids (same project or same
        province). Returns {"listings": [...full details...], "fields": [...]} where `fields` names
        the key comparison attributes so the UI can render a comparison table. Raises if <2 ids or
        any id is missing.
        """
        ids = list(dict.fromkeys(listing_ids))  # dedupe, keep order
        if not 2 <= len(ids) <= 4:
            raise ToolError("compare_listings needs between 2 and 4 distinct listing ids.")
        rows = svc.get_many(ids)
        found = {r["id"] for r in rows}
        missing = [i for i in ids if i not in found]
        if missing:
            raise ToolError(f"Listing id(s) not found: {', '.join(missing)}.")
        ordered = sorted(rows, key=lambda r: ids.index(r["id"]))
        return {
            "listings": ordered,
            "fields": [
                "price_vnd",
                "price_per_m2_vnd",
                "area_m2",
                "bedrooms",
                "bathrooms",
                "property_type",
                "direction_balcony",
                "view",
                "legal_status",
                "furnishing",
            ],
        }
