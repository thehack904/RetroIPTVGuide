#!/bin/bash
# RetroIPTVGuide Raspberry Pi Installer (Headless, Pi3/4/5)
# Installs to /home/iptv/iptv-server for consistency with Debian/Windows
# Logs to /var/log/retroiptvguide/install-YYYYMMDD-HHMMSS.log
# License: CC BY-NC-SA 4.0

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
echo "                   RetroIPTVGuide  |  Raspberry Pi Edition (Headless)"
echo "==========================================================================="
echo ""

set -e

# --- Logging ---
LOG_DIR="/var/log/retroiptvguide"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
LOG_FILE="$LOG_DIR/install-$TIMESTAMP.log"
sudo mkdir -p "$LOG_DIR"
sudo chmod 755 "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "Log file: $LOG_FILE"
echo ""

# --- Vars ---
APP_USER="iptv"
APP_DIR="/home/$APP_USER/iptv-server"
SERVICE_FILE="/etc/systemd/system/retroiptvguide.service"
CONFIG_FILE="/boot/config.txt"

ACTION="$1"
AUTO_YES=false
AUTO_AGREE=false
for arg in "$@"; do
  case "$arg" in
    --yes|-y) AUTO_YES=true ;;
    --agree|-a) AUTO_AGREE=true ;;
  esac
done

# --- Helpers ---
set_gpu_mem() {
  local val="$1"
  if command -v raspi-config >/dev/null 2>&1; then
    sudo raspi-config nonint set_config_var gpu_mem "$val" "$CONFIG_FILE"
  else
    # Fallback: edit/append gpu_mem in /boot/config.txt
    sudo sed -i -E 's/^\s*gpu_mem\s*=.*/gpu_mem='"$val"'/g' "$CONFIG_FILE" 2>/dev/null || true
    if ! grep -qE '^\s*gpu_mem\s*=' "$CONFIG_FILE" 2>/dev/null; then
      echo "gpu_mem=$val" | sudo tee -a "$CONFIG_FILE" >/dev/null
    fi
  fi
}

ensure_owned_by_iptv() {
  sudo chown -R "$APP_USER:$APP_USER" "$APP_DIR"
}

pip_install_as_iptv() {
  local cmd="$1"
  sudo -u "$APP_USER" bash -lc "$cmd"
}

#====================== INSTALL ======================#
install_app() {
  echo ""
  echo "============================================================"
  echo " RetroIPTVGuide Raspberry Pi Headless Installer "
  echo "============================================================"
  echo ""
  echo "This installer will perform the following actions:"
  echo "  - Detect Raspberry Pi model (3, 4, or newer)"
  echo "  - Install dependencies (Python3, ffmpeg, etc.)"
  echo "  - Create system user 'iptv' (if not present)"
  echo "  - Clone RetroIPTVGuide into /home/iptv/iptv-server"
  echo "  - Configure Python virtual environment and systemd service"
  echo "  - Auto-configure GPU memory for headless operation"
  echo "  - Enable the retroiptvguide service on boot"
  echo "  - Optionally reboot when done"
  echo ""
  echo "By continuing, you agree that:"
  echo "  - This software should only be run on internal networks."
  echo "  - It must not be exposed to the public Internet."
  echo "  - You accept all risks; no warranty is provided."
  echo ""

  if [ "$AUTO_AGREE" = true ]; then
    echo "[Auto-agree] Terms accepted via --agree flag."
  else
    read -p "Do you agree to these terms? (yes/no): " agreement
    if [ "$agreement" != "yes" ]; then
      echo "Installation aborted by user."
      exit 1
    fi
    echo "Agreement accepted. Continuing..."
  fi
  echo ""

  # Detect Pi model
  PI_MODEL=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo "Unknown Model")
  if echo "$PI_MODEL" | grep -q "Raspberry Pi 5"; then
    PI_TYPE="pi5"
  elif echo "$PI_MODEL" | grep -q "Raspberry Pi 4"; then
    PI_TYPE="pi4"
  elif echo "$PI_MODEL" | grep -q "Raspberry Pi 3"; then
    PI_TYPE="pi3"
  else
    PI_TYPE="unknown"
  fi
  echo "Detected board: $PI_MODEL ($PI_TYPE)"
  echo ""

  # Create system user
  if ! id "$APP_USER" &>/dev/null; then
    echo "Creating user '$APP_USER'..."
    sudo useradd -m -r -s /usr/sbin/nologin "$APP_USER"
  fi

  # Prepare app dir
  sudo mkdir -p "$APP_DIR"
  ensure_owned_by_iptv

  # Update & deps (apt-get, script-safe)
  echo "Installing dependencies..."
  sudo apt-get update -y
  sudo apt-get dist-upgrade -y
  sudo apt-get install -y git python3 python3-venv python3-pip ffmpeg mesa-utils v4l-utils
  # raspi-config is standard on Raspberry Pi OS; on Ubuntu it may be missing (we handle fallback in set_gpu_mem)
  sudo apt-get install -y raspi-config || true

  # Clone / update repo
  if [ ! -d "$APP_DIR/.git" ]; then
    sudo -u "$APP_USER" git clone https://github.com/thehack904/RetroIPTVGuide.git "$APP_DIR"
  else
    ( cd "$APP_DIR" && sudo -u "$APP_USER" git pull )
  fi

  # Python venv & deps (as iptv user)
  if [ ! -d "$APP_DIR/venv" ]; then
    sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
  fi
  pip_install_as_iptv "source '$APP_DIR/venv/bin/activate' && pip install --upgrade pip"
  if [ -f "$APP_DIR/requirements.txt" ]; then
    pip_install_as_iptv "source '$APP_DIR/venv/bin/activate' && pip install -r '$APP_DIR/requirements.txt'"
  else
    pip_install_as_iptv "source '$APP_DIR/venv/bin/activate' && pip install Flask"
  fi

  # Ensure DB/data dirs if app expects them
  sudo -u "$APP_USER" mkdir -p "$APP_DIR/data" || true

  # GPU memory per model (headless safe)
  echo "Configuring GPU memory..."
  case "$PI_TYPE" in
    pi4|pi5) set_gpu_mem 256 ;;
    pi3|unknown|*) set_gpu_mem 128 ;;
  esac

  # systemd service
  echo "Creating systemd service..."
  sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=RetroIPTVGuide Flask Server
