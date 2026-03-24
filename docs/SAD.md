# Software Architecture Document
## Plex Media Server MCP Server (`plex-mcp`)

**Version:** 1.0.0  
**Date:** 2026-02-18  
**Status:** Draft  
**Transport:** stdio (Model Context Protocol)

---

## Table of Contents

1. [Overview & Goals](#1-overview--goals)
2. [System Context](#2-system-context)
3. [Tool Catalogue & Schemas](#3-tool-catalogue--schemas)
4. [Error Handling Strategy](#4-error-handling-strategy)
5. [Response Format Design](#5-response-format-design)
6. [Security Considerations](#6-security-considerations)
7. [Dependencies & Project Structure](#7-dependencies--project-structure)
8. [Configuration](#8-configuration)
9. [Tool Annotations](#9-tool-annotations)

---

## 1. Overview & Goals

### 1.1 Purpose

`plex-mcp` is a Model Context Protocol (MCP) server that exposes a curated set of tools allowing LLM agents to interact with a Plex Media Server instance. It wraps the `python-plexapi` library behind an agent-optimised interface — not a 1:1 API proxy, but a workflow-oriented tool surface designed for the way agents actually use media libraries.

### 1.2 Design Goals

| Goal | Rationale |
|---|---|
| **Workflow-first, not endpoint-first** | Agents need outcomes ("play Breaking Bad on the living room TV") not raw API calls. Tools are composed for common agent tasks. |
| **Context-budget awareness** | Every response is concise by default. A `detailed=True` flag unlocks full metadata. Agents pay only for the tokens they need. |
| **Human-readable identifiers** | Tools accept and return `title (year)` strings rather than opaque `ratingKey` integers. Internal resolution is handled transparently. |
| **Actionable errors** | Every error message tells the agent exactly what to try next. No `500 Internal Server Error`; yes `Movie "Dune" not found — did you mean "Dune: Part Two (2024)"? Use search_media to confirm.` |
| **Markdown-first output** | Default responses are human-readable Markdown. JSON mode is available for programmatic consumption. |
| **Safety gates on mutations** | Any tool that triggers real-world side effects (playback) requires `confirmed=True`. Without it, the tool returns a dry-run summary for the agent to present to the user. |

### 1.3 Non-Goals

- **This is not a Plex admin tool.** Library management, user management, and server configuration are out of scope.
- **This is not a transcoding or streaming proxy.** The server does not handle media bytes.
- **This is not multi-server.** One `plex-mcp` instance targets one Plex server. Multi-server orchestration is the agent's responsibility.
- **This does not implement authentication flows.** A valid `PLEX_TOKEN` is a prerequisite; OAuth is not handled here.

### 1.4 Success Criteria

- An LLM agent can discover, inspect, and initiate media playback through natural-language tool calls with no knowledge of Plex internals.
- Error recovery is self-contained: the agent can act on error messages without consulting external documentation.
- Token overhead per tool call stays under 500 tokens in default (concise) mode.

---

## 2. System Context

### 2.1 Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LLM Agent Host                              │
│                                                                     │
│  ┌─────────────────────┐         ┌──────────────────────────────┐  │
│  │   LLM / Claude /    │  tool   │        MCP Client            │  │
│  │   GPT-4 / etc.      │◄───────►│  (Claude Desktop, OpenClaw,  │  │
│  │                     │  calls  │   custom agent framework)    │  │
│  └─────────────────────┘         └──────────────┬───────────────┘  │
│                                                 │                   │
└─────────────────────────────────────────────────┼───────────────────┘
                                                  │ stdio
                                                  │ (JSON-RPC 2.0)
                                   ┌──────────────▼───────────────┐
                                   │         plex-mcp             │
                                   │   (FastMCP / Python)         │
                                   │                              │
                                   │  ┌────────────────────────┐  │
                                   │  │   Tool Handlers        │  │
                                   │  │  search_media          │  │
                                   │  │  browse_library        │  │
                                   │  │  get_media_details     │  │
                                   │  │  now_playing           │  │
                                   │  │  on_deck               │  │
                                   │  │  recently_added        │  │
                                   │  │  play_media ⚠️          │  │
                                   │  │  playback_control ⚠️   │  │
                                   │  └───────────┬────────────┘  │
                                   │              │               │
                                   │  ┌───────────▼────────────┐  │
                                   │  │   PlexClient           │  │
                                   │  │  (connection pool,     │  │
                                   │  │   identity resolver,   │  │
                                   │  │   error normaliser)    │  │
                                   │  └───────────┬────────────┘  │
                                   │              │               │
                                   └──────────────┼───────────────┘
                                                  │ HTTP/HTTPS
                                                  │ X-Plex-Token
                                         ┌────────▼─────────┐
                                         │  Plex Media      │
                                         │  Server          │
                                         │  (local or       │
                                         │   plex.tv relay) │
                                         └────────┬─────────┘
                                                  │
                              ┌───────────────────┼──────────────────┐
                              │                   │                  │
                     ┌────────▼──────┐   ┌────────▼──────┐  ┌───────▼──────┐
                     │  Media Files  │   │  Plex Players │  │  plex.tv     │
                     │  (NAS, local) │   │  (TV, phone,  │  │  (metadata,  │
                     │               │   │   browser)    │  │   auth)      │
                     └───────────────┘   └───────────────┘  └──────────────┘
```

### 2.2 Data Flow — Typical Query

```
Agent: "What's on deck for me?"
  │
  ▼
MCP Client → stdio → plex-mcp
  │
  ▼
on_deck handler
  │
  ├─ PlexClient.connect() [cached connection]
  ├─ server.library.onDeck() → List[Video]
  ├─ format_on_deck_markdown(items, limit)
  └─ return ToolResult(content=markdown_str)
  │
  ▼
MCP Client → Agent
  │
  ▼
Agent response: "Here's what you have on deck:
  🎬 Breaking Bad S2E4 — 23 min remaining..."
```

### 2.3 Data Flow — Mutation with Confirmation Gate

```
Agent: play_media(title="Dune", year=2021, client="Living Room TV", confirmed=False)
  │
  ▼
play_media handler
  │
  ├─ Resolve media: found "Dune (2021)"
  ├─ Resolve client: found "Living Room TV" [Roku]
  ├─ confirmed=False → return DryRunResult
  │
  ▼
"⚠️ Ready to play:
   🎬 Dune (2021) · 2h 35m
   📺 Client: Living Room TV (Roku Ultra)
   
   Call play_media again with confirmed=True to start playback."
  │
  ▼
Agent presents to user → user confirms → Agent calls play_media(..., confirmed=True)
  │
  ▼
server.client("Living Room TV").playMedia(media) → success
```

---

## 3. Tool Catalogue & Schemas

All Pydantic models use `model_config = ConfigDict(strict=False)` to tolerate agent-generated coercion (e.g. int strings).

### 3.1 Shared Types

```python
# src/plex_mcp/schemas/common.py

from typing import Literal, Optional, Annotated
from pydantic import BaseModel, Field, ConfigDict

ResponseFormat = Literal["markdown", "json"]

class PlexMCPResponse(BaseModel):
    """Base wrapper for all tool responses when format='json'."""
    model_config = ConfigDict(strict=False)
    
    success: bool
    tool: str
    data: dict | list | None = None
    message: str | None = None        # human-readable summary
    error: "PlexError | None" = None

class PlexError(BaseModel):
    code: str                          # e.g. "MEDIA_NOT_FOUND"
    message: str                       # actionable description
    suggestions: list[str] = []        # what the agent can try next

class MediaRef(BaseModel):
    """Lightweight resolved media identity, shared across tools."""
    title: str
    year: int | None = None
    media_type: Literal["movie", "show", "season", "episode",
                        "artist", "album", "track"]
    library: str
    rating_key: int                    # internal; not surfaced in markdown output
    thumb_url: str | None = None

class SessionRef(BaseModel):
    """Lightweight session identity."""
    session_id: str
    user: str
    client_name: str
    client_platform: str
    media: MediaRef
    progress_pct: float
    state: Literal["playing", "paused", "buffering", "stopped"]
```

---

### 3.2 `search_media`

**Purpose:** Full-text search across all Plex libraries. The primary discovery tool. Returns concise cards by default.

#### Input Schema

```python
# src/plex_mcp/schemas/inputs.py

class SearchMediaInput(BaseModel):
    model_config = ConfigDict(strict=False)

    query: Annotated[str, Field(
        description="Search term — title, actor name, director, genre keyword, etc.",
        min_length=1,
        max_length=200,
    )]
    media_type: Annotated[
        Literal["movie", "show", "episode", "artist", "album", "track"] | None,
        Field(default=None, description="Restrict to a specific media type. Omit to search all types.")
    ] = None
    library: Annotated[str | None, Field(
        default=None,
        description="Restrict to a named library (e.g. 'Movies', 'TV Shows'). Omit for all libraries."
    )] = None
    limit: Annotated[int, Field(default=10, ge=1, le=50, description="Max results to return.")] = 10
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"
```

#### Output Schema

```python
class SearchResult(BaseModel):
    title: str
    year: int | None
    media_type: str
    library: str
    summary_short: str          # first 120 chars of summary
    rating: float | None        # audience rating 0-10
    duration_min: int | None
    genres: list[str]
    # Only in detailed / JSON mode:
    rating_key: int | None = None
    full_summary: str | None = None

class SearchMediaOutput(PlexMCPResponse):
    tool: str = "search_media"
    data: list[SearchResult] = []
    total_found: int = 0
    query: str = ""
```

#### Markdown Output Example

```markdown
## Search: "breaking bad" (4 results)

**Breaking Bad** (2008) · TV Show · Drama, Crime, Thriller
Rating: ⭐ 9.5 | 5 seasons | Library: TV Shows
> A high school chemistry teacher diagnosed with inoperable cancer...

---

**El Camino: A Breaking Bad Movie** (2019) · Movie · Drama, Crime
Rating: ⭐ 7.3 | 2h 2m | Library: Movies
> Fugitive Jesse Pinkman runs from his past...

---
*Use `get_media_details` for cast, file info, and full metadata.*
```

---

### 3.3 `browse_library`

**Purpose:** Paginated listing of a library's contents with server-side sorting and filtering. Use when the agent needs to enumerate a collection rather than search for a specific title.

#### Input Schema

```python
class BrowseLibraryInput(BaseModel):
    model_config = ConfigDict(strict=False)

    library: Annotated[str, Field(description="Library name exactly as shown in Plex (e.g. 'Movies', '4K TV').")]
    sort: Annotated[str, Field(
        default="titleSort:asc",
        description=(
            "Sort key with direction. Format: 'field:asc' or 'field:desc'. "
            "Common fields: titleSort, addedAt, rating, year, lastViewedAt. "
            "Defaults to title A→Z."
        )
    )] = "titleSort:asc"
    filters: Annotated[dict[str, str | list[str]] | None, Field(
        default=None,
        description=(
            "Server-side filter map. Keys are Plex filter fields. "
            "Examples: {'genre': 'Action'}, {'year>>': '2020'}, {'unwatched': '1'}. "
            "Supports Plex filter operators: >> (gt), << (lt), != (ne)."
        )
    )] = None
    page: Annotated[int, Field(default=1, ge=1, description="1-based page number.")] = 1
    page_size: Annotated[int, Field(default=20, ge=1, le=100)] = 20
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"
```

#### Output Schema

```python
class LibraryItem(BaseModel):
    title: str
    year: int | None
    media_type: str
    rating: float | None
    duration_min: int | None
    watched: bool | None           # None for shows (use progress instead)
    added_at: str                  # ISO date string

class BrowseLibraryOutput(PlexMCPResponse):
    tool: str = "browse_library"
    data: list[LibraryItem] = []
    library: str = ""
    total_items: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
```

#### Markdown Output Example

```markdown
## Movies · Action · Page 1 of 12 (230 total)
*Sorted by: Title A→Z*

| Title | Year | Rating | Duration | Watched |
|-------|------|--------|----------|---------|
| Aliens | 1986 | ⭐ 8.4 | 2h 17m | ✅ |
| Avengers: Endgame | 2019 | ⭐ 8.4 | 3h 1m | ✅ |
| Die Hard | 1988 | ⭐ 8.2 | 2h 12m | ✅ |
| Mad Max: Fury Road | 2015 | ⭐ 8.1 | 2h 0m | ❌ |

*Page 1 of 12 · Use `page=2` to continue · Use `get_media_details` for full info*
```

---

### 3.4 `get_media_details`

**Purpose:** Rich metadata for a single piece of media. Default mode returns a concise card; `detailed=True` adds cast, crew, file info, and availability.

#### Input Schema

```python
class GetMediaDetailsInput(BaseModel):
    model_config = ConfigDict(strict=False)

    title: Annotated[str, Field(description="Title of the movie, show, episode, or album.")]
    year: Annotated[int | None, Field(
        default=None,
        description="Release year to disambiguate titles. Strongly recommended for movies."
    )] = None
    media_type: Annotated[
        Literal["movie", "show", "episode", "artist", "album", "track"] | None,
        Field(default=None, description="Restrict resolution to a media type.")
    ] = None
    season: Annotated[int | None, Field(default=None, description="Season number (for episodes).")] = None
    episode: Annotated[int | None, Field(default=None, description="Episode number within season.")] = None
    detailed: Annotated[bool, Field(
        default=False,
        description="Set True for full metadata: cast, crew, file info, chapter list."
    )] = False
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"
```

#### Output Schema

```python
class CastMember(BaseModel):
    name: str
    role: str                    # character name or job title
    is_director: bool = False
    is_writer: bool = False

class MediaFile(BaseModel):
    filename: str
    size_gb: float
    container: str               # mkv, mp4, etc.
    video_codec: str
    resolution: str              # "1080p", "4K", "720p"
    audio_codec: str
    audio_channels: str          # "5.1", "7.1", "Stereo"
    bitrate_mbps: float

class MediaDetailsOutput(PlexMCPResponse):
    tool: str = "get_media_details"
    data: "MediaDetailsData | None" = None

class MediaDetailsData(BaseModel):
    # Always present
    title: str
    year: int | None
    media_type: str
    library: str
    summary: str
    rating_audience: float | None
    rating_critics: float | None  # Rotten Tomatoes / Metacritic if available
    content_rating: str | None    # "PG-13", "TV-MA", etc.
    genres: list[str]
    duration_min: int | None
    studio: str | None
    originally_available: str | None   # ISO date
    watched: bool | None
    watch_progress_pct: float | None
    # Detailed only (requires detailed=True)
    cast: list[CastMember] | None = None
    files: list[MediaFile] | None = None
    chapter_count: int | None = None
    labels: list[str] | None = None    # Plex labels/collections
    collections: list[str] | None = None
    # Show-specific
    season_count: int | None = None
    episode_count: int | None = None
    # Episode-specific
    season_number: int | None = None
    episode_number: int | None = None
    show_title: str | None = None
```

#### Markdown Output Example (default)

```markdown
## 🎬 Dune: Part Two (2024)

**Genre:** Sci-Fi, Adventure, Drama  
**Rating:** ⭐ 8.5 (audience) · 🍅 91% (critics)  
**Duration:** 2h 46m · Rated PG-13  
**Studio:** Legendary Entertainment  
**Released:** 2024-03-01  
**Status:** ✅ Watched

> Paul Atreides unites with Chani and the Fremen while on a path of revenge
> against the conspirators who destroyed his family...

*Use `detailed=True` for cast, crew, and file info.*
```

#### Markdown Output Example (detailed=True)

```markdown
## 🎬 Dune: Part Two (2024)
... [concise card above] ...

### Cast & Crew
**Director:** Denis Villeneuve  
**Writer:** Denis Villeneuve, Jon Spaihts  
| Actor | Role |
|-------|------|
| Timothée Chalamet | Paul Atreides |
| Zendaya | Chani |
| Rebecca Ferguson | Lady Jessica |

### File Info
| Property | Value |
|----------|-------|
| File | Dune.Part.Two.2024.2160p.UHD.BluRay.mkv |
| Size | 58.2 GB |
| Video | HEVC · 4K · HDR |
| Audio | TrueHD 7.1 Atmos |
| Bitrate | 55.1 Mbps |
```

---

### 3.5 `now_playing`

**Purpose:** Returns all active Plex sessions — who is watching what, on which device, and how far through.

#### Input Schema

```python
class NowPlayingInput(BaseModel):
    model_config = ConfigDict(strict=False)
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"
```

#### Output Schema

```python
class NowPlayingSession(BaseModel):
    session_id: str
    user: str
    client_name: str
    client_platform: str
    client_product: str
    media_title: str
    media_type: str
    show_title: str | None         # for episodes
    season_episode: str | None     # "S02E04"
    duration_min: int
    progress_min: int
    progress_pct: float
    state: Literal["playing", "paused", "buffering"]
    transcode_status: Literal["direct_play", "direct_stream", "transcode"]
    transcode_reason: str | None   # e.g. "audio codec not supported"
    bandwidth_kbps: int | None

class NowPlayingOutput(PlexMCPResponse):
    tool: str = "now_playing"
    data: list[NowPlayingSession] = []
    session_count: int = 0
```

#### Markdown Output Example

```markdown
## 📺 Now Playing (2 active sessions)

### 1. alice · Living Room TV (Roku Ultra)
**Breaking Bad** S02E04 — "Down"  
⏱ 18m / 47m (38%) · ▶ Playing · Direct Play

### 2. bob · iPhone (Plex for iOS)
**The Matrix** (1999)  
⏱ 52m / 136m (38%) · ⏸ Paused · Transcoding (video codec)

---
*Use `playback_control` to pause, resume, or stop a session.*
```

---

### 3.6 `on_deck`

**Purpose:** Returns the "On Deck" list — partially-watched items and next episodes ready to continue. Equivalent to Plex's Home → On Deck row.

#### Input Schema

```python
class OnDeckInput(BaseModel):
    model_config = ConfigDict(strict=False)
    
    limit: Annotated[int, Field(default=10, ge=1, le=50)] = 10
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"
```

#### Output Schema

```python
class OnDeckItem(BaseModel):
    media_title: str
    media_type: str
    show_title: str | None
    season_episode: str | None       # "S03E01" for next episodes
    progress_pct: float | None       # None for "next up" (0% watched)
    remaining_min: int | None
    thumb_url: str | None
    library: str

class OnDeckOutput(PlexMCPResponse):
    tool: str = "on_deck"
    data: list[OnDeckItem] = []
```

#### Markdown Output Example

```markdown
## ▶ On Deck (8 items)

1. **Breaking Bad** S02E05 — "Breakage" · TV Shows
   *(Next up — 0% watched)*

2. **Oppenheimer** (2023) · Movies  
   ⏱ 1h 12m remaining (41% watched)

3. **Shogun** S01E04 · TV Shows  
   ⏱ 32m remaining (28% watched)
```

---

### 3.7 `recently_added`

**Purpose:** Lists recently added media across all or specified libraries, with date filtering.

#### Input Schema

```python
class RecentlyAddedInput(BaseModel):
    model_config = ConfigDict(strict=False)
    
    library: Annotated[str | None, Field(
        default=None,
        description="Filter to a specific library name. Omit for all libraries."
    )] = None
    days: Annotated[int, Field(
        default=7,
        ge=1,
        le=365,
        description="Only show items added within the last N days."
    )] = 7
    limit: Annotated[int, Field(default=20, ge=1, le=100)] = 20
    media_type: Annotated[
        Literal["movie", "show", "episode", "album", "track"] | None,
        Field(default=None, description="Filter by media type.")
    ] = None
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"
```

#### Output Schema

```python
class RecentlyAddedItem(BaseModel):
    title: str
    year: int | None
    media_type: str
    library: str
    added_at: str                    # ISO datetime string
    added_human: str                 # "2 days ago", "Today"
    duration_min: int | None
    summary_short: str | None
    # Show-specific
    show_title: str | None
    season_episode: str | None

class RecentlyAddedOutput(PlexMCPResponse):
    tool: str = "recently_added"
    data: list[RecentlyAddedItem] = []
    cutoff_date: str = ""            # ISO date of oldest item shown
```

#### Markdown Output Example

```markdown
## 🆕 Recently Added (last 7 days · 14 items)

**Today**
- 🎬 **Dune: Part Two** (2024) · Movies · 2h 46m
  > Paul Atreides unites with Chani and the Fremen...

**Yesterday**
- 📺 **Shogun** S01E01-E04 · TV Shows

**3 days ago**
- 🎵 **Cowboy Carter** — Beyoncé · Music
- 🎬 **Civil War** (2024) · Movies · 1h 49m
```

---

### 3.8 `play_media`

**Purpose:** Start playback of a specific media item on a named Plex player. **This is a mutating operation** — it triggers real-world playback. Protected by a confirmation gate.

#### Input Schema

```python
class PlayMediaInput(BaseModel):
    model_config = ConfigDict(strict=False)
    
    title: Annotated[str, Field(description="Title of the movie, show, or track to play.")]
    year: Annotated[int | None, Field(
        default=None,
        description="Release year to disambiguate. Strongly recommended for movies."
    )] = None
    client: Annotated[str, Field(
        description=(
            "Name of the Plex player to play on, exactly as shown in Plex. "
            "Use now_playing or list_clients to see available players."
        )
    )]
    media_type: Annotated[
        Literal["movie", "show", "episode", "track"] | None,
        Field(default=None, description="Restrict media resolution to a type.")
    ] = None
    season: Annotated[int | None, Field(
        default=None,
        description="Season number (for TV shows — play a specific season's first episode)."
    )] = None
    episode: Annotated[int | None, Field(
        default=None,
        description="Episode number within season (requires season to be set)."
    )] = None
    offset_ms: Annotated[int | None, Field(
        default=None,
        description="Start playback at this millisecond offset. 0 = from beginning."
    )] = None
    confirmed: Annotated[bool, Field(
        default=False,
        description=(
            "MUST be True to actually start playback. "
            "Set False (default) to get a dry-run preview first. "
            "Always show the dry-run to the user before confirming."
        )
    )] = False
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"
```

#### Output Schema

```python
class PlayMediaOutput(PlexMCPResponse):
    tool: str = "play_media"
    data: "PlayMediaData | None" = None

class PlayMediaData(BaseModel):
    dry_run: bool                    # True = preview, False = actually started
    media_title: str
    media_type: str
    season_episode: str | None
    duration_min: int | None
    client_name: str
    client_platform: str
    offset_ms: int | None
    started_at: str | None           # ISO datetime, only when dry_run=False
```

#### Markdown Output Example (dry-run / confirmed=False)

```markdown
## ⚠️ Playback Preview (not started)

**Ready to play:**
🎬 **Dune: Part Two** (2024) · 2h 46m  
📺 **Client:** Living Room TV (Roku Ultra)  
⏱ **Starting at:** Beginning

**To confirm playback, call:**
`play_media(title="Dune: Part Two", year=2024, client="Living Room TV", confirmed=True)`
```

#### Markdown Output Example (confirmed=True)

```markdown
## ✅ Playback Started

🎬 **Dune: Part Two** (2024)  
📺 **Playing on:** Living Room TV (Roku Ultra)  
🕐 **Started at:** 17:23 UTC
```

---

### 3.9 `playback_control`

**Purpose:** Control an active playback session — pause, resume, stop, or seek. Also a mutating operation requiring `confirmed=True`.

#### Input Schema

```python
class PlaybackControlInput(BaseModel):
    model_config = ConfigDict(strict=False)
    
    action: Annotated[
        Literal["pause", "resume", "stop", "skip_next", "skip_prev", "seek"],
        Field(description="Playback action to perform.")
    ]
    client: Annotated[str | None, Field(
        default=None,
        description=(
            "Name of the Plex player to control. "
            "If omitted and exactly one session is active, that session is used. "
            "If multiple sessions are active, this field is required."
        )
    )] = None
    seek_offset_ms: Annotated[int | None, Field(
        default=None,
        description="For action='seek': target position in milliseconds from start.",
        ge=0
    )] = None
    confirmed: Annotated[bool, Field(
        default=False,
        description=(
            "MUST be True to apply the action. "
            "Set False (default) to preview what will happen."
        )
    )] = False
    format: Annotated[ResponseFormat, Field(default="markdown")] = "markdown"
```

#### Output Schema

```python
class PlaybackControlOutput(PlexMCPResponse):
    tool: str = "playback_control"
    data: "PlaybackControlData | None" = None

class PlaybackControlData(BaseModel):
    dry_run: bool
    action: str
    client_name: str
    client_platform: str
    media_title: str
    session_state_before: str
    session_state_after: str | None   # None for dry_run
    seek_position_min: float | None   # for seek actions
```

#### Markdown Output Example (dry-run)

```markdown
## ⚠️ Playback Control Preview (not applied)

**Action:** Pause  
📺 **Client:** Living Room TV (Roku Ultra)  
🎬 **Currently playing:** The Matrix (1999) at 52m / 136m

**To apply, call:**
`playback_control(action="pause", client="Living Room TV", confirmed=True)`
```

---

## 4. Error Handling Strategy

### 4.1 Error Taxonomy

All errors are normalised into `PlexError` objects with structured codes, actionable messages, and suggestions. The goal: an agent that receives an error should be able to self-recover in the next turn.

| Error Code | Trigger | Agent-Actionable Suggestion |
|---|---|---|
| `CONNECTION_FAILED` | Cannot reach Plex server | Check `PLEX_SERVER` env var; verify server is online |
| `AUTH_FAILED` | Invalid or expired token | Refresh `PLEX_TOKEN`; check plex.tv account |
| `LIBRARY_NOT_FOUND` | Library name not found | Call `browse_library` with no args to list libraries |
| `MEDIA_NOT_FOUND` | Title resolution failed | Try `search_media` with the title; check spelling |
| `MEDIA_AMBIGUOUS` | Multiple matches found | Provide `year` or `media_type` to disambiguate |
| `CLIENT_NOT_FOUND` | Player name not found | Use `now_playing` to list active clients |
| `CLIENT_OFFLINE` | Player not reachable | Check device is on and Plex app is open |
| `SESSION_NOT_FOUND` | Session ID invalid | Use `now_playing` to get current session list |
| `NO_ACTIVE_SESSION` | Control with no playback | Nothing is playing; use `play_media` to start |
| `MULTIPLE_SESSIONS` | Ambiguous control target | Specify `client` parameter |
| `PLAYBACK_ERROR` | Plex API rejected playback | Check client compatibility; try direct play |
| `CONFIRMATION_REQUIRED` | Mutation without `confirmed=True` | Show dry-run to user; re-call with `confirmed=True` |
| `INVALID_FILTER` | Bad browse filter key | Refer to Plex filter documentation in SAD |
| `RATE_LIMITED` | Too many API calls | Wait 1s and retry; reduce polling frequency |
| `UNKNOWN` | Unexpected Plex API error | Include raw error details for debugging |

### 4.2 Error Message Format

```python
# src/plex_mcp/errors.py

class PlexMCPError(Exception):
    """All tool errors are instances of this class."""
    
    def __init__(
        self,
        code: str,
        message: str,
        suggestions: list[str] | None = None,
        raw: Exception | None = None,
    ):
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
```

### 4.3 Error Construction Examples

```python
# Good — actionable, specific
raise PlexMCPError(
    code="MEDIA_NOT_FOUND",
    message='No media found matching "Dune" (2019) in your libraries.',
    suggestions=[
        'Try `search_media(query="Dune")` to see all Dune-related results.',
        'The movie may be "Dune (2021)" — specify `year=2021`.',
        'Check if the movie is in a library you have access to.',
    ]
)

# Good — disambiguates for the agent
raise PlexMCPError(
    code="MEDIA_AMBIGUOUS",
    message='Found 3 items matching "The Office": US (2005), UK (2001), Special (2003).',
    suggestions=[
        'Specify `year=2005` for the US version.',
        'Use `search_media(query="The Office")` to see all versions.',
    ]
)
```

### 4.4 Error Rendering

In `format="markdown"` mode, errors are returned as readable Markdown (not raised as MCP protocol errors) so the agent sees and can act on them. The response will have `success=False` in JSON mode.

Tool handlers wrap all logic in a try/except and convert to `PlexMCPError` at the boundary:

```python
# src/plex_mcp/tools/base.py

async def safe_tool_call(handler_fn, input_model, format: str) -> str:
    try:
        return await handler_fn(input_model)
    except PlexMCPError as e:
        if format == "json":
            return PlexMCPResponse(
                success=False,
                tool=handler_fn.__name__,
                error=e.to_plex_error()
            ).model_dump_json(indent=2)
        return e.to_markdown()
    except plexapi.exceptions.Unauthorized:
        return _auth_error(format)
    except plexapi.exceptions.NotFound as e:
        return _not_found_error(str(e), format)
    except Exception as e:
        return _unknown_error(e, format)
```

### 4.5 Resolution Strategy for Human-Readable Identifiers

A key design goal is accepting titles rather than rating keys. The resolution pipeline:

```
User title input
    │
    ▼
1. Exact title match (case-insensitive)
    │ no match
    ▼
2. Exact match + year filter
    │ no match
    ▼
3. Fuzzy match via server.search() (top 5)
    │ 0 results → MEDIA_NOT_FOUND with suggestions
    │ 1 result  → use it (log the resolution)
    │ 2+ results → MEDIA_AMBIGUOUS with candidate list
    ▼
4. If media_type provided: filter candidates by type
    │
    ▼
Resolved MediaRef → cache rating_key for session
```

---

## 5. Response Format Design

### 5.1 Philosophy

| Principle | Implementation |
|---|---|
| **Concise by default** | Tool responses target ≤300 tokens in default mode |
| **Progressive detail** | `detailed=True` flag unlocks full metadata on any tool |
| **Scannable structure** | Markdown headings, bold labels, tables for lists |
| **Agent-legible hints** | Every response ends with a hint about what to call next |
| **JSON for pipelines** | `format="json"` returns typed Pydantic output for downstream processing |

### 5.2 Markdown Design Conventions

```
## [Emoji] [Tool Name Result]           ← H2 header always present
                                         ← blank line
[Summary / key facts in bold pairs]     ← name: value or **Label:** content
                                         ← blank line
[Table or list for multiple items]      ← prefer tables for ≥3 items
                                         ← blank line
---                                      ← hr between items
                                         ← blank line
*[Navigation hint or next-step hint]*   ← italics, end of response
```

### 5.3 Emoji Vocabulary

Consistent emoji prefixes help agents (and humans) scan:

| Context | Emoji |
|---|---|
| Movie | 🎬 |
| TV Show / Episode | 📺 |
| Music | 🎵 |
| Playing | ▶ |
| Paused | ⏸ |
| Rating (audience) | ⭐ |
| Critics rating | 🍅 |
| Warning / dry-run | ⚠️ |
| Success | ✅ |
| Error | ❌ |
| New / recently added | 🆕 |
| File/technical | 📁 |

### 5.4 JSON Mode Contract

In `format="json"`, every tool returns a valid JSON object conforming to the `PlexMCPResponse` base model. The top-level structure is always:

```json
{
  "success": true,
  "tool": "search_media",
  "message": "Found 4 results for 'breaking bad'",
  "data": [ ... ],
  "error": null
}
```

Error case:
```json
{
  "success": false,
  "tool": "play_media",
  "message": null,
  "data": null,
  "error": {
    "code": "MEDIA_NOT_FOUND",
    "message": "No media found matching \"Dune\" (2019).",
    "suggestions": [
      "Try search_media(query=\"Dune\") to see all results.",
      "Specify year=2021 for the 2021 release."
    ]
  }
}
```

### 5.5 Token Budget Targets

| Tool | Default (tokens) | detailed=True (tokens) |
|---|---|---|
| `search_media` (10 results) | ~200 | ~400 |
| `browse_library` (20 items) | ~300 | N/A |
| `get_media_details` | ~150 | ~350 |
| `now_playing` (3 sessions) | ~150 | N/A |
| `on_deck` (10 items) | ~200 | N/A |
| `recently_added` (20 items) | ~300 | N/A |
| `play_media` (dry-run) | ~100 | N/A |
| `playback_control` (dry-run) | ~80 | N/A |

---

## 6. Security Considerations

### 6.1 Threat Model

`plex-mcp` runs as a local subprocess of an MCP client. The threat model assumes:

- The LLM agent is **untrusted but sandboxed** — it can only do what the tool surface allows.
- The Plex token grants **owner-level access** by default. Scope is not reducible via this MCP (Plex's ACL model doesn't support fine-grained per-app tokens).
- The primary risk is **unintended playback** (annoyance, not data breach): an agent starting media on a TV without user knowledge.

### 6.2 Mitigations

| Risk | Mitigation |
|---|---|
| **Accidental playback** | All mutating tools (`play_media`, `playback_control`) require `confirmed=True`. Default returns a dry-run. |
| **Token exposure in logs** | `PLEX_TOKEN` is read from env var only. Never logged, never included in error messages or tool output. |
| **Server URL leakage** | `PLEX_SERVER` is used only for connection. Not included in tool output. |
| **Prompt injection via media metadata** | Summaries and titles are treated as data, not instructions. FastMCP output is plain text/JSON. |
| **Excessive API calls** | Connection is pooled (singleton). No polling or background threads. |
| **Arbitrary library access** | No tool provides filesystem access, server config, or user management. |
| **Log injection** | All metadata values are sanitised before inclusion in log strings. |

### 6.3 Confirmation Gate Implementation

```python
# src/plex_mcp/tools/playback.py

async def play_media(input: PlayMediaInput) -> str:
    media = await resolve_media(input.title, input.year, input.media_type)
    client = await resolve_client(input.client)
    
    # Build dry-run response regardless
    dry_run = PlayMediaData(
        dry_run=True,
        media_title=media.title,
        ...
    )
    
    if not input.confirmed:
        # Always return dry-run — never side-effect without confirmation
        return format_dry_run(dry_run, input.format)
    
    # Confirmed: execute
    plex_client = _get_plex_client()
    plex_client.playMedia(media._raw)
    
    return format_success(
        PlayMediaData(dry_run=False, started_at=utcnow(), **dry_run.model_dump()),
        input.format
    )
```

### 6.4 Environment Variable Handling

```python
# src/plex_mcp/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    plex_token: str = Field(..., description="Plex authentication token (X-Plex-Token)")
    plex_server: str = Field(..., description="Plex server base URL, e.g. http://192.168.1.10:32400")
    plex_connect_timeout: int = Field(default=10, description="Connection timeout in seconds")
    plex_request_timeout: int = Field(default=30, description="Per-request timeout in seconds")
    log_level: str = Field(default="WARNING")
    
    # Never expose these in repr/str
    model_config = SettingsConfigDict(
        secrets_dir="/run/secrets",   # Docker secrets support
    )
    
    def __repr__(self) -> str:
        return f"Settings(plex_server={self.plex_server!r}, log_level={self.log_level!r})"
```

### 6.5 Logging Policy

- Log level defaults to `WARNING` — production-safe.
- `DEBUG` logs tool inputs/outputs (useful for development, not for prod).
- `PLEX_TOKEN` is **never** logged at any level — masked at settings load time.
- Media titles in logs are truncated to 100 chars to prevent log flooding.

---

## 7. Dependencies & Project Structure

### 7.1 Dependencies

```toml
# pyproject.toml

[project]
name = "plex-mcp"
version = "0.1.0"
description = "MCP server for Plex Media Server"
requires-python = ">=3.11"
license = { text = "MIT" }

dependencies = [
    # MCP framework
    "fastmcp>=2.0.0",          # FastMCP: tool registration, stdio transport, annotations
    
    # Plex API
    "plexapi>=4.15.0",         # python-plexapi: mature, full Plex HTTP API wrapper
    
    # Data modelling
    "pydantic>=2.7.0",         # Schema validation, serialisation
    "pydantic-settings>=2.3.0",# Env var / .env config loading
    
    # Utilities
    "python-dateutil>=2.9.0",  # Human-readable date formatting ("2 days ago")
    "anyio>=4.4.0",            # Async I/O compatibility layer (FastMCP dependency)
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.14.0",
    "httpx>=0.27.0",           # For mocking plexapi HTTP calls
    "ruff>=0.4.0",             # Linting + formatting
    "mypy>=1.10.0",            # Static type checking
    "types-python-dateutil",
]

[project.scripts]
plex-mcp = "plex_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### 7.2 Project Structure

```
plex-mcp/
│
├── SAD.md                          ← This document
├── README.md                       ← Quick-start guide
├── pyproject.toml                  ← Package metadata + dependencies
├── .env.example                    ← Template for environment variables
├── .gitignore
│
├── src/
│   └── plex_mcp/
│       ├── __init__.py
│       │
│       ├── server.py               ← FastMCP app entry point
│       │                             Tool registration + annotations
│       │                             main() for stdio entry point
│       │
│       ├── config.py               ← Pydantic Settings (env vars)
│       │
│       ├── client.py               ← PlexServer connection singleton
│       │                             connect(), get_server(), health_check()
│       │                             Media resolution helpers
│       │
│       ├── errors.py               ← PlexMCPError + all error codes
│       │                             safe_tool_call() decorator
│       │
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── common.py           ← PlexMCPResponse, PlexError, MediaRef, SessionRef
│       │   ├── inputs.py           ← All *Input models (8 tools)
│       │   └── outputs.py          ← All *Output + data models (8 tools)
│       │
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── search.py           ← search_media handler
│       │   ├── browse.py           ← browse_library handler
│       │   ├── details.py          ← get_media_details handler
│       │   ├── sessions.py         ← now_playing handler
│       │   ├── deck.py             ← on_deck + recently_added handlers
│       │   └── playback.py         ← play_media + playback_control handlers
│       │
│       └── formatters/
│           ├── __init__.py
│           ├── markdown.py         ← All markdown rendering functions
│           │                         format_search_results()
│           │                         format_library_list()
│           │                         format_media_details()
│           │                         format_sessions()
│           │                         format_on_deck()
│           │                         format_recently_added()
│           │                         format_dry_run()
│           │                         format_playback_success()
│           └── duration.py         ← Shared duration/date formatting utilities
│                                     min_to_human("2h 35m"), relative_date()
│
└── tests/
    ├── __init__.py
    ├── conftest.py                 ← Fixtures: mock PlexServer, fake media objects
    ├── test_search.py
    ├── test_browse.py
    ├── test_details.py
    ├── test_sessions.py
    ├── test_deck.py
    ├── test_playback.py
    └── test_formatters.py
```

### 7.3 Server Entry Point

```python
# src/plex_mcp/server.py

from fastmcp import FastMCP
from plex_mcp.config import Settings
from plex_mcp.tools import search, browse, details, sessions, deck, playback

settings = Settings()
mcp = FastMCP(
    name="plex-mcp",
    version="0.1.0",
    description="Control and query your Plex Media Server from an LLM agent.",
)

# Register tools with annotations (see Section 9)
mcp.add_tool(
    search.search_media,
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
mcp.add_tool(
    browse.browse_library,
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
mcp.add_tool(
    details.get_media_details,
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
mcp.add_tool(
    sessions.now_playing,
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
mcp.add_tool(
    deck.on_deck,
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
mcp.add_tool(
    deck.recently_added,
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
mcp.add_tool(
    playback.play_media,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,      # reversible — stop/pause can undo it
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
mcp.add_tool(
    playback.playback_control,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,        # pause/pause = same result
        "openWorldHint": False,
    },
)

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

---

## 8. Configuration

### 8.1 Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `PLEX_TOKEN` | ✅ | — | Plex authentication token. Obtain from: Account → XML → `X-Plex-Token` attribute, or via `python-plexapi`'s `MyPlexAccount` login flow. |
| `PLEX_SERVER` | ✅ | — | Base URL of the Plex server. Local: `http://192.168.1.10:32400`. Remote: `https://your-domain:32400`. |
| `PLEX_CONNECT_TIMEOUT` | ❌ | `10` | TCP connection timeout in seconds. |
| `PLEX_REQUEST_TIMEOUT` | ❌ | `30` | Per-request timeout in seconds. Increase for large library scans. |
| `PLEX_MCP_LOG_LEVEL` | ❌ | `WARNING` | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

### 8.2 `.env.example`

```dotenv
# .env.example — Copy to .env and fill in your values

# Required
PLEX_TOKEN=your_plex_token_here
PLEX_SERVER=http://192.168.1.10:32400

# Optional
PLEX_CONNECT_TIMEOUT=10
PLEX_REQUEST_TIMEOUT=30
PLEX_MCP_LOG_LEVEL=WARNING
```

### 8.3 MCP Client Configuration

#### Claude Desktop (`~/.config/claude/claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "plex": {
      "command": "uvx",
      "args": ["plex-mcp"],
      "env": {
        "PLEX_TOKEN": "your_token_here",
        "PLEX_SERVER": "http://192.168.1.10:32400"
      }
    }
  }
}
```

#### OpenClaw / Custom Host

```json
{
  "servers": [
    {
      "name": "plex-mcp",
      "transport": "stdio",
      "command": ["python", "-m", "plex_mcp.server"],
      "env": {
        "PLEX_TOKEN": "${PLEX_TOKEN}",
        "PLEX_SERVER": "${PLEX_SERVER}"
      }
    }
  ]
}
```

### 8.4 PlexServer Connection Singleton

```python
# src/plex_mcp/client.py

from functools import lru_cache
import plexapi.server
import plexapi.exceptions
from plex_mcp.config import Settings
from plex_mcp.errors import PlexMCPError

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

_server: plexapi.server.PlexServer | None = None

def get_server() -> plexapi.server.PlexServer:
    """Return a cached PlexServer connection, connecting on first call."""
    global _server
    if _server is None:
        _server = _connect()
    return _server

def _connect() -> plexapi.server.PlexServer:
    s = get_settings()
    try:
        server = plexapi.server.PlexServer(
            baseurl=s.plex_server,
            token=s.plex_token,
            timeout=s.plex_connect_timeout,
        )
        return server
    except plexapi.exceptions.Unauthorized:
        raise PlexMCPError(
            code="AUTH_FAILED",
            message="Plex authentication failed. Your PLEX_TOKEN may be invalid or expired.",
            suggestions=[
                "Verify PLEX_TOKEN in your environment.",
                "Generate a new token at: https://support.plex.tv/articles/204059436",
            ]
        )
    except Exception as e:
        raise PlexMCPError(
            code="CONNECTION_FAILED",
            message=f"Cannot connect to Plex at {s.plex_server}: {type(e).__name__}",
            suggestions=[
                f"Verify PLEX_SERVER={s.plex_server!r} is reachable.",
                "Check that Plex Media Server is running.",
                "For remote servers, check firewall rules.",
            ],
            raw=e,
        )
```

---

## 9. Tool Annotations

MCP tool annotations are hints to the client about tool behaviour. They do **not** enforce behaviour — that's the tool's own responsibility.

### 9.1 Annotation Reference

| Annotation | Type | Meaning |
|---|---|---|
| `readOnlyHint` | bool | Tool does not modify external state |
| `destructiveHint` | bool | Tool may cause irreversible data loss |
| `idempotentHint` | bool | Repeated identical calls have same effect |
| `openWorldHint` | bool | Tool interacts with systems outside the MCP server (internet) |

### 9.2 Tool Annotation Table

| Tool | readOnlyHint | destructiveHint | idempotentHint | openWorldHint | Notes |
|---|---|---|---|---|---|
| `search_media` | ✅ `true` | ✅ `false` | ✅ `true` | ❌ `false` | Pure read from local Plex instance |
| `browse_library` | ✅ `true` | ✅ `false` | ✅ `true` | ❌ `false` | Pure read; pagination is deterministic |
| `get_media_details` | ✅ `true` | ✅ `false` | ✅ `true` | ❌ `false` | Pure read |
| `now_playing` | ✅ `true` | ✅ `false` | ❌ `false` | ❌ `false` | Read-only but not idempotent (sessions change) |
| `on_deck` | ✅ `true` | ✅ `false` | ❌ `false` | ❌ `false` | Read-only; deck changes as watching progresses |
| `recently_added` | ✅ `true` | ✅ `false` | ❌ `false` | ❌ `false` | Read-only; library changes over time |
| `play_media` | ❌ `false` | ❌ `false` | ❌ `false` | ❌ `false` | Mutating; reversible via `playback_control(stop)` |
| `playback_control` | ❌ `false` | ❌ `false` | ✅ `true`* | ❌ `false` | Mutating; pause/pause = idempotent; stop/stop = idempotent |

*`idempotentHint=true` for `playback_control` is a reasonable simplification: applying `pause` twice leaves the session paused. `seek` is not strictly idempotent (timing changes) but the annotation applies to the common case.

### 9.3 FastMCP Annotation Implementation

```python
# In server.py — shown inline for clarity

@mcp.tool(
    name="search_media",
    description=(
        "Search across all Plex libraries by title, actor, director, or keyword. "
        "Returns concise result cards. Use get_media_details for full metadata."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def search_media(
    query: str,
    media_type: Literal["movie", "show", "episode", "artist", "album", "track"] | None = None,
    library: str | None = None,
    limit: int = 10,
    format: Literal["markdown", "json"] = "markdown",
) -> str:
    ...

@mcp.tool(
    name="play_media",
    description=(
        "Start playback of a movie, episode, or track on a named Plex player. "
        "⚠️ ALWAYS call without confirmed=True first to show the user a preview. "
        "Only pass confirmed=True after the user explicitly approves."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,   # Reversible: user can stop playback
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def play_media(
    title: str,
    client: str,
    year: int | None = None,
    media_type: Literal["movie", "show", "episode", "track"] | None = None,
    season: int | None = None,
    episode: int | None = None,
    offset_ms: int | None = None,
    confirmed: bool = False,
    format: Literal["markdown", "json"] = "markdown",
) -> str:
    ...
```

---

## Appendix A: Plex Filter Field Reference

Common filter fields usable in `browse_library`:

| Field | Operator Support | Example Value |
|---|---|---|
| `genre` | `=`, `!=` | `"Action"` |
| `year` | `=`, `>>`, `<<` | `"2020"` |
| `rating` | `>>`, `<<` | `"7"` |
| `contentRating` | `=` | `"PG-13"` |
| `unwatched` | `=` | `"1"` |
| `resolution` | `=` | `"4k"` |
| `studio` | `=` | `"HBO"` |
| `addedAt` | `>>`, `<<` | ISO date string |
| `lastViewedAt` | `>>`, `<<` | ISO date string |

Operators: `>>` = greater than, `<<` = less than, `!=` = not equal.

---

## Appendix B: Common Agent Workflows

### "What should I watch tonight?"
```
on_deck(limit=5) → browse_library(library="Movies", sort="rating:desc", page=1)
```

### "Play the next episode of Shogun"
```
on_deck() → identify "Shogun" next episode → 
play_media(title="Shogun", season=1, episode=5, client="Living Room TV", confirmed=False) →
[show user preview] →
play_media(..., confirmed=True)
```

### "What's everyone watching right now?"
```
now_playing()
```

### "Find all 4K action movies I haven't seen"
```
browse_library(
  library="Movies",
  filters={"resolution": "4k", "genre": "Action", "unwatched": "1"},
  sort="rating:desc"
)
```

### "Pause whatever's playing in the living room"
```
now_playing() → identify Living Room TV session →
playback_control(action="pause", client="Living Room TV", confirmed=False) →
playback_control(action="pause", client="Living Room TV", confirmed=True)
```

---

## Appendix C: Version History

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-02-18 | Initial draft |
