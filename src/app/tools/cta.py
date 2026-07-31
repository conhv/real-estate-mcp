"""Action/CTA tools — return UI-action payloads (forms, buttons) for the frontend.

Per the PRD "Action Triggering": the AI responds with concrete UI actions. These tools do NOT
write to the DB in this phase; they return the FORM SPEC the UI should render, handling the two
cases from US2.1/US2.2: authenticated vs not-authenticated. Actually persisting a booking is a
phase-2 TODO (needs a `bookings` table + write path).
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..services import locations as loc_svc

# Fields collected when the user is NOT authenticated (need contact info).
_GUEST_FIELDS = [
    {"name": "full_name", "label": "Họ và tên", "type": "text", "required": True},
    {"name": "phone", "label": "Số điện thoại", "type": "tel", "required": True},
    {"name": "email", "label": "Email", "type": "email", "required": False},
    {"name": "preferred_time", "label": "Thời gian mong muốn", "type": "datetime", "required": True},
    {"name": "note", "label": "Ghi chú", "type": "textarea", "required": False},
]

# Fields when the user IS authenticated (contact prefilled from profile).
_AUTHED_FIELDS = [
    {"name": "preferred_time", "label": "Thời gian mong muốn", "type": "datetime", "required": True},
    {"name": "note", "label": "Ghi chú", "type": "textarea", "required": False},
]


def _form_payload(action: str, project_id: str, is_authenticated: bool) -> dict:
    project = loc_svc.get_location(project_id)
    if project is None or project.get("level") != "project":
        raise ToolError(f"'{project_id}' is not a known project id.")
    return {
        "action": action,  # UI switches on this
        "project": {"id": project["id"], "name": project["name"]},
        "authenticated": is_authenticated,
        "fields": _AUTHED_FIELDS if is_authenticated else _GUEST_FIELDS,
        "submit_endpoint": f"/api/{action}",  # frontend posts the collected form here (phase 2)
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool
    def start_visit_booking(project_id: str, is_authenticated: bool = False) -> dict:
        """Build the 'đặt lịch tham quan' (site-visit) form for a project (US2.1).

        Use when the user picks the "Đặt lịch tham quan" CTA. Returns a form spec the UI renders;
        field set depends on `is_authenticated`. Requires a resolved project_id first.
        """
        return _form_payload("visit_booking", project_id, is_authenticated)

    @mcp.tool
    def start_consultation(project_id: str, is_authenticated: bool = False) -> dict:
        """Build the 'tư vấn mua nhà' (buyer consultation) form for a project (US2.2).

        Use when the user picks the "Tư vấn mua nhà" CTA. Returns a form spec; field set depends
        on `is_authenticated`. Requires a resolved project_id first.
        """
        return _form_payload("consultation", project_id, is_authenticated)

    @mcp.tool
    def listing_cta_actions(listing_id: str) -> dict:
        """Return the CTA buttons to show under a listing/result (US1).

        Use to render the action buttons: xem tất cả, đặt lịch tham quan, tư vấn mua nhà, xem bản đồ.
        Returns {"listing_id": ..., "ctas": [{action, label, next_tool}]} — the agent uses
        `next_tool` to know which tool to call when the user clicks each button.
        """
        return {
            "listing_id": listing_id,
            "ctas": [
                {"action": "view_all", "label": "Xem tất cả", "next_tool": "list_project_listings"},
                {"action": "book_visit", "label": "Đặt lịch tham quan", "next_tool": "start_visit_booking"},
                {"action": "consult", "label": "Tư vấn mua nhà", "next_tool": "start_consultation"},
                {"action": "view_map", "label": "Xem bản đồ", "next_tool": "map_listings"},
            ],
        }
