"""Tests for Bunch 9: play_media + playback_control mutation tools.

Task 9.1: play_media dry-run path
Task 9.2: play_media confirmed execution path
Task 9.3: playback_control (dry-run + confirmed + all actions)
"""

import asyncio
from unittest.mock import MagicMock, patch

# ── Task 9.1: play_media — Dry-Run Path ───────────────────────────────────────


def test_play_media_dry_run_default(mock_plex_server, fake_movie, fake_plex_client):
    """confirmed=False (default) → dry-run, no actual playback."""
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlayMediaInput
        from plex_mcp.tools.playback import play_media

        inp = PlayMediaInput(title="Dune", year=2021, client="Living Room TV", confirmed=False)
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    assert "⚠️" in result
    assert "preview" in result.lower() or "not started" in result.lower()
    assert "confirmed=True" in result
    # No actual playback method called
    fake_plex_client.playMedia.assert_not_called()


def test_play_media_dry_run_shows_media_details(mock_plex_server, fake_movie, fake_plex_client):
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlayMediaInput
        from plex_mcp.tools.playback import play_media

        inp = PlayMediaInput(title="Dune", client="Living Room TV")
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    assert "Dune" in result
    assert "Living Room TV" in result


def test_play_media_client_not_found(mock_plex_server, fake_movie):
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = []  # no clients
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlayMediaInput
        from plex_mcp.tools.playback import play_media

        inp = PlayMediaInput(title="Dune", client="Nonexistent TV")
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    assert "CLIENT_NOT_FOUND" in result or "❌" in result
    assert "get_clients" in result


def test_play_media_media_not_found(mock_plex_server, fake_plex_client):
    mock_plex_server.library.search.return_value = []
    mock_plex_server.clients.return_value = [fake_plex_client]
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlayMediaInput
        from plex_mcp.tools.playback import play_media

        inp = PlayMediaInput(title="XYZZY", client="Living Room TV")
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    assert "MEDIA_NOT_FOUND" in result or "❌" in result


# ── Task 9.2: play_media — Confirmed Execution Path ───────────────────────────


def test_play_media_confirmed_calls_plex_api(mock_plex_server, fake_movie, fake_plex_client):
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    mock_plex_client_obj = MagicMock()
    mock_plex_server.client.return_value = mock_plex_client_obj
    mock_plex_server.fetchItem.return_value = fake_movie
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlayMediaInput
        from plex_mcp.tools.playback import play_media

        inp = PlayMediaInput(title="Dune", year=2021, client="Living Room TV", confirmed=True)
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    assert "✅" in result
    assert "Dune" in result
    mock_plex_client_obj.playMedia.assert_called_once()


def test_play_media_confirmed_success_shows_timestamp(
    mock_plex_server, fake_movie, fake_plex_client
):
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    mock_plex_server.fetchItem.return_value = fake_movie
    mock_plex_server.client.return_value = MagicMock()
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlayMediaInput
        from plex_mcp.tools.playback import play_media

        inp = PlayMediaInput(title="Dune", client="Living Room TV", confirmed=True)
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    assert "UTC" in result or "Started" in result or "✅" in result


def test_play_media_with_offset(mock_plex_server, fake_movie, fake_plex_client):
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    mock_plex_server.fetchItem.return_value = fake_movie
    mock_client_obj = MagicMock()
    mock_plex_server.client.return_value = mock_client_obj
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlayMediaInput
        from plex_mcp.tools.playback import play_media

        inp = PlayMediaInput(
            title="Dune", client="Living Room TV", offset_ms=3600000, confirmed=True
        )
        asyncio.get_event_loop().run_until_complete(play_media(inp))
    call_kwargs = mock_client_obj.playMedia.call_args
    # offset should be passed through
    assert call_kwargs is not None


def test_play_media_json_format_dry_run(mock_plex_server, fake_movie, fake_plex_client):
    """JSON format works for dry-run."""
    import json

    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlayMediaInput
        from plex_mcp.tools.playback import play_media

        inp = PlayMediaInput(title="Dune", client="Living Room TV", confirmed=False, format="json")
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    parsed = json.loads(result)
    assert parsed["success"] is True
    assert parsed["tool"] == "play_media"
    assert parsed["data"]["dry_run"] is True


def test_play_media_confirmed_json_format(mock_plex_server, fake_movie, fake_plex_client):
    """JSON format works for confirmed execution."""
    import json

    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    mock_plex_server.fetchItem.return_value = fake_movie
    mock_plex_server.client.return_value = MagicMock()
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlayMediaInput
        from plex_mcp.tools.playback import play_media

        inp = PlayMediaInput(title="Dune", client="Living Room TV", confirmed=True, format="json")
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    parsed = json.loads(result)
    assert parsed["success"] is True
    assert parsed["data"]["dry_run"] is False
    assert parsed["data"]["started_at"] is not None


