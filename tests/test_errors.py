"""Tests for error handling infrastructure."""

import asyncio
import json

import plexapi.exceptions
import pytest

# --- Task 4.1: PlexMCPError Class ---


def test_plex_mcp_error_attributes():
    from plex_mcp.errors import PlexMCPError

    e = PlexMCPError(
        code="MEDIA_NOT_FOUND",
        message='No media matching "Dune" found.',
        suggestions=["Try search_media(query='Dune')"],
    )
    assert e.code == "MEDIA_NOT_FOUND"
    assert e.raw is None


def test_plex_mcp_error_to_plex_error():
    from plex_mcp.errors import PlexMCPError
    from plex_mcp.schemas.common import PlexError

    e = PlexMCPError(code="AUTH_FAILED", message="Bad token")
    schema = e.to_plex_error()
    assert isinstance(schema, PlexError)
    assert schema.code == "AUTH_FAILED"


def test_plex_mcp_error_to_markdown():
    from plex_mcp.errors import PlexMCPError

    e = PlexMCPError(
        code="CLIENT_NOT_FOUND",
        message="Client 'My TV' not found.",
        suggestions=["Use get_clients() to list available players."],
    )
    md = e.to_markdown()
    assert "## ❌ Error: CLIENT_NOT_FOUND" in md
    assert "Client 'My TV' not found." in md
    assert "get_clients()" in md
    assert "**What to try:**" in md


def test_plex_mcp_error_to_markdown_no_suggestions():
    from plex_mcp.errors import PlexMCPError

    e = PlexMCPError(code="UNKNOWN", message="Something broke.")
    md = e.to_markdown()
    assert "## ❌ Error: UNKNOWN" in md
    assert "**What to try:**" not in md


def test_plex_mcp_error_is_exception():
    from plex_mcp.errors import PlexMCPError

    with pytest.raises(PlexMCPError):
        raise PlexMCPError(code="RATE_LIMITED", message="Slow down.")


def test_error_raw_preserved():
    from plex_mcp.errors import PlexMCPError

    orig = RuntimeError("network gone")
    e = PlexMCPError(code="CONNECTION_FAILED", message="Can't connect", raw=orig)
    assert e.raw is orig


# --- Task 4.2: safe_tool_call Wrapper ---


def test_safe_tool_call_passes_through_success():
    from plex_mcp.errors import safe_tool_call

    async def handler(_):
        return "## ✅ Result"

    result = asyncio.get_event_loop().run_until_complete(
        safe_tool_call(handler, None, format="markdown")
    )
    assert result == "## ✅ Result"


def test_safe_tool_call_catches_plex_mcp_error_markdown():
    from plex_mcp.errors import PlexMCPError, safe_tool_call

    async def handler(_):
        raise PlexMCPError(code="MEDIA_NOT_FOUND", message="Not found.")

    result = asyncio.get_event_loop().run_until_complete(
        safe_tool_call(handler, None, format="markdown")
    )
    assert "## ❌ Error: MEDIA_NOT_FOUND" in result


def test_safe_tool_call_catches_plex_mcp_error_json():
    from plex_mcp.errors import PlexMCPError, safe_tool_call

    async def handler(_):
        raise PlexMCPError(code="AUTH_FAILED", message="Bad token.")

    result = asyncio.get_event_loop().run_until_complete(
        safe_tool_call(handler, None, format="json")
    )
    parsed = json.loads(result)
    assert parsed["success"] is False
    assert parsed["error"]["code"] == "AUTH_FAILED"


def test_safe_tool_call_catches_unauthorized():
    from plex_mcp.errors import safe_tool_call

    async def handler(_):
        raise plexapi.exceptions.Unauthorized("nope")

    result = asyncio.get_event_loop().run_until_complete(
        safe_tool_call(handler, None, format="markdown")
    )
    assert "AUTH_FAILED" in result


def test_safe_tool_call_catches_unknown_exception():
    from plex_mcp.errors import safe_tool_call

    async def handler(_):
        raise ValueError("something unexpected")

    result = asyncio.get_event_loop().run_until_complete(
        safe_tool_call(handler, None, format="markdown")
    )
    assert "UNKNOWN" in result or "❌" in result


# --- Task 4.3: Error Construction Helpers ---


def test_media_not_found_error_includes_title():
    from plex_mcp.errors import media_not_found_error

    e = media_not_found_error(title="Dune", year=2019)
    assert "Dune" in e.message
    assert "2019" in e.message
    assert e.code == "MEDIA_NOT_FOUND"
    assert any("search_media" in s for s in e.suggestions)


def test_media_ambiguous_error_lists_candidates():
    from plex_mcp.errors import media_ambiguous_error

    candidates = [("Dune", 2021, "movie"), ("Dune", 1984, "movie")]
    e = media_ambiguous_error(title="Dune", candidates=candidates)
    assert "2021" in e.message
    assert "1984" in e.message
    assert e.code == "MEDIA_AMBIGUOUS"


def test_client_not_found_error_mentions_get_clients():
    from plex_mcp.errors import client_not_found_error

    e = client_not_found_error("My TV")
    assert "My TV" in e.message
    assert any("get_clients" in s for s in e.suggestions)


def test_library_not_found_error_mentions_get_libraries():
    from plex_mcp.errors import library_not_found_error

    e = library_not_found_error("4K Movies")
    assert "4K Movies" in e.message
    assert any("get_libraries" in s for s in e.suggestions)


def test_no_active_session_error_mentions_play_media():
    from plex_mcp.errors import no_active_session_error

    e = no_active_session_error()
    assert any("play_media" in s for s in e.suggestions)
