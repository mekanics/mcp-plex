"""Markdown formatting functions for all plex-mcp tools.

Each function takes the corresponding *Output schema and returns a str.
Follows SAD §5.2 conventions:
  - H2 header always present
  - Bold labels (name: value)
  - Tables for ≥3 items
  - Navigation hint in italics at end
  - Emoji vocabulary from SAD §5.3
"""

from __future__ import annotations

from typing import Any

from plex_mcp.formatters.duration import min_to_human
from plex_mcp.schemas.outputs import (
    BrowseLibraryOutput,
    GetClientsOutput,
    GetLibrariesOutput,
    MediaDetailsOutput,
    NowPlayingOutput,
    OnDeckOutput,
    PlaybackControlData,
    PlayMediaData,
    RecentlyAddedOutput,
    SearchMediaOutput,
)

# Emoji map
_MEDIA_EMOJI = {
    "movie": "🎬",
    "show": "📺",
    "episode": "📺",
    "artist": "🎵",
    "album": "🎵",
    "track": "🎵",
}


def _media_emoji(media_type: str) -> str:
    return _MEDIA_EMOJI.get(media_type.lower(), "🎬")


def _state_emoji(state: str) -> str:
    return {"playing": "▶", "paused": "⏸", "buffering": "⏳", "stopped": "⏹"}.get(
        state.lower(), "▶"
    )


# ── search_media ───────────────────────────────────────────────────────────────


def format_search_results(out: SearchMediaOutput) -> str:
    lines: list[str] = []
    total = out.total_found or len(out.data)
    lines.append(f'## Search: "{out.query}" ({total} results)')
    lines.append("")

    if not out.data:
        lines.append("No results found. Try a different search term.")
        lines.append("")
        lines.append("*Use `search_media` with different keywords.*")
        return "\n".join(lines)

    for result in out.data:
        year_str = f" ({result.year})" if result.year else ""
        genre_str = ", ".join(result.genres) if result.genres else ""
        type_label = result.media_type.replace("_", " ").title()
        type_genre = f" · {type_label}" + (f" · {genre_str}" if genre_str else "")

        lines.append(f"**{result.title}**{year_str}{type_genre}")
        rating_str = f"⭐ {result.rating}" if result.rating else ""
        dur_str = min_to_human(result.duration_min) if result.duration_min else ""
        lib_str = f"Library: {result.library}" if result.library else ""
        meta_parts = [p for p in [rating_str, dur_str, lib_str] if p]
        if meta_parts:
            lines.append(" | ".join(meta_parts))
        if result.summary_short:
            lines.append(f"> {result.summary_short}")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("*Use `get_media_details` for cast, file info, and full metadata.*")
    return "\n".join(lines)


# ── browse_library ────────────────────────────────────────────────────────────


def format_library_list(out: BrowseLibraryOutput) -> str:
    lines: list[str] = []
    lines.append(
        f"## {out.library} · Page {out.page} of {out.total_pages} ({out.total_items} total)"
    )
    lines.append(f"*Sorted by: {out.library}*")
    lines.append("")

    if not out.data:
        lines.append("No items found.")
        lines.append("")
        lines.append(f"*Use `browse_library(library='{out.library}')` to explore.*")
        return "\n".join(lines)

    # Table for items
    lines.append("| Title | Year | Rating | Duration | Watched |")
    lines.append("|-------|------|--------|----------|---------|")
    for item in out.data:
        year_str = str(item.year) if item.year else "—"
        rating_str = f"⭐ {item.rating}" if item.rating else "—"
        dur_str = min_to_human(item.duration_min) if item.duration_min else "—"
        watched_str = "✅" if item.watched else ("❌" if item.watched is False else "—")
        lines.append(f"| {item.title} | {year_str} | {rating_str} | {dur_str} | {watched_str} |")

    lines.append("")
    lines.append(
        f"*Page {out.page} of {out.total_pages} · "
        f"Use `page={out.page + 1}` to continue · "
        f"Use `get_media_details` for full info*"
    )
    return "\n".join(lines)


