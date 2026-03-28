"""FastMCP server — plex-mcp entry point.

Registers all 10 tools with correct annotations and wires them to their
handlers. Run via `plex-mcp` (console script) or `python -m plex_mcp.server`.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastmcp import FastMCP

from plex_mcp.config import configure_logging, get_settings
from plex_mcp.errors import safe_tool_call
from plex_mcp.schemas.inputs import (
    BrowseLibraryInput,
    GetClientsInput,
    GetLibrariesInput,
    GetMediaDetailsInput,
    NowPlayingInput,
    OnDeckInput,
    PlaybackControlInput,
    PlayMediaInput,
    RecentlyAddedInput,
    SearchMediaInput,
)
from plex_mcp.tools.browse import browse_library as _browse_library
from plex_mcp.tools.deck import on_deck as _on_deck
from plex_mcp.tools.deck import recently_added as _recently_added
from plex_mcp.tools.details import get_media_details as _get_media_details
from plex_mcp.tools.libraries import get_clients as _get_clients
from plex_mcp.tools.libraries import get_libraries as _get_libraries
from plex_mcp.tools.playback import play_media as _play_media
from plex_mcp.tools.playback import playback_control as _playback_control
from plex_mcp.tools.search import search_media as _search_media
from plex_mcp.tools.sessions import now_playing as _now_playing

logger = logging.getLogger(__name__)

mcp: FastMCP = FastMCP(
    name="mcp-plex",
    version="0.1.0",
    instructions=(
        "MCP server for Plex Media Server. "
        "Search, browse, inspect, and control playback across your Plex library."
    ),
)

# ── Read-only tools ────────────────────────────────────────────────────────────


@mcp.tool(
    name="search_media",
    annotations={
        "readOnlyHint": True,
        "title": "Search Plex Library",
        "description": "Full-text search across all Plex libraries. Returns matching movies, shows, and episodes.",
    },
)
async def search_media(
    query: str,
    media_type: str | None = None,
    limit: int = 10,
    format: str = "markdown",
) -> str:
    """Search for media across all Plex libraries.

    Args:
        query: Search terms (title, actor, keyword).
        media_type: Filter by type: "movie", "show", "episode", "artist", "album".
        limit: Maximum number of results (1-50, default 10).
        format: Output format: "markdown" (default) or "json".
    """
    inp = SearchMediaInput(query=query, media_type=media_type, limit=limit, format=format)  # type: ignore[arg-type]
    return await safe_tool_call(_search_media, inp, format=format)


@mcp.tool(
    name="browse_library",
    annotations={
        "readOnlyHint": True,
        "title": "Browse Plex Library",
        "description": "Paginated browsing of a specific Plex library section with sort and filter support.",
    },
)
async def browse_library(
    library: str,
    sort: str = "titleSort:asc",
    filters: dict[str, Any] | None = None,
    page: int = 1,
    page_size: int = 20,
    format: str = "markdown",
) -> str:
    """Browse a Plex library section with pagination.

    Args:
        library: Library name (e.g. "Movies", "TV Shows"). Use get_libraries() to list all.
        sort: Sort field and direction (default "titleSort:asc").
        filters: Optional dict of plexapi filter criteria.
        page: Page number (1-indexed, default 1).
        page_size: Items per page (1-100, default 20).
        format: Output format: "markdown" (default) or "json".
    """
    inp = BrowseLibraryInput(
        library=library,
        sort=sort,
        filters=filters,
        page=page,
        page_size=page_size,
        format=format,  # type: ignore[arg-type]
    )
    return await safe_tool_call(_browse_library, inp, format=format)


@mcp.tool(
    name="get_media_details",
    annotations={
        "readOnlyHint": True,
        "title": "Get Media Details",
        "description": "Rich metadata for a single movie, show, or episode including cast, ratings, and file info.",
    },
)
async def get_media_details(
    title: str,
    year: int | None = None,
    media_type: str | None = None,
    season: int | None = None,
    episode: int | None = None,
    detailed: bool = False,
    format: str = "markdown",
) -> str:
    """Get detailed metadata for a specific piece of media.

    Args:
        title: Title to look up.
        year: Release year to disambiguate (recommended for movies).
        media_type: "movie", "show", or "episode".
        season: Season number (for episodes).
        episode: Episode number (for episodes).
        detailed: Include cast, crew, and file info (default False).
        format: Output format: "markdown" (default) or "json".
    """
    inp = GetMediaDetailsInput(
        title=title,
        year=year,
        media_type=media_type,  # type: ignore[arg-type]
        season=season,
        episode=episode,
        detailed=detailed,
        format=format,  # type: ignore[arg-type]
    )
    return await safe_tool_call(_get_media_details, inp, format=format)


@mcp.tool(
    name="now_playing",
    annotations={
        "readOnlyHint": True,
        "title": "Now Playing",
        "description": "Show all active streaming sessions on the Plex server.",
    },
)
async def now_playing(
    format: str = "markdown",
) -> str:
    """Show currently active Plex streaming sessions.

    Args:
        format: Output format: "markdown" (default) or "json".
    """
    inp = NowPlayingInput(format=format)  # type: ignore[arg-type]
    return await safe_tool_call(_now_playing, inp, format=format)


@mcp.tool(
    name="on_deck",
    annotations={
        "readOnlyHint": True,
        "title": "On Deck",
        "description": "List partially-watched and next-up items from the Plex On Deck list.",
    },
)
async def on_deck(
    limit: int = 10,
    format: str = "markdown",
) -> str:
    """List items on deck (partially watched or next up).

    Args:
        limit: Maximum number of items to return (default 10).
        format: Output format: "markdown" (default) or "json".
    """
    inp = OnDeckInput(limit=limit, format=format)  # type: ignore[arg-type]
    return await safe_tool_call(_on_deck, inp, format=format)


@mcp.tool(
    name="recently_added",
    annotations={
        "readOnlyHint": True,
        "title": "Recently Added",
        "description": "List items recently added to the Plex library, grouped by date.",
    },
)
async def recently_added(
    days: int = 7,
    media_type: str | None = None,
    limit: int = 20,
    format: str = "markdown",
) -> str:
    """List recently added media.

    Args:
        days: How many days back to look (1-365, default 7).
        media_type: Filter by type: "movie", "episode", etc.
        limit: Maximum number of results (default 20).
        format: Output format: "markdown" (default) or "json".
    """
    inp = RecentlyAddedInput(days=days, media_type=media_type, limit=limit, format=format)  # type: ignore[arg-type]
    return await safe_tool_call(_recently_added, inp, format=format)


@mcp.tool(
    name="get_libraries",
    annotations={
        "readOnlyHint": True,
        "title": "Get Libraries",
        "description": "List all Plex library sections with item counts and storage info.",
    },
)
async def get_libraries(
    format: str = "markdown",
) -> str:
    """List all Plex library sections.

    Args:
        format: Output format: "markdown" (default) or "json".
    """
    inp = GetLibrariesInput(format=format)  # type: ignore[arg-type]
    return await safe_tool_call(_get_libraries, inp, format=format)


@mcp.tool(
    name="get_clients",
    annotations={
        "readOnlyHint": True,
        "title": "Get Clients",
        "description": "List available Plex player clients (TVs, phones, computers) that can receive playback.",
    },
)
async def get_clients(
    format: str = "markdown",
) -> str:
    """List available Plex player clients.

    Args:
        format: Output format: "markdown" (default) or "json".
    """
    inp = GetClientsInput(format=format)  # type: ignore[arg-type]
    return await safe_tool_call(_get_clients, inp, format=format)


# ── Mutation tools ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="play_media",
    annotations={
        "readOnlyHint": False,
        "title": "Play Media",
        "description": (
            "Start playback of a movie, episode, or show on a named Plex client. "
            "Requires confirmed=True to execute — defaults to a dry-run preview."
        ),
    },
)
async def play_media(
    title: str,
    client: str,
    year: int | None = None,
    media_type: str | None = None,
    offset_ms: int | None = None,
    confirmed: bool = False,
    format: str = "markdown",
) -> str:
    """Start playback of a media item on a Plex client.

    IMPORTANT: By default this returns a preview (dry run). To actually start
    playback, call again with confirmed=True.

    Args:
        title: Title of the media to play.
        client: Client name to play on. Use get_clients() to find available clients.
        year: Release year (helps disambiguate).
        media_type: "movie", "show", or "episode".
        offset_ms: Start position in milliseconds (0 = beginning).
        confirmed: Must be True to execute playback (default False = preview only).
        format: Output format: "markdown" (default) or "json".
    """
    inp = PlayMediaInput(
        title=title,
        client=client,
        year=year,
        media_type=media_type,  # type: ignore[arg-type]
        offset_ms=offset_ms,
        confirmed=confirmed,
        format=format,  # type: ignore[arg-type]
    )
    return await safe_tool_call(_play_media, inp, format=format)


@mcp.tool(
    name="playback_control",
    annotations={
        "readOnlyHint": False,
        "title": "Playback Control",
        "description": (
            "Control an active Plex playback session: pause, resume, stop, seek, or skip. "
            "Requires confirmed=True to execute — defaults to a dry-run preview."
        ),
    },
)
async def playback_control(
    action: str,
    client: str | None = None,
    seek_offset_ms: int | None = None,
    confirmed: bool = False,
    format: str = "markdown",
) -> str:
    """Control an active Plex playback session.

    IMPORTANT: By default this returns a preview (dry run). To actually apply
    the action, call again with confirmed=True.

    Args:
        action: One of: "pause", "resume", "stop", "skip_next", "skip_prev", "seek".
        client: Client name (optional if only one session is active).
        seek_offset_ms: Position in milliseconds (required for "seek" action).
        confirmed: Must be True to execute (default False = preview only).
        format: Output format: "markdown" (default) or "json".
    """
    inp = PlaybackControlInput(
        action=action,  # type: ignore[arg-type]
        client=client,
        seek_offset_ms=seek_offset_ms,
        confirmed=confirmed,
        format=format,  # type: ignore[arg-type]
    )
    return await safe_tool_call(_playback_control, inp, format=format)


# ── Entry point ────────────────────────────────────────────────────────────────


def main() -> None:
    """Run the plex-mcp server.

    Transport is controlled by the MCP_TRANSPORT env var:
    - "streamable-http" (default in k8s) — listens on PORT (default 3000)
    - "stdio" — reads from stdin/stdout (for local/Claude Desktop usage)
    """
    settings = get_settings()
    configure_logging(settings)
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    logger.info("Starting plex-mcp server (version 0.1.0, transport=%s)", transport)
    if transport == "streamable-http":
        port = int(os.environ.get("PORT", "3000"))
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
