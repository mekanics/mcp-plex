"""Tests for Bunch 6: browse_library tool."""

import asyncio
import json
from unittest.mock import MagicMock, patch


def make_browse_input(library="Movies", **kwargs):
    from plex_mcp.schemas.inputs import BrowseLibraryInput

    return BrowseLibraryInput(library=library, **kwargs)


def test_browse_library_returns_markdown(mock_plex_server):
    mock_section = MagicMock()
    mock_section.title = "Movies"
    mock_section.search.return_value = [
        MagicMock(
            title="Aliens",
            year=1986,
            TYPE="movie",
            audienceRating=8.4,
            duration=8220000,
            isWatched=True,
            addedAt=MagicMock(isoformat=lambda: "2024-01-01"),
        )
    ]
    mock_plex_server.library.section.return_value = mock_section
    with patch("plex_mcp.tools.browse.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.browse import browse_library

        result = asyncio.get_event_loop().run_until_complete(browse_library(make_browse_input()))
    assert "Movies" in result
    assert "Aliens" in result


def test_browse_library_not_found_raises(mock_plex_server):
    import plexapi.exceptions

    mock_plex_server.library.section.side_effect = plexapi.exceptions.NotFound("nope")
    with patch("plex_mcp.tools.browse.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.browse import browse_library

        result = asyncio.get_event_loop().run_until_complete(
            browse_library(make_browse_input(library="Nonexistent"))
        )
    assert "LIBRARY_NOT_FOUND" in result or "❌" in result


def test_browse_library_pagination(mock_plex_server):
    mock_section = MagicMock()
    mock_section.title = "Movies"
    items = [
        MagicMock(
            title=f"Movie {i}",
            year=2000 + i,
            TYPE="movie",
            audienceRating=7.0,
            duration=5400000,
            isWatched=False,
            addedAt=MagicMock(isoformat=lambda: "2024-01-01"),
        )
        for i in range(50)
    ]
    mock_section.search.return_value = items
    with patch("plex_mcp.tools.browse.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.browse import browse_library

        result = asyncio.get_event_loop().run_until_complete(
            browse_library(make_browse_input(page=1, page_size=5))
        )
    assert "Page 1" in result


def test_browse_library_json_format(mock_plex_server):
    mock_section = MagicMock()
    mock_section.title = "Movies"
    mock_section.search.return_value = []
    mock_plex_server.library.section.return_value = mock_section
    with patch("plex_mcp.tools.browse.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.browse import browse_library

        result = asyncio.get_event_loop().run_until_complete(
            browse_library(make_browse_input(format="json"))
        )
    parsed = json.loads(result)
    assert parsed["tool"] == "browse_library"
