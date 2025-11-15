#!/bin/bash
VERSION="4.3.0"
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

# --- Helper functions ---
set_gpu_mem() {
  local val="$1"
  if command -v raspi-config >/dev/null 2>&1; then
    # Quietly apply GPU memory change and suppress unrelated warnings
    sudo raspi-config nonint set_config_var gpu_mem "$val" "$CONFIG_FILE" 2>/dev/null || true

    # Verify it was written correctly
    local current_val
    current_val=$(grep -E "^gpu_mem=" "$CONFIG_FILE" 2>/dev/null | tail -n1 | cut -d'=' -f2)
    if [ "$current_val" = "$val" ]; then
      echo "✅ Verified: GPU memory successfully set to ${val}MB" | tee -a "$LOG_FILE"
    else
      echo "⚠️  Warning: Could not confirm gpu_mem=$val in $CONFIG_FILE" | tee -a "$LOG_FILE"
    fi
  else
    # Manual fallback if raspi-config missing
    sudo sed -i -E 's/^\s*gpu_mem\s*=.*/gpu_mem='"$val"'/g' "$CONFIG_FILE" 2>/dev/null || true
    if ! grep -qE '^\s*gpu_mem\s*=' "$CONFIG_FILE" 2>/dev/null; then
      echo "gpu_mem=$val" | sudo tee -a "$CONFIG_FILE" >/dev/null
    fi
    echo "✅ Fallback: gpu_mem set manually to ${val}MB" | tee -a "$LOG_FILE"
  fi
}
ensure_owned_by_iptv() { sudo chown -R "$APP_USER:$APP_USER" "$APP_DIR"; }
pip_install_as_iptv()   { sudo -u "$APP_USER" bash -lc "$1"; }

#====================== INSTALL ======================#
install_app() {
  echo ""
  echo "============================================================"
  echo " RetroIPTVGuide Raspberry Pi Headless Installer "
  echo "============================================================"
  echo ""
  echo "This installer will perform the following actions:"
  echo "  - Detect Raspberry Pi model (3, 4, or newer)"
  echo "  - Check storage, RAM, and swap configuration"
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
    [[ "$agreement" != "yes" ]] && echo "Installation aborted." && exit 1
    echo "Agreement accepted. Continuing..."
  fi
  echo ""

  # Detect Pi model
  PI_MODEL=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo "Unknown Model")
  case "$PI_MODEL" in
    *"Raspberry Pi 5"*) PI_TYPE="pi5" ;;
    *"Raspberry Pi 4"*) PI_TYPE="pi4" ;;
    *"Raspberry Pi 3"*) PI_TYPE="pi3" ;;
    *) PI_TYPE="unknown" ;;
  esac
  echo "Detected board: $PI_MODEL ($PI_TYPE)"
  echo ""

  # Check SD card and swap
  echo "Checking storage and memory..."
  ROOT_DEV=$(df / | tail -1 | awk '{print $1}')
  SD_SIZE=$(df -h / | awk 'NR==2 {print $2}')
  MEM_TOTAL=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
  SWAP_TOTAL=$(awk '/SwapTotal/ {print int($2/1024)}' /proc/meminfo)
  echo "Root device: $ROOT_DEV"
  echo "Storage size: $SD_SIZE"
  echo "RAM: ${MEM_TOTAL}MB | Swap: ${SWAP_TOTAL}MB"
  if [ "$MEM_TOTAL" -lt 1000 ] && [ "$SWAP_TOTAL" -lt 400 ]; then
    echo "⚠️  Warning: <1GB RAM and <400MB swap — increase swap to 1GB for stability:"
    echo "   sudo dphys-swapfile swapoff && sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile && sudo dphys-swapfile setup && sudo dphys-swapfile swapon"
  fi
  if df -BG / | awk 'NR==2 {exit ($2<8)}'; then
    echo "⚠️  Warning: Root filesystem smaller than 8GB — limited space for logs/updates."
  fi
  echo ""

  # Create user if needed
  if ! id "$APP_USER" &>/dev/null; then
    echo "Creating user '$APP_USER'..."
    sudo useradd -m -r -s /usr/sbin/nologin "$APP_USER"
  fi
  sudo mkdir -p "$APP_DIR"
  ensure_owned_by_iptv

  # Update & deps
  echo "Installing dependencies..."
  sudo apt-get update -y
  sudo apt-get dist-upgrade -y
  sudo apt-get install -y git python3 python3-venv python3-pip ffmpeg mesa-utils v4l-utils raspi-config || true

  # Clone or update repo
  if [ ! -d "$APP_DIR/.git" ]; then
    sudo -u "$APP_USER" git clone https://github.com/thehack904/RetroIPTVGuide.git "$APP_DIR"
  else
    ( cd "$APP_DIR" && sudo -u "$APP_USER" git pull )
  fi

  # Python venv setup
  if [ ! -d "$APP_DIR/venv" ]; then
    sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
  fi
  pip_install_as_iptv "source '$APP_DIR/venv/bin/activate' && pip install --upgrade pip"
  if [ -f "$APP_DIR/requirements.txt" ]; then
    pip_install_as_iptv "source '$APP_DIR/venv/bin/activate' && pip install -r '$APP_DIR/requirements.txt'"
  else
    pip_install_as_iptv "source '$APP_DIR/venv/bin/activate' && pip install Flask"
  fi
  sudo -u "$APP_USER" mkdir -p "$APP_DIR/data" || true

  # GPU memory by model
  echo "Configuring GPU memory..."
  case "$PI_TYPE" in
    pi4|pi5) set_gpu_mem 256 ;;
    pi3|*)   set_gpu_mem 128 ;;
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
    echo "Waiting for web interface to start..."
    local wait_time=0
    local max_wait=15
    while [ $wait_time -lt $max_wait ]; do
      if curl -fs http://localhost:5000 >/dev/null 2>&1; then
        echo "✅ Web interface responding on port 5000 (after ${wait_time}s)."
        echo "✅ Verified: HTTP response received." | tee -a "$LOG_FILE"
        break
      fi
      sleep 2
      wait_time=$((wait_time+2))
    done
    if [ $wait_time -ge $max_wait ]; then
      echo "⚠️  Service active, but no HTTP response after ${max_wait}s. Check logs in $LOG_FILE."
      echo "⚠️  Possible slow startup on first run (SQLite or dependencies still initializing)." | tee -a "$LOG_FILE"
    fi
  else
    echo "❌ Service not active. Run: sudo systemctl status retroiptvguide"
  fi
  echo ""


  # Optional reboot
  if [ "$AUTO_YES" = false ]; then
    read -t 10 -p "Reboot now to apply GPU memory? (Y/n, default Y in 10s): " R || R="Y"
    R=${R:-Y}
    if [[ "$R" =~ ^[Yy]$ ]]; then
      echo "Rebooting..."
      sleep 2
      sudo reboot
    else
      echo "Reboot skipped. Run 'sudo reboot' later if GPU memory changed."
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
