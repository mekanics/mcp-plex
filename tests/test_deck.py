"""Tests for Bunch 7: on_deck and recently_added tools."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch


def make_deck_item(
    title="Breaking Bad",
    season=2,
    episode=5,
    view_offset_ms=120000,
    duration_ms=2700000,
    type_="episode",
):
    item = MagicMock()
    item.TYPE = type_
    item.title = f"{title} S0{season}E0{episode}" if type_ == "episode" else title
    item.grandparentTitle = title if type_ == "episode" else None
    item.parentIndex = season
    item.index = episode
    item.duration = duration_ms
    item.viewOffset = view_offset_ms
    item.thumb = None
    item.librarySectionTitle = "TV Shows"
    item.year = None
    return item


def test_on_deck_returns_items(mock_plex_server):
    mock_plex_server.library.onDeck.return_value = [make_deck_item()]
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import OnDeckInput
        from plex_mcp.tools.deck import on_deck

        result = asyncio.get_event_loop().run_until_complete(on_deck(OnDeckInput()))
    assert "## ▶ On Deck" in result
    assert "Breaking Bad" in result


def test_on_deck_respects_limit(mock_plex_server):
    items = [make_deck_item(title=f"Show {i}") for i in range(20)]
    mock_plex_server.library.onDeck.return_value = items
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import OnDeckInput
        from plex_mcp.tools.deck import on_deck

        result = asyncio.get_event_loop().run_until_complete(on_deck(OnDeckInput(limit=3)))
    assert result.count("Show") <= 3


def test_on_deck_empty(mock_plex_server):
    mock_plex_server.library.onDeck.return_value = []
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import OnDeckInput
        from plex_mcp.tools.deck import on_deck

        result = asyncio.get_event_loop().run_until_complete(on_deck(OnDeckInput()))
    assert "nothing" in result.lower() or "empty" in result.lower() or "0" in result


def test_on_deck_progress_pct_calculated(mock_plex_server):
    # 50% through a 45-minute episode
    mock_plex_server.library.onDeck.return_value = [
        make_deck_item(view_offset_ms=1350000, duration_ms=2700000)
    ]
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import OnDeckInput
        from plex_mcp.tools.deck import on_deck

        result = asyncio.get_event_loop().run_until_complete(on_deck(OnDeckInput()))
    assert "50%" in result or "22m" in result  # 50% of 45 min = 22.5m remaining


# ── recently_added tests ─────────────────────────────────────────────────────


def make_added_item(title, days_ago=1, type_="movie", duration_ms=5400000):
    item = MagicMock()
    item.TYPE = type_
    item.title = title
    item.year = 2024
    item.ratingKey = hash(title) % 10000
    item.duration = duration_ms
    item.addedAt = datetime.now(UTC) - timedelta(days=days_ago)
    item.summary = f"Summary of {title}"
    item.librarySectionTitle = "Movies"
    item.grandparentTitle = None
    item.parentIndex = None
    item.index = None
    return item


def test_recently_added_returns_items(mock_plex_server):
    mock_plex_server.library.recentlyAdded.return_value = [
        make_added_item("Dune: Part Two", days_ago=1),
        make_added_item("Anora", days_ago=3),
    ]
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import RecentlyAddedInput
        from plex_mcp.tools.deck import recently_added

        result = asyncio.get_event_loop().run_until_complete(
            recently_added(RecentlyAddedInput(days=7))
        )
    assert "## 🆕 Recently Added" in result
    assert "Dune: Part Two" in result
    assert "Anora" in result


def test_recently_added_filters_by_days(mock_plex_server):
    mock_plex_server.library.recentlyAdded.return_value = [
        make_added_item("Old Movie", days_ago=10),
        make_added_item("New Movie", days_ago=2),
    ]
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import RecentlyAddedInput
        from plex_mcp.tools.deck import recently_added

        result = asyncio.get_event_loop().run_until_complete(
            recently_added(RecentlyAddedInput(days=7))
        )
    assert "New Movie" in result
    assert "Old Movie" not in result


def test_recently_added_filters_by_media_type(mock_plex_server):
    mock_plex_server.library.recentlyAdded.return_value = [
        make_added_item("Movie A", type_="movie"),
        make_added_item("Episode B", type_="episode"),
    ]
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.schemas.inputs import RecentlyAddedInput
        from plex_mcp.tools.deck import recently_added

        result = asyncio.get_event_loop().run_until_complete(
            recently_added(RecentlyAddedInput(media_type="movie"))
        )
    assert "Movie A" in result
    assert "Episode B" not in result
