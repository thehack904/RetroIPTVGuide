#!/usr/bin/env bash
# retroiptv_linux.sh — Unified installer/uninstaller for RetroIPTVGuide (Linux only)
# Version: 3.1.0
# License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
#
# Usage:
#   sudo ./retroiptv_linux.sh install [--agree|-a] [--yes|-y]
#   sudo ./retroiptv_linux.sh uninstall [--yes|-y]
#   ./retroiptv_linux.sh --help
#
# Notes:
# - Designed for Debian/Ubuntu-based Linux systems.
# - Run with sudo for full install/uninstall.

set -e

VERSION="3.1.0"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOGFILE="retroiptv_${TIMESTAMP}.log"

# Log everything to file + console
exec > >(tee -a "$LOGFILE") 2>&1

# --- Banner ---
cat <<'EOF'
░█████████                ░██                        ░██████░█████████  ░██████████░██    ░██   ░██████             ░██       ░██            
░██     ░██               ░██                          ░██  ░██     ░██     ░██    ░██    ░██  ░██   ░██                      ░██            
░██     ░██  ░███████  ░████████ ░██░████  ░███████    ░██  ░██     ░██     ░██    ░██    ░██ ░██        ░██    ░██ ░██ ░████████  ░███████  
░█████████  ░██    ░██    ░██    ░███     ░██    ░██   ░██  ░█████████      ░██    ░██    ░██ ░██  █████ ░██    ░██ ░██░██    ░██ ░██    ░██ 
░██   ░██   ░█████████    ░██    ░██      ░██    ░██   ░██  ░██             ░██     ░██  ░██  ░██     ██ ░██    ░██ ░██░██    ░██ ░█████████ 
░██    ░██  ░██           ░██    ░██      ░██    ░██   ░██  ░██             ░██      ░██░██    ░██  ░███ ░██   ░███ ░██░██   ░███ ░██        
░██     ░██  ░███████      ░████ ░██       ░███████  ░██████░██             ░██       ░███      ░█████░█  ░█████░██ ░██ ░█████░██  ░███████  
                                                                                                                                             
EOF
echo "==========================================================================="
echo "                   RetroIPTVGuide  |  Linux Edition (Headless)"
echo "==========================================================================="
echo ""

echo "=== RetroIPTVGuide Unified Script (v$VERSION) ==="
echo "Start time: $(date)"
echo "Log file: $LOGFILE"

# --- Parse Arguments ---
ACTION="$1"
shift || true
AGREE_TERMS=false
AUTO_YES=false

for arg in "$@"; do
  case "$arg" in
    --agree|-a) AGREE_TERMS=true ;;
    --yes|-y) AUTO_YES=true ;;
  esac
done

# --- Environment Check ---
if [[ $(id -u) -ne 0 ]]; then
  echo "ERROR: This script must be run as root (use sudo)."
  exit 1
fi

APP_USER="iptv"
APP_HOME="/home/$APP_USER"
APP_DIR="$APP_HOME/iptv-server"
SERVICE_NAME="iptv-server"
SYSTEMD_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
LOG_DIR_LINUX="/var/log/iptv"

usage() {
  echo -e "\033[1;33mRetroIPTVGuide Unified Installer/Uninstaller (v$VERSION)\033[0m\n"
  echo -e "Usage:"
  echo -e "  \033[1;32msudo $0 install [--agree|-a] [--yes|-y]\033[0m   Install RetroIPTVGuide"
  echo -e "  \033[1;32msudo $0 uninstall [--yes|-y]\033[0m             Uninstall RetroIPTVGuide"
  echo -e "  \033[1;32m$0 --help\033[0m                                Show this help\n"
  echo "Flags:"
  echo "  --agree, -a    Automatically agree to the license terms"
  echo "  --yes, -y      Run non-interactively, auto-proceed on all prompts"
  echo ""
  echo "Examples:"
  echo -e "  \033[1;36msudo $0 install --agree --yes\033[0m"
  echo -e "  \033[1;36msudo $0 uninstall --yes\033[0m\n"
  echo "License: CC BY-NC-SA 4.0"
}

agree_terms() {
  if [[ "$AGREE_TERMS" == true ]]; then
    echo "User pre-agreed to license terms via flag (--agree)."
    return
  fi

  echo ""
  echo "============================================================"
  echo " RetroIPTVGuide Installer Agreement "
  echo "============================================================"
  echo ""
  echo "This installer will perform the following actions:"
  echo "  - Create system user 'iptv' if not already present"
  echo "  - Ensure python3-venv package is installed"
  echo "  - Copy project files into /home/iptv/iptv-server"
  echo "  - Create a Python virtual environment & install dependencies"
  echo "  - Create, enable, and start the iptv-server systemd service"
  echo ""
  echo "By continuing, you acknowledge and agree that:"
  echo "  - This software should ONLY be run on internal networks."
  echo "  - It must NOT be exposed to the public Internet."
  echo "  - You accept all risks; the author provides NO WARRANTY."
  echo "  - The author is NOT responsible for any damage, data loss,"
  echo "    or security vulnerabilities created by this installation."
  echo ""
  read -p "Do you agree to these terms? (yes/no): " agreement
  if [[ "$agreement" != "yes" ]]; then
    echo "Installation aborted by user."
    exit 1
  fi
}

