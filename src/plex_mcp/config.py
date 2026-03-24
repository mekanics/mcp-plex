"""Configuration module for plex-mcp.

Settings are loaded from environment variables and optional .env file.
The PLEX_TOKEN is intentionally hidden from repr/str output.

Note: configure_logging() should be called from server.py main(), not at import time,
to avoid side effects during testing.
"""

import logging
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    plex_token: str = Field(..., description="Plex authentication token (X-Plex-Token)")
    plex_server: str = Field(
        ..., description="Plex server base URL, e.g. http://192.168.1.10:32400"
    )
    plex_connect_timeout: int = Field(default=10, description="Connection timeout in seconds")
    plex_request_timeout: int = Field(default=30, description="Per-request timeout in seconds")
    log_level: str = Field(default="WARNING")

    def __repr__(self) -> str:
        return f"Settings(plex_server={self.plex_server!r}, log_level={self.log_level!r})"

    def __str__(self) -> str:
        return self.__repr__()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()  # type: ignore[call-arg]  # fields loaded from env/dotenv


def configure_logging(settings: Settings) -> None:
    """Configure Python logging. Call from server.py main(), not at import time."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.WARNING),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
