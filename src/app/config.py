"""Environment-based configuration. All secrets come from `.env` (gitignored)."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


@lru_cache(maxsize=1)
def supabase_url() -> str:
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise ConfigError("SUPABASE_URL is not set. Copy .env.example to .env and fill it in.")
    return url


@lru_cache(maxsize=1)
def supabase_key() -> str:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise ConfigError(
            "SUPABASE_SERVICE_ROLE_KEY is not set. Copy .env.example to .env and fill it in."
        )
    return key


def transport() -> str:
    return os.environ.get("MCP_TRANSPORT", "stdio")


def host() -> str:
    return os.environ.get("MCP_HOST", "127.0.0.1")


def port() -> int:
    return int(os.environ.get("MCP_PORT", "8000"))
