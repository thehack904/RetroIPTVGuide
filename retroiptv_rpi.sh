#!/bin/bash
VERSION="3.1.0"  # RetroIPTVGuide Raspberry Pi installer version
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

# ============================================================
# Initialization
# ============================================================
set -e

APP_USER="iptv"
APP_DIR="/home/$APP_USER/iptv-server"
SERVICE_NAME="retroiptvguide"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CONFIG_FILE="/boot/config.txt"
SELF_LINK="/usr/local/bin/retroiptv"

TIMESTAMP="$(date +"%Y%m%d-%H%M%S")"
LOG_DIR="/var/log/retroiptvguide"
LOG_FILE="$LOG_DIR/install-$TIMESTAMP.log"

ACTION="$1"; shift || true
AUTO_YES=false
AUTO_AGREE=false

for arg in "$@"; do
  case "$arg" in
    --yes|-y) AUTO_YES=true ;;
    --agree|-a) AUTO_AGREE=true ;;
  esac
done

# ============================================================
# Utility Functions
# ============================================================
require_root() {
  [ "$EUID" -ne 0 ] && { echo "Please run as root."; exit 1; }
}

setup_logging() {
  mkdir -p "$LOG_DIR"
  chmod 755 "$LOG_DIR"
  exec > >(tee -a "$LOG_FILE") 2>&1
  echo "Log file: $LOG_FILE"
  echo ""
}

ensure_self_install() {
  local src="$(readlink -f "$0" 2>/dev/null || echo "$0")"
  if [ ! -x "$SELF_LINK" ] || ! cmp -s "$src" "$SELF_LINK"; then
    cp "$src" "$SELF_LINK"
    chmod +x "$SELF_LINK"
    echo "Installed launcher: $SELF_LINK"
    echo ""
  fi
}

ensure_user() {
  id "$APP_USER" &>/dev/null || useradd -m -r -s /usr/sbin/nologin "$APP_USER"
}

chown_appdir() { chown -R "$APP_USER:$APP_USER" "$APP_DIR"; }
pip_as_iptv() { sudo -u "$APP_USER" bash -lc "$*"; }

detect_pi_type() {
  local model
  model=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo "Unknown Model")
  if echo "$model" | grep -q "Raspberry Pi 5"; then
    PI_TYPE="pi5"
  elif echo "$model" | grep -q "Raspberry Pi 4"; then
    PI_TYPE="pi4"
  elif echo "$model" | grep -q "Raspberry Pi 3"; then
    PI_TYPE="pi3"
  else
    PI_TYPE="unknown"
  fi
  echo "Detected board: $model ($PI_TYPE)"
  echo ""
}

# Silent raspi-config + verify gpu_mem
set_gpu_mem() {
  local val="$1"
  if command -v raspi-config >/dev/null 2>&1; then
    (
      exec 1>/dev/null 2>/dev/null
      raspi-config nonint set_config_var gpu_mem "$val" "$CONFIG_FILE" || true
    )
    local current_val
    current_val=$(grep -E "^gpu_mem=" "$CONFIG_FILE" 2>/dev/null | tail -n1 | cut -d'=' -f2)
    if [ "$current_val" = "$val" ]; then
      echo "✅ Verified: gpu_mem set to ${val}MB"
    else
      echo "⚠️  Warning: Could not confirm gpu_mem=$val in $CONFIG_FILE"
    fi
  else
    sed -i -E 's/^\s*gpu_mem\s*=.*/gpu_mem='"$val"'/g' "$CONFIG_FILE" 2>/dev/null || true
    if ! grep -qE '^\s*gpu_mem\s*=' "$CONFIG_FILE" 2>/dev/null; then
      echo "gpu_mem=$val" >> "$CONFIG_FILE"
    fi
    echo "✅ Fallback: gpu_mem set to ${val}MB"
  fi
}

interactive_resource_check() {
  echo "Checking storage and memory..."
  local sd_size mem_total swap_total
  sd_size=$(df -h / | awk 'NR==2 {print $2}')
  mem_total=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
  swap_total=$(awk '/SwapTotal/ {print int($2/1024)}' /proc/meminfo)
  echo "Storage: $sd_size | RAM: ${mem_total}MB | Swap: ${swap_total}MB"
  if [ "$mem_total" -lt 1000 ] && [ "$swap_total" -lt 400 ]; then
    echo "⚠️  Low RAM/swap — recommend increasing swap to 1GB for stability."
  fi
  echo ""
}

write_service() {
  cat > "$SERVICE_FILE" <<EOF
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
  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME"
}

