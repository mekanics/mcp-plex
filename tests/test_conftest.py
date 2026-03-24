"""Tests that validate the fixtures themselves."""


def test_mock_plex_server_fixture(mock_plex_server):
    """Fixture returns a usable mock; library names are predictable."""
    assert hasattr(mock_plex_server, "library")
    libs = mock_plex_server.library.sections()
    assert any(lib.title == "Movies" for lib in libs)
    assert any(lib.title == "TV Shows" for lib in libs)


def test_fake_movie_fixture(fake_movie):
    assert fake_movie.title == "Dune"
    assert fake_movie.year == 2021
    assert fake_movie.TYPE == "movie"


def test_fake_episode_fixture(fake_episode):
    assert fake_episode.TYPE == "episode"
    assert fake_episode.seasonNumber == 1
    assert fake_episode.index == 1


def test_fake_session_fixture(fake_session):
    assert fake_session.TYPE == "episode"
    assert hasattr(fake_session, "viewOffset")
    assert hasattr(fake_session, "player")


def test_fake_client_fixture(fake_plex_client):
    assert fake_plex_client.title == "Living Room TV"
    assert fake_plex_client.platform == "Roku"
