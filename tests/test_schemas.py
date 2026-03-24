import pytest
from pydantic import ValidationError

# --- Task 2.1: Common Schemas ---


def test_plex_error_model():
    from plex_mcp.schemas.common import PlexError

    e = PlexError(
        code="MEDIA_NOT_FOUND",
        message="No results.",
        suggestions=["Try search_media"],
    )
    assert e.code == "MEDIA_NOT_FOUND"
    assert len(e.suggestions) == 1


def test_media_ref_requires_rating_key():
    from plex_mcp.schemas.common import MediaRef

    with pytest.raises(ValidationError):
        MediaRef(title="Dune", media_type="movie", library="Movies")
        # missing rating_key


def test_media_ref_year_optional():
    from plex_mcp.schemas.common import MediaRef

    ref = MediaRef(title="Dune", media_type="movie", library="Movies", rating_key=12345)
    assert ref.year is None


def test_plex_mcp_response_defaults():
    from plex_mcp.schemas.common import PlexMCPResponse

    r = PlexMCPResponse(success=True, tool="search_media")
    assert r.data is None
    assert r.error is None


def test_plex_mcp_response_with_error():
    from plex_mcp.schemas.common import PlexError, PlexMCPResponse

    err = PlexError(code="AUTH_FAILED", message="Bad token")
    r = PlexMCPResponse(success=False, tool="search_media", error=err)
    assert r.success is False
    assert r.error.code == "AUTH_FAILED"


def test_session_ref_state_validation():
    from plex_mcp.schemas.common import MediaRef, SessionRef

    with pytest.raises(ValidationError):
        SessionRef(
            session_id="s1",
            user="alice",
            client_name="TV",
            client_platform="Roku",
            media=MediaRef(title="X", media_type="movie", library="M", rating_key=1),
            progress_pct=50.0,
            state="INVALID_STATE",  # must be playing|paused|buffering|stopped
        )


# --- Task 2.2: Input Schemas ---


def test_search_input_defaults():
    from plex_mcp.schemas.inputs import SearchMediaInput

    inp = SearchMediaInput(query="Dune")
    assert inp.limit == 10
    assert inp.format == "markdown"
    assert inp.media_type is None


def test_search_input_query_too_short():
    from plex_mcp.schemas.inputs import SearchMediaInput

    with pytest.raises(ValidationError):
        SearchMediaInput(query="")


def test_search_input_limit_clamp():
    from plex_mcp.schemas.inputs import SearchMediaInput

    with pytest.raises(ValidationError):
        SearchMediaInput(query="X", limit=100)  # max is 50


def test_play_media_input_confirmed_defaults_false():
    from plex_mcp.schemas.inputs import PlayMediaInput

    inp = PlayMediaInput(title="Dune", client="Living Room TV")
    assert inp.confirmed is False


def test_playback_control_seek_requires_offset():
    # seek action without seek_offset_ms is valid schema-wise;
    # business logic enforces it in the handler
    from plex_mcp.schemas.inputs import PlaybackControlInput

    inp = PlaybackControlInput(action="seek")
    assert inp.seek_offset_ms is None


def test_browse_library_defaults():
    from plex_mcp.schemas.inputs import BrowseLibraryInput

    inp = BrowseLibraryInput(library="Movies")
    assert inp.sort == "titleSort:asc"
    assert inp.page == 1
    assert inp.page_size == 20


def test_recently_added_days_clamp():
    from plex_mcp.schemas.inputs import RecentlyAddedInput

    with pytest.raises(ValidationError):
        RecentlyAddedInput(days=366)  # max 365


def test_get_libraries_input_default_format():
    from plex_mcp.schemas.inputs import GetLibrariesInput

    inp = GetLibrariesInput()
    assert inp.format == "markdown"


def test_get_clients_input_default_format():
    from plex_mcp.schemas.inputs import GetClientsInput

    inp = GetClientsInput()
    assert inp.format == "markdown"


# --- Task 2.3: Output Schemas ---


def test_search_result_summary_short_optional():
    from plex_mcp.schemas.outputs import SearchResult

    r = SearchResult(title="Dune", media_type="movie", library="Movies")
    assert r.summary_short == ""  # default empty string, not None


def test_search_media_output_default_tool_name():
    from plex_mcp.schemas.outputs import SearchMediaOutput

    out = SearchMediaOutput(success=True, tool="search_media")
    assert out.tool == "search_media"
    assert out.data == []


def test_now_playing_session_transcode_status():
    from plex_mcp.schemas.outputs import NowPlayingSession

    with pytest.raises(ValidationError):
        NowPlayingSession(
            session_id="s1",
            user="alice",
            client_name="TV",
            client_platform="Roku",
            client_product="Plex",
            media_title="Dune",
            media_type="movie",
            duration_min=166,
            progress_min=60,
            progress_pct=36.0,
            state="playing",
            transcode_status="INVALID",  # must be direct_play|direct_stream|transcode
        )


def test_play_media_data_dry_run_flag():
    from plex_mcp.schemas.outputs import PlayMediaData

    d = PlayMediaData(
        dry_run=True,
        media_title="Dune",
        media_type="movie",
        client_name="Living Room TV",
        client_platform="Roku",
    )
    assert d.dry_run is True
    assert d.started_at is None


def test_library_info_schema():
    from plex_mcp.schemas.outputs import LibraryInfo

    lib = LibraryInfo(name="Movies", library_type="movie", item_count=342, size_gb=4500.0)
    assert lib.library_type == "movie"


def test_client_info_schema():
    from plex_mcp.schemas.outputs import ClientInfo

    c = ClientInfo(
        name="Living Room TV",
        platform="Roku",
        product="Plex for Roku",
        device_id="abc123",
        state="online",
    )
    assert c.state == "online"
