"""Single Supabase client for the whole server.

The MCP server is trusted server-side code, so it uses the service-role key and reads all rows.
Never build one client per call — reuse the cached one.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from . import config


@lru_cache(maxsize=1)
def get_client() -> Client:
    """Return the process-wide Supabase client (created lazily on first use)."""
    return create_client(config.supabase_url(), config.supabase_key())
