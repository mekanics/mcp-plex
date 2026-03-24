"""Duration and date formatting utilities for plex-mcp."""

from __future__ import annotations

from datetime import UTC, datetime


def ms_to_min(ms: int) -> int:
    """Convert milliseconds to minutes (floor division)."""
    return ms // 60_000


def min_to_human(minutes: int) -> str:
    """Convert minutes to a human-readable string like '1h 30m' or '45m'."""
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def ms_to_human(ms: int) -> str:
    """Convert milliseconds directly to human-readable duration."""
    return min_to_human(ms_to_min(ms))


def relative_date(dt: datetime) -> str:
    """Return a human-readable relative date string.

    Returns 'Today', 'Yesterday', or 'N days ago'.
    Future dates and today (including slight future drift) return 'Today'.
    """
    now = datetime.now(UTC)

    # Ensure dt is timezone-aware (assume UTC if naive)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    delta = now - dt
    days = delta.days

    if days <= 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    return f"{days} days ago"


def format_season_episode(
    season: int | None,
    episode: int | None,
) -> str | None:
    """Format season/episode numbers as 'S02E04', or None if both are None."""
    if season is None and episode is None:
        return None
    s = season or 0
    e = episode or 0
    return f"S{s:02d}E{e:02d}"
