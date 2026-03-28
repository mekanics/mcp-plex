# syntax=docker/dockerfile:1
# plex-mcp — Dockerfile
# Base: python:3.11-slim (Debian bookworm, minimal footprint)
# Runs as non-root user `appuser` for security.
# Transport: stdio (MCP standard) — container communicates via stdin/stdout.

FROM python:3.13-slim

# ── System setup ──────────────────────────────────────────────────────────────
# Create a non-root user and app directory
RUN groupadd --gid 1000 appgroup \
 && useradd  --uid 1000 --gid appgroup --no-create-home appuser

WORKDIR /app

# ── Install production dependencies ───────────────────────────────────────────
# Copy only the project definition files first (layer cache optimisation)
COPY pyproject.toml ./

# Dummy src layout required by hatchling editable install
RUN mkdir -p src/plex_mcp && touch src/plex_mcp/__init__.py

# Install production deps only (no dev extras)
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir .

# ── Copy application source ───────────────────────────────────────────────────
COPY src/ ./src/

# Re-install to register the actual source (replaces the dummy)
RUN pip install --no-cache-dir --no-deps -e .

# ── Runtime user ──────────────────────────────────────────────────────────────
USER appuser

# ── Environment defaults ──────────────────────────────────────────────────────
# These must be provided at runtime; defaults shown here for reference only.
ENV PLEX_CONNECT_TIMEOUT=10 \
    PLEX_REQUEST_TIMEOUT=30 \
    LOG_LEVEL=WARNING

# ── Entry point ───────────────────────────────────────────────────────────────
# plex-mcp reads from stdin and writes to stdout (MCP stdio transport).
# MCP clients (Claude Desktop, OpenClaw) manage stdin/stdout directly.
ENTRYPOINT ["plex-mcp"]
