#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/scripts/ngrok.yml"
BACKEND_PORT="${BACKEND_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"

if ! command -v ngrok >/dev/null 2>&1; then
  echo "ERROR: ngrok is not installed."
  echo "Install: https://ngrok.com/download"
  exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
  echo "ERROR: ngrok config file not found at $CONFIG_FILE"
  exit 1
fi

# Optional: allow passing token via env var without editing global config manually.
if [ -n "${NGROK_AUTHTOKEN:-}" ]; then
  ngrok config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null
fi

if ! ngrok config check >/dev/null 2>&1; then
  echo "ERROR: invalid ngrok config."
  exit 1
fi

if ! ss -tuln | grep -q ":$BACKEND_PORT "; then
  echo "WARNING: backend port $BACKEND_PORT is not listening yet."
fi

if ! ss -tuln | grep -q ":$FRONTEND_PORT "; then
  echo "WARNING: frontend port $FRONTEND_PORT is not listening yet."
fi

echo "Starting ngrok tunnels from $CONFIG_FILE ..."
echo "- backend  -> http://localhost:$BACKEND_PORT"
echo "- frontend -> http://localhost:$FRONTEND_PORT"

ngrok start --all --config "$CONFIG_FILE"
