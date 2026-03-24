# Changelog

All notable changes to `plex-mcp` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-02-18

### Added

- `search_media` — full-text search across all Plex libraries; supports
  `media_type` filter and configurable `limit`; returns markdown or JSON
- `browse_library` — paginated library browsing with sort and filter support;
  returns page N of M with navigation hints
- `get_media_details` — rich metadata including rating, genres, runtime, and
  studio; `detailed=True` adds full cast/crew table and file codec info
- `now_playing` — active streaming sessions with transcode status, progress
  bar, and per-user/client breakdown
- `on_deck` — continue-watching list with progress percentage and remaining
  time; respects configurable `limit`
- `recently_added` — new library additions grouped by relative date (Today,
  Yesterday, N days ago); filterable by media type and lookback window
- `get_libraries` — list all Plex library sections with item counts and
  storage size; essential for discovering available library names
- `get_clients` — list available Plex player clients (TVs, phones, browsers)
  with platform, product, and IP; navigation hint for `play_media`
- `play_media` — start playback of any media item on any named client; full
  two-step confirmation gate (dry-run preview → `confirmed=True` execution)
- `playback_control` — pause, resume, stop, skip next/previous, and seek on
  active sessions; same two-step confirmation gate as `play_media`
- Uniform error surface: all errors return human-readable markdown or JSON
  with actionable suggestions; no raw Python exceptions leak to the MCP layer
- Token-efficient markdown output: search results < 500 tokens, empty
  responses < 100 tokens; all formatters respect SAD §5.5 budget table
- mypy strict-mode clean (0 errors across 21 source files)
- ruff lint + format clean (0 errors, consistent style)
- Full test suite: 141 tests, 0 failures

### Architecture

- Built on **FastMCP** ≥ 2.0 with stdio transport
- **pydantic-settings** for env-var/dotenv configuration
- **PlexAPI** ≥ 4.15 for Plex server communication
- All mutation tools protected by confirmation gate pattern
- All tool responses go through `safe_tool_call` — never propagate exceptions
  to the MCP transport layer
