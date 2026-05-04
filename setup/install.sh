#!/bin/bash
set -e

SERVICE_NAME="phone-call-light"

echo "=== Phone Call Light — Setup ==="

# Always work from the repo root (parent of setup/)
INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "Install directory: $INSTALL_DIR"

# Create virtualenv and install dependencies
echo "Installing Python dependencies ..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# Set auth token
echo ""
read -rp "Auth token (Enter = keep 'change-me-please'): " TOKEN
TOKEN="${TOKEN:-change-me-please}"

# Patch the service file with the chosen token, then install it
SERVICE_SRC="$INSTALL_DIR/setup/$SERVICE_NAME.service"
SERVICE_DEST="/etc/systemd/system/$SERVICE_NAME.service"

# Update WorkingDirectory and ExecStart to match actual install location
sudo sed \
    -e "s|change-me-please|$TOKEN|g" \
    -e "s|/home/pi/phone-call-light|$INSTALL_DIR|g" \
    "$SERVICE_SRC" | sudo tee "$SERVICE_DEST" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo ""
echo "=== Done! ==="
echo "Install dir: $INSTALL_DIR"
echo "Server running on port 5000"
echo "Auth token: $TOKEN"
echo ""
echo "Check status: sudo systemctl status $SERVICE_NAME"
echo "View logs:    journalctl -u $SERVICE_NAME -f"