# ── get_media_details ─────────────────────────────────────────────────────────


def format_media_details(out: MediaDetailsOutput) -> str:
    if not out.data:
        return "## ❌ No details available."

    d = out.data
    emoji = _media_emoji(d.media_type)
    year_str = f" ({d.year})" if d.year else ""
    lines: list[str] = []
    lines.append(f"## {emoji} {d.title}{year_str}")
    lines.append("")

    if d.genres:
        lines.append(f"**Genre:** {', '.join(d.genres)}")
    rating_parts = []
    if d.rating_audience:
        rating_parts.append(f"⭐ {d.rating_audience} (audience)")
    if d.rating_critics:
        rating_parts.append(f"🍅 {d.rating_critics}% (critics)")
    if rating_parts:
        lines.append(f"**Rating:** {' · '.join(rating_parts)}")
    if d.duration_min:
        dur_str = min_to_human(d.duration_min)
        cr_str = f" · Rated {d.content_rating}" if d.content_rating else ""
        lines.append(f"**Duration:** {dur_str}{cr_str}")
    if d.studio:
        lines.append(f"**Studio:** {d.studio}")
    if d.originally_available:
        lines.append(f"**Released:** {d.originally_available}")
    if d.watched is not None:
        watched_label = "✅ Watched" if d.watched else "❌ Not watched"
        lines.append(f"**Status:** {watched_label}")

    if d.summary:
        lines.append("")
        lines.append(f"> {d.summary[:300]}")

    # Show/episode specific
    if d.season_count:
        lines.append(f"**Seasons:** {d.season_count}")
    if d.season_number and d.episode_number:
        se = f"S{d.season_number:02d}E{d.episode_number:02d}"
        lines.append(f"**Episode:** {se}")
    if d.show_title:
        lines.append(f"**Show:** {d.show_title}")

    # Detailed sections
    if d.cast:
        lines.append("")
        lines.append("### Cast & Crew")
        directors = [m for m in d.cast if m.is_director]
        writers = [m for m in d.cast if m.is_writer]
        actors = [m for m in d.cast if not m.is_director and not m.is_writer]
        if directors:
            lines.append(f"**Director:** {', '.join(m.name for m in directors)}")
        if writers:
            lines.append(f"**Writer:** {', '.join(m.name for m in writers)}")
        if actors:
            lines.append("| Actor | Role |")
            lines.append("|-------|------|")
            for member in actors[:10]:
                lines.append(f"| {member.name} | {member.role} |")

    if d.files:
        lines.append("")
        lines.append("### File Info")
        lines.append("| Property | Value |")
        lines.append("|----------|-------|")
        for f in d.files[:1]:
            lines.append(f"| File | {f.filename} |")
            lines.append(f"| Size | {f.size_gb:.1f} GB |")
            lines.append(f"| Video | {f.video_codec.upper()} · {f.resolution} |")
            lines.append(f"| Audio | {f.audio_codec.upper()} {f.audio_channels} |")
            lines.append(f"| Bitrate | {f.bitrate_mbps:.1f} Mbps |")

    lines.append("")
    if not (d.cast or d.files):
        lines.append("*Use `detailed=True` for cast, crew, and file info.*")
    return "\n".join(lines)


# ── now_playing ───────────────────────────────────────────────────────────────


def format_sessions(out: NowPlayingOutput) -> str:
    count = out.session_count or len(out.data)
    lines: list[str] = []
    lines.append(f"## 📺 Now Playing ({count} active session{'s' if count != 1 else ''})")
    lines.append("")

    if not out.data:
        lines.append("No active sessions — nothing is currently playing.")
        lines.append("")
        lines.append("*Use `play_media` to start playback.*")
        return "\n".join(lines)

    for i, session in enumerate(out.data, start=1):
        state_e = _state_emoji(session.state)
        se_str = f" {session.season_episode} —" if session.season_episode else ""
        lines.append(f"### {i}. {session.user} · {session.client_name} ({session.client_platform})")
        title_line = f"**{session.media_title}**{se_str}"
        lines.append(title_line)
        tc_label = {
            "direct_play": "Direct Play",
            "direct_stream": "Direct Stream",
            "transcode": f"Transcoding ({session.transcode_reason or 'video codec'})",
        }.get(session.transcode_status, session.transcode_status)
        progress = (
            f"⏱ {session.progress_min}m / {session.duration_min}m "
            f"({session.progress_pct:.0f}%) · {state_e} "
            f"{'Playing' if session.state == 'playing' else session.state.capitalize()} · {tc_label}"
        )
        lines.append(progress)
        lines.append("")

    lines.append("---")
    lines.append("*Use `playback_control` to pause, resume, or stop a session.*")
    return "\n".join(lines)


