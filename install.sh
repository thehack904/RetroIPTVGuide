#!/bin/bash
set -e

# Create iptv system user if missing
if ! id -u iptv >/dev/null 2>&1; then
    echo "Creating iptv system user..."
    sudo adduser --system --home /home/iptv --group iptv
fi

# Ensure home and project directory exist
sudo mkdir -p /home/iptv/iptv-server
sudo chown -R iptv:iptv /home/iptv

# Copy project files from current repo directory into /home/iptv/iptv-server
SRC_DIR="$(pwd)"
echo "Copying project files from $SRC_DIR to /home/iptv/iptv-server..."
sudo rsync -a --exclude 'venv' "$SRC_DIR/" /home/iptv/iptv-server/
sudo chown -R iptv:iptv /home/iptv/iptv-server

# Switch to iptv user for installation
sudo -u iptv bash <<'EOF'
cd /home/iptv/iptv-server

# Setup venv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
EOF

# Install systemd service
sudo cp /home/iptv/iptv-server/iptv-server.service /etc/systemd/system/iptv-server.service
sudo systemctl daemon-reload
sudo systemctl enable iptv-server.service
sudo systemctl start iptv-server.service

echo "✅ IPTV server installed and running at http://<your-server-ip>:5000"

