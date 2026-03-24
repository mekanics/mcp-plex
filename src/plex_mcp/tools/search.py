"""search_media tool — full-text search across all Plex libraries."""

from __future__ import annotations

import logging

from plex_mcp.client import search_all_sections
from plex_mcp.errors import safe_tool_call
from plex_mcp.formatters.duration import ms_to_min
from plex_mcp.formatters.json_fmt import to_json_response
from plex_mcp.formatters.markdown import format_search_results
from plex_mcp.schemas.inputs import SearchMediaInput
from plex_mcp.schemas.outputs import SearchMediaOutput, SearchResult

logger = logging.getLogger(__name__)


async def _search_media_handler(inp: SearchMediaInput) -> str:
    raw_results = search_all_sections(query=inp.query, media_type=inp.media_type, limit=inp.limit)

    results: list[SearchResult] = []
    for item in raw_results:
        title = getattr(item, "title", "")
        year = getattr(item, "year", None)
        media_type = getattr(item, "TYPE", "movie")
        library = getattr(item, "librarySectionTitle", "")
        summary = getattr(item, "summary", "") or ""
        summary_short = summary[:120]
        rating = getattr(item, "audienceRating", None)
        duration = getattr(item, "duration", None)
        duration_min = ms_to_min(duration) if duration else None

        # Genres: list of objects with .tag attribute
        genre_objs = getattr(item, "genres", []) or []
        genres: list[str] = []
        for g in genre_objs:
            tag = getattr(g, "tag", None)
            if tag:
                genres.append(tag)

        results.append(
            SearchResult(
                title=title,
                year=year,
                media_type=media_type,
                library=library,
                summary_short=summary_short,
                rating=rating,
                duration_min=duration_min,
                genres=genres,
            )
        )

    out = SearchMediaOutput(
        success=True,
        tool="search_media",
        query=inp.query,
        total_found=len(results),
        data=results,
    )

    if inp.format == "json":
        return to_json_response(out)
    return format_search_results(out)


async def search_media(inp: SearchMediaInput) -> str:
    """Search for media across all Plex libraries."""
    return await safe_tool_call(_search_media_handler, inp, format=inp.format)
