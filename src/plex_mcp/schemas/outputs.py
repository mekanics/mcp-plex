"""Output Pydantic models for all plex-mcp tools."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from plex_mcp.schemas.common import PlexMCPResponse

# ── search_media ──────────────────────────────────────────────────────────────


class SearchResult(BaseModel):
    model_config = ConfigDict(strict=False)

    title: str
    year: int | None = None
    media_type: str
    library: str
    summary_short: str = ""  # default empty string (not None) for safe string ops
    rating: float | None = None
    duration_min: int | None = None
    genres: list[str] = []
    rating_key: int | None = None
    full_summary: str | None = None


class SearchMediaOutput(PlexMCPResponse):
    tool: str = "search_media"
    data: list[SearchResult] = []
    total_found: int = 0
    query: str = ""


# ── browse_library ────────────────────────────────────────────────────────────


class LibraryItem(BaseModel):
    model_config = ConfigDict(strict=False)

    title: str
    year: int | None = None
    media_type: str
    rating: float | None = None
    duration_min: int | None = None
    watched: bool | None = None
    added_at: str = ""


class BrowseLibraryOutput(PlexMCPResponse):
    tool: str = "browse_library"
    data: list[LibraryItem] = []
    library: str = ""
    total_items: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


# ── get_media_details ─────────────────────────────────────────────────────────


class CastMember(BaseModel):
    model_config = ConfigDict(strict=False)

    name: str
    role: str
    is_director: bool = False
    is_writer: bool = False


class MediaFile(BaseModel):
    model_config = ConfigDict(strict=False)

    filename: str
    size_gb: float
    container: str
    video_codec: str
    resolution: str
    audio_codec: str
    audio_channels: str
    bitrate_mbps: float


class MediaDetailsData(BaseModel):
    model_config = ConfigDict(strict=False)

    title: str
    year: int | None = None
    media_type: str
    library: str
    summary: str = ""
    rating_audience: float | None = None
    rating_critics: float | None = None
    content_rating: str | None = None
    genres: list[str] = []
    duration_min: int | None = None
    studio: str | None = None
    originally_available: str | None = None
    watched: bool | None = None
    watch_progress_pct: float | None = None
    # Detailed only
    cast: list[CastMember] | None = None
    files: list[MediaFile] | None = None
    chapter_count: int | None = None
    labels: list[str] | None = None
    collections: list[str] | None = None
    # Show-specific
    season_count: int | None = None
    episode_count: int | None = None
    # Episode-specific
    season_number: int | None = None
    episode_number: int | None = None
    show_title: str | None = None


class MediaDetailsOutput(PlexMCPResponse):
    tool: str = "get_media_details"
    data: MediaDetailsData | None = None


# ── now_playing ───────────────────────────────────────────────────────────────


class NowPlayingSession(BaseModel):
    model_config = ConfigDict(strict=False)

    session_id: str
    user: str
    client_name: str
    client_platform: str
    client_product: str
    media_title: str
    media_type: str
    show_title: str | None = None
    season_episode: str | None = None
    duration_min: int
    progress_min: int
    progress_pct: float
    state: Literal["playing", "paused", "buffering"]
    transcode_status: Literal["direct_play", "direct_stream", "transcode"]
    transcode_reason: str | None = None
    bandwidth_kbps: int | None = None


class NowPlayingOutput(PlexMCPResponse):
    tool: str = "now_playing"
    data: list[NowPlayingSession] = []
    session_count: int = 0


# ── on_deck ───────────────────────────────────────────────────────────────────


class OnDeckItem(BaseModel):
    model_config = ConfigDict(strict=False)

    media_title: str
    media_type: str
    show_title: str | None = None
    season_episode: str | None = None
    progress_pct: float | None = None
    remaining_min: int | None = None
    thumb_url: str | None = None
    library: str


class OnDeckOutput(PlexMCPResponse):
    tool: str = "on_deck"
    data: list[OnDeckItem] = []


# ── recently_added ────────────────────────────────────────────────────────────


class RecentlyAddedItem(BaseModel):
    model_config = ConfigDict(strict=False)

    title: str
    year: int | None = None
    media_type: str
    library: str
    added_at: str = ""
    added_human: str = ""
    duration_min: int | None = None
    summary_short: str | None = None
    show_title: str | None = None
    season_episode: str | None = None


class RecentlyAddedOutput(PlexMCPResponse):
    tool: str = "recently_added"
    data: list[RecentlyAddedItem] = []
    cutoff_date: str = ""


# ── play_media ────────────────────────────────────────────────────────────────


class PlayMediaData(BaseModel):
    model_config = ConfigDict(strict=False)

    dry_run: bool
    media_title: str
    media_type: str
    season_episode: str | None = None
    duration_min: int | None = None
    client_name: str
    client_platform: str
    offset_ms: int | None = None
    started_at: str | None = None  # ISO datetime, only when dry_run=False


class PlayMediaOutput(PlexMCPResponse):
    tool: str = "play_media"
    data: PlayMediaData | None = None


# ── playback_control ──────────────────────────────────────────────────────────


class PlaybackControlData(BaseModel):
    model_config = ConfigDict(strict=False)

    dry_run: bool
    action: str
    client_name: str
    client_platform: str
    media_title: str
    session_state_before: str
    session_state_after: str | None = None
    seek_position_min: float | None = None


class PlaybackControlOutput(PlexMCPResponse):
    tool: str = "playback_control"
    data: PlaybackControlData | None = None


# ── get_libraries ─────────────────────────────────────────────────────────────


class LibraryInfo(BaseModel):
    model_config = ConfigDict(strict=False)

    name: str
    library_type: str
    item_count: int
    size_gb: float
    agent: str | None = None


class GetLibrariesOutput(PlexMCPResponse):
    tool: str = "get_libraries"
    data: list[LibraryInfo] = []


# ── get_clients ───────────────────────────────────────────────────────────────


class ClientInfo(BaseModel):
    model_config = ConfigDict(strict=False)

    name: str
    platform: str
    product: str
    device_id: str
    state: str
    address: str | None = None


class GetClientsOutput(PlexMCPResponse):
    tool: str = "get_clients"
    data: list[ClientInfo] = []
