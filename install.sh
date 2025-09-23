#!/bin/bash
set -e

echo "=== RetroIPTVGuide Installer (v1.1) ==="

# Create iptv system user if it doesn't exist
if ! id "iptv" &>/dev/null; then
    echo "Creating iptv system user..."
    sudo useradd -m -d /home/iptv -s /bin/bash iptv
fi

# Prepare target directory
TARGET_DIR=/home/iptv/iptv-server
sudo mkdir -p $TARGET_DIR
sudo chown -R iptv:iptv $TARGET_DIR

# Copy project files to target directory
echo "Copying files to $TARGET_DIR..."
sudo cp -r . $TARGET_DIR
cd $TARGET_DIR

# Setup virtual environment
echo "Setting up virtual environment..."
sudo -u iptv python3 -m venv venv
sudo -u iptv ./venv/bin/pip install --upgrade pip
sudo -u iptv ./venv/bin/pip install -r requirements.txt

# Install systemd service
echo "Installing systemd service..."
sudo cp iptv-server.service /etc/systemd/system/iptv-server.service
sudo systemctl daemon-reexec
sudo systemctl enable iptv-server.service
sudo systemctl restart iptv-server.service

echo "Installation complete! Access the guide at http://<server-ip>:5000"
echo "Default login: admin / admin"
