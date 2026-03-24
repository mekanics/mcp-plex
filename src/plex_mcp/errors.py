"""Error handling infrastructure for plex-mcp.

All tool errors are instances of PlexMCPError. The safe_tool_call wrapper
converts exceptions into formatted strings so the MCP transport never sees
raw Python exceptions.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import plexapi.exceptions

from plex_mcp.schemas.common import PlexError, PlexMCPResponse

logger = logging.getLogger(__name__)

# Error code constants
AUTH_FAILED = "AUTH_FAILED"
CONNECTION_FAILED = "CONNECTION_FAILED"
LIBRARY_NOT_FOUND = "LIBRARY_NOT_FOUND"
MEDIA_NOT_FOUND = "MEDIA_NOT_FOUND"
MEDIA_AMBIGUOUS = "MEDIA_AMBIGUOUS"
CLIENT_NOT_FOUND = "CLIENT_NOT_FOUND"
CLIENT_OFFLINE = "CLIENT_OFFLINE"
SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
NO_ACTIVE_SESSION = "NO_ACTIVE_SESSION"
MULTIPLE_SESSIONS = "MULTIPLE_SESSIONS"
PLAYBACK_ERROR = "PLAYBACK_ERROR"
CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
INVALID_FILTER = "INVALID_FILTER"
RATE_LIMITED = "RATE_LIMITED"
UNKNOWN = "UNKNOWN"


class PlexMCPError(Exception):
    """All tool errors are instances of this class."""

    def __init__(
        self,
        code: str,
        message: str,
        suggestions: list[str] | None = None,
        raw: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggestions = suggestions or []
        self.raw = raw

    def to_plex_error(self) -> PlexError:
        return PlexError(
            code=self.code,
            message=self.message,
            suggestions=self.suggestions,
        )

    def to_markdown(self) -> str:
        lines = [
            f"## ❌ Error: {self.code}",
            "",
            self.message,
        ]
        if self.suggestions:
            lines += ["", "**What to try:**"]
            lines += [f"- {s}" for s in self.suggestions]
        return "\n".join(lines)


# ── safe_tool_call ─────────────────────────────────────────────────────────────


async def safe_tool_call(
    handler_fn: Callable[..., Awaitable[str]],
    input_model: Any,
    format: str,
    tool_name: str = "",
) -> str:
    """Wrap an async tool handler, converting all exceptions to formatted strings."""
    try:
        result: str = await handler_fn(input_model)
        return result
    except PlexMCPError as e:
        if format == "json":
            return PlexMCPResponse(
                success=False,
                tool=tool_name or getattr(handler_fn, "__name__", "unknown"),
                error=e.to_plex_error(),
            ).model_dump_json(indent=2)
        return e.to_markdown()
    except plexapi.exceptions.Unauthorized as e:
        err = PlexMCPError(
            code=AUTH_FAILED,
            message="Plex authentication failed. Your PLEX_TOKEN may be invalid or expired.",
            suggestions=[
                "Verify PLEX_TOKEN in your environment.",
                "Generate a new token at: https://support.plex.tv/articles/204059436",
            ],
            raw=e,
        )
        if format == "json":
            return PlexMCPResponse(
                success=False,
                tool=tool_name or getattr(handler_fn, "__name__", "unknown"),
                error=err.to_plex_error(),
            ).model_dump_json(indent=2)
        return err.to_markdown()
    except plexapi.exceptions.NotFound as e:
        err = PlexMCPError(
            code=MEDIA_NOT_FOUND,
            message=f"Resource not found: {str(e)[:200]}",
            suggestions=["Use search_media to find available media."],
            raw=e,
        )
        if format == "json":
            return PlexMCPResponse(
                success=False,
                tool=tool_name or getattr(handler_fn, "__name__", "unknown"),
                error=err.to_plex_error(),
            ).model_dump_json(indent=2)
        return err.to_markdown()
    except Exception as e:
        raw_msg = str(e)[:200]
        err = PlexMCPError(
            code=UNKNOWN,
            message=f"Unexpected error: {raw_msg}",
            raw=e,
        )
        logger.exception("Unexpected error in tool handler")
        if format == "json":
            return PlexMCPResponse(
                success=False,
                tool=tool_name or getattr(handler_fn, "__name__", "unknown"),
                error=err.to_plex_error(),
            ).model_dump_json(indent=2)
        return err.to_markdown()


# ── Factory helpers ────────────────────────────────────────────────────────────


def media_not_found_error(
    title: str,
    year: int | None = None,
    suggestions: list[str] | None = None,
) -> PlexMCPError:
    year_str = f" ({year})" if year else ""
    msg = f'No media found matching "{title}"{year_str} in your libraries.'
    default_suggestions = [
        f'Try `search_media(query="{title}")` to see all results.',
        "Check spelling or provide a year to disambiguate.",
        "The item may be in a library you don't have access to.",
    ]
    return PlexMCPError(
        code=MEDIA_NOT_FOUND,
        message=msg,
        suggestions=suggestions or default_suggestions,
    )


def media_ambiguous_error(
    title: str,
    candidates: list[tuple[Any, ...]],
) -> PlexMCPError:
    candidate_strs = ", ".join(f"{t} ({y})" if y else str(t) for t, y, *_ in candidates)
    msg = f'Found {len(candidates)} items matching "{title}": {candidate_strs}.'
    return PlexMCPError(
        code=MEDIA_AMBIGUOUS,
        message=msg,
        suggestions=[
            "Provide a `year` parameter to select the correct version.",
            f'Use `search_media(query="{title}")` to see all versions.',
        ],
    )


def client_not_found_error(name: str) -> PlexMCPError:
    return PlexMCPError(
        code=CLIENT_NOT_FOUND,
        message=f'Plex player "{name}" not found or is not reachable.',
        suggestions=[
            "Use `get_clients()` to list all available players.",
            "Ensure the Plex app is open on the target device.",
            "Player names are case-sensitive — check the exact name.",
        ],
    )


def library_not_found_error(name: str) -> PlexMCPError:
    return PlexMCPError(
        code=LIBRARY_NOT_FOUND,
        message=f'Library "{name}" not found on this Plex server.',
        suggestions=[
            "Use `get_libraries()` to list all available libraries.",
            "Library names are case-sensitive — check the exact name.",
        ],
    )


def no_active_session_error() -> PlexMCPError:
    return PlexMCPError(
        code=NO_ACTIVE_SESSION,
        message="No active playback sessions found.",
        suggestions=[
            "Use `play_media()` to start playback on a player.",
            "Use `now_playing()` to check current sessions.",
        ],
    )


def multiple_sessions_error(sessions: list[str]) -> PlexMCPError:
    session_list = ", ".join(sessions)
    return PlexMCPError(
        code=MULTIPLE_SESSIONS,
        message=f"Multiple active sessions found: {session_list}. Specify a client.",
        suggestions=[
            "Provide the `client` parameter to target a specific player.",
            "Use `now_playing()` to see all active sessions.",
        ],
    )
