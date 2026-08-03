"""Action/CTA tools — return UI-action payloads (forms, buttons) for the frontend.

Per the PRD "Action Triggering": the AI responds with concrete UI actions. These tools do NOT
write to the DB in this phase; they return the FORM SPEC the UI should render, handling the two
cases from US2.1/US2.2: authenticated vs not-authenticated. Actually persisting a booking is a
phase-2 TODO (needs a `bookings` table + write path).
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..services import listings as listing_svc
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
    template = _AUTHED_FIELDS if is_authenticated else _GUEST_FIELDS
    return {
        "action": action,  # UI switches on this
        "project": {"id": project["id"], "name": project["name"]},
        "authenticated": is_authenticated,
        # Copy: returning the module-level list would hand every caller the same objects, so one
        # in-place edit (a UI tweaking a label) would change the form for every later call.
        "fields": [dict(field) for field in template],
        "submit_endpoint": f"/api/{action}",  # frontend posts the collected form here (phase 2)
        # Nothing is written to the database yet — see the `bookings` table item in
        # docs/TOOLS_TODO.md. Stated in the payload as well as the docstrings because an agent
        # that treats this call as "the booking is made" would tell the user it is confirmed.
        "persisted": False,
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool
    def start_visit_booking(project_id: str, is_authenticated: bool = False) -> dict:
        """Open the "đặt lịch tham quan" (site-visit) form for a project (US2.1).

        Use when the user picks the "Đặt lịch tham quan" CTA or asks to visit a project. Resolve
        the project first with resolve_project / search_projects.

        This does NOT create a booking. It returns the form for the UI to render, and nothing is
        saved anywhere — `persisted` is false. Never tell the user their visit is booked or
        confirmed off the back of this call; the booking exists only once they submit the form.

        Returns {"action": "visit_booking", "project": {id, name}, "authenticated": bool,
        "fields": [{name, label, type, required}], "submit_endpoint": str, "persisted": false}.
        Render `fields` as-is rather than inventing your own; a guest form asks full_name, phone,
        email, preferred_time, note, and a signed-in form asks only preferred_time and note
        because the contact details come from the profile. Raises if `project_id` is not a real
        project.

        Args:
            project_id: a project id from resolve_project / search_projects.
            is_authenticated: whether this user is signed in. This is session state the host
                application knows — do not guess it from the conversation. If you are unsure,
                leave it false: asking a signed-in user for their phone again is a small
                annoyance, while marking a guest as signed in produces a request with no
                contact details at all.
        """
        return _form_payload("visit_booking", project_id, is_authenticated)

    @mcp.tool
    def start_consultation(project_id: str, is_authenticated: bool = False) -> dict:
        """Open the "tư vấn mua nhà" (buyer consultation) form for a project (US2.2).

        Use when the user picks the "Tư vấn mua nhà" CTA, or asks to speak to an advisor — for
        example when a policy or legal question falls outside what these tools can answer.
        Resolve the project first with resolve_project / search_projects.

        This does NOT request a consultation. It returns the form for the UI to render, and
        nothing is saved anywhere — `persisted` is false. Never tell the user an advisor will
        contact them off the back of this call; that only follows once they submit the form.

        Returns the same shape as start_visit_booking with "action": "consultation" —
        {"action", "project": {id, name}, "authenticated", "fields": [{name, label, type,
        required}], "submit_endpoint", "persisted": false}. Here `preferred_time` is when the
        user wants the advisor to call, and `note` is where their question belongs. Raises if
        `project_id` is not a real project.

        Args:
            project_id: a project id from resolve_project / search_projects.
            is_authenticated: whether this user is signed in — session state from the host
                application, not something to infer. When unsure leave it false; see
                start_visit_booking for why.
        """
        return _form_payload("consultation", project_id, is_authenticated)

    @mcp.tool
    def listing_cta_actions(listing_id: str) -> dict:
        """Return the four CTA buttons to show under a listing result (US1).

        Use once you are showing a specific listing to the user, to offer the next steps:
        xem tất cả, đặt lịch tham quan, tư vấn mua nhà, xem bản đồ.

        Returns {"listing_id", "project_id", "ctas": [{action, label, next_tool, args}]}. Each
        cta is directly executable: when the user clicks one, call its `next_tool` with its
        `args` exactly as given. `args` is prefilled with the listing's project_id, which the
        booking and "xem tất cả" tools all require. Raises if the listing does not exist.

        When to show these: the UI rule is 1-3 search results -> render each card with these
        CTAs; more than 3 -> summarise and lead with the "xem tất cả" button instead of
        listing everything.

        Args:
            listing_id: the `id` of a listing you are currently showing.
        """
        listing = listing_svc.get_listing_ref(listing_id)
        if listing is None:
            raise ToolError(f"No listing found with id '{listing_id}'.")
        # Every next_tool below needs the project, not the listing — a CTA carrying only the
        # listing id would leave the agent to guess or re-query before it could act.
        args = {"project_id": listing["project_id"]}
        return {
            "listing_id": listing_id,
            "project_id": listing["project_id"],
            "ctas": [
                {"action": "view_all", "label": "Xem tất cả",
                 "next_tool": "list_project_listings", "args": args},
                {"action": "book_visit", "label": "Đặt lịch tham quan",
                 "next_tool": "start_visit_booking", "args": args},
                {"action": "consult", "label": "Tư vấn mua nhà",
                 "next_tool": "start_consultation", "args": args},
                {"action": "view_map", "label": "Xem bản đồ",
                 "next_tool": "map_listings", "args": args},
            ],
        }
