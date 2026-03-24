"""Input Pydantic models for all plex-mcp tools."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from plex_mcp.schemas.common import ResponseFormat


class SearchMediaInput(BaseModel):
    model_config = ConfigDict(strict=False)

    query: Annotated[
        str,
        Field(
            description="Search term — title, actor name, director, genre keyword, etc.",
            min_length=1,
            max_length=200,
        ),
    ]
    media_type: Annotated[
        Literal["movie", "show", "episode", "artist", "album", "track"] | None,
        Field(default=None, description="Restrict to a specific media type."),
    ] = None
    library: Annotated[
        str | None,
        Field(default=None, description="Restrict to a named library."),
    ] = None
    limit: Annotated[
        int,
        Field(default=10, ge=1, le=50, description="Max results to return."),
    ] = 10
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"


class BrowseLibraryInput(BaseModel):
    model_config = ConfigDict(strict=False)

    library: Annotated[
        str,
        Field(description="Library name exactly as shown in Plex."),
    ]
    sort: Annotated[
        str,
        Field(default="titleSort:asc", description="Sort key with direction."),
    ] = "titleSort:asc"
    filters: Annotated[
        dict[str, str | list[str]] | None,
        Field(default=None, description="Server-side filter map."),
    ] = None
    page: Annotated[int, Field(default=1, ge=1, description="1-based page number.")] = 1
    page_size: Annotated[int, Field(default=20, ge=1, le=100)] = 20
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"


class GetMediaDetailsInput(BaseModel):
    model_config = ConfigDict(strict=False)

    title: Annotated[str, Field(description="Title of the movie, show, episode, or album.")]
    year: Annotated[int | None, Field(default=None, description="Release year.")] = None
    media_type: Annotated[
        Literal["movie", "show", "episode", "artist", "album", "track"] | None,
        Field(default=None, description="Restrict resolution to a media type."),
    ] = None
    season: Annotated[int | None, Field(default=None)] = None
    episode: Annotated[int | None, Field(default=None)] = None
    detailed: Annotated[
        bool,
        Field(default=False, description="Set True for full metadata: cast, crew, file info."),
    ] = False
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"


class NowPlayingInput(BaseModel):
    model_config = ConfigDict(strict=False)
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"


class OnDeckInput(BaseModel):
    model_config = ConfigDict(strict=False)
    limit: Annotated[int, Field(default=10, ge=1, le=50)] = 10
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"


class RecentlyAddedInput(BaseModel):
    model_config = ConfigDict(strict=False)

    library: Annotated[str | None, Field(default=None)] = None
    days: Annotated[
        int,
        Field(default=7, ge=1, le=365, description="Only show items added within the last N days."),
    ] = 7
    limit: Annotated[int, Field(default=20, ge=1, le=100)] = 20
    media_type: Annotated[
        Literal["movie", "show", "episode", "album", "track"] | None,
        Field(default=None),
    ] = None
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"


class PlayMediaInput(BaseModel):
    model_config = ConfigDict(strict=False)

    title: Annotated[str, Field(description="Title of the movie, show, or track to play.")]
    year: Annotated[int | None, Field(default=None)] = None
    client: Annotated[str, Field(description="Name of the Plex player to play on.")]
    media_type: Annotated[
        Literal["movie", "show", "episode", "track"] | None,
        Field(default=None),
    ] = None
    season: Annotated[int | None, Field(default=None)] = None
    episode: Annotated[int | None, Field(default=None)] = None
    offset_ms: Annotated[int | None, Field(default=None)] = None
    confirmed: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "MUST be True to actually start playback. "
                "Set False (default) to get a dry-run preview first."
            ),
        ),
    ] = False
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"


class PlaybackControlInput(BaseModel):
    model_config = ConfigDict(strict=False)

    action: Annotated[
        Literal["pause", "resume", "stop", "skip_next", "skip_prev", "seek"],
        Field(description="Playback action to perform."),
    ]
    client: Annotated[str | None, Field(default=None)] = None
    seek_offset_ms: Annotated[int | None, Field(default=None, ge=0)] = None
    confirmed: Annotated[bool, Field(default=False)] = False
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"


class GetLibrariesInput(BaseModel):
    model_config = ConfigDict(strict=False)
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"


class GetClientsInput(BaseModel):
    model_config = ConfigDict(strict=False)
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"