After=network.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python app.py
Restart=always
Environment=FLASK_RUN_PORT=5000
Environment=FLASK_RUN_HOST=0.0.0.0

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reload
  sudo systemctl enable retroiptvguide
  sudo systemctl restart retroiptvguide

  echo ""
  echo "============================================================"
  echo " Installation Complete "
  echo "============================================================"
  echo "End time: $(date)"
  echo "Access in browser: http://$(hostname -I | awk '{print $1}'):5000"
  echo "Default login: admin / strongpassword123"
  echo "NOTE: BETA build — internal network use only."
  echo "GPU accel: $PI_TYPE"
  echo "Service: retroiptvguide"
  echo "User: $APP_USER"
  echo "Install path: $APP_DIR"
  echo ""
  echo "Full log saved to: $LOG_FILE"
  echo ""

  # --- Post-install verification ---
  echo "Verifying service status..."
  sleep 3
  if systemctl is-active --quiet retroiptvguide; then
    echo "✅ Service is active."
    if curl -fs http://localhost:5000 >/dev/null 2>&1; then
      echo "✅ Web interface responding on port 5000."
    else
      echo "⚠️  Service active, but no HTTP response. Check logs in $LOG_FILE."
    fi
  else
    echo "❌ Service not active. Run: sudo systemctl status retroiptvguide"
  fi
  echo ""

  # Optional reboot prompt
  if [ "$AUTO_YES" = true ]; then
    # For unattended runs, perform a quick service check and skip reboot by default
    systemctl is-active --quiet retroiptvguide && echo "Service is active." || echo "Warning: service not active."
  else
    read -t 10 -p "Reboot now to ensure GPU memory takes effect? (Y/n, default Y in 10s): " R || R="Y"
    R=${R:-Y}
    if [[ "$R" =~ ^[Yy]$ ]]; then
      echo "Rebooting..."
      sleep 2
      sudo reboot
    else
      echo "Reboot skipped. Run 'sudo reboot' later to apply GPU memory if changed."
    fi
  fi
}

#====================== UNINSTALL ======================#
uninstall_app() {
  echo ""
  echo "============================================================"
  echo " RetroIPTVGuide Uninstaller (Headless) "
  echo "============================================================"

  if [ "$AUTO_YES" = false ]; then
    read -p "Proceed with uninstallation? (yes/no): " c
    [[ "$c" != "yes" ]] && echo "Aborted." && exit 1
  fi

  systemctl stop retroiptvguide 2>/dev/null || true
  systemctl disable retroiptvguide 2>/dev/null || true
  [ -f "$SERVICE_FILE" ] && sudo rm -f "$SERVICE_FILE" && sudo systemctl daemon-reload

  if [ -d "$APP_DIR" ]; then
    if [ "$AUTO_YES" = true ]; then
      sudo rm -rf "$APP_DIR"
      echo "Removed $APP_DIR"
    else
      read -p "Delete $APP_DIR? (yes/no): " d
      [[ "$d" == "yes" ]] && sudo rm -rf "$APP_DIR" && echo "Removed $APP_DIR"
    fi
  fi

  echo ""
  echo "Uninstallation complete. End time: $(date)"
  echo "Log file: $LOG_FILE"
  echo ""
}

#====================== MAIN ======================#
case "$ACTION" in
  install) install_app ;;
  uninstall) uninstall_app ;;
  *)
    echo "Usage: sudo $0 install|uninstall [--yes|-y] [--agree|-a]"
    exit 1
    ;;
esac
