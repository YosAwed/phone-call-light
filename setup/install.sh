#!/bin/bash
set -e

REPO="yosawed/phone-call-light"
BRANCH="master"
INSTALL_DIR="/home/pi/phone-call-light"
SERVICE_NAME="phone-call-light"

echo "=== Phone Call Light — Setup ==="

# If run from inside the cloned repo, use those files; otherwise clone from GitHub
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ "$SRC_DIR" != "$INSTALL_DIR" ]; then
    echo "Copying files to $INSTALL_DIR ..."
    sudo mkdir -p "$INSTALL_DIR"
    sudo cp -r "$SRC_DIR/." "$INSTALL_DIR/"
    sudo chown -R pi:pi "$INSTALL_DIR"
fi

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
sudo sed "s/change-me-please/$TOKEN/g" "$SERVICE_SRC" | sudo tee "$SERVICE_DEST" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo ""
echo "=== Done! ==="
echo "Server running on port 5000"
echo "Auth token: $TOKEN"
echo ""
echo "Check status: sudo systemctl status $SERVICE_NAME"
echo "View logs:    journalctl -u $SERVICE_NAME -f"