install_linux() {
  agree_terms

  echo "\n=== Creating system user ($APP_USER) if needed..."
  if id "$APP_USER" &>/dev/null; then
    echo "User $APP_USER already exists."
    if [[ "$AUTO_YES" != true ]]; then
      read -p "Reuse existing user $APP_USER? (yes/no): " reuse
      [[ "$reuse" != "yes" ]] && exit 1
    fi
  else
    adduser --system --home "$APP_HOME" --group "$APP_USER"
    echo "Created system user: $APP_USER"
  fi

  echo "\n=== Ensuring python3-venv is installed..."
  if ! dpkg -s python3-venv >/dev/null 2>&1; then
    apt-get update
    apt-get install -y python3-venv
  fi

  echo "\n=== Preparing application directory: $APP_DIR"
  mkdir -p "$APP_DIR"
  chown -R $APP_USER:$APP_USER "$APP_HOME"

  echo "\n=== Copying project files..."
  rsync -a --exclude 'venv' ./ "$APP_DIR/"
  chown -R $APP_USER:$APP_USER "$APP_DIR"

  if [[ -d "$APP_DIR/venv" && "$AUTO_YES" == true ]]; then
    echo "Existing venv detected — auto-reusing (--yes)."
  else
    echo "\n=== Creating Python virtual environment..."
    sudo -u $APP_USER python3 -m venv "$APP_DIR/venv"
  fi

  echo "\n=== Installing Python dependencies..."
  sudo -u $APP_USER "$APP_DIR/venv/bin/pip" install --upgrade pip
  sudo -u $APP_USER "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

  echo "\n=== Writing systemd service: $SYSTEMD_FILE"
  cat > "$SYSTEMD_FILE" <<EOF
[Unit]
Description=IPTV Flask Server (RetroIPTVGuide)
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

  echo "\n=== Enabling and starting service..."
  systemctl daemon-reload
  systemctl enable ${SERVICE_NAME}.service
  systemctl restart ${SERVICE_NAME}.service

  echo "
Verifying service status..."
  sleep 3
  if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "✅ Service is active."
    echo "Waiting for web interface to start..."
    wait_time=0
    max_wait=15

    if command -v curl >/dev/null 2>&1; then
      while [ $wait_time -lt $max_wait ]; do
        if curl -fs http://127.0.0.1:5000 >/dev/null 2>&1; then
          echo "✅ Web interface responding on port 5000 (after ${wait_time}s)."
          echo "✅ Verified: HTTP response received." | tee -a "$LOGFILE"
          break
        fi
        sleep 2
        wait_time=$((wait_time+2))
      done
    elif command -v wget >/dev/null 2>&1; then
      while [ $wait_time -lt $max_wait ]; do
        if wget -q --spider http://127.0.0.1:5000 2>/dev/null; then
          echo "✅ Web interface responding on port 5000 (after ${wait_time}s)."
          echo "✅ Verified: HTTP response received." | tee -a "$LOGFILE"
          break
        fi
        sleep 2
        wait_time=$((wait_time+2))
      done
    else
      echo "⚠️  Neither curl nor wget found; skipping HTTP check."
      wait_time=$max_wait
    fi

    if [ $wait_time -ge $max_wait ]; then
      echo "⚠️  Service active, but no HTTP response after ${max_wait}s. Check logs in $LOGFILE."
      echo "⚠️  Possible slow startup on first run (SQLite or dependencies still initializing)." | tee -a "$LOGFILE"
    fi
  else
    echo "❌ Service not active. Run: sudo systemctl status ${SERVICE_NAME}"
  fi

  echo ""
  echo "============================================================"
  echo " Installation Complete "
  echo "============================================================"
  echo "End time: $(date)"
  echo "Access in browser: http://$(hostname -I | awk '{print $1}'):5000"
  echo "Default login: admin / strongpassword123"
  echo "NOTE: BETA build — internal network use only."
  echo "Service: $SERVICE_NAME"
  echo "User: $APP_USER"
  echo "Install path: $APP_DIR"
  echo ""
  echo "Full log saved to: $LOGFILE"
  echo ""
}

uninstall_linux() {
  echo "\n=== Stopping and disabling ${SERVICE_NAME}.service ..."
  systemctl stop ${SERVICE_NAME}.service 2>/dev/null || true
  systemctl disable ${SERVICE_NAME}.service 2>/dev/null || true

  echo "\n=== Removing systemd unit ..."
  if [[ -f "$SYSTEMD_FILE" ]]; then
    rm -f "$SYSTEMD_FILE"
    systemctl daemon-reload
  fi

  echo "\n=== Removing logs and user..."
  rm -rf "$LOG_DIR_LINUX" 2>/dev/null || true
  if id "$APP_USER" &>/dev/null; then
    userdel -r "$APP_USER" || true
  elif [[ -d "$APP_HOME" ]]; then
    rm -rf "$APP_HOME"
  fi

  echo ""
  echo "============================================================"
  echo " Uninstallation Complete "
  echo "============================================================"
  echo "End time: $(date)"
  echo "User: $APP_USER"
  echo "Service: $SERVICE_NAME"
  echo "Removed directories: $APP_HOME, $LOG_DIR_LINUX"
  echo "Full log saved to: $LOGFILE"
  echo ""
}

case "$ACTION" in
  install)
    install_linux ;;
  uninstall)
    uninstall_linux ;;
  -h|--help|help)
    usage ;;
  *)
    usage ;;
esac

echo "\nEnd time: $(date)"
