"""get_media_details tool — rich metadata for a single piece of media."""

from __future__ import annotations

import logging
from typing import Any

from plex_mcp.client import get_server, search_all_sections
from plex_mcp.errors import (
    media_ambiguous_error,
    media_not_found_error,
    safe_tool_call,
)
from plex_mcp.formatters.duration import ms_to_min
from plex_mcp.formatters.json_fmt import to_json_response
from plex_mcp.formatters.markdown import format_media_details
from plex_mcp.schemas.inputs import GetMediaDetailsInput
from plex_mcp.schemas.outputs import (
    CastMember,
    MediaDetailsData,
    MediaDetailsOutput,
    MediaFile,
)

logger = logging.getLogger(__name__)


def _resolution_from_height(height: int | None) -> str:
    if not height:
        return "Unknown"
    if height >= 2160:
        return "4K"
    if height >= 1080:
        return "1080p"
    if height >= 720:
        return "720p"
    return f"{height}p"


def _resolve_media_local(
    title: str, year: int | None, media_type: str | None
) -> Any:
    """Resolve a media title to a single Plex item."""
    raw_results = search_all_sections(query=title, media_type=media_type, limit=10)

    # Exact title match (case-insensitive)
    title_lower = title.lower()
    matched = [r for r in raw_results if getattr(r, "title", "").lower() == title_lower]
    if not matched:
        matched = raw_results

    if not matched:
        raise media_not_found_error(title=title, year=year)

    # Year filter
    if year is not None:
        year_matched = [r for r in matched if getattr(r, "year", None) == year]
        if year_matched:
            matched = year_matched

    if len(matched) == 1:
        return matched[0]

    # Multiple matches
    candidates = [
        (getattr(r, "title", ""), getattr(r, "year", None), getattr(r, "TYPE", "")) for r in matched
    ]
    raise media_ambiguous_error(title=title, candidates=candidates)


