#!/bin/bash
set -e

echo "=== RetroIPTVGuide Installer (v2.0) ==="

# Ensure script is run with sudo
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run with sudo."
   exit 1
fi

# Variables
APP_USER="iptv"
APP_HOME="/home/$APP_USER"
APP_DIR="$APP_HOME/iptv-server"
SERVICE_FILE="/etc/systemd/system/iptv-server.service"

# Create system user if not exists
if id "$APP_USER" &>/dev/null; then
    echo "User $APP_USER already exists."
else
    echo "Creating iptv system user..."
    adduser --system --home "$APP_HOME" --group "$APP_USER"
fi

# Ensure python3-venv is installed
echo "Checking for python3-venv..."
if ! dpkg -s python3-venv >/dev/null 2>&1; then
  echo "python3-venv not found. Installing..."
  apt-get update
  apt-get install -y python3-venv
else
  echo "python3-venv is already installed."
fi

# Create app directory
mkdir -p "$APP_DIR"
chown -R $APP_USER:$APP_USER "$APP_HOME"

# Copy project files into place
echo "Copying project files..."
rsync -a --exclude 'venv' ./ "$APP_DIR/"
chown -R $APP_USER:$APP_USER "$APP_DIR"

# Setup virtual environment
cd "$APP_DIR"
echo "Setting up Python virtual environment..."
sudo -u $APP_USER python3 -m venv venv

echo "Upgrading pip..."
sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade pip

echo "Installing requirements..."
sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r "$APP_DIR/requirements.txt"

# Create systemd service
echo "Creating systemd service..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=IPTV Flask Server
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
echo "Enabling and starting service..."
systemctl daemon-reload
systemctl enable iptv-server.service
systemctl restart iptv-server.service

echo "=== Installation complete! ==="
echo "Access the server in your browser at: http://<your-server-ip>:5000"
echo "Default login: admin / strongpassword123"
echo "NOTE: This is a **BETA build**. Do not expose it directly to the public internet."
