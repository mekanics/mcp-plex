"""Tests for Bunch 8: get_libraries and get_clients tools."""

import asyncio
import json
from unittest.mock import MagicMock, patch


def make_mock_section(name, type_, count):
    s = MagicMock()
    s.title = name
    s.type = type_
    s.totalSize = count
    s.totalStorage = count * 1_000_000_000  # rough GB
    s.agent = "tv.plex.agents.movie"
    return s


def test_get_libraries_returns_all_sections(mock_plex_server):
    mock_plex_server.library.sections.return_value = [
        make_mock_section("Movies", "movie", 342),
        make_mock_section("TV Shows", "show", 89),
        make_mock_section("Music", "artist", 500),
    ]
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import GetLibrariesInput
        from plex_mcp.tools.libraries import get_libraries

        result = asyncio.get_event_loop().run_until_complete(get_libraries(GetLibrariesInput()))
    assert "## 📚 Libraries" in result
    assert "Movies" in result
    assert "TV Shows" in result
    assert "342" in result


def test_get_libraries_json_format(mock_plex_server):
    mock_plex_server.library.sections.return_value = [
        make_mock_section("Movies", "movie", 100),
    ]
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import GetLibrariesInput
        from plex_mcp.tools.libraries import get_libraries

        result = asyncio.get_event_loop().run_until_complete(
            get_libraries(GetLibrariesInput(format="json"))
        )
    parsed = json.loads(result)
    assert parsed["tool"] == "get_libraries"
    assert len(parsed["data"]) == 1
    assert parsed["data"][0]["name"] == "Movies"


def test_get_libraries_empty_server(mock_plex_server):
    mock_plex_server.library.sections.return_value = []
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import GetLibrariesInput
        from plex_mcp.tools.libraries import get_libraries

        result = asyncio.get_event_loop().run_until_complete(get_libraries(GetLibrariesInput()))
    assert "no libraries" in result.lower() or "0" in result or "empty" in result.lower()


# ── get_clients tests ─────────────────────────────────────────────────────────


def make_mock_client(name, platform, product, state="online"):
    c = MagicMock()
    c.title = name
    c.platform = platform
    c.product = product
    c.machineIdentifier = f"id_{name.lower().replace(' ', '_')}"
    c.state = state
    c.address = "192.168.1.50"
    return c


def test_get_clients_lists_available_players(mock_plex_server):
    mock_plex_server.clients.return_value = [
        make_mock_client("Living Room TV", "Roku", "Plex for Roku"),
        make_mock_client("MacBook", "MacOSX", "Plex for Mac"),
    ]
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import GetClientsInput
        from plex_mcp.tools.libraries import get_clients

        result = asyncio.get_event_loop().run_until_complete(get_clients(GetClientsInput()))
    assert "Living Room TV" in result
    assert "Roku" in result
    assert "MacBook" in result


def test_get_clients_no_clients_message(mock_plex_server):
    mock_plex_server.clients.return_value = []
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import GetClientsInput
        from plex_mcp.tools.libraries import get_clients

        result = asyncio.get_event_loop().run_until_complete(get_clients(GetClientsInput()))
    assert "no clients" in result.lower() or "no players" in result.lower() or "0" in result


def test_get_clients_json_format(mock_plex_server):
    mock_plex_server.clients.return_value = [
        make_mock_client("Apple TV", "tvOS", "Plex for Apple TV"),
    ]
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import GetClientsInput
        from plex_mcp.tools.libraries import get_clients

        result = asyncio.get_event_loop().run_until_complete(
            get_clients(GetClientsInput(format="json"))
        )
    parsed = json.loads(result)
    assert parsed["tool"] == "get_clients"
    assert parsed["data"][0]["name"] == "Apple TV"
    assert parsed["data"][0]["platform"] == "tvOS"


def test_get_clients_hint_for_play_media(mock_plex_server):
    mock_plex_server.clients.return_value = [
        make_mock_client("Living Room TV", "Roku", "Plex for Roku"),
    ]
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import GetClientsInput
        from plex_mcp.tools.libraries import get_clients

        result = asyncio.get_event_loop().run_until_complete(get_clients(GetClientsInput()))
    # Navigation hint should mention play_media
    assert "play_media" in result
