"""now_playing tool — active Plex streaming sessions."""

from __future__ import annotations

import logging
from typing import Any

from plex_mcp.client import get_server
from plex_mcp.errors import safe_tool_call
from plex_mcp.formatters.duration import format_season_episode, ms_to_min
from plex_mcp.formatters.json_fmt import to_json_response
from plex_mcp.formatters.markdown import format_sessions
from plex_mcp.schemas.inputs import NowPlayingInput
from plex_mcp.schemas.outputs import NowPlayingOutput, NowPlayingSession

logger = logging.getLogger(__name__)


def _transcode_status(session: Any) -> tuple[str, str | None, int | None]:
    """Return (transcode_status, transcode_reason, bandwidth_kbps)."""
    transcode_sessions = getattr(session, "transcodeSessions", []) or []
    if not isinstance(transcode_sessions, list) or not transcode_sessions:
        return "direct_play", None, None

    ts = transcode_sessions[0]
    video_decision = getattr(ts, "videoDecision", "directplay") or "directplay"
    audio_decision = getattr(ts, "audioDecision", "directplay") or "directplay"
    bandwidth = getattr(ts, "bandwidth", None)
    bw = int(bandwidth) if isinstance(bandwidth, (int, float)) else None

    if video_decision == "transcode":
        return "transcode", "video codec", bw
    if audio_decision == "transcode":
        return "transcode", "audio codec", bw
    if video_decision == "copy" or audio_decision == "copy":
        return "direct_stream", None, bw
    return "direct_play", None, bw


async def _now_playing_handler(inp: NowPlayingInput) -> str:
    server = get_server()
    sessions = server.sessions()  # type: ignore[no-untyped-call]

    session_items: list[NowPlayingSession] = []
    for session in sessions:
        media_type = getattr(session, "TYPE", "movie")
        if not isinstance(media_type, str):
            media_type = "movie"

        # Title logic
        if media_type == "episode":
            media_title = getattr(session, "grandparentTitle", "") or getattr(session, "title", "")
            season_num = getattr(session, "seasonNumber", None) or getattr(
                session, "parentIndex", None
            )
            episode_num = getattr(session, "index", None)
            season_num = int(season_num) if isinstance(season_num, int) else None
            episode_num = int(episode_num) if isinstance(episode_num, int) else None
            season_episode = format_season_episode(season_num, episode_num)
        else:
            media_title = getattr(session, "title", "")
            season_episode = None

        if not isinstance(media_title, str):
            media_title = str(media_title)

        # User
        usernames = getattr(session, "usernames", []) or []
        user = usernames[0] if isinstance(usernames, list) and usernames else "unknown"
        if not isinstance(user, str):
            user = "unknown"

        # Player
        player = getattr(session, "player", None)
        client_name = getattr(player, "title", "Unknown") if player else "Unknown"
        client_platform = getattr(player, "platform", "Unknown") if player else "Unknown"
        client_product = getattr(player, "product", "Unknown") if player else "Unknown"
        player_state = getattr(player, "state", "playing") if player else "playing"

        for attr in [client_name, client_platform, client_product, player_state]:
            if not isinstance(attr, str):
                pass  # handled below

        if not isinstance(client_name, str):
            client_name = "Unknown"
        if not isinstance(client_platform, str):
            client_platform = "Unknown"
        if not isinstance(client_product, str):
            client_product = "Unknown"
        if not isinstance(player_state, str):
            player_state = "playing"

        # Map state
        state_map = {"playing": "playing", "paused": "paused", "buffering": "buffering"}
        state = state_map.get(player_state.lower(), "playing")

        # Duration / progress
        duration = getattr(session, "duration", None)
        view_offset = getattr(session, "viewOffset", None)
        duration_min = ms_to_min(duration) if isinstance(duration, int) else 0
        progress_min = ms_to_min(view_offset) if isinstance(view_offset, int) else 0
        if duration_min and duration_min > 0:
            progress_pct = round((progress_min / duration_min) * 100, 1)
        else:
            progress_pct = 0.0

        # Transcode info
        tc_status, tc_reason, bw = _transcode_status(session)

        session_items.append(
            NowPlayingSession(
                session_id=str(getattr(session, "ratingKey", id(session))),
                user=user,
                client_name=client_name,
                client_platform=client_platform,
                client_product=client_product,
                media_title=media_title,
                media_type=media_type,
                show_title=media_title if media_type == "episode" else None,
                season_episode=season_episode,
                duration_min=duration_min,
                progress_min=progress_min,
                progress_pct=progress_pct,
                state=state,  # type: ignore[arg-type]
                transcode_status=tc_status,  # type: ignore[arg-type]
                transcode_reason=tc_reason,
                bandwidth_kbps=bw,
            )
        )

    out = NowPlayingOutput(
        success=True,
        tool="now_playing",
        data=session_items,
        session_count=len(session_items),
    )

    if inp.format == "json":
        return to_json_response(out)
    return format_sessions(out)


async def now_playing(inp: NowPlayingInput) -> str:
    """Return all active Plex streaming sessions."""
    return await safe_tool_call(_now_playing_handler, inp, format=inp.format)
