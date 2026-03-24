# Implementation Tasks — `plex-mcp`

**Version:** 1.0  
**Date:** 2026-02-18  
**Methodology:** TDD — write the test first, implement to pass, verify  
**Reference:** [SAD.md](./SAD.md) · [FLOWS.md](./FLOWS.md)

---

## Reading This Document

Each task follows the same rhythm:
1. **Test first** — write a failing test that describes the desired behaviour
2. **Implement** — write the minimal code that makes the test pass
3. **Verify** — run the test suite; confirm only new tests were added

Every bunch is self-contained: after completing all tasks in a bunch, `pytest` must pass cleanly.

> **Dependency order:** Bunch 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11  
> Never skip a bunch; each one builds the foundation for the next.

---

## Bunch 1: Project Scaffold + Config

*Goal: runnable project skeleton with working configuration loading.*

### Task 1.1: Initialize Project Structure

**Test first:**
```python
# tests/test_config.py
def test_package_importable():
    import plex_mcp  # noqa: F401

def test_submodules_importable():
    from plex_mcp import config, client, errors  # noqa: F401
    from plex_mcp.schemas import common, inputs, outputs  # noqa: F401
    from plex_mcp.tools import search, browse, details, sessions, deck, playback  # noqa: F401
    from plex_mcp.formatters import markdown, duration  # noqa: F401
```

**Implement:**
- Create `pyproject.toml` exactly as specified in SAD §7.1 (hatchling build, all deps, ruff/mypy config, `asyncio_mode = "auto"`)
- Create directory tree:
  ```
  src/plex_mcp/__init__.py
  src/plex_mcp/config.py          # stub: pass
  src/plex_mcp/client.py          # stub: pass
  src/plex_mcp/errors.py          # stub: pass
  src/plex_mcp/server.py          # stub: pass
  src/plex_mcp/schemas/__init__.py
  src/plex_mcp/schemas/common.py  # stub: pass
  src/plex_mcp/schemas/inputs.py  # stub: pass
  src/plex_mcp/schemas/outputs.py # stub: pass
  src/plex_mcp/tools/__init__.py
  src/plex_mcp/tools/search.py    # stub: pass
  src/plex_mcp/tools/browse.py    # stub: pass
  src/plex_mcp/tools/details.py   # stub: pass
  src/plex_mcp/tools/sessions.py  # stub: pass
  src/plex_mcp/tools/deck.py      # stub: pass
  src/plex_mcp/tools/playback.py  # stub: pass
  src/plex_mcp/formatters/__init__.py
  src/plex_mcp/formatters/markdown.py  # stub: pass
  src/plex_mcp/formatters/duration.py  # stub: pass
  tests/__init__.py
  tests/conftest.py               # stub: pass
  .env.example
  .gitignore
  ```
- Install in editable mode: `pip install -e ".[dev]"`

**Verify:**
```bash
pytest tests/test_config.py::test_package_importable -v
pytest tests/test_config.py::test_submodules_importable -v
```

---

### Task 1.2: Settings — Loading from Environment

**Test first:**
```python
# tests/test_config.py  (extend existing file)
import pytest
from pydantic import ValidationError

def test_settings_requires_plex_token(monkeypatch):
    monkeypatch.delenv("PLEX_TOKEN", raising=False)
    monkeypatch.delenv("PLEX_SERVER", raising=False)
    with pytest.raises(ValidationError):
        from plex_mcp.config import Settings
        Settings()

def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "fake-token-abc")
    monkeypatch.setenv("PLEX_SERVER", "http://192.168.1.10:32400")
    from plex_mcp.config import Settings
    s = Settings()
    assert s.plex_token == "fake-token-abc"
    assert s.plex_server == "http://192.168.1.10:32400"

def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "tok")
    monkeypatch.setenv("PLEX_SERVER", "http://localhost:32400")
    from plex_mcp.config import Settings
    s = Settings()
    assert s.plex_connect_timeout == 10
    assert s.plex_request_timeout == 30
    assert s.log_level == "WARNING"

def test_settings_repr_hides_token(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "super-secret")
    monkeypatch.setenv("PLEX_SERVER", "http://localhost:32400")
    from plex_mcp.config import Settings
    s = Settings()
    assert "super-secret" not in repr(s)
```

**Implement:**  
Fill in `src/plex_mcp/config.py` with the `Settings` class exactly as specified in SAD §6.4:
- `plex_token: str` (required)
- `plex_server: str` (required)
- `plex_connect_timeout: int = 10`
- `plex_request_timeout: int = 30`
- `log_level: str = "WARNING"`
- `SettingsConfigDict(env_file=".env", case_sensitive=False)`
- `__repr__` that omits `plex_token`

Create `.env.example` with all five variables documented.

**Verify:**
```bash
pytest tests/test_config.py -v
# All 5 tests green, no import errors
```

---

### Task 1.3: Settings — Singleton + Logging Bootstrap

**Test first:**
```python
# tests/test_config.py  (extend)
def test_get_settings_returns_same_instance(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "tok")
    monkeypatch.setenv("PLEX_SERVER", "http://localhost:32400")
    # Clear lru_cache between test runs
    from plex_mcp.config import get_settings
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

def test_logging_configured_at_import(monkeypatch, caplog):
    monkeypatch.setenv("PLEX_TOKEN", "tok")
    monkeypatch.setenv("PLEX_SERVER", "http://localhost:32400")
    import importlib
    import plex_mcp.config as cfg_mod
    importlib.reload(cfg_mod)   # trigger module-level logging setup
    # No exceptions thrown; log level applied
```

**Implement:**
- Add `get_settings()` with `@lru_cache(maxsize=1)` to `config.py`
- Add module-level `logging.basicConfig(level=settings.log_level)` (lazy, called from `server.py` main, not at import time — document this)
- Add `configure_logging(settings: Settings) -> None` helper function

**Verify:**
```bash
pytest tests/test_config.py -v
# All tests pass; no circular import warnings
```

---

## Bunch 2: Schemas (Pydantic Models)

*Goal: complete, validated data models for all tool inputs and outputs.*

### Task 2.1: Common Schemas

**Test first:**
```python
# tests/test_schemas.py
from plex_mcp.schemas.common import PlexMCPResponse, PlexError, MediaRef, SessionRef

def test_plex_error_model():
    e = PlexError(
        code="MEDIA_NOT_FOUND",
        message="No results.",
        suggestions=["Try search_media"],
    )
    assert e.code == "MEDIA_NOT_FOUND"
    assert len(e.suggestions) == 1

def test_media_ref_requires_rating_key():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        MediaRef(title="Dune", media_type="movie", library="Movies")
        # missing rating_key

def test_media_ref_year_optional():
    ref = MediaRef(title="Dune", media_type="movie", library="Movies", rating_key=12345)
    assert ref.year is None

def test_plex_mcp_response_defaults():
    r = PlexMCPResponse(success=True, tool="search_media")
    assert r.data is None
    assert r.error is None

def test_plex_mcp_response_with_error():
    err = PlexError(code="AUTH_FAILED", message="Bad token")
    r = PlexMCPResponse(success=False, tool="search_media", error=err)
    assert r.success is False
    assert r.error.code == "AUTH_FAILED"

def test_session_ref_state_validation():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SessionRef(
            session_id="s1", user="alice", client_name="TV",
            client_platform="Roku",
            media=MediaRef(title="X", media_type="movie", library="M", rating_key=1),
            progress_pct=50.0,
            state="INVALID_STATE",   # must be playing|paused|buffering|stopped
        )
```

**Implement:**  
Fill `src/plex_mcp/schemas/common.py` with all types from SAD §3.1:
- `ResponseFormat = Literal["markdown", "json"]`
- `PlexMCPResponse` (base), `PlexError`, `MediaRef`, `SessionRef`
- All use `ConfigDict(strict=False)` for agent coercion tolerance

**Verify:**
```bash
pytest tests/test_schemas.py -v
```

---

### Task 2.2: Input Schemas

**Test first:**
```python
# tests/test_schemas.py  (extend)
from plex_mcp.schemas.inputs import (
    SearchMediaInput, BrowseLibraryInput, GetMediaDetailsInput,
    NowPlayingInput, OnDeckInput, RecentlyAddedInput,
    PlayMediaInput, PlaybackControlInput,
    GetLibrariesInput, GetClientsInput,
)

def test_search_input_defaults():
    inp = SearchMediaInput(query="Dune")
    assert inp.limit == 10
    assert inp.format == "markdown"
    assert inp.media_type is None

def test_search_input_query_too_short():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SearchMediaInput(query="")

def test_search_input_limit_clamp():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SearchMediaInput(query="X", limit=100)   # max is 50

def test_play_media_input_confirmed_defaults_false():
    inp = PlayMediaInput(title="Dune", client="Living Room TV")
    assert inp.confirmed is False

def test_playback_control_seek_requires_offset():
    # seek action without seek_offset_ms is valid schema-wise;
    # business logic enforces it in the handler
    inp = PlaybackControlInput(action="seek")
    assert inp.seek_offset_ms is None

def test_browse_library_defaults():
    inp = BrowseLibraryInput(library="Movies")
    assert inp.sort == "titleSort:asc"
    assert inp.page == 1
    assert inp.page_size == 20

def test_recently_added_days_clamp():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        RecentlyAddedInput(days=366)   # max 365

def test_get_libraries_input_default_format():
    inp = GetLibrariesInput()
    assert inp.format == "markdown"

def test_get_clients_input_default_format():
    inp = GetClientsInput()
    assert inp.format == "markdown"
```

**Implement:**  
Fill `src/plex_mcp/schemas/inputs.py` with all `*Input` models from SAD §3.2–3.9, plus:
- `GetLibrariesInput(format: ResponseFormat = "markdown")`
- `GetClientsInput(format: ResponseFormat = "markdown")`

All use `ConfigDict(strict=False)`.

**Verify:**
```bash
pytest tests/test_schemas.py -v
```

---

### Task 2.3: Output Schemas

