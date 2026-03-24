"""Tests for Bunch 7: now_playing tool."""

import asyncio
import json
from unittest.mock import MagicMock, patch


def test_now_playing_active_sessions(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    with patch("plex_mcp.tools.sessions.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import NowPlayingInput
        from plex_mcp.tools.sessions import now_playing

        result = asyncio.get_event_loop().run_until_complete(now_playing(NowPlayingInput()))
    assert "## 📺 Now Playing" in result
    assert "1 active" in result or "session" in result.lower()


def test_now_playing_empty_sessions(mock_plex_server):
    mock_plex_server.sessions.return_value = []
    with patch("plex_mcp.tools.sessions.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import NowPlayingInput
        from plex_mcp.tools.sessions import now_playing

        result = asyncio.get_event_loop().run_until_complete(now_playing(NowPlayingInput()))
    assert "No active sessions" in result or "nothing" in result.lower() or "0" in result


def test_now_playing_json_format(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    with patch("plex_mcp.tools.sessions.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import NowPlayingInput
        from plex_mcp.tools.sessions import now_playing

        result = asyncio.get_event_loop().run_until_complete(
            now_playing(NowPlayingInput(format="json"))
        )
    parsed = json.loads(result)
    assert parsed["tool"] == "now_playing"
    assert isinstance(parsed["data"], list)


def test_now_playing_transcode_status_mapped(mock_plex_server):
    session = MagicMock()
    session.TYPE = "movie"
    session.title = "Dune"
    session.grandparentTitle = None
    session.year = 2021
    session.ratingKey = 1
    session.duration = 9300000
    session.viewOffset = 3600000
    session.usernames = ["alice"]
    session.player = MagicMock(title="Apple TV", platform="tvOS", product="Plex", state="playing")
    transcode = MagicMock()
    transcode.videoDecision = "transcode"
    transcode.audioDecision = "copy"
    transcode.bandwidth = 12000
    transcode.error = None
    session.transcodeSessions = [transcode]
    mock_plex_server.sessions.return_value = [session]
    with patch("plex_mcp.tools.sessions.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import NowPlayingInput
        from plex_mcp.tools.sessions import now_playing

        result = asyncio.get_event_loop().run_until_complete(now_playing(NowPlayingInput()))
    assert "Transcod" in result or "transcode" in result.lower()
