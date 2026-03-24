"""JSON response formatting for plex-mcp."""

from __future__ import annotations

from plex_mcp.schemas.common import PlexMCPResponse


def to_json_response(out: PlexMCPResponse) -> str:
    """Serialize a PlexMCPResponse to a JSON string."""
    return out.model_dump_json(indent=2)