**Test first:**
```python
# tests/test_schemas.py  (extend)
from plex_mcp.schemas.outputs import (
    SearchResult, SearchMediaOutput,
    LibraryItem, BrowseLibraryOutput,
    MediaDetailsData, MediaDetailsOutput,
    NowPlayingSession, NowPlayingOutput,
    OnDeckItem, OnDeckOutput,
    RecentlyAddedItem, RecentlyAddedOutput,
    PlayMediaData, PlayMediaOutput,
    PlaybackControlData, PlaybackControlOutput,
    LibraryInfo, GetLibrariesOutput,
    ClientInfo, GetClientsOutput,
)

def test_search_result_summary_short_optional():
    r = SearchResult(title="Dune", media_type="movie", library="Movies")
    assert r.summary_short == ""   # default empty string, not None

def test_search_media_output_default_tool_name():
    out = SearchMediaOutput(success=True, tool="search_media")
    assert out.tool == "search_media"
    assert out.data == []

def test_now_playing_session_transcode_status():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        NowPlayingSession(
            session_id="s1", user="alice", client_name="TV",
            client_platform="Roku", client_product="Plex",
            media_title="Dune", media_type="movie",
            duration_min=166, progress_min=60, progress_pct=36.0,
            state="playing",
            transcode_status="INVALID",   # must be direct_play|direct_stream|transcode
        )

def test_play_media_data_dry_run_flag():
    d = PlayMediaData(
        dry_run=True,
        media_title="Dune", media_type="movie",
        client_name="Living Room TV", client_platform="Roku",
    )
    assert d.dry_run is True
    assert d.started_at is None

def test_library_info_schema():
    lib = LibraryInfo(
        name="Movies", library_type="movie",
        item_count=342, size_gb=4500.0
    )
    assert lib.library_type == "movie"

def test_client_info_schema():
    c = ClientInfo(
        name="Living Room TV", platform="Roku",
        product="Plex for Roku", device_id="abc123",
        state="online",
    )
    assert c.state == "online"
```

**Implement:**  
Fill `src/plex_mcp/schemas/outputs.py` with all output/data models from SAD §3.2–3.9, plus:
- `LibraryInfo(name, library_type, item_count, size_gb, agent)` — library descriptor
- `GetLibrariesOutput(PlexMCPResponse)` with `data: list[LibraryInfo]`
- `ClientInfo(name, platform, product, device_id, state, address?)` — player descriptor
- `GetClientsOutput(PlexMCPResponse)` with `data: list[ClientInfo]`

`summary_short` defaults to `""` not `None` for safe string ops. All fields with `list` default to `[]`.

**Verify:**
```bash
pytest tests/test_schemas.py -v
# All schema tests pass
```

---

## Bunch 3: Plex Client Connection + Mocking

*Goal: a testable connection layer and rich fixture set for all subsequent tests.*

### Task 3.1: Test Fixtures — conftest.py

