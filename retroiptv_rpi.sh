#!/bin/bash
# RetroIPTVGuide Raspberry Pi Manager (Installer + Uninstaller)
# Logs all output to /var/log/retroiptvguide/YYYYMMDD-HHMMSS.log
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
echo "                   RetroIPTVGuide  |  Raspberry Pi Edition"
echo "==========================================================================="
echo ""

set -e

# --- Logging Setup ---
LOG_DIR="/var/log/retroiptvguide"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
LOG_FILE="$LOG_DIR/install-$TIMESTAMP.log"

# Make sure log directory exists and is writable
sudo mkdir -p "$LOG_DIR"
sudo chmod 755 "$LOG_DIR"

# Redirect all stdout/stderr to tee so user sees it and it’s saved
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Log file: $LOG_FILE"
echo ""

APP_DIR="/opt/RetroIPTVGuide"
SERVICE_FILE="/etc/systemd/system/retroiptvguide.service"
CONFIG_FILE="/boot/config.txt"
USER_NAME="${SUDO_USER:-$(whoami)}"

ACTION="$1"
AUTO_YES=false
if [[ "$2" == "--yes" || "$2" == "-y" ]]; then AUTO_YES=true; fi

#======================  FUNCTIONS  ======================#
show_usage() {
  echo ""
  echo "Usage:"
  echo "  sudo ./retroiptv_rpi.sh install"
  echo "  sudo ./retroiptv_rpi.sh uninstall [--yes|-y]"
  echo ""
  exit 1
}

#----------------------------------------------------------
install_app() {
  echo ""
  echo "============================================================"
  echo " RetroIPTVGuide Raspberry Pi Installer Agreement "
  echo "============================================================"
  echo ""
  echo "This installer will perform the following actions:"
  echo "  - Detect Raspberry Pi model (3 or 4)"
  echo "  - Install dependencies (Python3, ffmpeg, etc.)"
  echo "  - Clone or update RetroIPTVGuide into /opt/RetroIPTVGuide"
  echo "  - Configure Python virtual environment and systemd service"
  echo "  - Auto-configure GPU acceleration (KMS/Fake KMS)"
  echo "  - Optionally reboot when done"
  echo ""
  read -p "Do you agree to these terms? (yes/no): " agreement
  [[ "$agreement" != "yes" ]] && echo "Installation aborted." && exit 1

  # Detect model
  PI_MODEL=$(tr -d '\0' < /proc/device-tree/model)
  if echo "$PI_MODEL" | grep -q "Raspberry Pi 4"; then PI_TYPE="pi4"
  elif echo "$PI_MODEL" | grep -q "Raspberry Pi 3"; then PI_TYPE="pi3"
  else PI_TYPE="unknown"; fi
  echo "Detected board: $PI_MODEL ($PI_TYPE)"

  sudo apt update -y && sudo apt full-upgrade -y
  sudo apt install -y git python3 python3-venv python3-pip ffmpeg mesa-utils v4l-utils raspi-config

  if [ ! -d "$APP_DIR" ]; then
    sudo git clone https://github.com/thehack904/RetroIPTVGuide.git "$APP_DIR"
  else
    cd "$APP_DIR" && sudo git pull
  fi

  cd "$APP_DIR"
  sudo python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip
  [ -f requirements.txt ] && pip install -r requirements.txt || pip install Flask
  deactivate

  sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=RetroIPTVGuide Flask Server
After=network.target
[Service]
User=$USER_NAME
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

  echo "Configuring GPU acceleration..."
  sudo usermod -aG video "$USER_NAME"
  case "$PI_TYPE" in
    pi3)
      sudo raspi-config nonint do_gldriver G1
      sudo raspi-config nonint do_memory_split 128
      grep -q "dtoverlay=vc4-fkms-v3d" "$CONFIG_FILE" || echo "dtoverlay=vc4-fkms-v3d" | sudo tee -a "$CONFIG_FILE"
      ;;
    pi4)
      sudo raspi-config nonint do_gldriver G2
      sudo raspi-config nonint do_memory_split 256
      grep -q "dtoverlay=vc4-kms-v3d" "$CONFIG_FILE" || echo "dtoverlay=vc4-kms-v3d" | sudo tee -a "$CONFIG_FILE"
      ;;
    *) sudo raspi-config nonint do_memory_split 128 ;;
  esac

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
  echo ""
  echo "Full log saved to: $LOG_FILE"
  echo ""

  read -t 10 -p "Reboot now? (Y/n, default Y in 10s): " R || R="Y"
  [[ "${R:-Y}" =~ ^[Yy]$ ]] && sudo reboot || echo "Reboot skipped."
}

#----------------------------------------------------------
uninstall_app() {
  echo ""
  echo "============================================================"
  echo " RetroIPTVGuide Uninstaller for Raspberry Pi "
  echo "============================================================"
  echo ""

  if [ "$AUTO_YES" = false ]; then
    read -p "Proceed with uninstallation? (yes/no): " c
    [[ "$c" != "yes" ]] && echo "Aborted." && exit 1
  fi

  systemctl stop retroiptvguide 2>/dev/null || true
  systemctl disable retroiptvguide 2>/dev/null || true
  [ -f "$SERVICE_FILE" ] && sudo rm -f "$SERVICE_FILE" && sudo systemctl daemon-reload

  if [ -d "$APP_DIR" ]; then
    if [ "$AUTO_YES" = true ]; then sudo rm -rf "$APP_DIR"
    else read -p "Delete $APP_DIR? (yes/no): " d && [[ "$d" == "yes" ]] && sudo rm -rf "$APP_DIR"; fi
  fi

  LOG_DIRS=("/var/log/retroiptvguide" "/tmp/retroiptvguide" "$HOME/.cache/retroiptvguide")
  for dir in "${LOG_DIRS[@]}"; do
    [ -d "$dir" ] || continue
    if [ "$AUTO_YES" = true ]; then sudo rm -rf "$dir"
    else read -p "Delete logs in $dir? (yes/no): " a && [[ "$a" == "yes" ]] && sudo rm -rf "$dir"; fi
  done

  echo ""
  echo "============================================================"
  echo " Uninstallation Complete "
  echo "============================================================"
  echo "All RetroIPTVGuide components removed."
  echo "End time: $(date)"
  echo "Log file: $LOG_FILE"
  echo ""
}

#======================  MAIN  ======================#
if [[ -z "$ACTION" ]]; then show_usage; fi
case "$ACTION" in
  install) install_app ;;
  uninstall) uninstall_app ;;
  *) show_usage ;;
esac
