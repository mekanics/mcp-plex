"""Mutation tools: play_media + playback_control.

Both tools are protected by a confirmation gate (confirmed=True required to
execute). Without confirmation, a dry-run preview is returned.

Architecture reference: SAD §3.8, §3.9, §6.3

IMPORTANT: Resolution helpers are inlined here (not delegated to client.py
functions) so that the single `get_server()` call at the top of each handler
is the only server access — making the tools straightforward to test by
patching `plex_mcp.tools.playback.get_server`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from plex_mcp.client import get_server
from plex_mcp.errors import (
    PLAYBACK_ERROR,
    PlexMCPError,
    client_not_found_error,
    media_ambiguous_error,
    media_not_found_error,
    multiple_sessions_error,
    no_active_session_error,
    safe_tool_call,
)
from plex_mcp.formatters.duration import ms_to_min
from plex_mcp.formatters.json_fmt import to_json_response
from plex_mcp.formatters.markdown import format_dry_run, format_playback_success
from plex_mcp.schemas.common import MediaRef
from plex_mcp.schemas.inputs import PlaybackControlInput, PlayMediaInput
from plex_mcp.schemas.outputs import (
    ClientInfo,
    PlaybackControlData,
    PlaybackControlOutput,
    PlayMediaData,
    PlayMediaOutput,
)

logger = logging.getLogger(__name__)


def _resolve_media_with_server(
    server: Any, title: str, year: int | None, media_type: str | None
) -> MediaRef:
    """Resolve media title → MediaRef using a pre-fetched server object."""
    raw_results = server.library.search(query=title, limit=10)

    if media_type:
        raw_results = [r for r in raw_results if getattr(r, "TYPE", None) == media_type]

    title_lower = title.lower()
    matched = [r for r in raw_results if getattr(r, "title", "").lower() == title_lower]
    if not matched:
        matched = raw_results

    if not matched:
        raise media_not_found_error(title=title, year=year)

    if year is not None:
        year_matched = [r for r in matched if getattr(r, "year", None) == year]
        if year_matched:
            matched = year_matched

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

    candidates = [
        (getattr(r, "title", ""), getattr(r, "year", None), getattr(r, "TYPE", "")) for r in matched
    ]
    raise media_ambiguous_error(title=title, candidates=candidates)


def _resolve_client_with_server(server: Any, client_name: str) -> ClientInfo:
    """Resolve client name → ClientInfo using a pre-fetched server object."""
    clients = server.clients()
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


async def play_media(inp: PlayMediaInput) -> str:
    """Start playback of a media item on a named Plex client.

    Returns a dry-run preview when confirmed=False (default).
    Executes playback and returns a success confirmation when confirmed=True.
    """

    async def _handler(inp: PlayMediaInput) -> str:
        server = get_server()

        # Resolve media (raises MEDIA_NOT_FOUND / MEDIA_AMBIGUOUS on failure)
        media = _resolve_media_with_server(server, inp.title, inp.year, inp.media_type)

        # Fetch the full Plex item (needed for playMedia call)
        plex_item = server.fetchItem(media.rating_key)  # type: ignore[no-untyped-call]

        # Resolve client (raises CLIENT_NOT_FOUND on failure)
        client_info = _resolve_client_with_server(server, inp.client)

        # Build dry-run data (always constructed before checking confirmed)
        duration_ms = getattr(plex_item, "duration", None)
        duration_min = ms_to_min(duration_ms) if duration_ms else None

        # Detect season/episode for TV content
        season_episode: str | None = None
        if getattr(plex_item, "TYPE", None) == "episode":
            s = getattr(plex_item, "parentIndex", None)
            e = getattr(plex_item, "index", None)
            if s is not None and e is not None:
                season_episode = f"S{s:02d}E{e:02d}"

        dry_run_data = PlayMediaData(
            dry_run=True,
            media_title=media.title,
            media_type=media.media_type,
            season_episode=season_episode,
            duration_min=duration_min,
            client_name=client_info.name,
            client_platform=client_info.platform,
            offset_ms=inp.offset_ms,
            started_at=None,
        )

        if not inp.confirmed:
            # Return dry-run preview — no side effects
            if inp.format == "json":
                out = PlayMediaOutput(success=True, tool="play_media", data=dry_run_data)
                return to_json_response(out)
            return format_dry_run(dry_run_data)

        # ── Confirmed: execute playback ───────────────────────────────────────
        plex_client = server.client(inp.client)  # type: ignore[no-untyped-call]
        try:
            plex_client.playMedia(plex_item, offset=inp.offset_ms or 0)
        except Exception as e:
            raise PlexMCPError(
                code=PLAYBACK_ERROR,
                message=f"Playback failed on '{inp.client}': {type(e).__name__}: {e}",
                suggestions=[
                    "Check that the client is online and the Plex app is open.",
                    "Verify the media is compatible with the client.",
                ],
                raw=e,
            ) from e

        started_at = datetime.now(UTC).isoformat()
        result_data = PlayMediaData(
            dry_run=False,
            media_title=media.title,
            media_type=media.media_type,
            season_episode=season_episode,
            duration_min=duration_min,
            client_name=client_info.name,
            client_platform=client_info.platform,
            offset_ms=inp.offset_ms,
            started_at=started_at,
        )

        if inp.format == "json":
            out = PlayMediaOutput(success=True, tool="play_media", data=result_data)
            return to_json_response(out)
        return format_playback_success(result_data)

    return await safe_tool_call(_handler, inp, format=inp.format, tool_name="play_media")


async def playback_control(inp: PlaybackControlInput) -> str:
    """Control an active Plex playback session.

    Supports: pause, resume, stop, skip_next, skip_prev, seek.
    Returns a dry-run preview when confirmed=False (default).
    Executes the action when confirmed=True.
    """

    async def _handler(inp: PlaybackControlInput) -> str:
        server = get_server()
        sessions = server.sessions()  # type: ignore[no-untyped-call]

        # ── No sessions active ───────────────────────────────────────────────
        if not sessions:
            raise no_active_session_error()

        # ── Resolve target session ───────────────────────────────────────────
        if inp.client:
            matched = [
                s
                for s in sessions
                if getattr(s, "player", None)
                and getattr(s.player, "title", "").lower() == inp.client.lower()
            ]
            if matched:
                target_session = matched[0]
            elif len(sessions) == 1:
                # Only 1 session → use it regardless of name mismatch
                target_session = sessions[0]
            else:
                session_names = [
                    getattr(getattr(s, "player", None), "title", "Unknown") for s in sessions
                ]
                raise multiple_sessions_error(session_names)
        else:
            # No client specified
            if len(sessions) > 1:
                session_names = [
                    getattr(getattr(s, "player", None), "title", "Unknown") for s in sessions
                ]
                raise multiple_sessions_error(session_names)
            target_session = sessions[0]

        # ── Validate seek ────────────────────────────────────────────────────
        if inp.action == "seek" and inp.seek_offset_ms is None:
            raise PlexMCPError(
                code=PLAYBACK_ERROR,
                message="'seek' action requires the seek_offset_ms parameter.",
                suggestions=[
                    "Provide seek_offset_ms as milliseconds from the start of the media.",
                    "Example: playback_control(action='seek', seek_offset_ms=1800000)",
                ],
            )

        # ── Extract session info ─────────────────────────────────────────────
        player = getattr(target_session, "player", None)
        client_name = getattr(player, "title", inp.client or "Unknown")
        client_platform = getattr(player, "platform", "Unknown")
        session_state = getattr(player, "state", "playing")

        media_title: str = str(
            getattr(target_session, "grandparentTitle", None)
            or getattr(target_session, "title", "Unknown")
            or "Unknown"
        )

        seek_position_min = inp.seek_offset_ms / 60000 if inp.seek_offset_ms is not None else None

        dry_run_data = PlaybackControlData(
            dry_run=True,
            action=inp.action,
            client_name=client_name,
            client_platform=client_platform,
            media_title=media_title,
            session_state_before=session_state,
            session_state_after=None,
            seek_position_min=seek_position_min,
        )

        if not inp.confirmed:
            if inp.format == "json":
                out = PlaybackControlOutput(
                    success=True, tool="playback_control", data=dry_run_data
                )
                return to_json_response(out)
            return format_dry_run(dry_run_data)

        # ── Confirmed: execute action ────────────────────────────────────────
        plex_client = server.client(client_name)  # type: ignore[no-untyped-call]
        try:
            if inp.action == "pause":
                plex_client.pause()
                state_after = "paused"
            elif inp.action == "resume":
                plex_client.play()
                state_after = "playing"
            elif inp.action == "stop":
                plex_client.stop()
                state_after = "stopped"
            elif inp.action == "skip_next":
                plex_client.skipNext()
                state_after = "playing"
            elif inp.action == "skip_prev":
                plex_client.skipPrevious()
                state_after = "playing"
            elif inp.action == "seek":
                plex_client.seekTo(inp.seek_offset_ms)
                state_after = "playing"
            else:
                raise PlexMCPError(
                    code=PLAYBACK_ERROR,
                    message=f"Unknown playback action: '{inp.action}'",
                    suggestions=["Valid actions: pause, resume, stop, skip_next, skip_prev, seek"],
                )
        except PlexMCPError:
            raise
        except Exception as e:
            raise PlexMCPError(
                code=PLAYBACK_ERROR,
                message=f"Playback control failed on '{client_name}': {type(e).__name__}: {e}",
                suggestions=[
                    "Check that the client is online and responsive.",
                    "Use now_playing() to verify the session is still active.",
                ],
                raw=e,
            ) from e

        result_data = PlaybackControlData(
            dry_run=False,
            action=inp.action,
            client_name=client_name,
            client_platform=client_platform,
            media_title=media_title,
            session_state_before=session_state,
            session_state_after=state_after,
            seek_position_min=seek_position_min,
        )

        if inp.format == "json":
            out = PlaybackControlOutput(success=True, tool="playback_control", data=result_data)
            return to_json_response(out)
        return format_playback_success(result_data)

    return await safe_tool_call(_handler, inp, format=inp.format, tool_name="playback_control")
