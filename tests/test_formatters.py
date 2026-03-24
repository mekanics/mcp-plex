"""Tests for duration utilities and markdown formatters."""

import json
from datetime import UTC, datetime, timedelta

# --- Task 5.1: Duration and Date Utilities ---


def test_ms_to_min():
    from plex_mcp.formatters.duration import ms_to_min

    assert ms_to_min(5400000) == 90  # 90 minutes exact
    assert ms_to_min(5401000) == 90  # rounds down


def test_min_to_human_hours_and_minutes():
    from plex_mcp.formatters.duration import min_to_human

    assert min_to_human(90) == "1h 30m"
    assert min_to_human(60) == "1h 0m"
    assert min_to_human(45) == "45m"
    assert min_to_human(0) == "0m"


def test_ms_to_human():
    from plex_mcp.formatters.duration import ms_to_human

    assert ms_to_human(5400000) == "1h 30m"


def test_relative_date_today():
    from plex_mcp.formatters.duration import relative_date

    now = datetime.now(UTC)
    result = relative_date(now)
    assert result == "Today"


def test_relative_date_yesterday():
    from plex_mcp.formatters.duration import relative_date

    yesterday = datetime.now(UTC) - timedelta(days=1)
    assert relative_date(yesterday) == "Yesterday"


def test_relative_date_n_days():
    from plex_mcp.formatters.duration import relative_date

    three_days_ago = datetime.now(UTC) - timedelta(days=3)
    assert relative_date(three_days_ago) == "3 days ago"


def test_format_season_episode():
    from plex_mcp.formatters.duration import format_season_episode

    assert format_season_episode(2, 4) == "S02E04"
    assert format_season_episode(1, 10) == "S01E10"
    assert format_season_episode(None, None) is None


def test_relative_date_future_is_today():
    from plex_mcp.formatters.duration import relative_date

    future = datetime.now(UTC) + timedelta(seconds=30)
    assert relative_date(future) == "Today"


# --- Task 5.2: Markdown Formatters — Read-Only Tools ---


def test_format_search_results_header():
    from plex_mcp.formatters.markdown import format_search_results
    from plex_mcp.schemas.outputs import SearchMediaOutput, SearchResult

    out = SearchMediaOutput(
        success=True,
        tool="search_media",
        query="dune",
        total_found=2,
        data=[
            SearchResult(
                title="Dune",
                year=2021,
                media_type="movie",
                library="Movies",
                rating=8.5,
                duration_min=155,
                genres=["Sci-Fi", "Adventure"],
            ),
        ],
    )
    md = format_search_results(out)
    assert '## Search: "dune"' in md
    assert "**Dune**" in md
    assert "⭐" in md
    assert "get_media_details" in md  # navigation hint at end


def test_format_search_results_empty():
    from plex_mcp.formatters.markdown import format_search_results
    from plex_mcp.schemas.outputs import SearchMediaOutput

    out = SearchMediaOutput(success=True, tool="search_media", query="xyzzy", total_found=0)
    md = format_search_results(out)
    assert "No results" in md or "0 results" in md


def test_format_sessions_with_sessions():
    from plex_mcp.formatters.markdown import format_sessions
    from plex_mcp.schemas.outputs import NowPlayingOutput, NowPlayingSession

    session = NowPlayingSession(
        session_id="s1",
        user="alice",
        client_name="Apple TV",
        client_platform="tvOS",
        client_product="Plex for Apple TV",
        media_title="Dune",
        media_type="movie",
        duration_min=155,
        progress_min=60,
        progress_pct=38.7,
        state="playing",
        transcode_status="direct_play",
    )
    out = NowPlayingOutput(success=True, tool="now_playing", data=[session], session_count=1)
    md = format_sessions(out)
    assert "## 📺 Now Playing" in md
    assert "alice" in md
    assert "Dune" in md
    assert "▶" in md


def test_format_sessions_empty():
    from plex_mcp.formatters.markdown import format_sessions
    from plex_mcp.schemas.outputs import NowPlayingOutput

    out = NowPlayingOutput(success=True, tool="now_playing", data=[], session_count=0)
    md = format_sessions(out)
    assert "No active sessions" in md or "nothing" in md.lower()