post_install_verify() {
  echo "Verifying service status..."
  sleep 3
  if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Service is active."
    echo "Waiting for web interface to start..."
    local wait_time=0 max_wait=15
    while [ $wait_time -lt $max_wait ]; do
      if curl -fs http://localhost:5000 >/dev/null 2>&1; then
        echo "✅ Web interface responding on port 5000 (after ${wait_time}s)."
        break
      fi
      sleep 2
      wait_time=$((wait_time+2))
    done
    [ $wait_time -ge $max_wait ] && echo "⚠️  Service active, but no HTTP response after ${max_wait}s."
  else
    echo "❌ Service not active. Check logs."
  fi
  echo ""
}

# ============================================================
# Actions
# ============================================================
do_install() {
  echo ""
  echo "This installer will perform the following actions:"
  echo "  - Detect Raspberry Pi model and set GPU memory"
  echo "  - Install dependencies (Python3, ffmpeg, etc.)"
  echo "  - Create system user 'iptv' and setup venv"
  echo "  - Configure and enable ${SERVICE_NAME} service"
  echo ""

  if [ "$AUTO_AGREE" = false ]; then
    read -p "Do you agree to these terms? (yes/no): " A
    [ "$A" = "yes" ] || { echo "Aborted."; exit 1; }
  fi

  require_root
  setup_logging
  ensure_self_install
  detect_pi_type
  [ "$AUTO_YES" = true ] || interactive_resource_check

  echo "Installing dependencies..."
  apt-get update -y && apt-get install -y git python3 python3-venv python3-pip ffmpeg mesa-utils v4l-utils raspi-config

  ensure_user
  mkdir -p "$APP_DIR"
  chown_appdir

  if [ ! -d "$APP_DIR/.git" ]; then
    sudo -u "$APP_USER" git clone https://github.com/thehack904/RetroIPTVGuide.git "$APP_DIR"
  else
    (cd "$APP_DIR" && sudo -u "$APP_USER" git pull)
  fi

  sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
  pip_as_iptv "source '$APP_DIR/venv/bin/activate' && pip install --upgrade pip && pip install -r '$APP_DIR/requirements.txt'"

  echo "Configuring GPU memory..."
  case "$PI_TYPE" in
    pi4|pi5) set_gpu_mem 256 ;;
    pi3) set_gpu_mem 128 ;;
    *) set_gpu_mem 128 ;;
  esac

  echo "Creating systemd service..."
  write_service
  systemctl restart "$SERVICE_NAME"

  echo ""
  echo "============================================================"
  echo " Installation Complete "
  echo "============================================================"
  echo "Access in your browser: http://$(hostname -I | awk '{print $1}'):5000"
  echo "Default login: admin / strongpassword123"
  echo "GPU accel: $PI_TYPE"
  echo "Service: ${SERVICE_NAME}"
  echo "Install path: $APP_DIR"
  echo ""
  post_install_verify
}

do_uninstall() {
  echo ""
  echo "============================================================"
  echo " Uninstaller Started "
  echo "============================================================"
  require_root
  setup_logging

  if [ "$AUTO_YES" = false ]; then
    read -p "Proceed with uninstallation? (yes/no): " C
    [ "$C" = "yes" ] || { echo "Aborted."; exit 1; }
  fi

  systemctl stop "$SERVICE_NAME" 2>/dev/null || true
  systemctl disable "$SERVICE_NAME" 2>/dev/null || true
  rm -f "$SERVICE_FILE"
  systemctl daemon-reload

  rm -rf "$APP_DIR"

  echo ""
  echo "============================================================"
  echo " Uninstallation Complete "
  echo "============================================================"
  echo "End time: $(date)"
  echo "Log file: $LOG_FILE"
  echo ""
}

do_update() {
  echo ""
  echo "============================================================"
  echo " Update Started "
  echo "============================================================"
  require_root
  setup_logging

  sudo -u "$APP_USER" bash -H -c "cd '$APP_DIR' && git fetch --all && git reset --hard origin/main"
  systemctl daemon-reload
  systemctl restart "${SERVICE_NAME}.service"

  echo ""
  echo "============================================================"
  echo " Update Complete "
  echo "============================================================"
  echo "Service restarted: ${SERVICE_NAME}"
  echo "Log file: $LOG_FILE"
  echo ""
}

print_usage() {
  echo "Usage: sudo $0 {install|uninstall|update} [--yes|-y] [--agree|-a]"
  echo ""
  echo "Examples:"
  echo "  sudo $0 install --agree"
  echo "  sudo $0 update"
  echo "  sudo $0 uninstall --yes"
  echo ""
}

# ============================================================
# Main
# ============================================================
case "$ACTION" in
  install) do_install ;;
  uninstall) do_uninstall ;;
  update) do_update ;;
  *) print_usage; exit 1 ;;
esac