**Test first:**  
*(These tests validate the fixtures themselves — they're used by every later test.)*
```python
# tests/test_conftest.py
def test_mock_plex_server_fixture(mock_plex_server):
    """Fixture returns a usable mock; library names are predictable."""
    assert hasattr(mock_plex_server, "library")
    libs = mock_plex_server.library.sections()
    assert any(lib.title == "Movies" for lib in libs)
    assert any(lib.title == "TV Shows" for lib in libs)

def test_fake_movie_fixture(fake_movie):
    assert fake_movie.title == "Dune"
    assert fake_movie.year == 2021
    assert fake_movie.TYPE == "movie"

def test_fake_episode_fixture(fake_episode):
    assert fake_episode.TYPE == "episode"
    assert fake_episode.seasonNumber == 1
    assert fake_episode.index == 1

def test_fake_session_fixture(fake_session):
    assert fake_session.TYPE == "episode"
    assert hasattr(fake_session, "viewOffset")
    assert hasattr(fake_session, "player")

def test_fake_client_fixture(fake_plex_client):
    assert fake_plex_client.title == "Living Room TV"
    assert fake_plex_client.platform == "Roku"
```

**Implement:**  
Build `tests/conftest.py` with `pytest.fixture` objects:

- **`mock_plex_server`** — `MagicMock(spec=PlexServer)` with:
  - `library.sections()` → two `MagicMock` library sections (Movies, TV Shows)
  - `library.search(query)` → returns list of fake media items
  - `library.onDeck()` → list of fake on-deck items
  - `library.recentlyAdded()` → list of fake recently-added items
  - `sessions()` → list of fake session objects
  - `clients()` → list of fake client objects
- **`fake_movie`** — `MagicMock` with `TYPE="movie"`, `title="Dune"`, `year=2021`, `ratingKey=12345`, `summary="A hero's journey..."`, `audienceRating=8.5`, `duration=9300000` (ms), `genres=[...]`, `isFullyWatched=False`
- **`fake_episode`** — episode with `TYPE="episode"`, `showTitle="Breaking Bad"`, `seasonNumber=1`, `index=1`
- **`fake_session`** — session with `viewOffset`, `duration`, `player` (mock with `title`, `platform`)
- **`fake_plex_client`** — client mock with `title`, `platform`, `product`

Use `pytest-mock`'s `MagicMock`; patch `plex_mcp.client._server` via a fixture that auto-resets.

**Verify:**
```bash
pytest tests/test_conftest.py -v
```

---

### Task 3.2: Client Module — Connection Singleton

**Test first:**
```python
# tests/test_client.py
import pytest
from unittest.mock import patch, MagicMock

def test_get_server_returns_cached_connection(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "tok")
    monkeypatch.setenv("PLEX_SERVER", "http://localhost:32400")
    mock_server = MagicMock()
    with patch("plexapi.server.PlexServer", return_value=mock_server):
        from plex_mcp.client import get_server, _reset_server
        _reset_server()
        s1 = get_server()
        s2 = get_server()
        assert s1 is s2   # same object — singleton

def test_get_server_raises_on_auth_failure(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "bad-tok")
    monkeypatch.setenv("PLEX_SERVER", "http://localhost:32400")
    import plexapi.exceptions
    from plex_mcp.errors import PlexMCPError
    with patch("plexapi.server.PlexServer", side_effect=plexapi.exceptions.Unauthorized("bad")):
        from plex_mcp.client import get_server, _reset_server
        _reset_server()
        with pytest.raises(PlexMCPError) as exc_info:
            get_server()
        assert exc_info.value.code == "AUTH_FAILED"

def test_get_server_raises_on_connection_failure(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "tok")
    monkeypatch.setenv("PLEX_SERVER", "http://bad-host:32400")
    from plex_mcp.errors import PlexMCPError
    with patch("plexapi.server.PlexServer", side_effect=ConnectionRefusedError("refused")):
        from plex_mcp.client import get_server, _reset_server
        _reset_server()
        with pytest.raises(PlexMCPError) as exc_info:
            get_server()
        assert exc_info.value.code == "CONNECTION_FAILED"
        assert len(exc_info.value.suggestions) > 0
```

**Implement:**  
Fill `src/plex_mcp/client.py` per SAD §8.4:
- Module-level `_server: PlexServer | None = None`
- `get_server() -> PlexServer` — returns cached or calls `_connect()`
- `_connect() -> PlexServer` — creates `PlexServer(baseurl, token, timeout)`, wraps exceptions in `PlexMCPError`
- `_reset_server()` — test helper to clear singleton (sets `_server = None`)
- No lru_cache on `get_server` itself; use the module-level variable directly so `_reset_server` works cleanly

**Verify:**
```bash
pytest tests/test_client.py -v
```

---

### Task 3.3: Media Resolution Helper

**Test first:**
```python
# tests/test_client.py  (extend)
from unittest.mock import patch

def test_resolve_media_exact_match(mock_plex_server, fake_movie):
    """Exact title match returns a MediaRef."""
    mock_plex_server.library.search.return_value = [fake_movie]
    with patch("plex_mcp.client.get_server", return_value=mock_plex_server):
        from plex_mcp.client import resolve_media
        from plex_mcp.schemas.common import MediaRef
        result = resolve_media(title="Dune", year=2021)
        assert isinstance(result, MediaRef)
        assert result.title == "Dune"
        assert result.rating_key == fake_movie.ratingKey

def test_resolve_media_not_found_raises(mock_plex_server):
    mock_plex_server.library.search.return_value = []
    with patch("plex_mcp.client.get_server", return_value=mock_plex_server):
        from plex_mcp.client import resolve_media
        from plex_mcp.errors import PlexMCPError
        with pytest.raises(PlexMCPError) as exc_info:
            resolve_media(title="Nonexistent Movie XYZZY")
        assert exc_info.value.code == "MEDIA_NOT_FOUND"
        assert "search_media" in exc_info.value.suggestions[0].lower() or \
               "search_media" in str(exc_info.value.suggestions)

def test_resolve_media_ambiguous_raises(mock_plex_server, fake_movie):
    """Two matches with no year = MEDIA_AMBIGUOUS."""
    fake2 = MagicMock()
    fake2.title = "Dune"
    fake2.year = 1984
    fake2.TYPE = "movie"
    fake2.ratingKey = 99
    mock_plex_server.library.search.return_value = [fake_movie, fake2]
    with patch("plex_mcp.client.get_server", return_value=mock_plex_server):
        from plex_mcp.client import resolve_media
        from plex_mcp.errors import PlexMCPError
        with pytest.raises(PlexMCPError) as exc_info:
            resolve_media(title="Dune")   # no year → ambiguous
        assert exc_info.value.code == "MEDIA_AMBIGUOUS"

def test_resolve_media_year_disambiguates(mock_plex_server, fake_movie):
    fake2 = MagicMock()
    fake2.title = "Dune"
    fake2.year = 1984
    fake2.TYPE = "movie"
    fake2.ratingKey = 99
    mock_plex_server.library.search.return_value = [fake_movie, fake2]
    with patch("plex_mcp.client.get_server", return_value=mock_plex_server):
        from plex_mcp.client import resolve_media
        result = resolve_media(title="Dune", year=2021)
        assert result.year == 2021
```

**Implement:**  
Add to `src/plex_mcp/client.py`:
- `resolve_media(title: str, year: int | None, media_type: str | None) -> MediaRef`
  - Calls `server.library.search(query=title, limit=10)`
  - Exact match: case-insensitive title + optional year filter
  - 0 results → `MEDIA_NOT_FOUND` with suggestions to use `search_media`
  - 1 result → convert to `MediaRef` and return
  - 2+ results without year → `MEDIA_AMBIGUOUS` listing candidates
  - 2+ results with year → filter by year; if still ambiguous → `MEDIA_AMBIGUOUS`
- `resolve_client(client_name: str) -> ClientInfo` — stubs OK for now; full impl in Bunch 8

**Verify:**
```bash
pytest tests/test_client.py -v
```

---

## Bunch 4: Error Handling Infrastructure

*Goal: a robust, uniform error surface that all tools use.*

### Task 4.1: PlexMCPError Class + Error Codes

**Test first:**
```python
# tests/test_errors.py
import pytest
from plex_mcp.errors import PlexMCPError
from plex_mcp.schemas.common import PlexError

def test_plex_mcp_error_attributes():
    e = PlexMCPError(
        code="MEDIA_NOT_FOUND",
        message='No media matching "Dune" found.',
        suggestions=["Try search_media(query='Dune')"],
    )
    assert e.code == "MEDIA_NOT_FOUND"
    assert e.raw is None

def test_plex_mcp_error_to_plex_error():
    e = PlexMCPError(code="AUTH_FAILED", message="Bad token")
    schema = e.to_plex_error()
    assert isinstance(schema, PlexError)
    assert schema.code == "AUTH_FAILED"

def test_plex_mcp_error_to_markdown():
    e = PlexMCPError(
        code="CLIENT_NOT_FOUND",
        message="Client 'My TV' not found.",
        suggestions=["Use get_clients() to list available players."],
    )
    md = e.to_markdown()
    assert "## ❌ Error: CLIENT_NOT_FOUND" in md
    assert "Client 'My TV' not found." in md
    assert "get_clients()" in md
    assert "**What to try:**" in md

def test_plex_mcp_error_to_markdown_no_suggestions():
    e = PlexMCPError(code="UNKNOWN", message="Something broke.")
    md = e.to_markdown()
    assert "## ❌ Error: UNKNOWN" in md
    assert "**What to try:**" not in md

def test_plex_mcp_error_is_exception():
    with pytest.raises(PlexMCPError):
        raise PlexMCPError(code="RATE_LIMITED", message="Slow down.")

def test_error_raw_preserved():
    orig = RuntimeError("network gone")
    e = PlexMCPError(code="CONNECTION_FAILED", message="Can't connect", raw=orig)
    assert e.raw is orig
```

**Implement:**  
Fill `src/plex_mcp/errors.py` with `PlexMCPError(Exception)` class per SAD §4.2:
- `__init__(code, message, suggestions=None, raw=None)`
- `to_plex_error() -> PlexError`
- `to_markdown() -> str` — includes `**What to try:**` section only when suggestions exist
- All error code constants as module-level strings:
  ```python
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
  ```

**Verify:**
```bash
pytest tests/test_errors.py -v
```

---

### Task 4.2: safe_tool_call Wrapper

**Test first:**
```python
# tests/test_errors.py  (extend)
import asyncio
import plexapi.exceptions

def test_safe_tool_call_passes_through_success():
    from plex_mcp.errors import safe_tool_call

    async def handler(_):
        return "## ✅ Result"

    result = asyncio.get_event_loop().run_until_complete(
        safe_tool_call(handler, None, format="markdown")
    )
    assert result == "## ✅ Result"

def test_safe_tool_call_catches_plex_mcp_error_markdown():
    from plex_mcp.errors import safe_tool_call, PlexMCPError

    async def handler(_):
        raise PlexMCPError(code="MEDIA_NOT_FOUND", message="Not found.")

    result = asyncio.get_event_loop().run_until_complete(
        safe_tool_call(handler, None, format="markdown")
    )
    assert "## ❌ Error: MEDIA_NOT_FOUND" in result

def test_safe_tool_call_catches_plex_mcp_error_json():
    from plex_mcp.errors import safe_tool_call, PlexMCPError
    import json

    async def handler(_):
        raise PlexMCPError(code="AUTH_FAILED", message="Bad token.")

    result = asyncio.get_event_loop().run_until_complete(
        safe_tool_call(handler, None, format="json")
    )
    parsed = json.loads(result)
    assert parsed["success"] is False
    assert parsed["error"]["code"] == "AUTH_FAILED"

def test_safe_tool_call_catches_unauthorized():
    from plex_mcp.errors import safe_tool_call

    async def handler(_):
        raise plexapi.exceptions.Unauthorized("nope")

    result = asyncio.get_event_loop().run_until_complete(
        safe_tool_call(handler, None, format="markdown")
    )
    assert "AUTH_FAILED" in result

def test_safe_tool_call_catches_unknown_exception():
    from plex_mcp.errors import safe_tool_call

    async def handler(_):
        raise ValueError("something unexpected")

    result = asyncio.get_event_loop().run_until_complete(
        safe_tool_call(handler, None, format="markdown")
    )
    assert "UNKNOWN" in result or "❌" in result
```

**Implement:**  
Add to `src/plex_mcp/errors.py`:
```python
async def safe_tool_call(
    handler_fn: Callable,
    input_model: Any,
    format: str,
    tool_name: str = "",
) -> str:
```
- Calls `await handler_fn(input_model)`
- Catches `PlexMCPError` → `to_markdown()` or JSON `PlexMCPResponse(success=False)`
- Catches `plexapi.exceptions.Unauthorized` → `AUTH_FAILED` error
- Catches `plexapi.exceptions.NotFound` → `MEDIA_NOT_FOUND` error
- Catches all other `Exception` → `UNKNOWN` error with raw message (truncated to 200 chars)
- Never propagates exceptions to the MCP transport layer

**Verify:**
```bash
pytest tests/test_errors.py -v
```

---

### Task 4.3: Error Construction Helpers

**Test first:**
```python
# tests/test_errors.py  (extend)
from plex_mcp.errors import (
    media_not_found_error,
    media_ambiguous_error,
    client_not_found_error,
    library_not_found_error,
    no_active_session_error,
)

def test_media_not_found_error_includes_title():
    e = media_not_found_error(title="Dune", year=2019)
    assert "Dune" in e.message
    assert "2019" in e.message
    assert e.code == "MEDIA_NOT_FOUND"
    assert any("search_media" in s for s in e.suggestions)

def test_media_ambiguous_error_lists_candidates():
    candidates = [("Dune", 2021, "movie"), ("Dune", 1984, "movie")]
    e = media_ambiguous_error(title="Dune", candidates=candidates)
    assert "2021" in e.message
    assert "1984" in e.message
    assert e.code == "MEDIA_AMBIGUOUS"

def test_client_not_found_error_mentions_get_clients():
    e = client_not_found_error("My TV")
    assert "My TV" in e.message
    assert any("get_clients" in s for s in e.suggestions)

def test_library_not_found_error_mentions_get_libraries():
    e = library_not_found_error("4K Movies")
    assert "4K Movies" in e.message
    assert any("get_libraries" in s for s in e.suggestions)

def test_no_active_session_error_mentions_play_media():
    e = no_active_session_error()
    assert any("play_media" in s for s in e.suggestions)
```

**Implement:**  
Add factory functions to `src/plex_mcp/errors.py`:
- `media_not_found_error(title, year=None, suggestions=None) -> PlexMCPError`
- `media_ambiguous_error(title, candidates: list[tuple]) -> PlexMCPError`
- `client_not_found_error(name) -> PlexMCPError`
- `library_not_found_error(name) -> PlexMCPError`
- `no_active_session_error() -> PlexMCPError`
- `multiple_sessions_error(sessions: list[str]) -> PlexMCPError`

Each includes pre-built, actionable suggestion strings referencing the correct follow-up tools.

**Verify:**
```bash
pytest tests/test_errors.py -v
# All 12+ error tests pass
```

---

## Bunch 5: Formatters

*Goal: all markdown and duration rendering functions, tested independently of tools.*

### Task 5.1: Duration and Date Utilities

**Test first:**
```python
# tests/test_formatters.py
from plex_mcp.formatters.duration import (
    ms_to_min, min_to_human, ms_to_human, relative_date, format_season_episode
)
from datetime import datetime, timezone, timedelta

def test_ms_to_min():
    assert ms_to_min(5400000) == 90      # 90 minutes exact
    assert ms_to_min(5401000) == 90      # rounds down

def test_min_to_human_hours_and_minutes():
    assert min_to_human(90) == "1h 30m"
    assert min_to_human(60) == "1h 0m"
    assert min_to_human(45) == "45m"
    assert min_to_human(0) == "0m"

def test_ms_to_human():
    assert ms_to_human(5400000) == "1h 30m"

def test_relative_date_today():
    now = datetime.now(timezone.utc)
    result = relative_date(now)
    assert result == "Today"

def test_relative_date_yesterday():
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    assert relative_date(yesterday) == "Yesterday"

def test_relative_date_n_days():
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    assert relative_date(three_days_ago) == "3 days ago"

def test_format_season_episode():
    assert format_season_episode(2, 4) == "S02E04"
    assert format_season_episode(1, 10) == "S01E10"
    assert format_season_episode(None, None) is None

def test_relative_date_future_is_today():
    future = datetime.now(timezone.utc) + timedelta(seconds=30)
    assert relative_date(future) == "Today"
```

**Implement:**  
Fill `src/plex_mcp/formatters/duration.py`:
- `ms_to_min(ms: int) -> int` — floor division by 60000
- `min_to_human(minutes: int) -> str` — returns `"Xh Ym"` or `"Ym"` for <60
- `ms_to_human(ms: int) -> str` — composes the above
- `relative_date(dt: datetime) -> str` — "Today", "Yesterday", "N days ago" (using UTC)
- `format_season_episode(season: int | None, episode: int | None) -> str | None`

**Verify:**
```bash
pytest tests/test_formatters.py -v
```

---

### Task 5.2: Markdown Formatters — Read-Only Tools

**Test first:**
```python
# tests/test_formatters.py  (extend)
from plex_mcp.formatters.markdown import (
    format_search_results,
    format_library_list,
    format_media_details,
    format_sessions,
    format_on_deck,
    format_recently_added,
    format_libraries,
    format_clients,
)
from plex_mcp.schemas.outputs import (
    SearchResult, SearchMediaOutput,
    LibraryItem, BrowseLibraryOutput,
    NowPlayingSession, NowPlayingOutput,
    OnDeckItem, OnDeckOutput,
    RecentlyAddedItem, RecentlyAddedOutput,
    LibraryInfo, GetLibrariesOutput,
    ClientInfo, GetClientsOutput,
)

def test_format_search_results_header():
    out = SearchMediaOutput(
        success=True, tool="search_media", query="dune",
        total_found=2,
        data=[
            SearchResult(title="Dune", year=2021, media_type="movie",
                         library="Movies", rating=8.5, duration_min=155,
                         genres=["Sci-Fi", "Adventure"]),
        ]
    )
    md = format_search_results(out)
    assert '## Search: "dune"' in md
    assert "**Dune**" in md
    assert "⭐" in md
    assert "get_media_details" in md   # navigation hint at end

def test_format_search_results_empty():
    out = SearchMediaOutput(success=True, tool="search_media", query="xyzzy", total_found=0)
    md = format_search_results(out)
    assert "No results" in md or "0 results" in md

def test_format_sessions_with_sessions():
    session = NowPlayingSession(
        session_id="s1", user="alice", client_name="Apple TV",
        client_platform="tvOS", client_product="Plex for Apple TV",
        media_title="Dune", media_type="movie",
        duration_min=155, progress_min=60, progress_pct=38.7,
        state="playing", transcode_status="direct_play",
    )
    out = NowPlayingOutput(success=True, tool="now_playing", data=[session], session_count=1)
    md = format_sessions(out)
    assert "## 📺 Now Playing" in md
    assert "alice" in md
    assert "Dune" in md
    assert "▶" in md

def test_format_sessions_empty():
    out = NowPlayingOutput(success=True, tool="now_playing", data=[], session_count=0)
    md = format_sessions(out)
    assert "No active sessions" in md or "nothing" in md.lower()

def test_format_on_deck_items():
    item = OnDeckItem(
        media_title="Breaking Bad", media_type="episode",
        show_title="Breaking Bad", season_episode="S02E05",
        progress_pct=28.0, remaining_min=32, library="TV Shows"
    )
    out = OnDeckOutput(success=True, tool="on_deck", data=[item])
    md = format_on_deck(out)
    assert "## ▶ On Deck" in md
    assert "Breaking Bad" in md
    assert "S02E05" in md

def test_format_libraries():
    out = GetLibrariesOutput(
        success=True, tool="get_libraries",
        data=[
            LibraryInfo(name="Movies", library_type="movie", item_count=342, size_gb=4500.0),
            LibraryInfo(name="TV Shows", library_type="show", item_count=89, size_gb=8200.0),
        ]
    )
    md = format_libraries(out)
    assert "## 📚 Libraries" in md
    assert "Movies" in md
    assert "342" in md

def test_format_clients():
    out = GetClientsOutput(
        success=True, tool="get_clients",
        data=[
            ClientInfo(name="Living Room TV", platform="Roku",
                       product="Plex for Roku", device_id="abc", state="online"),
        ]
    )
    md = format_clients(out)
    assert "Living Room TV" in md
    assert "Roku" in md
```

**Implement:**  
Fill `src/plex_mcp/formatters/markdown.py` with all formatting functions:
- Each function takes the corresponding `*Output` schema and returns a `str`
- Follow the markdown design conventions in SAD §5.2 (H2 header, bold labels, tables for ≥3 items, emoji vocabulary from §5.3, navigation hint in italics at end)
- `format_search_results(out: SearchMediaOutput) -> str`
- `format_library_list(out: BrowseLibraryOutput) -> str`
- `format_media_details(out: MediaDetailsOutput) -> str` — two modes (default + detailed)
- `format_sessions(out: NowPlayingOutput) -> str`
- `format_on_deck(out: OnDeckOutput) -> str`
- `format_recently_added(out: RecentlyAddedOutput) -> str` — group by relative date
- `format_libraries(out: GetLibrariesOutput) -> str`
- `format_clients(out: GetClientsOutput) -> str`

**Verify:**
```bash
pytest tests/test_formatters.py -v
```

---

### Task 5.3: Formatters — Mutation Tools + JSON Mode

**Test first:**
```python
# tests/test_formatters.py  (extend)
from plex_mcp.formatters.markdown import format_dry_run, format_playback_success
from plex_mcp.formatters.json_fmt import to_json_response
from plex_mcp.schemas.outputs import PlayMediaData, PlayMediaOutput, PlaybackControlData
import json

def test_format_dry_run_play_media():
    data = PlayMediaData(
        dry_run=True,
        media_title="Dune: Part Two", media_type="movie",
        client_name="Living Room TV", client_platform="Roku",
        duration_min=166,
    )
    md = format_dry_run(data)
    assert "⚠️" in md
    assert "not started" in md.lower() or "preview" in md.lower()
    assert "Living Room TV" in md
    assert "confirmed=True" in md   # shows the call to make

def test_format_playback_success():
    from datetime import datetime, timezone
    data = PlayMediaData(
        dry_run=False,
        media_title="Dune: Part Two", media_type="movie",
        client_name="Living Room TV", client_platform="Roku",
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    md = format_playback_success(data)
    assert "✅" in md
    assert "Living Room TV" in md
    assert "Dune: Part Two" in md

def test_to_json_response_success():
    out = PlayMediaOutput(success=True, tool="play_media")
    json_str = to_json_response(out)
    parsed = json.loads(json_str)
    assert parsed["success"] is True
    assert parsed["tool"] == "play_media"

def test_to_json_response_preserves_nested_data():
    data = PlayMediaData(dry_run=True, media_title="X", media_type="movie",
                         client_name="TV", client_platform="Roku")
    out = PlayMediaOutput(success=True, tool="play_media", data=data)
    json_str = to_json_response(out)
    parsed = json.loads(json_str)
    assert parsed["data"]["dry_run"] is True
    assert parsed["data"]["media_title"] == "X"
```

**Implement:**
- Add `format_dry_run(data: PlayMediaData | PlaybackControlData) -> str` to `markdown.py`
  - Shows `⚠️ Playback Preview (not started)` header, all resolved details, and the exact `confirmed=True` call string
- Add `format_playback_success(data: PlayMediaData | PlaybackControlData) -> str`
  - Shows `✅ Playback Started` with media, client, and timestamp
- Create `src/plex_mcp/formatters/json_fmt.py`:
  - `to_json_response(out: PlexMCPResponse) -> str` — `model.model_dump_json(indent=2)`

**Verify:**
```bash
pytest tests/test_formatters.py -v
# All formatter tests pass (≥15 tests green)
```

---

## Bunch 6: Read-Only Tools — Search, Browse, Details

*Goal: the three core discovery tools, fully tested against mock PlexServer.*

### Task 6.1: search_media Tool

**Test first:**
```python
# tests/test_search.py
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def search_input():
    from plex_mcp.schemas.inputs import SearchMediaInput
    return SearchMediaInput(query="Dune", limit=5)

def test_search_media_returns_markdown(mock_plex_server, fake_movie, search_input):
    mock_plex_server.library.search.return_value = [fake_movie]
    with patch("plex_mcp.tools.search.get_server", return_value=mock_plex_server):
        import asyncio
        from plex_mcp.tools.search import search_media
        result = asyncio.get_event_loop().run_until_complete(search_media(search_input))
    assert "## Search" in result
    assert "Dune" in result

def test_search_media_no_results_message(mock_plex_server, search_input):
    mock_plex_server.library.search.return_value = []
    with patch("plex_mcp.tools.search.get_server", return_value=mock_plex_server):
        import asyncio
        from plex_mcp.tools.search import search_media
        result = asyncio.get_event_loop().run_until_complete(search_media(search_input))
    assert "No results" in result or "0 results" in result

def test_search_media_json_format(mock_plex_server, fake_movie):
    from plex_mcp.schemas.inputs import SearchMediaInput
    mock_plex_server.library.search.return_value = [fake_movie]
    with patch("plex_mcp.tools.search.get_server", return_value=mock_plex_server):
        import asyncio, json
        from plex_mcp.tools.search import search_media
        inp = SearchMediaInput(query="Dune", format="json")
        result = asyncio.get_event_loop().run_until_complete(search_media(inp))
    parsed = json.loads(result)
    assert parsed["success"] is True
    assert parsed["tool"] == "search_media"
    assert isinstance(parsed["data"], list)

def test_search_media_type_filter(mock_plex_server, fake_movie):
    from plex_mcp.schemas.inputs import SearchMediaInput
    fake_episode = MagicMock()
    fake_episode.TYPE = "episode"
    fake_episode.title = "Dune Pilot"
    mock_plex_server.library.search.return_value = [fake_movie, fake_episode]
    with patch("plex_mcp.tools.search.get_server", return_value=mock_plex_server):
        import asyncio
        from plex_mcp.tools.search import search_media
        inp = SearchMediaInput(query="Dune", media_type="movie")
        result = asyncio.get_event_loop().run_until_complete(search_media(inp))
    assert "Dune" in result
    # episode should be filtered out — only movie in result

def test_search_media_respects_limit(mock_plex_server):
    from plex_mcp.schemas.inputs import SearchMediaInput
    many = [MagicMock(TYPE="movie", title=f"Movie {i}", year=2020+i,
                      ratingKey=i, summary="...", audienceRating=7.0,
                      duration=5400000, genres=[]) for i in range(20)]
    mock_plex_server.library.search.return_value = many
    with patch("plex_mcp.tools.search.get_server", return_value=mock_plex_server):
        import asyncio
        from plex_mcp.tools.search import search_media
        inp = SearchMediaInput(query="Movie", limit=3)
        result = asyncio.get_event_loop().run_until_complete(search_media(inp))
    # Only 3 results rendered
    assert result.count("**Movie") <= 3
```

**Implement:**  
Create `src/plex_mcp/tools/search.py`:
```python
async def search_media(inp: SearchMediaInput) -> str:
    server = get_server()
    raw_results = server.library.search(query=inp.query, limit=inp.limit * 2)
    # Filter by media_type if specified; cap at inp.limit
    # Build list[SearchResult] from plexapi objects
    # Build SearchMediaOutput
    # Return format_search_results(out) or to_json_response(out)
```
- Map plexapi attributes to `SearchResult` fields (handle missing attrs with `getattr(x, "attr", None)`)
- `summary_short` = first 120 chars of `summary`
- `duration_min` = `ms_to_min(item.duration)` if `item.duration` else `None`

Wrap entire function body in `safe_tool_call`.

**Verify:**
```bash
pytest tests/test_search.py -v
```

---

### Task 6.2: browse_library Tool

**Test first:**
```python
# tests/test_browse.py
import pytest
from unittest.mock import patch, MagicMock
import asyncio

def make_browse_input(library="Movies", **kwargs):
    from plex_mcp.schemas.inputs import BrowseLibraryInput
    return BrowseLibraryInput(library=library, **kwargs)

def test_browse_library_returns_markdown(mock_plex_server):
    mock_section = MagicMock()
    mock_section.title = "Movies"
    mock_section.search.return_value = [MagicMock(
        title="Aliens", year=1986, TYPE="movie",
        audienceRating=8.4, duration=8220000,
        isWatched=True, addedAt=MagicMock(isoformat=lambda: "2024-01-01")
    )]
    mock_plex_server.library.section.return_value = mock_section
    with patch("plex_mcp.tools.browse.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.browse import browse_library
        result = asyncio.get_event_loop().run_until_complete(
            browse_library(make_browse_input())
        )
    assert "## Movies" in result or "Movies" in result
    assert "Aliens" in result

def test_browse_library_not_found_raises(mock_plex_server):
    import plexapi.exceptions
    mock_plex_server.library.section.side_effect = plexapi.exceptions.NotFound("nope")
    with patch("plex_mcp.tools.browse.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.browse import browse_library
        result = asyncio.get_event_loop().run_until_complete(
            browse_library(make_browse_input(library="Nonexistent"))
        )
    assert "LIBRARY_NOT_FOUND" in result or "❌" in result

def test_browse_library_pagination(mock_plex_server):
    mock_section = MagicMock()
    mock_section.title = "Movies"
    items = [MagicMock(title=f"Movie {i}", year=2000+i, TYPE="movie",
                       audienceRating=7.0, duration=5400000,
                       isWatched=False, addedAt=MagicMock(isoformat=lambda: "2024-01-01"))
             for i in range(50)]
    mock_section.search.return_value = items
    with patch("plex_mcp.tools.browse.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.browse import browse_library
        result = asyncio.get_event_loop().run_until_complete(
            browse_library(make_browse_input(page=1, page_size=5))
        )
    assert "Page 1" in result

def test_browse_library_json_format(mock_plex_server):
    mock_section = MagicMock()
    mock_section.title = "Movies"
    mock_section.search.return_value = []
    mock_plex_server.library.section.return_value = mock_section
    with patch("plex_mcp.tools.browse.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.browse import browse_library
        import json
        result = asyncio.get_event_loop().run_until_complete(
            browse_library(make_browse_input(format="json"))
        )
    parsed = json.loads(result)
    assert parsed["tool"] == "browse_library"
```

**Implement:**  
Create `src/plex_mcp/tools/browse.py`:
- `async def browse_library(inp: BrowseLibraryInput) -> str`
- Call `server.library.section(inp.library)` — catch `NotFound` → `library_not_found_error`
- Call `section.search(sort=inp.sort, filters=inp.filters or {})` to get all matching items
- Slice for pagination: `items[(page-1)*page_size : page*page_size]`
- Compute `total_pages = ceil(total / page_size)`
- Build `BrowseLibraryOutput` → `format_library_list(out)` or JSON

**Verify:**
```bash
pytest tests/test_browse.py -v
```

---

### Task 6.3: get_media_details Tool

**Test first:**
```python
# tests/test_details.py
import pytest
from unittest.mock import patch, MagicMock
import asyncio

def test_get_media_details_concise(mock_plex_server, fake_movie):
    from plex_mcp.schemas.inputs import GetMediaDetailsInput
    mock_plex_server.library.search.return_value = [fake_movie]
    with patch("plex_mcp.tools.details.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.details import get_media_details
        inp = GetMediaDetailsInput(title="Dune", year=2021)
        result = asyncio.get_event_loop().run_until_complete(get_media_details(inp))
    assert "Dune" in result
    assert "## 🎬" in result or "##" in result

def test_get_media_details_detailed_flag(mock_plex_server, fake_movie):
    from plex_mcp.schemas.inputs import GetMediaDetailsInput
    # Setup cast/crew on fake_movie
    fake_movie.roles = [MagicMock(tag="Timothée Chalamet", role="Paul Atreides")]
    fake_movie.directors = [MagicMock(tag="Denis Villeneuve")]
    fake_movie.media = [MagicMock(
        parts=[MagicMock(
            file="/movies/Dune.mkv",
            size=62000000000,
            container="mkv",
            videoStreams=[MagicMock(codec="hevc", height=2160, width=3840)],
            audioStreams=[MagicMock(codec="truehd", audioChannelLayout="7.1")],
        )]
    )]
    mock_plex_server.library.search.return_value = [fake_movie]
    with patch("plex_mcp.tools.details.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.details import get_media_details
        inp = GetMediaDetailsInput(title="Dune", year=2021, detailed=True)
        result = asyncio.get_event_loop().run_until_complete(get_media_details(inp))
    assert "Cast" in result or "Director" in result

def test_get_media_details_not_found(mock_plex_server):
    from plex_mcp.schemas.inputs import GetMediaDetailsInput
    mock_plex_server.library.search.return_value = []
    with patch("plex_mcp.tools.details.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.details import get_media_details
        inp = GetMediaDetailsInput(title="XYZZY Movie That Doesnt Exist")
        result = asyncio.get_event_loop().run_until_complete(get_media_details(inp))
    assert "MEDIA_NOT_FOUND" in result or "❌" in result

def test_get_media_details_episode_resolution(mock_plex_server, fake_episode):
    from plex_mcp.schemas.inputs import GetMediaDetailsInput
    mock_plex_server.library.search.return_value = [fake_episode]
    with patch("plex_mcp.tools.details.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.details import get_media_details
        inp = GetMediaDetailsInput(title="Breaking Bad", season=1, episode=1,
                                   media_type="episode")
        result = asyncio.get_event_loop().run_until_complete(get_media_details(inp))
    assert "Breaking Bad" in result or "S01E01" in result
```

**Implement:**  
Create `src/plex_mcp/tools/details.py`:
- `async def get_media_details(inp: GetMediaDetailsInput) -> str`
- Use `resolve_media(inp.title, inp.year, inp.media_type)` to get `MediaRef`
- Fetch full item via `server.fetchItem(media_ref.rating_key)`
- Build `MediaDetailsData` — include `cast`/`files` only when `inp.detailed=True`
- Handle show-level vs. episode-level attributes carefully (check `item.TYPE`)
- Return `format_media_details(out)` or JSON

**Verify:**
```bash
pytest tests/test_details.py -v
```

---

## Bunch 7: Read-Only Tools — Sessions, Deck & Recent

*Goal: the three "what's happening now" tools.*

### Task 7.1: now_playing Tool

**Test first:**
```python
# tests/test_sessions.py
import pytest
from unittest.mock import patch, MagicMock
import asyncio

def test_now_playing_active_sessions(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    with patch("plex_mcp.tools.sessions.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.sessions import now_playing
        from plex_mcp.schemas.inputs import NowPlayingInput
        result = asyncio.get_event_loop().run_until_complete(now_playing(NowPlayingInput()))
    assert "## 📺 Now Playing" in result
    assert "1 active" in result or "session" in result.lower()

def test_now_playing_empty_sessions(mock_plex_server):
    mock_plex_server.sessions.return_value = []
    with patch("plex_mcp.tools.sessions.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.sessions import now_playing
        from plex_mcp.schemas.inputs import NowPlayingInput
        result = asyncio.get_event_loop().run_until_complete(now_playing(NowPlayingInput()))
    assert "No active sessions" in result or "nothing" in result.lower() or "0" in result

def test_now_playing_json_format(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    with patch("plex_mcp.tools.sessions.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.sessions import now_playing
        from plex_mcp.schemas.inputs import NowPlayingInput
        import json
        result = asyncio.get_event_loop().run_until_complete(
            now_playing(NowPlayingInput(format="json"))
        )
    parsed = json.loads(result)
    assert parsed["tool"] == "now_playing"
    assert isinstance(parsed["data"], list)

def test_now_playing_transcode_status_mapped(mock_plex_server):
    session = MagicMock()
    session.TYPE = "movie"
    session.title = "Dune"
    session.year = 2021
    session.ratingKey = 1
    session.duration = 9300000
    session.viewOffset = 3600000
    session.usernames = ["alice"]
    session.player = MagicMock(title="Apple TV", platform="tvOS", product="Plex",
                                state="playing")
    transcode = MagicMock()
    transcode.videoDecision = "transcode"
    transcode.audioDecision = "copy"
    transcode.bandwidth = 12000
    transcode.error = None
    session.transcodeSessions = [transcode]
    mock_plex_server.sessions.return_value = [session]
    with patch("plex_mcp.tools.sessions.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.sessions import now_playing
        from plex_mcp.schemas.inputs import NowPlayingInput
        result = asyncio.get_event_loop().run_until_complete(now_playing(NowPlayingInput()))
    assert "Transcod" in result or "transcode" in result.lower()
```

**Implement:**  
Create `src/plex_mcp/tools/sessions.py`:
- `async def now_playing(inp: NowPlayingInput) -> str`
- `server.sessions()` → list of session objects
- Map each session to `NowPlayingSession`:
  - `user = session.usernames[0]` if available
  - `transcode_status` from `session.transcodeSessions` (empty → `"direct_play"`)
  - `progress_pct = (viewOffset / duration) * 100`
- Build `NowPlayingOutput` → `format_sessions(out)` or JSON

**Verify:**
```bash
pytest tests/test_sessions.py -v
```

---

### Task 7.2: on_deck Tool

**Test first:**
```python
# tests/test_deck.py
import pytest
from unittest.mock import patch, MagicMock
import asyncio

def make_deck_item(title="Breaking Bad", season=2, episode=5, view_offset_ms=120000,
                   duration_ms=2700000, type_="episode"):
    item = MagicMock()
    item.TYPE = type_
    item.title = f"{title} S0{season}E0{episode}" if type_ == "episode" else title
    item.grandparentTitle = title if type_ == "episode" else None
    item.parentIndex = season
    item.index = episode
    item.duration = duration_ms
    item.viewOffset = view_offset_ms
    item.thumb = None
    item.librarySectionTitle = "TV Shows"
    item.year = None
    return item

def test_on_deck_returns_items(mock_plex_server):
    mock_plex_server.library.onDeck.return_value = [make_deck_item()]
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.deck import on_deck
        from plex_mcp.schemas.inputs import OnDeckInput
        result = asyncio.get_event_loop().run_until_complete(on_deck(OnDeckInput()))
    assert "## ▶ On Deck" in result
    assert "Breaking Bad" in result

def test_on_deck_respects_limit(mock_plex_server):
    items = [make_deck_item(title=f"Show {i}") for i in range(20)]
    mock_plex_server.library.onDeck.return_value = items
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.deck import on_deck
        from plex_mcp.schemas.inputs import OnDeckInput
        result = asyncio.get_event_loop().run_until_complete(on_deck(OnDeckInput(limit=3)))
    assert result.count("Show") <= 3

def test_on_deck_empty(mock_plex_server):
    mock_plex_server.library.onDeck.return_value = []
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.deck import on_deck
        from plex_mcp.schemas.inputs import OnDeckInput
        result = asyncio.get_event_loop().run_until_complete(on_deck(OnDeckInput()))
    assert "nothing" in result.lower() or "empty" in result.lower() or "0" in result

def test_on_deck_progress_pct_calculated(mock_plex_server):
    # 50% through
    mock_plex_server.library.onDeck.return_value = [
        make_deck_item(view_offset_ms=1350000, duration_ms=2700000)
    ]
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.deck import on_deck
        from plex_mcp.schemas.inputs import OnDeckInput
        result = asyncio.get_event_loop().run_until_complete(on_deck(OnDeckInput()))
    assert "50%" in result or "22m" in result   # 50% of 45 min = 22.5m remaining
```

**Implement:**  
Add to `src/plex_mcp/tools/deck.py`:
- `async def on_deck(inp: OnDeckInput) -> str`
- `server.library.onDeck()[:inp.limit]`
- Map to `OnDeckItem`: compute `progress_pct`, `remaining_min`, format `season_episode`
- Build `OnDeckOutput` → `format_on_deck(out)` or JSON

**Verify:**
```bash
pytest tests/test_deck.py -v
```

---

### Task 7.3: recently_added Tool

**Test first:**
```python
# tests/test_deck.py  (extend)
from datetime import datetime, timezone, timedelta

def make_added_item(title, days_ago=1, type_="movie", duration_ms=5400000):
    item = MagicMock()
    item.TYPE = type_
    item.title = title
    item.year = 2024
    item.ratingKey = hash(title) % 10000
    item.duration = duration_ms
    item.addedAt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    item.summary = f"Summary of {title}"
    item.librarySectionTitle = "Movies"
    item.grandparentTitle = None
    item.parentIndex = None
    item.index = None
    return item

def test_recently_added_returns_items(mock_plex_server):
    mock_plex_server.library.recentlyAdded.return_value = [
        make_added_item("Dune: Part Two", days_ago=1),
        make_added_item("Anora", days_ago=3),
    ]
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.deck import recently_added
        from plex_mcp.schemas.inputs import RecentlyAddedInput
        result = asyncio.get_event_loop().run_until_complete(
            recently_added(RecentlyAddedInput(days=7))
        )
    assert "## 🆕 Recently Added" in result
    assert "Dune: Part Two" in result
    assert "Anora" in result

def test_recently_added_filters_by_days(mock_plex_server):
    mock_plex_server.library.recentlyAdded.return_value = [
        make_added_item("Old Movie", days_ago=10),
        make_added_item("New Movie", days_ago=2),
    ]
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.deck import recently_added
        from plex_mcp.schemas.inputs import RecentlyAddedInput
        result = asyncio.get_event_loop().run_until_complete(
            recently_added(RecentlyAddedInput(days=7))
        )
    assert "New Movie" in result
    assert "Old Movie" not in result

def test_recently_added_filters_by_media_type(mock_plex_server):
    mock_plex_server.library.recentlyAdded.return_value = [
        make_added_item("Movie A", type_="movie"),
        make_added_item("Episode B", type_="episode"),
    ]
    with patch("plex_mcp.tools.deck.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.deck import recently_added
        from plex_mcp.schemas.inputs import RecentlyAddedInput
        result = asyncio.get_event_loop().run_until_complete(
            recently_added(RecentlyAddedInput(media_type="movie"))
        )
    assert "Movie A" in result
    assert "Episode B" not in result
```

**Implement:**  
Add to `src/plex_mcp/tools/deck.py`:
- `async def recently_added(inp: RecentlyAddedInput) -> str`
- Call `server.library.recentlyAdded(maxresults=inp.limit * 2)` (over-fetch to allow filtering)
- Filter by `addedAt` >= `now - timedelta(days=inp.days)`
- Filter by `media_type` if provided
- Cap at `inp.limit`
- Map to `RecentlyAddedItem` with `added_human = relative_date(item.addedAt)`
- Build `RecentlyAddedOutput` → `format_recently_added(out)` or JSON

**Verify:**
```bash
pytest tests/test_deck.py -v
# All deck tests pass (on_deck + recently_added)
```

---

## Bunch 8: get_libraries + get_clients

*Goal: the two discovery tools identified as critical missing tools in FLOWS.md.*

### Task 8.1: get_libraries Tool

**Test first:**
```python
# tests/test_libraries_clients.py
import pytest
from unittest.mock import patch, MagicMock
import asyncio

def make_mock_section(name, type_, count):
    s = MagicMock()
    s.title = name
    s.type = type_
    s.totalSize = count
    s.totalStorage = count * 1_000_000_000   # rough GB
    s.agent = "tv.plex.agents.movie"
    return s

def test_get_libraries_returns_all_sections(mock_plex_server):
    mock_plex_server.library.sections.return_value = [
        make_mock_section("Movies", "movie", 342),
        make_mock_section("TV Shows", "show", 89),
        make_mock_section("Music", "artist", 500),
    ]
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.libraries import get_libraries
        from plex_mcp.schemas.inputs import GetLibrariesInput
        result = asyncio.get_event_loop().run_until_complete(
            get_libraries(GetLibrariesInput())
        )
    assert "## 📚 Libraries" in result
    assert "Movies" in result
    assert "TV Shows" in result
    assert "342" in result

def test_get_libraries_json_format(mock_plex_server):
    mock_plex_server.library.sections.return_value = [
        make_mock_section("Movies", "movie", 100),
    ]
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.libraries import get_libraries
        from plex_mcp.schemas.inputs import GetLibrariesInput
        import json
        result = asyncio.get_event_loop().run_until_complete(
            get_libraries(GetLibrariesInput(format="json"))
        )
    parsed = json.loads(result)
    assert parsed["tool"] == "get_libraries"
    assert len(parsed["data"]) == 1
    assert parsed["data"][0]["name"] == "Movies"

def test_get_libraries_empty_server(mock_plex_server):
    mock_plex_server.library.sections.return_value = []
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.libraries import get_libraries
        from plex_mcp.schemas.inputs import GetLibrariesInput
        result = asyncio.get_event_loop().run_until_complete(
            get_libraries(GetLibrariesInput())
        )
    assert "no libraries" in result.lower() or "0" in result or "empty" in result.lower()
```

**Implement:**  
Create `src/plex_mcp/tools/libraries.py`:
- `async def get_libraries(inp: GetLibrariesInput) -> str`
- `server.library.sections()` → list of `LibrarySection` objects
- Map each to `LibraryInfo(name=s.title, library_type=s.type, item_count=s.totalSize, size_gb=s.totalStorage/1e9, agent=s.agent)`
- Build `GetLibrariesOutput` → `format_libraries(out)` or JSON
- Navigation hint: "Use `browse_library(library='...')` to explore a library"
- Add this tool to `tools/__init__.py` exports

**Verify:**
```bash
pytest tests/test_libraries_clients.py::test_get_libraries_* -v
```

---

### Task 8.2: get_clients Tool

**Test first:**
```python
# tests/test_libraries_clients.py  (extend)
def make_mock_client(name, platform, product, state="online"):
    c = MagicMock()
    c.title = name
    c.platform = platform
    c.product = product
    c.machineIdentifier = f"id_{name.lower().replace(' ', '_')}"
    c.state = state
    c.address = "192.168.1.50"
    return c

def test_get_clients_lists_available_players(mock_plex_server):
    mock_plex_server.clients.return_value = [
        make_mock_client("Living Room TV", "Roku", "Plex for Roku"),
        make_mock_client("MacBook", "MacOSX", "Plex for Mac"),
    ]
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.libraries import get_clients
        from plex_mcp.schemas.inputs import GetClientsInput
        result = asyncio.get_event_loop().run_until_complete(
            get_clients(GetClientsInput())
        )
    assert "Living Room TV" in result
    assert "Roku" in result
    assert "MacBook" in result

def test_get_clients_no_clients_message(mock_plex_server):
    mock_plex_server.clients.return_value = []
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.libraries import get_clients
        from plex_mcp.schemas.inputs import GetClientsInput
        result = asyncio.get_event_loop().run_until_complete(
            get_clients(GetClientsInput())
        )
    assert "no clients" in result.lower() or "no players" in result.lower() or "0" in result

def test_get_clients_json_format(mock_plex_server):
    mock_plex_server.clients.return_value = [
        make_mock_client("Apple TV", "tvOS", "Plex for Apple TV"),
    ]
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.libraries import get_clients
        from plex_mcp.schemas.inputs import GetClientsInput
        import json
        result = asyncio.get_event_loop().run_until_complete(
            get_clients(GetClientsInput(format="json"))
        )
    parsed = json.loads(result)
    assert parsed["tool"] == "get_clients"
    assert parsed["data"][0]["name"] == "Apple TV"
    assert parsed["data"][0]["platform"] == "tvOS"

def test_get_clients_hint_for_play_media(mock_plex_server):
    mock_plex_server.clients.return_value = [
        make_mock_client("Living Room TV", "Roku", "Plex for Roku"),
    ]
    with patch("plex_mcp.tools.libraries.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.libraries import get_clients
        from plex_mcp.schemas.inputs import GetClientsInput
        result = asyncio.get_event_loop().run_until_complete(
            get_clients(GetClientsInput())
        )
    # Navigation hint should mention play_media
    assert "play_media" in result
```

**Implement:**  
Add to `src/plex_mcp/tools/libraries.py`:
- `async def get_clients(inp: GetClientsInput) -> str`
- `server.clients()` → list of `PlexClient` objects
- Map each to `ClientInfo(name=c.title, platform=c.platform, product=c.product, device_id=c.machineIdentifier, state="online", address=c.address)`
- Build `GetClientsOutput` → `format_clients(out)` or JSON
- Navigation hint: "Use client name in `play_media(client='...')` to start playback"
- Also complete `resolve_client(name: str) -> ClientInfo` in `client.py` using `server.clients()` + name match → `CLIENT_NOT_FOUND` error with `get_clients()` suggestion

**Verify:**
```bash
pytest tests/test_libraries_clients.py -v
# All 7 tests pass
```

---

## Bunch 9: Mutation Tools — play_media + playback_control

*Goal: the two side-effecting tools with full confirmation gate.*

### Task 9.1: play_media — Dry-Run Path

**Test first:**
```python
# tests/test_playback.py
import pytest
from unittest.mock import patch, MagicMock
import asyncio

def test_play_media_dry_run_default(mock_plex_server, fake_movie, fake_plex_client):
    """confirmed=False (default) → dry-run, no actual playback."""
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.playback import play_media
        from plex_mcp.schemas.inputs import PlayMediaInput
        inp = PlayMediaInput(title="Dune", year=2021, client="Living Room TV", confirmed=False)
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    assert "⚠️" in result
    assert "preview" in result.lower() or "not started" in result.lower()
    assert "confirmed=True" in result
    # No actual playback method called
    fake_plex_client.playMedia.assert_not_called()

def test_play_media_dry_run_shows_media_details(mock_plex_server, fake_movie, fake_plex_client):
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.playback import play_media
        from plex_mcp.schemas.inputs import PlayMediaInput
        inp = PlayMediaInput(title="Dune", client="Living Room TV")
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    assert "Dune" in result
    assert "Living Room TV" in result

def test_play_media_client_not_found(mock_plex_server, fake_movie):
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = []    # no clients
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.playback import play_media
        from plex_mcp.schemas.inputs import PlayMediaInput
        inp = PlayMediaInput(title="Dune", client="Nonexistent TV")
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    assert "CLIENT_NOT_FOUND" in result or "❌" in result
    assert "get_clients" in result

def test_play_media_media_not_found(mock_plex_server, fake_plex_client):
    mock_plex_server.library.search.return_value = []
    mock_plex_server.clients.return_value = [fake_plex_client]
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.playback import play_media
        from plex_mcp.schemas.inputs import PlayMediaInput
        inp = PlayMediaInput(title="XYZZY", client="Living Room TV")
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    assert "MEDIA_NOT_FOUND" in result or "❌" in result
```

**Implement:**  
Create `src/plex_mcp/tools/playback.py`:
```python
async def play_media(inp: PlayMediaInput) -> str:
    server = get_server()
    media = resolve_media(inp.title, inp.year, inp.media_type)
    plex_item = server.fetchItem(media.rating_key)
    client = resolve_client(inp.client)   # raises CLIENT_NOT_FOUND if not found

    dry_run_data = PlayMediaData(
        dry_run=True,
        media_title=media.title,
        media_type=media.media_type,
        client_name=client.name,
        client_platform=client.platform,
        duration_min=ms_to_min(plex_item.duration) if plex_item.duration else None,
        offset_ms=inp.offset_ms,
    )

    if not inp.confirmed:
        return format_dry_run(dry_run_data)

    # Confirmed: execute
    plex_client = server.client(inp.client)
    plex_client.playMedia(plex_item, offset=inp.offset_ms or 0)
    ...
```
- All resolution happens before the `confirmed` check — dry-run must validate fully
- Wrap in `safe_tool_call`

**Verify:**
```bash
pytest tests/test_playback.py -k "dry_run or not_found" -v
```

---

### Task 9.2: play_media — Confirmed Execution Path

**Test first:**
```python
# tests/test_playback.py  (extend)
def test_play_media_confirmed_calls_plex_api(mock_plex_server, fake_movie, fake_plex_client):
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    mock_plex_client_obj = MagicMock()
    mock_plex_server.client.return_value = mock_plex_client_obj
    mock_plex_server.fetchItem.return_value = fake_movie
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.playback import play_media
        from plex_mcp.schemas.inputs import PlayMediaInput
        inp = PlayMediaInput(title="Dune", year=2021, client="Living Room TV", confirmed=True)
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    assert "✅" in result
    assert "Dune" in result
    mock_plex_client_obj.playMedia.assert_called_once()

def test_play_media_confirmed_success_shows_timestamp(mock_plex_server, fake_movie, fake_plex_client):
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    mock_plex_server.fetchItem.return_value = fake_movie
    mock_plex_server.client.return_value = MagicMock()
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.playback import play_media
        from plex_mcp.schemas.inputs import PlayMediaInput
        inp = PlayMediaInput(title="Dune", client="Living Room TV", confirmed=True)
        result = asyncio.get_event_loop().run_until_complete(play_media(inp))
    assert "UTC" in result or "Started" in result or "✅" in result

def test_play_media_with_offset(mock_plex_server, fake_movie, fake_plex_client):
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    mock_plex_server.fetchItem.return_value = fake_movie
    mock_client_obj = MagicMock()
    mock_plex_server.client.return_value = mock_client_obj
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.playback import play_media
        from plex_mcp.schemas.inputs import PlayMediaInput
        inp = PlayMediaInput(
            title="Dune", client="Living Room TV",
            offset_ms=3600000, confirmed=True
        )
        asyncio.get_event_loop().run_until_complete(play_media(inp))
    call_kwargs = mock_client_obj.playMedia.call_args
    # offset should be passed through
    assert call_kwargs is not None
```

**Implement:**  
Complete the confirmed execution branch in `play_media`:
- `server.client(inp.client).playMedia(plex_item, offset=inp.offset_ms or 0)`
- On success: build `PlayMediaData(dry_run=False, started_at=datetime.now(timezone.utc).isoformat(), ...)`
- Return `format_playback_success(data)` or JSON
- On `plexapi` exception during playback: wrap in `PlexMCPError(code="PLAYBACK_ERROR", ...)`

**Verify:**
```bash
pytest tests/test_playback.py -v
# All play_media tests pass
```

---

### Task 9.3: playback_control Tool

**Test first:**
```python
# tests/test_playback.py  (extend)
def test_playback_control_dry_run_shows_preview(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    mock_plex_server.clients.return_value = []
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.playback import playback_control
        from plex_mcp.schemas.inputs import PlaybackControlInput
        inp = PlaybackControlInput(action="pause", client="Living Room TV", confirmed=False)
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "⚠️" in result
    assert "pause" in result.lower()
    assert "confirmed=True" in result

def test_playback_control_no_active_session(mock_plex_server):
    mock_plex_server.sessions.return_value = []
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.playback import playback_control
        from plex_mcp.schemas.inputs import PlaybackControlInput
        inp = PlaybackControlInput(action="pause", confirmed=False)
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "NO_ACTIVE_SESSION" in result or "❌" in result
    assert "play_media" in result

def test_playback_control_multiple_sessions_require_client(mock_plex_server, fake_session):
    session2 = MagicMock()
    session2.player = MagicMock(title="MacBook", platform="MacOSX")
    mock_plex_server.sessions.return_value = [fake_session, session2]
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.playback import playback_control
        from plex_mcp.schemas.inputs import PlaybackControlInput
        inp = PlaybackControlInput(action="pause", client=None, confirmed=True)
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "MULTIPLE_SESSIONS" in result or "❌" in result

def test_playback_control_confirmed_calls_pause(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    mock_client = MagicMock()
    mock_plex_server.client.return_value = mock_client
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.playback import playback_control
        from plex_mcp.schemas.inputs import PlaybackControlInput
        inp = PlaybackControlInput(
            action="pause",
            client=fake_session.player.title,
            confirmed=True
        )
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "✅" in result or "pause" in result.lower()
    mock_client.pause.assert_called_once()

def test_playback_control_seek_requires_offset(mock_plex_server, fake_session):
    mock_plex_server.sessions.return_value = [fake_session]
    with patch("plex_mcp.tools.playback.get_server", return_value=mock_plex_server):
        from plex_mcp.tools.playback import playback_control
        from plex_mcp.schemas.inputs import PlaybackControlInput
        inp = PlaybackControlInput(
            action="seek", seek_offset_ms=None,   # missing offset
            client=fake_session.player.title, confirmed=True
        )
        result = asyncio.get_event_loop().run_until_complete(playback_control(inp))
    assert "❌" in result or "seek_offset_ms" in result
```

**Implement:**  
Add `async def playback_control(inp: PlaybackControlInput) -> str` to `playback.py`:
- Auto-resolve session: if `client=None` and exactly 1 session → use it; else `MULTIPLE_SESSIONS` error
- `client` specified → find matching session by `session.player.title`
- Dry-run (confirmed=False) → `format_dry_run(data)` showing what will happen
- Confirmed: dispatch by action:
  - `pause` → `plex_client.pause()`
  - `resume` → `plex_client.play()`
  - `stop` → `plex_client.stop()`
  - `skip_next` → `plex_client.skipNext()`
  - `skip_prev` → `plex_client.skipPrevious()`
  - `seek` → require `seek_offset_ms`, call `plex_client.seekTo(inp.seek_offset_ms)`
- Return `format_playback_success(data)` or JSON

**Verify:**
```bash
pytest tests/test_playback.py -v
# All playback tests pass (≥10 tests)
```

---

## Bunch 10: Server Entry Point + Integration

*Goal: a runnable FastMCP server with all 10 tools registered, end-to-end smoke tested.*

### Task 10.1: Server Entry Point

**Test first:**
```python
# tests/test_server.py
def test_server_module_importable():
    import plex_mcp.server  # noqa: F401

def test_mcp_app_has_all_tools(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "tok")
    monkeypatch.setenv("PLEX_SERVER", "http://localhost:32400")
    from plex_mcp.server import mcp
    tool_names = {t.name for t in mcp.list_tools()}
    expected = {
        "search_media", "browse_library", "get_media_details",
        "now_playing", "on_deck", "recently_added",
        "play_media", "playback_control",
        "get_libraries", "get_clients",
    }
    assert expected == tool_names

def test_read_only_tools_have_correct_annotations(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "tok")
    monkeypatch.setenv("PLEX_SERVER", "http://localhost:32400")
    from plex_mcp.server import mcp
    tools_by_name = {t.name: t for t in mcp.list_tools()}
    for read_only_name in ["search_media", "browse_library", "get_media_details",
                            "now_playing", "on_deck", "recently_added",
                            "get_libraries", "get_clients"]:
        tool = tools_by_name[read_only_name]
        assert tool.annotations.get("readOnlyHint") is True, f"{read_only_name} should be readOnly"

def test_mutation_tools_have_correct_annotations(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "tok")
    monkeypatch.setenv("PLEX_SERVER", "http://localhost:32400")
    from plex_mcp.server import mcp
    tools_by_name = {t.name: t for t in mcp.list_tools()}
    for mut_name in ["play_media", "playback_control"]:
        tool = tools_by_name[mut_name]
        assert tool.annotations.get("readOnlyHint") is False

def test_main_entry_point_exists():
    from plex_mcp.server import main
    assert callable(main)
```

**Implement:**  
Fill `src/plex_mcp/server.py`:
- Create `FastMCP(name="plex-mcp", version="0.1.0", description="...")`
- Register all 10 tools with `@mcp.tool(name=..., annotations={...})` decorators (per SAD §9.3)
  - All tool functions are thin wrappers: validate input schema, call `safe_tool_call(handler, inp, format)`
- `def main(): mcp.run(transport="stdio")`
- Module-level `configure_logging(get_settings())`
- Confirm `[project.scripts]` entry point in `pyproject.toml` points to `plex_mcp.server:main`

**Verify:**
```bash
pytest tests/test_server.py -v
```

---

### Task 10.2: Integration Tests

**Test first:**
```python
# tests/test_integration.py
"""
End-to-end tests: full call chain from schema → tool handler → formatter → string.
Uses mock PlexServer; no real network calls.
"""
import pytest
from unittest.mock import patch
import asyncio, json

def test_search_then_details_workflow(mock_plex_server, fake_movie):
    """Simulate: agent searches, picks top result, gets details."""
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.fetchItem.return_value = fake_movie
    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.tools.search import search_media
        from plex_mcp.tools.details import get_media_details
        from plex_mcp.schemas.inputs import SearchMediaInput, GetMediaDetailsInput

        search_result = asyncio.get_event_loop().run_until_complete(
            search_media(SearchMediaInput(query="Dune"))
        )
        assert "Dune" in search_result

        detail_result = asyncio.get_event_loop().run_until_complete(
            get_media_details(GetMediaDetailsInput(title="Dune", year=2021))
        )
        assert "🎬" in detail_result or "Dune" in detail_result

def test_play_media_workflow(mock_plex_server, fake_movie, fake_plex_client):
    """Simulate: dry-run → user confirms → play."""
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.clients.return_value = [fake_plex_client]
    mock_plex_server.fetchItem.return_value = fake_movie
    mock_plex_server.client.return_value = fake_plex_client

    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.tools.playback import play_media
        from plex_mcp.schemas.inputs import PlayMediaInput

        dry = asyncio.get_event_loop().run_until_complete(
            play_media(PlayMediaInput(title="Dune", client="Living Room TV", confirmed=False))
        )
        assert "⚠️" in dry and "confirmed=True" in dry

        confirmed = asyncio.get_event_loop().run_until_complete(
            play_media(PlayMediaInput(title="Dune", client="Living Room TV", confirmed=True))
        )
        assert "✅" in confirmed

def test_get_clients_then_play_workflow(mock_plex_server, fake_movie, fake_plex_client):
    """Simulate: agent calls get_clients to find target, then play_media."""
    mock_plex_server.clients.return_value = [fake_plex_client]
    mock_plex_server.library.search.return_value = [fake_movie]
    mock_plex_server.fetchItem.return_value = fake_movie
    mock_plex_server.client.return_value = fake_plex_client

    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.tools.libraries import get_clients
        from plex_mcp.tools.playback import play_media
        from plex_mcp.schemas.inputs import GetClientsInput, PlayMediaInput

        clients_result = asyncio.get_event_loop().run_until_complete(
            get_clients(GetClientsInput())
        )
        assert "Living Room TV" in clients_result

        play_result = asyncio.get_event_loop().run_until_complete(
            play_media(PlayMediaInput(
                title="Dune", client="Living Room TV", confirmed=True
            ))
        )
        assert "✅" in play_result

def test_error_propagation_is_user_friendly(mock_plex_server):
    """Errors should return readable markdown, not raise exceptions."""
    mock_plex_server.library.search.return_value = []
    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.tools.search import search_media
        from plex_mcp.schemas.inputs import SearchMediaInput
        result = asyncio.get_event_loop().run_until_complete(
            search_media(SearchMediaInput(query=""))
        )
    # Empty query is rejected at schema level → validation error surfaced cleanly
    # OR no results → handled gracefully; either way no exception propagates
    assert isinstance(result, str)
```

**Implement:**
- Wire up `plex_mcp.client._server` monkeypatching path properly in integration tests
- Fix any import cycles discovered during end-to-end wiring
- Ensure all 10 tool handlers properly call `get_server()` from `plex_mcp.client` (not local imports) so the `_server` patch works

**Verify:**
```bash
pytest tests/test_integration.py -v
pytest tests/ -v   # Full suite must pass: target ≥40 tests green, 0 failures
```

---

### Task 10.3: Token Budget Smoke Test

**Test first:**
```python
# tests/test_integration.py  (extend)
def rough_token_count(text: str) -> int:
    """Approximation: ~4 chars per token."""
    return len(text) // 4

def test_search_response_token_budget(mock_plex_server):
    """Default search response must stay under 500 tokens (SAD §1.4)."""
    from unittest.mock import MagicMock
    movies = [MagicMock(
        TYPE="movie", title=f"Movie {i}", year=2020+i, ratingKey=i,
        summary="A " + "word " * 30 + "summary.",
        audienceRating=7.5, duration=7200000, genres=[MagicMock(tag="Action")]
    ) for i in range(10)]
    mock_plex_server.library.search.return_value = movies
    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.tools.search import search_media
        from plex_mcp.schemas.inputs import SearchMediaInput
        result = asyncio.get_event_loop().run_until_complete(
            search_media(SearchMediaInput(query="Movie", limit=10))
        )
    tokens = rough_token_count(result)
    assert tokens <= 500, f"Search result too long: {tokens} tokens (max 500)"

def test_now_playing_empty_response_concise(mock_plex_server):
    mock_plex_server.sessions.return_value = []
    with patch("plex_mcp.client._server", mock_plex_server):
        from plex_mcp.tools.sessions import now_playing
        from plex_mcp.schemas.inputs import NowPlayingInput
        result = asyncio.get_event_loop().run_until_complete(now_playing(NowPlayingInput()))
    assert rough_token_count(result) < 100, "Empty now_playing should be very short"
```

**Implement:**
- Review formatter output lengths against SAD §5.5 token budget table
- Truncate `summary_short` to 120 chars in `SearchResult` population (already in schema)
- Trim `recently_added` grouped output; abbreviate long library names in `browse_library` table
- No functional changes needed if formatters were built correctly in Bunch 5

**Verify:**
```bash
pytest tests/test_integration.py -v
pytest tests/ --tb=short   # Complete suite: all green
```

---

## Bunch 11: Polish — Types, Lint, and Documentation

*Goal: production-ready codebase; clean mypy strict, ruff, and human-readable README.*

### Task 11.1: mypy Strict Pass

**Test first:**
```bash
# This is a static analysis task; "test first" = run mypy and capture all errors before fixing
mypy src/plex_mcp --strict --ignore-missing-imports 2>&1 | tee mypy-baseline.txt
# Target: 0 errors
```

**Implement:**
- Add explicit return type annotations to all functions that lack them
- Add `None` checks around all `getattr(item, "attr", None)` usages
- Replace bare `dict` with `dict[str, Any]` where needed
- Add `__all__` to `schemas/__init__.py`, `tools/__init__.py`, `formatters/__init__.py`
- Fix any `type: ignore` usage by finding the proper type annotation instead
- Common patterns to fix:
  - `MagicMock` in conftest: add `# type: ignore[assignment]` comments only where unavoidable
  - `plexapi` objects: use `Any` + narrow to concrete types after attribute access
  - Forward references in schemas: use `from __future__ import annotations` at top of files

**Verify:**
```bash
mypy src/plex_mcp --strict --ignore-missing-imports
# Output: "Success: no issues found in N source files"
pytest tests/ -v   # ensure no regressions
```

---

### Task 11.2: Ruff Lint + Format Pass

**Test first:**
```bash
# Capture baseline lint issues before fixing
ruff check src/ tests/ 2>&1 | tee ruff-baseline.txt
ruff format --check src/ tests/ 2>&1 | tee ruff-format-baseline.txt
```

**Implement:**
- Run `ruff check --fix src/ tests/` — auto-fix all fixable issues
- Run `ruff format src/ tests/` — apply consistent formatting
- Manually fix remaining issues (typically: unused imports, line length, `SIM` simplifications)
- Ensure `pyproject.toml` ruff config is complete:
  ```toml
  [tool.ruff.lint]
  select = ["E", "F", "I", "UP", "B", "SIM"]
  ignore = ["E501"]   # line length enforced by formatter, not linter
  
  [tool.ruff.lint.isort]
  known-first-party = ["plex_mcp"]
  ```
- Add `ruff check` and `ruff format --check` to CI (document in README)

**Verify:**
```bash
ruff check src/ tests/    # 0 errors
ruff format --check src/ tests/   # "N files would be left unchanged"
pytest tests/ -v   # still all green after formatting
```

---

### Task 11.3: README + .env.example + CHANGELOG

**Test first:**  
*(Documentation tasks have acceptance criteria, not pytest tests.)*

Acceptance criteria:
1. `README.md` exists and contains all sections below
2. `.env.example` matches `config.py` Settings fields
3. `CHANGELOG.md` has a v0.1.0 entry
4. `python -m plex_mcp.server --help` or `plex-mcp --help` does not crash (entry point wired)

**Implement:**

`README.md` must include:
- **Quick-start** (3 steps: clone, install, configure)
- **Configuration** table (all env vars from SAD §8.1)
- **MCP Client Setup** (Claude Desktop + OpenClaw JSON examples from SAD §8.3)
- **Tool Reference** table: all 10 tools, one-line purpose, read-only/mutating flag
- **Development** section: `pytest`, `mypy`, `ruff` commands
- **Confirmation Gate** explanation: why mutations require `confirmed=True` and how to use it
- **Troubleshooting** section: common errors and fixes (maps to error taxonomy in SAD §4.1)

`CHANGELOG.md`:
```markdown
# Changelog

## [0.1.0] — 2026-02-18

### Added
- `search_media` — full-text search across all libraries
- `browse_library` — paginated library browsing with sort and filter
- `get_media_details` — rich metadata, cast, file info (with `detailed=True`)
- `now_playing` — active streaming sessions
- `on_deck` — continue-watching list
- `recently_added` — new library additions
- `get_libraries` — list all Plex library sections
- `get_clients` — list available Plex player clients
- `play_media` — start playback with confirmation gate
- `playback_control` — pause/resume/stop/seek with confirmation gate
```

**Verify:**
```bash
# Check entry point is wired
pip install -e .
plex-mcp --help   # should not crash (FastMCP prints usage)

# Check README has key sections
grep -c "## " README.md   # expect ≥ 6 headings

# Final full suite
pytest tests/ -v --tb=short
mypy src/plex_mcp --strict --ignore-missing-imports
ruff check src/ tests/
```

---

## Summary Table

| Bunch | Theme | Tasks | Key Output |
|-------|-------|-------|------------|
| 1 | Project Scaffold + Config | 3 | `pyproject.toml`, `config.py`, directory tree |
| 2 | Schemas | 3 | `schemas/common.py`, `inputs.py`, `outputs.py` |
| 3 | Plex Client + Mocking | 3 | `client.py`, `conftest.py`, `resolve_media()` |
| 4 | Error Handling | 3 | `errors.py`, `safe_tool_call`, factory helpers |
| 5 | Formatters | 3 | `formatters/markdown.py`, `duration.py`, `json_fmt.py` |
| 6 | Search, Browse, Details | 3 | `tools/search.py`, `browse.py`, `details.py` |
| 7 | Sessions, Deck, Recent | 3 | `tools/sessions.py`, `deck.py` |
| 8 | get_libraries + get_clients | 2 | `tools/libraries.py` (2 new tools from FLOWS) |
| 9 | Mutation Tools | 3 | `tools/playback.py` (confirmation gate) |
| 10 | Server + Integration | 3 | `server.py`, integration tests, token budget |
| 11 | Polish | 3 | mypy clean, ruff clean, README |

**Total tasks:** 32  
**Estimated time:** 8–16 hours (15–30 min per task)  
**Test count target:** ≥50 tests by Bunch 10 completion

---

## Running the Full Suite

```bash
# From project root:
pip install -e ".[dev]"

# All tests
pytest tests/ -v

# Type check
mypy src/plex_mcp --strict --ignore-missing-imports

# Lint
ruff check src/ tests/
ruff format --check src/ tests/

# Run server (requires .env)
plex-mcp
```

---

---

## Bunch 12: Dockerfile & Container

### Task 12.1: Create Dockerfile

**Test first:** Write a test script (`tests/test_docker.sh`) that builds the image and verifies:
- Image builds successfully (`docker build -t plex-mcp .`)
- Container starts and exits cleanly when no stdin is provided (stdio transport)
- `plex-mcp --help` or `python -m plex_mcp.server` is the entrypoint
- Image size is reasonable (slim base)

**Implement:**
- Create `Dockerfile` using `python:3.11-slim` base
- Install only production deps (no dev)
- Use non-root user
- Set `ENTRYPOINT ["plex-mcp"]`
- Add `.dockerignore` (exclude tests, docs, .env, .git)

**Verify:**
```bash
docker build -t plex-mcp .
docker run --rm plex-mcp --help  # or verify it starts and waits on stdin
docker images plex-mcp --format '{{.Size}}'  # should be <150MB
```

### Task 12.2: Add docker-compose.yml for development

**Test first:** Verify `docker compose config` validates without errors.

**Implement:**
- Create `docker-compose.yml` with env_file support (`.env`)
- Map stdin/stdout for stdio transport
- Add comments explaining usage with MCP clients

**Verify:**
```bash
docker compose config  # validates
docker compose build   # builds
```

---

*Generated 2026-02-18 · References: [SAD.md](./SAD.md) · [FLOWS.md](./FLOWS.md)*