async def _get_media_details_handler(inp: GetMediaDetailsInput) -> str:
    server = get_server()

    # Resolve the media item inline
    item = _resolve_media_local(inp.title, inp.year, inp.media_type)

    # Fetch the full item via fetchItem if available, else use resolved item
    rating_key = getattr(item, "ratingKey", None)
    if rating_key:
        import contextlib

        with contextlib.suppress(Exception):
            item = server.fetchItem(rating_key)  # type: ignore[no-untyped-call]

    media_type = getattr(item, "TYPE", "movie")
    title = getattr(item, "title", inp.title)
    year = getattr(item, "year", None)
    library = getattr(item, "librarySectionTitle", "")
    summary = getattr(item, "summary", "") or ""
    rating_audience = getattr(item, "audienceRating", None)
    rating_critics = getattr(item, "rating", None)
    content_rating = getattr(item, "contentRating", None)

    # Only use typed values
    if not isinstance(rating_audience, (int, float)):
        rating_audience = None
    if not isinstance(rating_critics, (int, float)):
        rating_critics = None
    if not isinstance(content_rating, str):
        content_rating = None

    genre_objs = getattr(item, "genres", []) or []
    genres: list[str] = []
    for g in genre_objs:
        tag = getattr(g, "tag", None)
        if isinstance(tag, str) and tag:
            genres.append(tag)

    duration = getattr(item, "duration", None)
    duration_min = ms_to_min(duration) if isinstance(duration, int) else None
    studio = getattr(item, "studio", None)
    if not isinstance(studio, str):
        studio = None
    originally_available = getattr(item, "originallyAvailableAt", None)
    orig_str: str | None = None
    if isinstance(originally_available, str):
        orig_str = originally_available
    elif originally_available is not None:
        # Try isoformat() — only accept if result is a real string
        try:
            result_iso = originally_available.isoformat()
            if isinstance(result_iso, str):
                orig_str = result_iso
        except Exception:
            pass

    watched = getattr(item, "isWatched", None)
    if not isinstance(watched, bool):
        watched = None
    view_offset = getattr(item, "viewOffset", None)
    watch_progress_pct: float | None = None
    if isinstance(view_offset, int) and isinstance(duration, int) and duration > 0:
        watch_progress_pct = round((view_offset / duration) * 100, 1)

    # Show-specific (only real ints)
    season_count_raw = getattr(item, "childCount", None)
    season_count = int(season_count_raw) if isinstance(season_count_raw, int) else None
    episode_count_raw = getattr(item, "leafCount", None)
    episode_count = int(episode_count_raw) if isinstance(episode_count_raw, int) else None

    # Episode-specific
    season_number_raw = getattr(item, "seasonNumber", None) or getattr(item, "parentIndex", None)
    season_number = int(season_number_raw) if isinstance(season_number_raw, int) else None
    episode_number_raw = getattr(item, "index", None)
    episode_number = int(episode_number_raw) if isinstance(episode_number_raw, int) else None
    show_title = getattr(item, "grandparentTitle", None) or getattr(item, "showTitle", None)
    if not isinstance(show_title, str):
        show_title = None

    # Detailed fields (only when inp.detailed=True)
    cast: list[CastMember] | None = None
    files: list[MediaFile] | None = None

    if inp.detailed:
        cast = []
        directors = getattr(item, "directors", []) or []
        if isinstance(directors, list):
            for d in directors:
                name = getattr(d, "tag", "")
                if isinstance(name, str) and name:
                    cast.append(CastMember(name=name, role="Director", is_director=True))

        writers = getattr(item, "writers", []) or []
        if isinstance(writers, list):
            for w in writers:
                name = getattr(w, "tag", "")
                if isinstance(name, str) and name:
                    cast.append(CastMember(name=name, role="Writer", is_writer=True))

        roles = getattr(item, "roles", []) or []
        if isinstance(roles, list):
            for r in roles[:10]:
                name = getattr(r, "tag", "")
                role = getattr(r, "role", "")
                if isinstance(name, str) and name:
                    cast.append(CastMember(name=name, role=role if isinstance(role, str) else ""))

        # File info
        media_list = getattr(item, "media", []) or []
        files = []
        if isinstance(media_list, list):
            for m in media_list:
                parts = getattr(m, "parts", []) or []
                if not isinstance(parts, list):
                    continue
                for part in parts:
                    video_streams = getattr(part, "videoStreams", []) or []
                    audio_streams = getattr(part, "audioStreams", []) or []
                    v_codec = ""
                    v_height = None
                    a_codec = ""
                    a_channels = ""
                    if isinstance(video_streams, list) and video_streams:
                        vs = video_streams[0]
                        v_codec = getattr(vs, "codec", "") or ""
                        v_height_raw = getattr(vs, "height", None)
                        v_height = int(v_height_raw) if isinstance(v_height_raw, int) else None
                    if isinstance(audio_streams, list) and audio_streams:
                        as_ = audio_streams[0]
                        a_codec = getattr(as_, "codec", "") or ""
                        a_channels = getattr(as_, "audioChannelLayout", "") or ""

                    size_bytes = getattr(part, "size", 0) or 0
                    size_gb = (size_bytes / 1e9) if isinstance(size_bytes, (int, float)) else 0.0

                    files.append(
                        MediaFile(
                            filename=getattr(part, "file", "") or "",
                            size_gb=size_gb,
                            container=getattr(part, "container", "") or "",
                            video_codec=v_codec if isinstance(v_codec, str) else "",
                            resolution=_resolution_from_height(v_height),
                            audio_codec=a_codec if isinstance(a_codec, str) else "",
                            audio_channels=a_channels if isinstance(a_channels, str) else "",
                            bitrate_mbps=0.0,
                        )
                    )

    data = MediaDetailsData(
        title=title,
        year=year if isinstance(year, int) else None,
        media_type=media_type if isinstance(media_type, str) else "movie",
        library=library if isinstance(library, str) else "",
        summary=summary if isinstance(summary, str) else "",
        rating_audience=rating_audience,
        rating_critics=rating_critics,
        content_rating=content_rating,
        genres=genres,
        duration_min=duration_min,
        studio=studio,
        originally_available=orig_str,
        watched=watched,
        watch_progress_pct=watch_progress_pct,
        cast=cast,
        files=files,
        season_count=season_count,
        episode_count=episode_count,
        season_number=season_number,
        episode_number=episode_number,
        show_title=show_title,
    )

    out = MediaDetailsOutput(
        success=True,
        tool="get_media_details",
        data=data,
    )

    if inp.format == "json":
        return to_json_response(out)
    return format_media_details(out)


async def get_media_details(inp: GetMediaDetailsInput) -> str:
    """Get rich metadata for a single piece of media."""
    return await safe_tool_call(_get_media_details_handler, inp, format=inp.format)
