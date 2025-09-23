#!/bin/bash
set -e

echo "Installing RetroIPTVGuide..."

# Install system dependencies
sudo apt update
sudo apt install -y python3 python3-venv python3-pip

# Setup venv
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Install systemd service
sudo cp iptv-server.service /etc/systemd/system/iptv-server.service
sudo systemctl daemon-reload

echo "Installation complete. Run 'sudo systemctl start iptv-server.service' to start."