def test_format_on_deck_items():
    from plex_mcp.formatters.markdown import format_on_deck
    from plex_mcp.schemas.outputs import OnDeckItem, OnDeckOutput

    item = OnDeckItem(
        media_title="Breaking Bad",
        media_type="episode",
        show_title="Breaking Bad",
        season_episode="S02E05",
        progress_pct=28.0,
        remaining_min=32,
        library="TV Shows",
    )
    out = OnDeckOutput(success=True, tool="on_deck", data=[item])
    md = format_on_deck(out)
    assert "## ▶ On Deck" in md
    assert "Breaking Bad" in md
    assert "S02E05" in md


def test_format_libraries():
    from plex_mcp.formatters.markdown import format_libraries
    from plex_mcp.schemas.outputs import GetLibrariesOutput, LibraryInfo

    out = GetLibrariesOutput(
        success=True,
        tool="get_libraries",
        data=[
            LibraryInfo(name="Movies", library_type="movie", item_count=342, size_gb=4500.0),
            LibraryInfo(name="TV Shows", library_type="show", item_count=89, size_gb=8200.0),
        ],
    )
    md = format_libraries(out)
    assert "## 📚 Libraries" in md
    assert "Movies" in md
    assert "342" in md


def test_format_clients():
    from plex_mcp.formatters.markdown import format_clients
    from plex_mcp.schemas.outputs import ClientInfo, GetClientsOutput

    out = GetClientsOutput(
        success=True,
        tool="get_clients",
        data=[
            ClientInfo(
                name="Living Room TV",
                platform="Roku",
                product="Plex for Roku",
                device_id="abc",
                state="online",
            ),
        ],
    )
    md = format_clients(out)
    assert "Living Room TV" in md
    assert "Roku" in md


# --- Task 5.3: Mutation Tools + JSON Mode ---


def test_format_dry_run_play_media():
    from plex_mcp.formatters.markdown import format_dry_run
    from plex_mcp.schemas.outputs import PlayMediaData

    data = PlayMediaData(
        dry_run=True,
        media_title="Dune: Part Two",
        media_type="movie",
        client_name="Living Room TV",
        client_platform="Roku",
        duration_min=166,
    )
    md = format_dry_run(data)
    assert "⚠️" in md
    assert "not started" in md.lower() or "preview" in md.lower()
    assert "Living Room TV" in md
    assert "confirmed=True" in md  # shows the call to make


def test_format_playback_success():
    from plex_mcp.formatters.markdown import format_playback_success
    from plex_mcp.schemas.outputs import PlayMediaData

    data = PlayMediaData(
        dry_run=False,
        media_title="Dune: Part Two",
        media_type="movie",
        client_name="Living Room TV",
        client_platform="Roku",
        started_at=datetime.now(UTC).isoformat(),
    )
    md = format_playback_success(data)
    assert "✅" in md
    assert "Living Room TV" in md
    assert "Dune: Part Two" in md


def test_to_json_response_success():
    from plex_mcp.formatters.json_fmt import to_json_response
    from plex_mcp.schemas.outputs import PlayMediaOutput

    out = PlayMediaOutput(success=True, tool="play_media")
    json_str = to_json_response(out)
    parsed = json.loads(json_str)
    assert parsed["success"] is True
    assert parsed["tool"] == "play_media"


def test_to_json_response_preserves_nested_data():
    from plex_mcp.formatters.json_fmt import to_json_response
    from plex_mcp.schemas.outputs import PlayMediaData, PlayMediaOutput

    data = PlayMediaData(
        dry_run=True, media_title="X", media_type="movie", client_name="TV", client_platform="Roku"
    )
    out = PlayMediaOutput(success=True, tool="play_media", data=data)
    json_str = to_json_response(out)
    parsed = json.loads(json_str)
    assert parsed["data"]["dry_run"] is True
    assert parsed["data"]["media_title"] == "X"