# ── on_deck ───────────────────────────────────────────────────────────────────


def format_on_deck(out: OnDeckOutput) -> str:
    count = len(out.data)
    lines: list[str] = []
    lines.append(f"## ▶ On Deck ({count} items)")
    lines.append("")

    if not out.data:
        lines.append("Nothing on deck — no partially-watched or next-up items.")
        lines.append("")
        lines.append("*Use `recently_added` or `browse_library` to find something to watch.*")
        return "\n".join(lines)

    for i, item in enumerate(out.data, start=1):
        emoji = _media_emoji(item.media_type)
        show_str = (
            f" — {item.show_title}"
            if item.show_title and item.show_title != item.media_title
            else ""
        )
        se_str = f" {item.season_episode}" if item.season_episode else ""
        lines.append(f"{i}. {emoji} **{item.media_title}**{se_str}{show_str}")
        if item.progress_pct is not None and item.progress_pct > 0:
            rem_str = f" · ⏱ {item.remaining_min}m remaining" if item.remaining_min else ""
            lines.append(f"   *({item.progress_pct:.0f}% watched{rem_str})*")
        else:
            lines.append("   *(Next up — 0% watched)*")
        lines.append("")

    lines.append("*Use `play_media` to start watching.*")
    return "\n".join(lines)


# ── recently_added ────────────────────────────────────────────────────────────


def format_recently_added(out: RecentlyAddedOutput) -> str:
    count = len(out.data)
    lines: list[str] = []
    lines.append(f"## 🆕 Recently Added ({count} items)")
    lines.append("")

    if not out.data:
        lines.append("No recently added items.")
        lines.append("")
        lines.append("*Use `browse_library` to explore your library.*")
        return "\n".join(lines)

    # Group by added_human
    from collections import defaultdict

    groups: dict[str, list[Any]] = defaultdict(list)
    for item in out.data:
        groups[item.added_human].append(item)

    # Ordered by appearance in data list (preserves date order)
    seen_groups: list[str] = []
    for item in out.data:
        if item.added_human not in seen_groups:
            seen_groups.append(item.added_human)

    for group_label in seen_groups:
        lines.append(f"**{group_label}**")
        for item in groups[group_label]:
            emoji = _media_emoji(item.media_type)
            year_str = f" ({item.year})" if item.year else ""
            lib_str = f" · {item.library}" if item.library else ""
            dur_str = f" · {min_to_human(item.duration_min)}" if item.duration_min else ""
            se_str = f" {item.season_episode}" if item.season_episode else ""
            title_line = f"- {emoji} **{item.title}**{se_str}{year_str}{lib_str}{dur_str}"
            lines.append(title_line)
            if item.summary_short:
                lines.append(f"  > {item.summary_short[:100]}")
        lines.append("")

    lines.append("*Use `get_media_details` for more info or `play_media` to watch.*")
    return "\n".join(lines)


# ── get_libraries ─────────────────────────────────────────────────────────────


def format_libraries(out: GetLibrariesOutput) -> str:
    lines: list[str] = []
    lines.append("## 📚 Libraries")
    lines.append("")

    if not out.data:
        lines.append("No libraries found on this Plex server.")
        lines.append("")
        lines.append("*Check your Plex server configuration.*")
        return "\n".join(lines)

    lines.append("| Name | Type | Items | Size |")
    lines.append("|------|------|-------|------|")
    for lib in out.data:
        size_str = f"{lib.size_gb:.0f} GB" if lib.size_gb else "—"
        lines.append(f"| {lib.name} | {lib.library_type} | {lib.item_count} | {size_str} |")

    lines.append("")
    lines.append("*Use `browse_library(library='...')` to explore a library.*")
    return "\n".join(lines)


