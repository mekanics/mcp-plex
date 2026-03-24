"""Plex client connection singleton and media/client resolution helpers."""

from __future__ import annotations

import logging
from typing import Any

import plexapi.exceptions
import plexapi.server

from plex_mcp.errors import (
    AUTH_FAILED,
    CONNECTION_FAILED,
    PlexMCPError,
    client_not_found_error,
    media_ambiguous_error,
    media_not_found_error,
)
from plex_mcp.schemas.common import MediaRef
from plex_mcp.schemas.outputs import ClientInfo

logger = logging.getLogger(__name__)

_server: plexapi.server.PlexServer | None = None


def get_server() -> plexapi.server.PlexServer:
    """Return a cached PlexServer connection, connecting on first call."""
    global _server
    if _server is None:
        _server = _connect()
    return _server


def _connect() -> plexapi.server.PlexServer:
    """Create a new PlexServer connection."""
    from plex_mcp.config import get_settings

    s = get_settings()
    try:
        server = plexapi.server.PlexServer(  # type: ignore[no-untyped-call]
            baseurl=s.plex_server,
            token=s.plex_token,
            timeout=s.plex_connect_timeout,
        )
        logger.info("Connected to Plex server at %s", s.plex_server)
        return server
    except plexapi.exceptions.Unauthorized as e:
        raise PlexMCPError(
            code=AUTH_FAILED,
            message="Plex authentication failed. Your PLEX_TOKEN may be invalid or expired.",
            suggestions=[
                "Verify PLEX_TOKEN in your environment.",
                "Generate a new token at: https://support.plex.tv/articles/204059436",
            ],
            raw=e,
        ) from e
    except Exception as e:
        from plex_mcp.config import get_settings as _gs

        try:
            server_url = _gs().plex_server
        except Exception:
            server_url = "unknown"
        raise PlexMCPError(
            code=CONNECTION_FAILED,
            message=f"Cannot connect to Plex at {server_url}: {type(e).__name__}",
            suggestions=[
                f"Verify PLEX_SERVER={server_url!r} is reachable.",
                "Check that Plex Media Server is running.",
                "For remote servers, check firewall rules.",
            ],
            raw=e,
        ) from e


def _reset_server() -> None:
    """Test helper — clear the cached server singleton."""
    global _server
    _server = None


# Maps media_type values to the section TYPE that contains them.
_MEDIA_TYPE_TO_SECTION: dict[str, str] = {
    "movie": "movie",
    "show": "show",
    "episode": "show",
    "artist": "artist",
    "album": "artist",
    "track": "artist",
}


def search_all_sections(
    query: str,
    media_type: str | None = None,
    limit: int = 20,
) -> list[Any]:
    """Search across all relevant library sections using LibrarySection.search().

    Uses per-section search (LibrarySection.search) which correctly accepts
    `title` and `libtype` parameters, unlike Library.search() which silently
    drops unrecognised keyword arguments.

    Args:
        query: Title string to search for (partial matches supported).
        media_type: Optional Plex media type ("movie", "show", "episode", etc.).
                    When provided, only sections of the matching type are queried
                    and libtype is forwarded to narrow results further.
        limit: Maximum number of results to return across all sections.
    """
    server = get_server()
    results: list[Any] = []

    expected_section_type = _MEDIA_TYPE_TO_SECTION.get(media_type or "", None) if media_type else None

    for section in server.library.sections():  # type: ignore[no-untyped-call]
        section_type = getattr(section, "TYPE", None)
        if expected_section_type and section_type != expected_section_type:
            continue

        kwargs: dict[str, Any] = {"title": query, "maxresults": limit}
        if media_type:
            kwargs["libtype"] = media_type

        try:
            results.extend(section.search(**kwargs))
        except Exception:
            logger.exception("Section search failed for library %r", getattr(section, "title", "?"))

    return results[:limit]


def resolve_media(
    title: str,
    year: int | None = None,
    media_type: str | None = None,
) -> MediaRef:
    """Resolve a human-readable title (+ optional year/type) to a MediaRef.

    Resolution strategy:
    1. Search library for title
    2. Filter by media_type if provided
    3. 0 results → MEDIA_NOT_FOUND
    4. 1 result  → return it
    5. 2+ results, no year → MEDIA_AMBIGUOUS
    6. 2+ results, with year → filter by year; still ambiguous → MEDIA_AMBIGUOUS
    """
    raw_results = search_all_sections(query=title, media_type=media_type, limit=10)

    # Filter to items whose title matches case-insensitively
    title_lower = title.lower()
    matched = [r for r in raw_results if getattr(r, "title", "").lower() == title_lower]
    if not matched:
        # Fall back to all search results (server fuzzy match)
        matched = raw_results

    if not matched:
        raise media_not_found_error(title=title, year=year)

    # If year provided, filter further
    if year is not None:
        year_matched = [r for r in matched if getattr(r, "year", None) == year]
        if year_matched:
            matched = year_matched
        # If year filter yields nothing, keep original matches and let ambiguity handle it

    if len(matched) == 1:
        item = matched[0]
        raw_type: str = getattr(item, "TYPE", media_type or "movie") or "movie"
        return MediaRef(
            title=getattr(item, "title", title),
            year=getattr(item, "year", None),
            media_type=raw_type,  # type: ignore[arg-type]
            library=getattr(item, "librarySectionTitle", ""),
            rating_key=getattr(item, "ratingKey", 0),
        )

    # Multiple matches — need disambiguation
    if year is None:
        candidates = [
            (getattr(r, "title", ""), getattr(r, "year", None), getattr(r, "TYPE", ""))
            for r in matched
        ]
        raise media_ambiguous_error(title=title, candidates=candidates)

    # Multiple matches even after year filter
    candidates = [
        (getattr(r, "title", ""), getattr(r, "year", None), getattr(r, "TYPE", "")) for r in matched
    ]
    raise media_ambiguous_error(title=title, candidates=candidates)


def resolve_client(client_name: str) -> ClientInfo:
    """Resolve a client name to a ClientInfo object.

    Raises CLIENT_NOT_FOUND if the client is not available.
    """
    server = get_server()
    clients = server.clients()  # type: ignore[no-untyped-call]
    name_lower = client_name.lower()

    for c in clients:
        if getattr(c, "title", "").lower() == name_lower:
            return ClientInfo(
                name=getattr(c, "title", client_name),
                platform=getattr(c, "platform", "Unknown"),
                product=getattr(c, "product", "Unknown"),
                device_id=getattr(c, "machineIdentifier", ""),
                state="online",
                address=getattr(c, "address", None),
            )

    raise client_not_found_error(client_name)
