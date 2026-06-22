"""
Thin Anthropic SDK wrapper.

Lazily initialises a single client instance.  All code that needs to call
Claude goes through get_client() so the API key and timeout are configured
in exactly one place.
"""

from anthropic import Anthropic

from app.config import settings

_client: Anthropic | None = None

# Hard timeout for every Claude call — consistent with §6.9's "wrap in try/except
# with a timeout; on failure mark needs_review, never raise to the user."
DEFAULT_TIMEOUT = 30.0


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=DEFAULT_TIMEOUT,
        )
    return _client
