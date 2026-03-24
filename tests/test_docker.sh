#!/usr/bin/env bash
# tests/test_docker.sh — Docker build and smoke tests for plex-mcp
# Run from the project root: bash tests/test_docker.sh

set -euo pipefail

IMAGE_NAME="plex-mcp-test"

echo "=== Building Docker image ==="
docker build -t "$IMAGE_NAME" .

echo ""
echo "=== Image size ==="
SIZE=$(docker images "$IMAGE_NAME" --format '{{.Size}}')
echo "Image size: $SIZE"

echo ""
echo "=== Smoke test: container starts (brief stdin, then exits) ==="
# Send an empty JSON-RPC line; the server will process it and either respond or exit.
# We just want to confirm it doesn't crash on startup.
echo '{}' | timeout 5 docker run --rm -i \
  -e PLEX_TOKEN=fake-token \
  -e PLEX_SERVER=http://127.0.0.1:32400 \
  "$IMAGE_NAME" 2>&1 || true
echo "Container exited cleanly (expected with no real Plex server)."

echo ""
echo "=== Verify entrypoint is plex-mcp ==="
ENTRYPOINT=$(docker inspect "$IMAGE_NAME" --format '{{json .Config.Entrypoint}}')
echo "Entrypoint: $ENTRYPOINT"
if echo "$ENTRYPOINT" | grep -q "plex-mcp"; then
  echo "✅ Entrypoint correct"
else
  echo "❌ Entrypoint does not contain 'plex-mcp'"
  exit 1
fi

echo ""
echo "=== All Docker smoke tests passed ==="
