"""Tests for Bunch 6: search_media tool."""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def search_input():
    from plex_mcp.schemas.inputs import SearchMediaInput

    return SearchMediaInput(query="Dune", limit=5)


def test_search_media_returns_markdown(mock_plex_server, fake_movie, search_input):
    mock_plex_server.library.search.return_value = [fake_movie]
    with patch("plex_mcp.tools.search.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.search import search_media

        result = asyncio.get_event_loop().run_until_complete(search_media(search_input))
    assert "## Search" in result
    assert "Dune" in result


def test_search_media_no_results_message(mock_plex_server, search_input):
    mock_plex_server.library.search.return_value = []
    with patch("plex_mcp.tools.search.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.search import search_media

        result = asyncio.get_event_loop().run_until_complete(search_media(search_input))
    assert "No results" in result or "0 results" in result


def test_search_media_json_format(mock_plex_server, fake_movie):
    from plex_mcp.schemas.inputs import SearchMediaInput

    mock_plex_server.library.search.return_value = [fake_movie]
    with patch("plex_mcp.tools.search.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.search import search_media

        inp = SearchMediaInput(query="Dune", format="json")
        result = asyncio.get_event_loop().run_until_complete(search_media(inp))
    parsed = json.loads(result)
    assert parsed["success"] is True
    assert parsed["tool"] == "search_media"
    assert isinstance(parsed["data"], list)


def test_search_media_type_filter(mock_plex_server, fake_movie):
    from plex_mcp.schemas.inputs import SearchMediaInput

    fake_episode = MagicMock()
    fake_episode.TYPE = "episode"
    fake_episode.title = "Dune Pilot"
    mock_plex_server.library.search.return_value = [fake_movie, fake_episode]
    with patch("plex_mcp.tools.search.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.search import search_media

        inp = SearchMediaInput(query="Dune", media_type="movie")
        result = asyncio.get_event_loop().run_until_complete(search_media(inp))
    assert "Dune" in result
    # episode should be filtered out — only movie in result
    assert "Dune Pilot" not in result


def test_search_media_respects_limit(mock_plex_server):
    from plex_mcp.schemas.inputs import SearchMediaInput

    many = [
        MagicMock(
            TYPE="movie",
            title=f"Movie {i}",
            year=2020 + i,
            ratingKey=i,
            summary="...",
            audienceRating=7.0,
            duration=5400000,
            genres=[],
        )
        for i in range(20)
    ]
    mock_plex_server.library.search.return_value = many
    with patch("plex_mcp.tools.search.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.search import search_media

        inp = SearchMediaInput(query="Movie", limit=3)
        result = asyncio.get_event_loop().run_until_complete(search_media(inp))
    # Only 3 results rendered
    assert result.count("**Movie") <= 3
