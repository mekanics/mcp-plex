"""Common shared Pydantic models used across all plex-mcp tools."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

ResponseFormat = Literal["markdown", "json"]


class PlexError(BaseModel):
    """Structured error descriptor returned in JSON mode."""

    model_config = ConfigDict(strict=False)

    code: str
    message: str
    suggestions: list[str] = []


class PlexMCPResponse(BaseModel):
    """Base wrapper for all tool responses."""

    model_config = ConfigDict(strict=False)

    success: bool
    tool: str
    data: dict[str, Any] | list[Any] | Any | None = None
    message: str | None = None
    error: PlexError | None = None


class MediaRef(BaseModel):
    """Lightweight resolved media identity, shared across tools."""

    model_config = ConfigDict(strict=False)

    title: str
    year: int | None = None
    media_type: Literal["movie", "show", "season", "episode", "artist", "album", "track"]
    library: str
    rating_key: int  # required — internal Plex ID
    thumb_url: str | None = None


class SessionRef(BaseModel):
    """Lightweight session identity."""

    model_config = ConfigDict(strict=False)

    session_id: str
    user: str
    client_name: str
    client_platform: str
    media: MediaRef
    progress_pct: float
    state: Literal["playing", "paused", "buffering", "stopped"]
