"""browse_library tool — paginated listing of a library's contents."""

from __future__ import annotations

import logging
import math
from typing import Any

import plexapi.exceptions

from plex_mcp.client import get_server
from plex_mcp.errors import library_not_found_error, safe_tool_call
from plex_mcp.formatters.duration import ms_to_min
from plex_mcp.formatters.json_fmt import to_json_response
from plex_mcp.formatters.markdown import format_library_list
from plex_mcp.schemas.inputs import BrowseLibraryInput
from plex_mcp.schemas.outputs import BrowseLibraryOutput, LibraryItem

logger = logging.getLogger(__name__)


async def _browse_library_handler(inp: BrowseLibraryInput) -> str:
    server = get_server()

    try:
        section = server.library.section(inp.library)
    except plexapi.exceptions.NotFound as exc:
        raise library_not_found_error(inp.library) from exc

    # Fetch all items with sort and optional filters
    search_kwargs: dict[str, Any] = {"sort": inp.sort}
    if inp.filters:
        search_kwargs["filters"] = inp.filters

    all_items = section.search(**search_kwargs)
    total = len(all_items)

    # Pagination
    page_size = inp.page_size
    page = inp.page
    start = (page - 1) * page_size
    end = start + page_size
    page_items = all_items[start:end]
    total_pages = max(1, math.ceil(total / page_size))

    items: list[LibraryItem] = []
    for item in page_items:
        title = getattr(item, "title", "")
        year = getattr(item, "year", None)
        media_type = getattr(item, "TYPE", "movie")
        rating = getattr(item, "audienceRating", None)
        duration = getattr(item, "duration", None)
        duration_min = ms_to_min(duration) if duration else None
        watched = getattr(item, "isWatched", None)
        added_at = getattr(item, "addedAt", None)
        added_at_str = (
            added_at.isoformat()
            if added_at and hasattr(added_at, "isoformat")
            else str(added_at or "")
        )

        items.append(
            LibraryItem(
                title=title,
                year=year,
                media_type=media_type,
                rating=rating,
                duration_min=duration_min,
                watched=watched,
                added_at=added_at_str,
            )
        )

    out = BrowseLibraryOutput(
        success=True,
        tool="browse_library",
        data=items,
        library=inp.library,
        total_items=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )

    if inp.format == "json":
        return to_json_response(out)
    return format_library_list(out)


async def browse_library(inp: BrowseLibraryInput) -> str:
    """Browse a Plex library with pagination, sorting, and filtering."""
    return await safe_tool_call(_browse_library_handler, inp, format=inp.format)
