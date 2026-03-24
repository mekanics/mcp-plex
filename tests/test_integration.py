"""Integration tests — Tasks 10.2 and 10.3.

End-to-end tests: full call chain from schema → tool handler → formatter → string.
Uses mock PlexServer; no real network calls.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

# ── Helpers ────────────────────────────────────────────────────────────────────


def rough_token_count(text: str) -> int:
    """Approximation: ~4 chars per token."""
    return len(text) // 4


# ── Task 10.2: Integration tests ───────────────────────────────────────────────


def test_search_then_details_workflow(mock_plex_server: MagicMock, fake_movie: MagicMock) -> None:
    """Simulate: agent searches, picks top result, gets details."""
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.fetchItem.return_value = fake_movie

    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.schemas.inputs import GetMediaDetailsInput, SearchMediaInput
        from plex_mcp.tools.details import get_media_details
        from plex_mcp.tools.search import search_media

        search_result = asyncio.get_event_loop().run_until_complete(
            search_media(SearchMediaInput(query="Dune"))
        )
        assert "Dune" in search_result

        detail_result = asyncio.get_event_loop().run_until_complete(
            get_media_details(GetMediaDetailsInput(title="Dune", year=2021))
        )
        assert "Dune" in detail_result


def test_play_media_workflow(
    mock_plex_server: MagicMock,
    fake_movie: MagicMock,
    fake_plex_client: MagicMock,
) -> None:
    """Simulate: dry-run → user confirms → play."""
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    mock_plex_server.fetchItem.return_value = fake_movie
    mock_plex_server.client.return_value = fake_plex_client

    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.schemas.inputs import PlayMediaInput
        from plex_mcp.tools.playback import play_media

        dry = asyncio.get_event_loop().run_until_complete(
            play_media(PlayMediaInput(title="Dune", client="Living Room TV", confirmed=False))
        )
        assert "⚠️" in dry
        assert "confirmed=True" in dry

        confirmed = asyncio.get_event_loop().run_until_complete(
            play_media(PlayMediaInput(title="Dune", client="Living Room TV", confirmed=True))
        )
        assert "✅" in confirmed


def test_get_clients_then_play_workflow(
    mock_plex_server: MagicMock,
    fake_movie: MagicMock,
    fake_plex_client: MagicMock,
) -> None:
    """Simulate: agent calls get_clients to find target, then play_media."""
    mock_plex_server.clients.return_value = [fake_plex_client]
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.fetchItem.return_value = fake_movie
    mock_plex_server.client.return_value = fake_plex_client

    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.schemas.inputs import GetClientsInput, PlayMediaInput
        from plex_mcp.tools.libraries import get_clients
        from plex_mcp.tools.playback import play_media

        clients_result = asyncio.get_event_loop().run_until_complete(get_clients(GetClientsInput()))
        assert "Living Room TV" in clients_result

        play_result = asyncio.get_event_loop().run_until_complete(
            play_media(PlayMediaInput(title="Dune", client="Living Room TV", confirmed=True))
        )
        assert "✅" in play_result


def test_error_propagation_is_user_friendly(mock_plex_server: MagicMock) -> None:
    """Errors should return readable strings, not raise exceptions."""
    mock_plex_server.library.search.return_value = []

    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.schemas.inputs import SearchMediaInput
        from plex_mcp.tools.search import search_media

        # Empty query rejected at schema validation — safe_tool_call surfaces it cleanly
        try:
            result = asyncio.get_event_loop().run_until_complete(
                search_media(SearchMediaInput(query="xyzzy_nonexistent"))
            )
            # No results path → graceful message
            assert isinstance(result, str)
            assert "No results" in result or "0 results" in result or "xyzzy" in result.lower()
        except Exception as e:
            pytest.fail(f"search_media raised an unexpected exception: {e}")


def test_playback_control_workflow(mock_plex_server: MagicMock, fake_session: MagicMock) -> None:
    """Simulate: dry-run pause → confirm pause."""
    mock_plex_server.sessions.return_value = [fake_session]
    mock_client = MagicMock()
    mock_plex_server.client.return_value = mock_client

    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.schemas.inputs import PlaybackControlInput
        from plex_mcp.tools.playback import playback_control

        dry = asyncio.get_event_loop().run_until_complete(
            playback_control(PlaybackControlInput(action="pause", confirmed=False))
        )
        assert "⚠️" in dry
        assert "confirmed=True" in dry

        confirmed = asyncio.get_event_loop().run_until_complete(
            playback_control(
                PlaybackControlInput(
                    action="pause",
                    client=fake_session.player.title,
                    confirmed=True,
                )
            )
        )
        assert "✅" in confirmed
        mock_client.pause.assert_called_once()


def test_browse_then_details_workflow(mock_plex_server: MagicMock, fake_movie: MagicMock) -> None:
    """Simulate: browse library → pick item → get details."""
    # Give fake_movie a proper addedAt string for browse_library
    fake_movie.addedAt = "2024-01-15T10:00:00"

    mock_section = MagicMock()
    mock_section.title = "Movies"
    mock_section.search.return_value = [fake_movie]
    mock_plex_server.library.section.return_value = mock_section
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.fetchItem.return_value = fake_movie

    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.schemas.inputs import BrowseLibraryInput, GetMediaDetailsInput
        from plex_mcp.tools.browse import browse_library
        from plex_mcp.tools.details import get_media_details

        browse_result = asyncio.get_event_loop().run_until_complete(
            browse_library(BrowseLibraryInput(library="Movies"))
        )
        assert "Dune" in browse_result

        details_result = asyncio.get_event_loop().run_until_complete(
            get_media_details(GetMediaDetailsInput(title="Dune", year=2021))
        )
        assert "Dune" in details_result


def test_json_format_end_to_end(mock_plex_server: MagicMock, fake_movie: MagicMock) -> None:
    """JSON format works consistently across tools."""
    mock_plex_server.library.search.return_value = [fake_movie]

    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.schemas.inputs import SearchMediaInput
        from plex_mcp.tools.search import search_media

        result = asyncio.get_event_loop().run_until_complete(
            search_media(SearchMediaInput(query="Dune", format="json"))
        )
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["tool"] == "search_media"
        assert isinstance(parsed["data"], list)
        assert parsed["data"][0]["title"] == "Dune"


# ── Task 10.3: Token budget smoke tests ────────────────────────────────────────


def test_search_response_token_budget(mock_plex_server: MagicMock) -> None:
    """Default search response must stay under 500 tokens (SAD §1.4)."""
    movies = [
        MagicMock(
            TYPE="movie",
            title=f"Movie {i}",
            year=2020 + i,
            ratingKey=i,
            summary="A " + "word " * 30 + "summary.",
            audienceRating=7.5,
            duration=7200000,
            genres=[MagicMock(tag="Action")],
        )
        for i in range(10)
    ]
    mock_plex_server.library.search.return_value = movies

    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.schemas.inputs import SearchMediaInput
        from plex_mcp.tools.search import search_media

        result = asyncio.get_event_loop().run_until_complete(
            search_media(SearchMediaInput(query="Movie", limit=10))
        )

    tokens = rough_token_count(result)
    assert tokens <= 500, f"Search result too long: {tokens} tokens (max 500)"


def test_now_playing_empty_response_concise(mock_plex_server: MagicMock) -> None:
    """Empty now_playing response should be very concise."""
    mock_plex_server.sessions.return_value = []

    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.schemas.inputs import NowPlayingInput
        from plex_mcp.tools.sessions import now_playing

        result = asyncio.get_event_loop().run_until_complete(now_playing(NowPlayingInput()))

    assert rough_token_count(result) < 100, "Empty now_playing should be very short"


def test_library_list_token_budget(mock_plex_server: MagicMock) -> None:
    """get_libraries for a typical server should stay under 200 tokens."""
    sections = [
        MagicMock(
            title=f"Library {i}",
            type="movie",
            totalSize=100 * i,
            totalStorage=1_000_000_000 * i,
            agent="tv.plex.agents.movie",
        )
        for i in range(5)
    ]
    mock_plex_server.library.sections.return_value = sections

    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.schemas.inputs import GetLibrariesInput
        from plex_mcp.tools.libraries import get_libraries

        result = asyncio.get_event_loop().run_until_complete(get_libraries(GetLibrariesInput()))

    tokens = rough_token_count(result)
    assert tokens <= 200, f"Libraries response too long: {tokens} tokens (max 200)"
