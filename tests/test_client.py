"""Tests for the Plex client connection singleton and resolution helpers."""

from unittest.mock import MagicMock, patch

import pytest


def test_get_server_returns_cached_connection(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "tok")
    monkeypatch.setenv("PLEX_SERVER", "http://localhost:32400")
    mock_server = MagicMock()
    with patch("plexapi.server.PlexServer", return_value=mock_server):
        from plex_mcp.client import _reset_server, get_server

        _reset_server()
        s1 = get_server()
        s2 = get_server()
        assert s1 is s2  # same object — singleton


def test_get_server_raises_on_auth_failure(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "bad-tok")
    monkeypatch.setenv("PLEX_SERVER", "http://localhost:32400")
    import plexapi.exceptions

    from plex_mcp.errors import PlexMCPError

    with patch("plexapi.server.PlexServer", side_effect=plexapi.exceptions.Unauthorized("bad")):
        from plex_mcp.client import _reset_server, get_server

        _reset_server()
        with pytest.raises(PlexMCPError) as exc_info:
            get_server()
        assert exc_info.value.code == "AUTH_FAILED"


def test_get_server_raises_on_connection_failure(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "tok")
    monkeypatch.setenv("PLEX_SERVER", "http://bad-host:32400")
    from plex_mcp.errors import PlexMCPError

    with patch("plexapi.server.PlexServer", side_effect=ConnectionRefusedError("refused")):
        from plex_mcp.client import _reset_server, get_server

        _reset_server()
        with pytest.raises(PlexMCPError) as exc_info:
            get_server()
        assert exc_info.value.code == "CONNECTION_FAILED"
        assert len(exc_info.value.suggestions) > 0


def test_resolve_media_exact_match(mock_plex_server, fake_movie):
    """Exact title match returns a MediaRef."""
    mock_plex_server.library.search.return_value = [fake_movie]
    with patch("plex_mcp.client.get_server", return_value=mock_plex_server):
        from plex_mcp.client import resolve_media
        from plex_mcp.schemas.common import MediaRef

        result = resolve_media(title="Dune", year=2021)
        assert isinstance(result, MediaRef)
        assert result.title == "Dune"
        assert result.rating_key == fake_movie.ratingKey


def test_resolve_media_not_found_raises(mock_plex_server):
    mock_plex_server.library.search.return_value = []
    with patch("plex_mcp.client.get_server", return_value=mock_plex_server):
        from plex_mcp.client import resolve_media
        from plex_mcp.errors import PlexMCPError

        with pytest.raises(PlexMCPError) as exc_info:
            resolve_media(title="Nonexistent Movie XYZZY")
        assert exc_info.value.code == "MEDIA_NOT_FOUND"
        assert "search_media" in exc_info.value.suggestions[0].lower() or "search_media" in str(
            exc_info.value.suggestions
        )


def test_resolve_media_ambiguous_raises(mock_plex_server, fake_movie):
    """Two matches with no year = MEDIA_AMBIGUOUS."""
    fake2 = MagicMock()
    fake2.title = "Dune"
    fake2.year = 1984
    fake2.TYPE = "movie"
    fake2.ratingKey = 99
    mock_plex_server.library.search.return_value = [fake_movie, fake2]
    with patch("plex_mcp.client.get_server", return_value=mock_plex_server):
        from plex_mcp.client import resolve_media
        from plex_mcp.errors import PlexMCPError

        with pytest.raises(PlexMCPError) as exc_info:
            resolve_media(title="Dune")  # no year → ambiguous
        assert exc_info.value.code == "MEDIA_AMBIGUOUS"


def test_resolve_media_year_disambiguates(mock_plex_server, fake_movie):
    fake2 = MagicMock()
    fake2.title = "Dune"
    fake2.year = 1984
    fake2.TYPE = "movie"
    fake2.ratingKey = 99
    mock_plex_server.library.search.return_value = [fake_movie, fake2]
    with patch("plex_mcp.client.get_server", return_value=mock_plex_server):
        from plex_mcp.client import resolve_media

        result = resolve_media(title="Dune", year=2021)
        assert result.year == 2021
