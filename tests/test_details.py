"""Tests for Bunch 6: get_media_details tool."""

import asyncio
from unittest.mock import MagicMock, patch


def test_get_media_details_concise(mock_plex_server, fake_movie):
    from plex_mcp.schemas.inputs import GetMediaDetailsInput

    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.fetchItem.return_value = fake_movie
    with patch("plex_mcp.tools.details.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.details import get_media_details

        inp = GetMediaDetailsInput(title="Dune", year=2021)
        result = asyncio.get_event_loop().run_until_complete(get_media_details(inp))
    assert "Dune" in result
    assert "##" in result


def test_get_media_details_detailed_flag(mock_plex_server, fake_movie):
    from plex_mcp.schemas.inputs import GetMediaDetailsInput

    # Setup cast/crew on fake_movie
    fake_movie.roles = [MagicMock(tag="Timothée Chalamet", role="Paul Atreides")]
    fake_movie.directors = [MagicMock(tag="Denis Villeneuve")]
    fake_movie.media = [
        MagicMock(
            parts=[
                MagicMock(
                    file="/movies/Dune.mkv",
                    size=62000000000,
                    container="mkv",
                    videoStreams=[MagicMock(codec="hevc", height=2160, width=3840)],
                    audioStreams=[MagicMock(codec="truehd", audioChannelLayout="7.1")],
                )
            ]
        )
    ]
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.fetchItem.return_value = fake_movie
    with patch("plex_mcp.tools.details.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.details import get_media_details

        inp = GetMediaDetailsInput(title="Dune", year=2021, detailed=True)
        result = asyncio.get_event_loop().run_until_complete(get_media_details(inp))
    assert "Cast" in result or "Director" in result


def test_get_media_details_not_found(mock_plex_server):
    from plex_mcp.schemas.inputs import GetMediaDetailsInput

    mock_plex_server.library.search.return_value = []
    with patch("plex_mcp.tools.details.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.details import get_media_details

        inp = GetMediaDetailsInput(title="XYZZY Movie That Doesnt Exist")
        result = asyncio.get_event_loop().run_until_complete(get_media_details(inp))
    assert "MEDIA_NOT_FOUND" in result or "❌" in result


def test_get_media_details_episode_resolution(mock_plex_server, fake_episode):
    from plex_mcp.schemas.inputs import GetMediaDetailsInput

    mock_plex_server.library.search.return_value = [fake_episode]
    mock_plex_server.fetchItem.return_value = fake_episode
    with patch("plex_mcp.tools.details.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.details import get_media_details

        inp = GetMediaDetailsInput(title="Breaking Bad", season=1, episode=1, media_type="episode")
        result = asyncio.get_event_loop().run_until_complete(get_media_details(inp))
    assert "Breaking Bad" in result or "S01E01" in result