# ── get_clients ───────────────────────────────────────────────────────────────


def format_clients(out: GetClientsOutput) -> str:
    lines: list[str] = []
    lines.append("## 📺 Available Players")
    lines.append("")

    if not out.data:
        lines.append("No clients found — no active players detected.")
        lines.append("")
        lines.append("*Open the Plex app on a device to make it available.*")
        return "\n".join(lines)

    for client in out.data:
        lines.append(f"**{client.name}** · {client.platform} · {client.product}")
        lines.append(f"  Status: {client.state}")
        lines.append("")

    lines.append("*Use the client name in `play_media(client='...')` to start playback.*")
    return "\n".join(lines)


# ── Mutation formatters ───────────────────────────────────────────────────────


def format_dry_run(data: PlayMediaData | PlaybackControlData) -> str:
    """Format a dry-run (preview) response for play_media or playback_control."""
    lines: list[str] = []
    lines.append("## ⚠️ Playback Preview (not started)")
    lines.append("")
    lines.append("**Ready to play:**")

    if isinstance(data, PlayMediaData):
        # PlayMediaData
        emoji = _media_emoji(data.media_type)
        year_str = ""
        se_str = f" {data.season_episode}" if getattr(data, "season_episode", None) else ""
        _dur_min = getattr(data, "duration_min", None)
        dur_str = f" · {min_to_human(_dur_min)}" if _dur_min else ""
        lines.append(f"{emoji} **{data.media_title}**{se_str}{year_str}{dur_str}")
        lines.append(f"📺 **Client:** {data.client_name} ({data.client_platform})")
        offset = getattr(data, "offset_ms", None)
        if offset:
            lines.append(f"⏱ **Starting at:** {min_to_human(offset // 60000)}")
        else:
            lines.append("⏱ **Starting at:** Beginning")
        lines.append("")
        lines.append("**To confirm playback, call:**")
        lines.append(
            f'`play_media(title="{data.media_title}", client="{data.client_name}", confirmed=True)`'
        )
    else:
        # PlaybackControlData
        action_label = data.action.replace("_", " ").title()
        lines.append(f"**Action:** {action_label}")
        lines.append(f"📺 **Client:** {data.client_name} ({data.client_platform})")
        lines.append(f"🎬 **Currently playing:** {data.media_title}")
        lines.append("")
        lines.append("**To apply, call:**")
        lines.append(
            f'`playback_control(action="{data.action}", '
            f'client="{data.client_name}", confirmed=True)`'
        )

    return "\n".join(lines)


def format_playback_success(data: PlayMediaData | PlaybackControlData) -> str:
    """Format a successful playback or control response."""
    lines: list[str] = []
    lines.append("## ✅ Playback Started")
    lines.append("")

    if isinstance(data, PlayMediaData):
        emoji = _media_emoji(data.media_type)
        se_str = f" {data.season_episode}" if getattr(data, "season_episode", None) else ""
        lines.append(f"{emoji} **{data.media_title}**{se_str}")
        lines.append(f"📺 **Playing on:** {data.client_name} ({data.client_platform})")
        started_at = getattr(data, "started_at", None)
        if started_at:
            # Extract just the time portion
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M UTC")
                lines.append(f"🕐 **Started at:** {time_str}")
            except Exception:
                lines.append(f"🕐 **Started at:** {started_at}")
    else:
        # PlaybackControlData
        action_label = data.action.replace("_", " ").title()
        lines.append(f"✅ **Action applied:** {action_label}")
        lines.append(f"📺 **Client:** {data.client_name} ({data.client_platform})")
        lines.append(f"🎬 **Media:** {data.media_title}")

    return "\n".join(lines)
