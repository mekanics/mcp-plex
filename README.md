# plex-mcp

A Model Context Protocol (MCP) server for Plex Media Server. Gives AI assistants
(Claude, OpenClaw, etc.) the ability to search, browse, and control your Plex library
through natural language.

---

## Quick Start

**3 steps to a running server:**

```bash
# 1. Clone and install
git clone https://github.com/your-org/plex-mcp
cd plex-mcp
pip install -e .

# 2. Configure
cp .env.example .env
# Edit .env with your PLEX_TOKEN and PLEX_SERVER

# 3. Run
plex-mcp
```

The server communicates over **streamable-http** by default (FastMCP native transport).
Connect it to your MCP client as shown in the [MCP Client Setup](#mcp-client-setup) section.

---

## Configuration

All settings are loaded from environment variables or a `.env` file in the working directory.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PLEX_TOKEN` | ✅ Yes | — | Plex authentication token ([how to find it](https://support.plex.tv/articles/204059436)) |
| `PLEX_SERVER` | ✅ Yes | — | Plex server URL, e.g. `http://192.168.1.10:32400` |
| `PLEX_CONNECT_TIMEOUT` | No | `10` | Connection timeout in seconds |
| `PLEX_REQUEST_TIMEOUT` | No | `30` | Per-request timeout in seconds |
| `LOG_LEVEL` | No | `WARNING` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `FASTMCP_TRANSPORT` | No | `streamable-http` | MCP transport (`streamable-http` or `sse`) |
| `FASTMCP_HOST` | No | `0.0.0.0` | Bind address |
| `FASTMCP_PORT` | No | `8000` | Port the server listens on |

Create a `.env` file:
```
PLEX_TOKEN=your_token_here
PLEX_SERVER=http://192.168.1.10:32400
```

---

## MCP Client Setup

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "plex": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### OpenClaw

Add to your OpenClaw MCP config:

```json
{
  "name": "plex",
  "type": "http",
  "url": "http://localhost:8000/mcp"
}
```

---

## Tool Reference

| Tool | Purpose | Type |
|------|---------|------|
| `search_media` | Full-text search across all libraries | Read-only |
| `browse_library` | Paginated browsing of a library section | Read-only |
| `get_media_details` | Rich metadata, cast, file info for one item | Read-only |
| `now_playing` | Active streaming sessions on the server | Read-only |
| `on_deck` | Continue-watching / next-up list | Read-only |
| `recently_added` | New items grouped by date added | Read-only |
| `get_libraries` | List all Plex library sections | Read-only |
| `get_clients` | List available Plex player clients | Read-only |
| `play_media` | Start playback on a named client | **Mutating** |
| `playback_control` | Pause, resume, stop, seek, or skip | **Mutating** |

---

## Confirmation Gate

The two mutating tools (`play_media` and `playback_control`) use a **two-step
confirmation gate** to prevent accidental playback:

1. **Default (dry run):** Call the tool normally — it returns a preview showing
   exactly what will happen without doing anything.
2. **Confirm:** Call again with `confirmed=True` to execute.

**Example:**
```
# Step 1: Preview
play_media(title="Dune", client="Living Room TV")
# → ⚠️ Playback Preview (not started) — Dune on Living Room TV

# Step 2: Execute
play_media(title="Dune", client="Living Room TV", confirmed=True)
# → ✅ Playback Started — Dune on Living Room TV
```

This prevents the AI from accidentally starting playback during casual conversation.

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Type check
mypy src/plex_mcp --strict --ignore-missing-imports

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# All-in-one CI check
pytest tests/ -v && mypy src/plex_mcp --strict --ignore-missing-imports && ruff check src/ tests/
```

### Project Structure

```
src/plex_mcp/
├── server.py          # FastMCP server, tool registration, entry point
├── config.py          # Settings (pydantic-settings, env vars)
├── client.py          # PlexServer singleton, resolve_media(), resolve_client()
├── errors.py          # PlexMCPError, safe_tool_call, error factory helpers
├── schemas/
│   ├── common.py      # PlexMCPResponse, MediaRef, SessionRef, PlexError
│   ├── inputs.py      # All *Input models (one per tool)
│   └── outputs.py     # All *Output and *Data models
├── tools/
│   ├── search.py      # search_media
│   ├── browse.py      # browse_library
│   ├── details.py     # get_media_details
│   ├── sessions.py    # now_playing
│   ├── deck.py        # on_deck, recently_added
│   ├── libraries.py   # get_libraries, get_clients
│   └── playback.py    # play_media, playback_control
└── formatters/
    ├── markdown.py    # All markdown rendering functions
    ├── duration.py    # Time/date formatting utilities
    └── json_fmt.py    # JSON serialisation helper
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `AUTH_FAILED` | Invalid or expired `PLEX_TOKEN` | [Generate a new token](https://support.plex.tv/articles/204059436) |
| `CONNECTION_FAILED` | Can't reach `PLEX_SERVER` | Check the URL and that Plex is running |
| `LIBRARY_NOT_FOUND` | Library name typo or wrong case | Use `get_libraries()` to list exact names |
| `MEDIA_NOT_FOUND` | Title not in library | Use `search_media()` to find the exact title |
| `MEDIA_AMBIGUOUS` | Multiple matches (e.g. remakes) | Add the `year` parameter |
| `CLIENT_NOT_FOUND` | Player not visible | Open Plex app on device; use `get_clients()` to list |
| `CLIENT_OFFLINE` | Player went offline | Ensure the device is on and Plex app is active |
| `NO_ACTIVE_SESSION` | `playback_control` but nothing playing | Use `play_media()` first |
| `MULTIPLE_SESSIONS` | Multiple sessions, no client specified | Add `client=` to target a specific player |
| `PLAYBACK_ERROR` | Plex rejected the playback command | Check client compatibility and try again |

---

## Docker

See [Bunch 12](#) — a `Dockerfile` and `docker-compose.yml` are included for
containerised deployment.

```bash
# Build
docker build -t plex-mcp .

# Run (with environment variables)
docker run --rm \
  -e PLEX_TOKEN=... \
  -e PLEX_SERVER=http://192.168.1.10:32400 \
  -p 8000:8000 \
  plex-mcp

# Or with docker compose
cp .env.example .env  # edit with your values
docker compose up
```

---

## License

MIT
