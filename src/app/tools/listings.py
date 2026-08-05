"""Listing tools (US1 results, US6 compare, listing detail)."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..services import listings as svc
from ..services import locations as loc_svc

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
        building_id: str | None = None,
        property_type: str | None = None,
        min_price_vnd: int | None = None,
        max_price_vnd: int | None = None,
        bedrooms: int | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search property LISTINGS with filters. Use after the project is known (US1 results).

        Returns a list of listing cards {id, title, url, source, project_id, building_id,
        property_type, area_m2, bedrooms, bathrooms, price_vnd, price_per_m2_vnd, status, lat,
        lng, thumbnail}, cheapest first. An empty list means nothing matched the filters, not
        that the search failed — offer to relax a filter rather than reporting an error.

        How to present the result: 1-3 cards -> show them with the CTA buttons from
        listing_cta_actions; more than 3 -> summarise and offer a "xem tất cả" button backed by
        list_project_listings.

        Filters combine with AND and all run in the database, so `limit` caps the cheapest
        matches rather than hiding some. Note that `bedrooms` is missing on 6% of listings and
        `building_id` on 10%, so filtering on them drops listings that simply lack the field
        rather than ones that fail the test.

        Args:
            project_id: restrict to one project, e.g. "oh:amber-riverside". Strongly recommended;
                without it the search spans every project.
            building_id: restrict to one tower, using an id from list_project_buildings. Only
                "building"-level ids match; a cluster id returns nothing.
            property_type: one of can_ho, lien_ke, nha_pho, shophouse, thuong_mai_dich_vu,
                biet_thu_don_lap, biet_thu_song_lap, biet_thu_tu_lap. Anything else raises.
            min_price_vnd: lowest acceptable total price in VND (e.g. 3000000000 for 3 tỷ).
            max_price_vnd: highest acceptable total price in VND.
            bedrooms: exact bedroom count. The data holds 1-4.
            limit: max cards to return (default 10).
        """
        if property_type and property_type not in PROPERTY_TYPES:
            raise ToolError(
                f"Unknown property_type '{property_type}'. Valid: {', '.join(PROPERTY_TYPES)}."
            )
        return svc.search_listings(
            project_id=project_id,
            building_id=building_id,
            property_type=property_type,
            min_price_vnd=min_price_vnd,
            max_price_vnd=max_price_vnd,
            bedrooms=bedrooms,
            limit=limit,
        )

    @mcp.tool
    def get_listing(listing_id: str) -> dict:
        """Get the full detail of one listing — the detail page in US1.

        Use when the user asks about one specific unit they picked from a search result, or
        before answering a question a search card cannot answer (floor, view, legal status,
        furnishing, photos).

        Returns one object with every card field (id, title, url, source, project_id,
        building_id, property_type, area_m2, bedrooms, bathrooms, price_vnd, price_per_m2_vnd,
        status, lat, lng, thumbnail) plus the detail-only fields: floor_num, floor_band,
        direction_balcony, view, legal_status, furnishing, usage_status, price_type, area_type,
        image_count, images, first_seen, last_seen, crawled_at. Raises if the id does not exist,
        so a returned object is always a real listing.

        Reading the result honestly:
        - Many fields are genuinely missing in the source data (floor_num on 60% of listings,
          bathrooms on 23%, view on 22%, legal_status on 12%). A null means "not recorded" —
          say so instead of guessing or implying the feature is absent.
        - `status` is either "ĐANG BÁN" or null; null means unknown, never "đã bán". Do not
          tell the user a unit is still available on the strength of a null.
        - `images` is capped at 40 URLs while `image_count` is the count at the source, so
          image_count > len(images) on about a third of listings. Cite len(images) for what you
          can actually show, and `url` for the full gallery.
        - `price_type` is "asking" — the seller's asking price, not an appraisal.

        Args:
            listing_id: the `id` from a search result card, e.g. one returned by search_listings.
        """
        row = svc.get_listing(listing_id)
        if row is None:
            raise ToolError(f"No listing found with id '{listing_id}'.")
        return row

    @mcp.tool
    def list_project_listings(project_id: str, limit: int = 50, offset: int = 0) -> dict:
        """Page through every listing in a project — the "xem tất cả" view.

        Use when a search returned more than 3 results, or the user asks to see everything in a
        project. For a filtered subset (price, bedrooms, tower) use search_listings instead.

        Returns {"total": int, "offset": int, "count": int, "has_more": bool, "listings": [...]}
        where `listings` holds the same card objects as search_listings, cheapest first, and
        `total` is how many the project has in all. Tell the user the total, not the page size:
        the largest projects hold 685 and 623 listings, so a first page of 50 is a small slice.
        When `has_more` is true, fetch the next page by calling again with
        offset = offset + count. Raises if `project_id` is not a real project.

        Args:
            project_id: a project id from search_projects / resolve_project.
            limit: page size, max cards per call (default 50).
            offset: how many listings to skip; 0 is the first page.
        """
        project = loc_svc.get_location(project_id)
        if project is None or project.get("level") != "project":
            raise ToolError(f"'{project_id}' is not a known project id.")
        if limit < 1 or offset < 0:
            raise ToolError("limit must be >= 1 and offset >= 0.")
        return svc.list_by_project(project_id=project_id, limit=limit, offset=offset)

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
