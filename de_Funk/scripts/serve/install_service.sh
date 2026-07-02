#!/usr/bin/env bash
# Install and enable the de_funk API as a systemd user service.
# Runs at user login without root — no sudo required.
#
# Usage: bash scripts/serve/install_service.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/defunk-api.service"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

mkdir -p "$SYSTEMD_USER_DIR"

# Substitute actual home path into service file
sed "s|%h|$HOME|g" "$SERVICE_FILE" > "$SYSTEMD_USER_DIR/defunk-api.service"

systemctl --user daemon-reload
systemctl --user enable defunk-api
systemctl --user start  defunk-api

echo ""
echo "de_funk API service installed."
echo ""
echo "Status:  systemctl --user status defunk-api"
echo "Logs:    journalctl --user -u defunk-api -f"
echo "Stop:    systemctl --user stop defunk-api"
echo "Disable: systemctl --user disable defunk-api"
echo ""
echo "Health check: curl http://localhost:8765/api/health"
