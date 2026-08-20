"""The single FastMCP server instance for Real Estate Market Intelligence.

Run locally (stdio):   python -m app
Run for an agent (http): set MCP_TRANSPORT=http in .env, then python -m app
Or via fastmcp CLI:     fastmcp run src/app/server.py
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import config
from .tools import register_all

mcp = FastMCP(
    name="real-estate-mcp",
    instructions=(
        "Tools for searching and analyzing Vietnamese real-estate projects and property listings. "
        "Data is descriptive only: never give valuation, financing, or investment advice "
        "(out of scope). Resolve the user's target PROJECT first (search_projects/resolve_project), "
        "then search listings, show details, compare, analyze, map, or start a booking/consultation."
    ),
)

register_all(mcp)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(request: Request) -> JSONResponse:
    """Unauthenticated liveness probe for the hosting platform.

    /mcp cannot serve this purpose: it answers 401 without a token, which a
    platform health check reads as a failing service. On a scale-to-zero plan
    the probe is also what keeps the server awake — without it the first tool
    call an agent makes lands on a cold start and fails rather than waits.
    """
    return JSONResponse({"status": "ok"})


def main() -> None:
    """Console-script / `python -m` entrypoint. Transport is chosen via env (.env)."""
    transport = config.transport()
    if transport == "http":
        token = config.auth_token()
        if token:
            # Shared-secret gate for agent -> server calls. Needed whenever the
            # server is reachable outside a private network; the caller sends
            # `Authorization: Bearer <token>`.
            mcp.auth = StaticTokenVerifier(tokens={token: {"client_id": "agent"}})
        mcp.run(transport="http", host=config.host(), port=config.port())
    else:
        mcp.run()  # stdio


if __name__ == "__main__":
    main()
