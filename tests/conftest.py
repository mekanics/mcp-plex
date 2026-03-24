"""Test fixtures for plex-mcp.

Provides mock PlexServer and fake media objects for all test modules.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_plex_server():
    """A MagicMock PlexServer with predictable library sections."""
    server = MagicMock()

    # Library sections
    movies_section = MagicMock()
    movies_section.title = "Movies"
    movies_section.type = "movie"
    movies_section.totalSize = 100
    movies_section.totalStorage = 100_000_000_000
    movies_section.agent = "tv.plex.agents.movie"

    tv_section = MagicMock()
    tv_section.title = "TV Shows"
    tv_section.type = "show"
    tv_section.totalSize = 50
    tv_section.totalStorage = 50_000_000_000
    tv_section.agent = "tv.plex.agents.series"

    server.library.sections.return_value = [movies_section, tv_section]
    server.library.search.return_value = []
    server.library.onDeck.return_value = []
    server.library.recentlyAdded.return_value = []
    server.sessions.return_value = []
    server.clients.return_value = []

    # Reset singleton so tests don't bleed into each other
    import plex_mcp.client as client_mod

    client_mod._server = None

    return server


@pytest.fixture
def fake_movie():
    """A fake Plex movie object resembling PlexAPI Video."""
    movie = MagicMock()
    movie.TYPE = "movie"
    movie.title = "Dune"
    movie.year = 2021
    movie.ratingKey = 12345
    movie.summary = (
        "A hero's journey across the desert planet Arrakis. "
        "Paul Atreides leads the Fremen against the oppressive Harkonnen."
    )
    movie.audienceRating = 8.5
    movie.rating = 7.8
    movie.duration = 9300000  # 155 minutes in ms
    movie.genres = [MagicMock(tag="Sci-Fi"), MagicMock(tag="Adventure")]
    movie.isFullyWatched = False
    movie.isWatched = False
    movie.viewOffset = 0
    movie.librarySectionTitle = "Movies"
    movie.contentRating = "PG-13"
    movie.studio = "Legendary Entertainment"
    movie.originallyAvailableAt = None
    movie.roles = []
    movie.directors = []
    movie.writers = []
    movie.media = []
    movie.chapters = []
    movie.labels = []
    movie.collections = []
    return movie


@pytest.fixture
def fake_episode():
    """A fake Plex episode object."""
    episode = MagicMock()
    episode.TYPE = "episode"
    episode.title = "Pilot"
    episode.grandparentTitle = "Breaking Bad"
    episode.showTitle = "Breaking Bad"
    episode.seasonNumber = 1
    episode.parentIndex = 1
    episode.index = 1
    episode.ratingKey = 99001
    episode.summary = "Walter White begins his descent."
    episode.audienceRating = 9.5
    episode.duration = 2760000  # 46 minutes
    episode.genres = []
    episode.isWatched = False
    episode.viewOffset = 0
    episode.librarySectionTitle = "TV Shows"
    return episode


@pytest.fixture
def fake_session():
    """A fake active Plex session."""
    session = MagicMock()
    session.TYPE = "episode"
    session.title = "Pilot"
    session.grandparentTitle = "Breaking Bad"
    session.year = 2008
    session.ratingKey = 99001
    session.duration = 2760000  # 46 min in ms
    session.viewOffset = 1200000  # 20 min in ms
    session.usernames = ["alice"]

    player = MagicMock()
    player.title = "Apple TV"
    player.platform = "tvOS"
    player.product = "Plex for Apple TV"
    player.state = "playing"
    session.player = player

    session.transcodeSessions = []  # direct play
    return session


@pytest.fixture
def fake_plex_client():
    """A fake Plex player/client."""
    client = MagicMock()
    client.title = "Living Room TV"
    client.platform = "Roku"
    client.product = "Plex for Roku"
    client.machineIdentifier = "roku-abc123"
    client.state = "online"
    client.address = "192.168.1.50"
    return client
