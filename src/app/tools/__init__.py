"""Tool modules. Each exposes a `register(mcp)` function that attaches its @mcp.tool functions."""

from fastmcp import FastMCP

from . import analytics, cta, listings, locations, rag


def register_all(mcp: FastMCP) -> None:
    """Register every tool group on the single server instance."""
    locations.register(mcp)
    listings.register(mcp)
    analytics.register(mcp)
    cta.register(mcp)
    rag.register(mcp)  # phase-2 stubs, disabled by default
