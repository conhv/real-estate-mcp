"""The single FastMCP server instance for Real Estate Market Intelligence.

Run locally (stdio):   python -m app
Run for an agent (http): set MCP_TRANSPORT=http in .env, then python -m app
Or via fastmcp CLI:     fastmcp run src/app/server.py
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

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
