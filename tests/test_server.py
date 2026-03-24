"""Tests for server.py — Task 10.1: entry point and tool registration."""

from __future__ import annotations

import asyncio
import os


def _get_tools() -> dict:  # type: ignore[type-arg]
    """Run mcp.get_tools() in a fresh event loop without closing the running loop."""
    from plex_mcp.server import mcp

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(mcp.get_tools())
    finally:
        loop.close()


def test_server_module_importable() -> None:
    os.environ.setdefault("PLEX_TOKEN", "tok")
    os.environ.setdefault("PLEX_SERVER", "http://localhost:32400")
    import plex_mcp.server  # noqa: F401


def test_mcp_app_has_all_tools() -> None:
    os.environ["PLEX_TOKEN"] = "tok"
    os.environ["PLEX_SERVER"] = "http://localhost:32400"

    tools = _get_tools()
    tool_names = set(tools.keys())
    expected = {
        "search_media",
        "browse_library",
        "get_media_details",
        "now_playing",
        "on_deck",
        "recently_added",
        "play_media",
        "playback_control",
        "get_libraries",
        "get_clients",
    }
    assert expected == tool_names, f"Missing or extra tools: {tool_names ^ expected}"


def test_read_only_tools_have_correct_annotations() -> None:
    os.environ["PLEX_TOKEN"] = "tok"
    os.environ["PLEX_SERVER"] = "http://localhost:32400"

    tools = _get_tools()
    for read_only_name in [
        "search_media",
        "browse_library",
        "get_media_details",
        "now_playing",
        "on_deck",
        "recently_added",
        "get_libraries",
        "get_clients",
    ]:
        tool = tools[read_only_name]
        ann = tool.annotations
        assert ann is not None, f"{read_only_name} has no annotations"
        assert ann.readOnlyHint is True, f"{read_only_name} should have readOnlyHint=True"


def test_mutation_tools_have_correct_annotations() -> None:
    os.environ["PLEX_TOKEN"] = "tok"
    os.environ["PLEX_SERVER"] = "http://localhost:32400"

    tools = _get_tools()
    for mut_name in ["play_media", "playback_control"]:
        tool = tools[mut_name]
        ann = tool.annotations
        assert ann is not None, f"{mut_name} has no annotations"
        assert ann.readOnlyHint is False, f"{mut_name} should have readOnlyHint=False"


def test_main_entry_point_exists() -> None:
    from plex_mcp.server import main

    assert callable(main)
