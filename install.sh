#!/bin/bash
set -e

VERSION="2.1.0"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOGFILE="install_${TIMESTAMP}.log"

# Log everything to file + console
exec > >(tee -a "$LOGFILE") 2>&1

echo "=== RetroIPTVGuide Installer (v$VERSION) ==="
echo "Start time: $(date)"
echo "Log file: $LOGFILE"

# --- Detect Environment ---
if grep -qi microsoft /proc/version 2>/dev/null; then
    ENVIRONMENT="WSL"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    ENVIRONMENT="GITBASH"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    ENVIRONMENT="LINUX"
else
    ENVIRONMENT="UNKNOWN"
fi

echo "Detected environment: $ENVIRONMENT"

windows_install() {
#!/usr/bin/env bash
# install.sh - Installer for RetroIPTVGuide
# Detects environment, creates venv, ensures pip is up-to-date only if needed.

set -e

echo "=== RetroIPTVGuide Installer ==="

# Detect environment
if grep -qi "microsoft" /proc/version 2>/dev/null; then
    ENVIRONMENT="WSL"
elif [ -n "$WINDIR" ] && [ -x "/bin/bash" ] && uname -s | grep -qi "mingw"; then
    ENVIRONMENT="GITBASH"
else
    ENVIRONMENT="LINUX"
fi

echo "Environment detected: $ENVIRONMENT"

# Ensure Python is available
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    echo "Python is not installed. Please install Python 3 and rerun."
    exit 1
fi

# Pick python executable
if command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    PY=python
fi

# Create virtual environment
if [ "$ENVIRONMENT" = "GITBASH" ]; then
    $PY -m venv venv
    PYTHON_BIN="$PWD/venv/Scripts/python.exe"
else
    $PY -m venv venv
    PYTHON_BIN="$PWD/venv/bin/python"
fi

# Upgrade pip only if needed
CURRENT_PIP=$($PYTHON_BIN -m pip --version | awk '{print $2}')
LATEST_PIP=$(curl -s https://pypi.org/pypi/pip/json | grep -oP '"version":\s*"\K[0-9.]+' | head -1)

if [ "$CURRENT_PIP" != "$LATEST_PIP" ] && [ -n "$LATEST_PIP" ]; then
    echo "Upgrading pip from $CURRENT_PIP to $LATEST_PIP..."
    $PYTHON_BIN -m pip install --upgrade pip
else
    echo "pip is already up-to-date ($CURRENT_PIP)"
fi

# Install requirements
$PYTHON_BIN -m pip install -r requirements.txt

}


linux_install(){
# Ensure script is run with sudo on Linux/WSL
if [[ "$ENVIRONMENT" == "LINUX" || "$ENVIRONMENT" == "WSL" ]]; then
    if [[ $EUID -ne 0 ]]; then
        echo "This script must be run with sudo."
        exit 1
    fi
fi

# Variables
APP_USER="iptv"
APP_HOME="/home/$APP_USER"
APP_DIR="$APP_HOME/iptv-server"
SERVICE_FILE="/etc/systemd/system/iptv-server.service"

# --- Linux/WSL Install Path ---
if [[ "$ENVIRONMENT" == "LINUX" || "$ENVIRONMENT" == "WSL" ]]; then
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

    # Copy project files
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

# --- Git Bash Path ---
elif [[ "$ENVIRONMENT" == "GITBASH" ]]; then
    echo "Running in Git Bash on Windows."
    echo "Assuming Python was installed by the PowerShell bootstrap."
    if ! command -v python >/dev/null 2>&1; then
        echo "Error: Python not found in PATH. Please install Python 3 manually."
        exit 1
    fi
    echo "Setting up Python virtual environment..."
    python -m venv venv
    source venv/Scripts/activate
    echo "Upgrading pip..."
    pip install --upgrade pip
    echo "Installing requirements..."
    pip install -r requirements.txt
    echo "Starting RetroIPTVGuide in development mode..."
    python app.py &
else
    echo "Unsupported environment: $OSTYPE"
    exit 1
fi
}

if [ "$ENVIRONMENT" = "GITBASH" ]; then
    windows_install
else
    linux_install
fi
