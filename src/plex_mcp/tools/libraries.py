"""get_libraries and get_clients tools."""

from __future__ import annotations

import logging

from plex_mcp.client import get_server
from plex_mcp.errors import safe_tool_call
from plex_mcp.formatters.json_fmt import to_json_response
from plex_mcp.formatters.markdown import format_clients, format_libraries
from plex_mcp.schemas.inputs import GetClientsInput, GetLibrariesInput
from plex_mcp.schemas.outputs import ClientInfo, GetClientsOutput, GetLibrariesOutput, LibraryInfo

logger = logging.getLogger(__name__)


# ── get_libraries ─────────────────────────────────────────────────────────────


async def _get_libraries_handler(inp: GetLibrariesInput) -> str:
    server = get_server()
    sections = server.library.sections()

    libs: list[LibraryInfo] = []
    for s in sections:
        name = getattr(s, "title", "")
        if not isinstance(name, str):
            name = str(name)
        library_type = getattr(s, "type", "movie")
        if not isinstance(library_type, str):
            library_type = "movie"
        item_count_raw = getattr(s, "totalSize", 0)
        item_count = int(item_count_raw) if isinstance(item_count_raw, (int, float)) else 0
        storage_raw = getattr(s, "totalStorage", 0)
        size_gb = (storage_raw / 1e9) if isinstance(storage_raw, (int, float)) else 0.0
        agent = getattr(s, "agent", None)
        if not isinstance(agent, str):
            agent = None

        libs.append(
            LibraryInfo(
                name=name,
                library_type=library_type,
                item_count=item_count,
                size_gb=size_gb,
                agent=agent,
            )
        )

    out = GetLibrariesOutput(
        success=True,
        tool="get_libraries",
        data=libs,
    )

    if inp.format == "json":
        return to_json_response(out)
    return format_libraries(out)


async def get_libraries(inp: GetLibrariesInput) -> str:
    """List all Plex library sections."""
    return await safe_tool_call(_get_libraries_handler, inp, format=inp.format)


# ── get_clients ───────────────────────────────────────────────────────────────


async def _get_clients_handler(inp: GetClientsInput) -> str:
    server = get_server()
    raw_clients = server.clients()  # type: ignore[no-untyped-call]

    clients: list[ClientInfo] = []
    for c in raw_clients:
        name = getattr(c, "title", "")
        if not isinstance(name, str):
            name = str(name)
        platform = getattr(c, "platform", "Unknown")
        if not isinstance(platform, str):
            platform = "Unknown"
        product = getattr(c, "product", "Unknown")
        if not isinstance(product, str):
            product = "Unknown"
        device_id = getattr(c, "machineIdentifier", "")
        if not isinstance(device_id, str):
            device_id = str(device_id)
        state = getattr(c, "state", "online")
        if not isinstance(state, str):
            state = "online"
        address = getattr(c, "address", None)
        if not isinstance(address, str):
            address = None

        clients.append(
            ClientInfo(
                name=name,
                platform=platform,
                product=product,
                device_id=device_id,
                state=state,
                address=address,
            )
        )

    out = GetClientsOutput(
        success=True,
        tool="get_clients",
        data=clients,
    )

    if inp.format == "json":
        return to_json_response(out)
    return format_clients(out)


async def get_clients(inp: GetClientsInput) -> str:
    """List all available Plex player clients."""
    return await safe_tool_call(_get_clients_handler, inp, format=inp.format)
