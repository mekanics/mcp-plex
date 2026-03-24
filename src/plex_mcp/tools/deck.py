"""on_deck and recently_added tools."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from plex_mcp.client import get_server
from plex_mcp.errors import safe_tool_call
from plex_mcp.formatters.duration import format_season_episode, ms_to_min, relative_date
from plex_mcp.formatters.json_fmt import to_json_response
from plex_mcp.formatters.markdown import format_on_deck, format_recently_added
from plex_mcp.schemas.inputs import OnDeckInput, RecentlyAddedInput
from plex_mcp.schemas.outputs import (
    OnDeckItem,
    OnDeckOutput,
    RecentlyAddedItem,
    RecentlyAddedOutput,
)

logger = logging.getLogger(__name__)


# ── on_deck ───────────────────────────────────────────────────────────────────


async def _on_deck_handler(inp: OnDeckInput) -> str:
    server = get_server()
    raw_items = server.library.onDeck()
    raw_items = raw_items[: inp.limit]

    items: list[OnDeckItem] = []
    for item in raw_items:
        media_type = getattr(item, "TYPE", "movie")
        if not isinstance(media_type, str):
            media_type = "movie"

        duration = getattr(item, "duration", None)
        view_offset = getattr(item, "viewOffset", None)
        duration_ms = int(duration) if isinstance(duration, int) else None
        offset_ms = int(view_offset) if isinstance(view_offset, int) else None

        progress_pct: float | None = None
        remaining_min: int | None = None
        if duration_ms and duration_ms > 0:
            if offset_ms is not None:
                progress_pct = round((offset_ms / duration_ms) * 100, 1)
                remaining_ms = duration_ms - offset_ms
                remaining_min = ms_to_min(remaining_ms)
            else:
                progress_pct = 0.0
                remaining_min = ms_to_min(duration_ms)

        # Media title
        if media_type == "episode":
            show_title_raw = getattr(item, "grandparentTitle", None)
            show_title = show_title_raw if isinstance(show_title_raw, str) else None
            media_title = show_title or getattr(item, "title", "")
            season_num = getattr(item, "parentIndex", None)
            episode_num = getattr(item, "index", None)
            season_num = int(season_num) if isinstance(season_num, int) else None
            episode_num = int(episode_num) if isinstance(episode_num, int) else None
            season_episode = format_season_episode(season_num, episode_num)
        else:
            media_title = getattr(item, "title", "")
            show_title = None
            season_episode = None

        if not isinstance(media_title, str):
            media_title = str(media_title)

        library = getattr(item, "librarySectionTitle", "")
        if not isinstance(library, str):
            library = ""

        items.append(
            OnDeckItem(
                media_title=media_title,
                media_type=media_type,
                show_title=show_title,
                season_episode=season_episode,
                progress_pct=progress_pct,
                remaining_min=remaining_min,
                thumb_url=None,
                library=library,
            )
        )

    out = OnDeckOutput(
        success=True,
        tool="on_deck",
        data=items,
    )

    if inp.format == "json":
        return to_json_response(out)
    return format_on_deck(out)


async def on_deck(inp: OnDeckInput) -> str:
    """Return the On Deck list — partially watched or next-up items."""
    return await safe_tool_call(_on_deck_handler, inp, format=inp.format)


# ── recently_added ────────────────────────────────────────────────────────────


async def _recently_added_handler(inp: RecentlyAddedInput) -> str:
    server = get_server()
    raw_items = server.library.recentlyAdded()

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=inp.days)

    items: list[RecentlyAddedItem] = []
    for item in raw_items:
        if len(items) >= inp.limit:
            break

        # Date filter
        added_at = getattr(item, "addedAt", None)
        if added_at is None:
            continue
        # Convert to timezone-aware if needed
        if isinstance(added_at, datetime):
            if added_at.tzinfo is None:
                added_at = added_at.replace(tzinfo=UTC)
            if added_at < cutoff:
                continue
        else:
            # Skip items with non-datetime addedAt
            continue

        # Media type filter
        media_type = getattr(item, "TYPE", "movie")
        if not isinstance(media_type, str):
            media_type = "movie"
        if inp.media_type and media_type != inp.media_type:
            continue

        title = getattr(item, "title", "")
        if not isinstance(title, str):
            title = str(title)
        year = getattr(item, "year", None)
        year = int(year) if isinstance(year, int) else None
        library = getattr(item, "librarySectionTitle", "")
        if not isinstance(library, str):
            library = ""

        added_at_str = added_at.isoformat()
        added_human = relative_date(added_at)

        duration = getattr(item, "duration", None)
        duration_min = ms_to_min(duration) if isinstance(duration, int) else None

        summary = getattr(item, "summary", "") or ""
        summary_short = summary[:120] if isinstance(summary, str) else None

        # Episode-specific
        show_title_raw = getattr(item, "grandparentTitle", None)
        show_title = show_title_raw if isinstance(show_title_raw, str) else None
        season_num = getattr(item, "parentIndex", None)
        episode_num = getattr(item, "index", None)
        season_num = int(season_num) if isinstance(season_num, int) else None
        episode_num = int(episode_num) if isinstance(episode_num, int) else None
        season_episode = (
            format_season_episode(season_num, episode_num) if media_type == "episode" else None
        )

        items.append(
            RecentlyAddedItem(
                title=title,
                year=year,
                media_type=media_type,
                library=library,
                added_at=added_at_str,
                added_human=added_human,
                duration_min=duration_min,
                summary_short=summary_short,
                show_title=show_title,
                season_episode=season_episode,
            )
        )

    cutoff_date = cutoff.date().isoformat()
    out = RecentlyAddedOutput(
        success=True,
        tool="recently_added",
        data=items,
        cutoff_date=cutoff_date,
    )

    if inp.format == "json":
        return to_json_response(out)
    return format_recently_added(out)


async def recently_added(inp: RecentlyAddedInput) -> str:
    """Return recently added media, filtered by date and type."""
    return await safe_tool_call(_recently_added_handler, inp, format=inp.format)
