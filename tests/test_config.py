import pytest
from pydantic import ValidationError


def test_package_importable():
    import plex_mcp  # noqa: F401


def test_submodules_importable():
    from plex_mcp import client, config, errors  # noqa: F401
    from plex_mcp.formatters import duration, markdown  # noqa: F401
    from plex_mcp.schemas import common, inputs, outputs  # noqa: F401
    from plex_mcp.tools import browse, deck, details, playback, search, sessions  # noqa: F401


def test_settings_requires_plex_token(monkeypatch):
    monkeypatch.delenv("PLEX_TOKEN", raising=False)
    monkeypatch.delenv("PLEX_SERVER", raising=False)
    with pytest.raises(ValidationError):
        from plex_mcp.config import Settings

        Settings(_env_file=None)


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


def test_get_settings_returns_same_instance(monkeypatch):
    monkeypatch.setenv("PLEX_TOKEN", "tok")
    monkeypatch.setenv("PLEX_SERVER", "http://localhost:32400")
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

    importlib.reload(cfg_mod)  # trigger module-level logging setup
    # No exceptions thrown; log level applied