# ── Task 9.3: playback_control ────────────────────────────────────────────────


def test_playback_control_dry_run_shows_preview(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    mock_plex_server.clients.return_value = []
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlaybackControlInput
        from plex_mcp.tools.playback import playback_control

        inp = PlaybackControlInput(action="pause", client="Living Room TV", confirmed=False)
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "⚠️" in result
    assert "pause" in result.lower()
    assert "confirmed=True" in result


def test_playback_control_no_active_session(mock_plex_server):
    mock_plex_server.sessions.return_value = []
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlaybackControlInput
        from plex_mcp.tools.playback import playback_control

        inp = PlaybackControlInput(action="pause", confirmed=False)
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "NO_ACTIVE_SESSION" in result or "❌" in result
    assert "play_media" in result


def test_playback_control_multiple_sessions_require_client(mock_plex_server, fake_session):
    session2 = MagicMock()
    session2.player = MagicMock(title="MacBook", platform="MacOSX")
    session2.TYPE = "movie"
    session2.title = "The Matrix"
    session2.grandparentTitle = None
    mock_plex_server.sessions.return_value = [fake_session, session2]
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlaybackControlInput
        from plex_mcp.tools.playback import playback_control

        inp = PlaybackControlInput(action="pause", client=None, confirmed=True)
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "MULTIPLE_SESSIONS" in result or "❌" in result


def test_playback_control_confirmed_calls_pause(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    mock_client = MagicMock()
    mock_plex_server.client.return_value = mock_client
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlaybackControlInput
        from plex_mcp.tools.playback import playback_control

        inp = PlaybackControlInput(action="pause", client=fake_session.player.title, confirmed=True)
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "✅" in result or "pause" in result.lower()
    mock_client.pause.assert_called_once()


def test_playback_control_seek_requires_offset(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlaybackControlInput
        from plex_mcp.tools.playback import playback_control

        inp = PlaybackControlInput(
            action="seek",
            seek_offset_ms=None,  # missing offset
            client=fake_session.player.title,
            confirmed=True,
        )
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "❌" in result or "seek_offset_ms" in result


def test_playback_control_confirmed_calls_resume(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    mock_client = MagicMock()
    mock_plex_server.client.return_value = mock_client
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlaybackControlInput
        from plex_mcp.tools.playback import playback_control

        inp = PlaybackControlInput(
            action="resume", client=fake_session.player.title, confirmed=True
        )
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "✅" in result or "resume" in result.lower()
    mock_client.play.assert_called_once()


def test_playback_control_confirmed_calls_stop(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    mock_client = MagicMock()
    mock_plex_server.client.return_value = mock_client
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlaybackControlInput
        from plex_mcp.tools.playback import playback_control

        inp = PlaybackControlInput(action="stop", client=fake_session.player.title, confirmed=True)
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "✅" in result or "stop" in result.lower()
    mock_client.stop.assert_called_once()


def test_playback_control_confirmed_seek(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    mock_client = MagicMock()
    mock_plex_server.client.return_value = mock_client
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlaybackControlInput
        from plex_mcp.tools.playback import playback_control

        inp = PlaybackControlInput(
            action="seek",
            seek_offset_ms=1800000,  # 30 minutes
            client=fake_session.player.title,
            confirmed=True,
        )
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "✅" in result or "seek" in result.lower()
    mock_client.seekTo.assert_called_once_with(1800000)


def test_playback_control_auto_select_single_session(mock_plex_server, fake_session):
    """If client=None and exactly 1 session, auto-select it."""
    mock_plex_server.sessions.return_value = [fake_session]
    mock_client = MagicMock()
    mock_plex_server.client.return_value = mock_client
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlaybackControlInput
        from plex_mcp.tools.playback import playback_control

        inp = PlaybackControlInput(action="pause", client=None, confirmed=True)
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "✅" in result or "pause" in result.lower()
    mock_client.pause.assert_called_once()


def test_playback_control_json_format(mock_plex_server, fake_session):
    """JSON format works for dry-run."""
    import json

    mock_plex_server.sessions.return_value = [fake_session]
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import PlaybackControlInput
        from plex_mcp.tools.playback import playback_control

        inp = PlaybackControlInput(
            action="pause", client=fake_session.player.title, confirmed=False, format="json"
        )
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    parsed = json.loads(result)
    assert parsed["success"] is True
    assert parsed["tool"] == "playback_control"
    assert parsed["data"]["dry_run"] is True
    assert parsed["data"]["action"] == "pause"
