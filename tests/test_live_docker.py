#!/usr/bin/env python3
"""Live Docker integration test — exercises all 10 plex-mcp tools against the real server.

Run from project root:
    python tests/test_live_docker.py

Requires:
    - docker compose image already built  (docker compose build)
    - .env populated with PLEX_TOKEN + PLEX_SERVER pointing at a live Plex instance

Each tool is called once via the MCP stdio transport inside a docker compose container.
Mutation tools (play_media, playback_control) are exercised in dry-run mode only
(confirmed=False) so no real playback is triggered.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from typing import Any

# ── Configuration ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
TOOL_TIMEOUT = 30  # seconds per tool call
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"


# ── MCP stdio client ───────────────────────────────────────────────────────────


class MCPClient:
    """Minimal MCP JSON-RPC client over a subprocess stdin/stdout pair."""

    def __init__(self, proc: subprocess.Popen) -> None:  # type: ignore[type-arg]
        self._proc = proc
        self._id = 0
        self._lock = threading.Lock()

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _send(self, msg: dict[str, Any]) -> None:
        line = json.dumps(msg) + "\n"
        assert self._proc.stdin is not None
        self._proc.stdin.write(line.encode())
        self._proc.stdin.flush()

    def _recv(self, timeout: float = TOOL_TIMEOUT) -> dict[str, Any]:
        assert self._proc.stdout is not None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self._proc.stdout.readline()
            if not line:
                raise EOFError("Server closed stdout unexpectedly")
            text = line.decode().strip()
            if text:
                return json.loads(text)  # type: ignore[no-any-return]
        raise TimeoutError(f"No response within {timeout}s")

    def initialize(self) -> dict[str, Any]:
        req_id = self._next_id()
        self._send({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "live-test", "version": "1.0.0"},
            },
        })
        # Read until we get the response for our initialize request
        for _ in range(10):
            msg = self._recv()
            if msg.get("id") == req_id:
                # Send initialized notification back
                self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
                return msg
        raise RuntimeError("Never received initialize response")

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        req_id = self._next_id()
        self._send({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        # Read until we match our request id
        for _ in range(20):
            msg = self._recv(timeout=TOOL_TIMEOUT)
            if msg.get("id") == req_id:
                if "error" in msg:
                    raise RuntimeError(f"JSON-RPC error: {msg['error']}")
                content = msg.get("result", {}).get("content", [])
                texts = [c["text"] for c in content if c.get("type") == "text"]
                return "\n".join(texts)
        raise RuntimeError(f"Never received response for tool '{name}' (id={req_id})")


# ── Test runner ────────────────────────────────────────────────────────────────


def start_container() -> subprocess.Popen:  # type: ignore[type-arg]
    """Launch `docker compose run --rm plex-mcp` with stdio piped."""
    cmd = [
        "docker", "compose",
        "-f", str(PROJECT_ROOT / "docker-compose.yml"),
        "run", "--rm", "plex-mcp",
    ]
    return subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(PROJECT_ROOT),
    )


def fmt_result(text: str, max_lines: int = 6) -> str:
    """Trim long output to a readable preview."""
    lines = text.strip().splitlines()
    preview = lines[:max_lines]
    suffix = f"\n  … ({len(lines) - max_lines} more lines)" if len(lines) > max_lines else ""
    indented = "\n".join(f"  {l}" for l in preview)
    return indented + suffix


def run_case(
    client: MCPClient,
    label: str,
    tool: str,
    args: dict[str, Any],
    must_contain: list[str] | None = None,
    may_contain: list[str] | None = None,
) -> bool:
    """Run one tool call, print result. Returns True on pass."""
    print(f"\n{CYAN}{BOLD}── {label}{RESET}")
    print(f"   tool={tool}  args={json.dumps(args)}")
    try:
        result = client.call_tool(tool, args)
        ok = True
        failures = []
        for needle in (must_contain or []):
            if needle.lower() not in result.lower():
                failures.append(f"missing '{needle}'")
        if failures:
            ok = False
            print(f"{RED}   ✗ FAIL: {', '.join(failures)}{RESET}")
        else:
            print(f"{GREEN}   ✓ PASS{RESET}")
        print(fmt_result(result))
        return ok
    except Exception as exc:
        print(f"{RED}   ✗ ERROR: {exc}{RESET}")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  plex-mcp — Live Docker integration test{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")

    proc = start_container()
    stderr_lines: list[str] = []

    def drain_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_lines.append(line.decode())

    t = threading.Thread(target=drain_stderr, daemon=True)
    t.start()

    client = MCPClient(proc)

    passed = 0
    failed = 0
    discovered_library: str | None = None
    discovered_title: str | None = None
    discovered_client: str | None = None

    try:
        # ── Handshake ──────────────────────────────────────────────────────────
        print(f"\n{YELLOW}Initializing MCP session …{RESET}")
        init = client.initialize()
        server_info = init.get("result", {}).get("serverInfo", {})
        print(f"  Server: {server_info.get('name', '?')} v{server_info.get('version', '?')}")

        # ── 1. get_libraries ──────────────────────────────────────────────────
        ok = run_case(client, "1/10  get_libraries", "get_libraries", {"format": "json"})
        if ok:
            # Try to parse library name for later use
            try:
                libs_raw = client.call_tool("get_libraries", {"format": "json"})
                libs_data = json.loads(libs_raw)
                sections = libs_data.get("data", [])
                if sections:
                    discovered_library = sections[0]["name"]
                    print(f"  {YELLOW}→ discovered library: {discovered_library!r}{RESET}")
            except Exception:
                pass
        passed += ok; failed += not ok

        # ── 2. get_clients ────────────────────────────────────────────────────
        ok = run_case(client, "2/10  get_clients", "get_clients", {"format": "json"})
        if ok:
            try:
                clients_raw = client.call_tool("get_clients", {"format": "json"})
                clients_data = json.loads(clients_raw)
                entries = clients_data.get("data", [])
                if entries:
                    discovered_client = entries[0].get("name") or entries[0].get("title")
                    print(f"  {YELLOW}→ discovered client: {discovered_client!r}{RESET}")
            except Exception:
                pass
        passed += ok; failed += not ok

        # ── 3. now_playing ────────────────────────────────────────────────────
        ok = run_case(
            client, "3/10  now_playing", "now_playing", {"format": "markdown"},
        )
        passed += ok; failed += not ok

        # ── 4. on_deck ────────────────────────────────────────────────────────
        ok = run_case(
            client, "4/10  on_deck", "on_deck", {"limit": 5, "format": "markdown"},
        )
        passed += ok; failed += not ok

        # ── 5. recently_added ─────────────────────────────────────────────────
        ok = run_case(
            client, "5/10  recently_added", "recently_added",
            {"days": 30, "limit": 5, "format": "markdown"},
        )
        passed += ok; failed += not ok

        # ── 6. search_media ───────────────────────────────────────────────────
        ok = run_case(
            client, "6/10  search_media", "search_media",
            {"query": "the", "limit": 3, "format": "json"},
        )
        if ok:
            try:
                search_raw = client.call_tool("search_media", {"query": "the", "limit": 3, "format": "json"})
                search_data = json.loads(search_raw)
                items = search_data.get("data", [])
                if items:
                    discovered_title = items[0].get("title")
                    print(f"  {YELLOW}→ discovered title: {discovered_title!r}{RESET}")
            except Exception:
                pass
        passed += ok; failed += not ok

        # ── 7. browse_library ─────────────────────────────────────────────────
        library_name = discovered_library or "Movies"
        ok = run_case(
            client, "7/10  browse_library", "browse_library",
            {"library": library_name, "page": 1, "page_size": 3, "format": "markdown"},
        )
        passed += ok; failed += not ok

        # ── 8. get_media_details ──────────────────────────────────────────────
        title = discovered_title or "the"
        ok = run_case(
            client, "8/10  get_media_details", "get_media_details",
            {"title": title, "format": "markdown"},
        )
        passed += ok; failed += not ok

        # ── 9. play_media (dry-run) ───────────────────────────────────────────
        # When no client is reachable the tool returns CLIENT_NOT_FOUND; when one
        # is reachable it returns the confirmation-required preview.  Both are
        # valid structured responses — we just check the tool doesn't crash.
        client_name = discovered_client or "TV"
        ok = run_case(
            client, "9/10  play_media (dry-run, confirmed=False)", "play_media",
            {
                "title": title or "the",
                "client": client_name,
                "confirmed": False,
                "format": "markdown",
            },
        )
        passed += ok; failed += not ok

        # ── 10. playback_control (dry-run) ────────────────────────────────────
        # When nothing is playing the tool returns NO_ACTIVE_SESSION; when a
        # session exists it returns the confirmation-required preview.  Both are
        # valid structured responses.
        ok = run_case(
            client, "10/10 playback_control (dry-run, confirmed=False)", "playback_control",
            {"action": "pause", "confirmed": False, "format": "markdown"},
        )
        passed += ok; failed += not ok

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    # ── Summary ────────────────────────────────────────────────────────────────
    total = passed + failed
    print(f"\n{BOLD}{'═' * 60}{RESET}")
    colour = GREEN if failed == 0 else RED
    print(f"{colour}{BOLD}  Results: {passed}/{total} passed{RESET}")
    if failed:
        print(f"{RED}  {failed} test(s) FAILED{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}\n")

    if stderr_lines:
        print(f"{YELLOW}── Server stderr (last 10 lines) ──{RESET}")
        for line in stderr_lines[-10:]:
            print(f"  {line}", end="")
        print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
