#!/usr/bin/env bash
# retroiptv_linux.sh — Unified installer/updater/uninstaller for RetroIPTVGuide (Linux only)
# Version: 3.2.0
# License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
#
# Usage:
#   sudo ./retroiptv_linux.sh install [--agree|-a] [--yes|-y]
#   sudo ./retroiptv_linux.sh uninstall [--yes|-y]
#   sudo ./retroiptv_linux.sh update
#   ./retroiptv_linux.sh --help
#
# Notes:
# - Designed for Debian/Ubuntu and RHEL-family (Rocky/Alma/CentOS Stream/Fedora).
# - Run with sudo for full install/uninstall.

set -euo pipefail

VERSION="3.2.0"
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
printf "===========================================================================\n"
echo "                   RetroIPTVGuide  |  Linux Edition (Headless)"
printf "===========================================================================\n\n"

echo "=== RetroIPTVGuide Unified Script (v$VERSION) ==="
echo "Start time: $(date)"
echo "Log file: $LOGFILE"

# --- Globals ---
ACTION="${1:-}"
shift || true
AGREE_TERMS=false
AUTO_YES=false

for arg in "$@"; do
  case "$arg" in
    --agree|-a) AGREE_TERMS=true ;;
    --yes|-y) AUTO_YES=true ;;
  esac
done

if [[ $(id -u) -ne 0 ]]; then
  echo "ERROR: This script must be run as root (use sudo)."
  exit 1
fi

APP_USER="iptv"
APP_HOME="/home/$APP_USER"
APP_DIR="$APP_HOME/iptv-server"
SERVICE_NAME="iptv-server"
SYSTEMD_FILE="/etc/systemd/system/${SERVICE_NAME}.service"  # /etc works on both Debian & RHEL for local units
LOG_DIR_LINUX="/var/log/iptv"

# --- OS & package-manager detection ---
DISTRO_ID=""
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  DISTRO_ID=${ID,,}
fi

PKG_MANAGER=""
PKG_INSTALL=""
PKG_UPDATE=""
PKG_REMOVE=""

case "$DISTRO_ID" in
  ubuntu|debian|raspbian)
    PKG_MANAGER="apt"
    PKG_INSTALL="apt-get install -y"
    PKG_UPDATE="apt-get update -y"
    PKG_REMOVE="apt-get remove -y"
    ;;
  rhel|centos|rocky|almalinux|fedora)
    if command -v dnf >/dev/null 2>&1; then
      PKG_MANAGER="dnf"
      PKG_INSTALL="dnf install -y"
      PKG_UPDATE="dnf -y makecache && dnf upgrade -y || true"
      PKG_REMOVE="dnf remove -y"
    else
      PKG_MANAGER="yum"
      PKG_INSTALL="yum install -y"
      PKG_UPDATE="yum makecache -y && yum update -y || true"
      PKG_REMOVE="yum remove -y"
    fi
    ;;
  *)
    echo "⚠️  Unsupported or unknown distribution. Proceeding best-effort."
    if command -v apt-get >/dev/null 2>&1; then
      PKG_MANAGER="apt"; PKG_INSTALL="apt-get install -y"; PKG_UPDATE="apt-get update -y"; PKG_REMOVE="apt-get remove -y"
    elif command -v dnf >/dev/null 2>&1; then
      PKG_MANAGER="dnf"; PKG_INSTALL="dnf install -y"; PKG_UPDATE="dnf -y makecache && dnf upgrade -y || true"; PKG_REMOVE="dnf remove -y"
    elif command -v yum >/dev/null 2>&1; then
      PKG_MANAGER="yum"; PKG_INSTALL="yum install -y"; PKG_UPDATE="yum makecache -y && yum update -y || true"; PKG_REMOVE="yum remove -y"
    else
      echo "❌ No supported package manager found (apt, dnf, yum)."; exit 1
    fi
    ;;
esac

# --- Helpers ---
usage() {
  local SCRIPT_NAME
  SCRIPT_NAME=$(basename "$0")
  echo -e "\033[1;33mRetroIPTVGuide Unified Installer/Updater/Uninstaller (v$VERSION)\033[0m\n"
  echo -e "Usage:"
  echo -e "  \033[1;32msudo $SCRIPT_NAME install [--agree|-a] [--yes|-y]\033[0m   Install RetroIPTVGuide"
  echo -e "  \033[1;32msudo $SCRIPT_NAME uninstall [--yes|-y]\033[0m             Uninstall RetroIPTVGuide"
  echo -e "  \033[1;32msudo $SCRIPT_NAME update\033[0m                            Update RetroIPTVGuide from GitHub"
  echo -e "  \033[1;32m$SCRIPT_NAME --help\033[0m                                Show this help\n"
  echo "Flags:"
  echo "  --agree, -a    Automatically agree to the license terms"
  echo "  --yes, -y      Run non-interactively, auto-proceed on all prompts"
  echo ""
  echo "Examples:"
  echo -e "  \033[1;36msudo $SCRIPT_NAME install --agree --yes\033[0m"
  echo -e "  \033[1;36msudo $SCRIPT_NAME uninstall --yes\033[0m"
  echo -e "  \033[1;36msudo $SCRIPT_NAME update\033[0m\n"
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
  echo "  - Ensure runtime dependencies are installed (Python, pip, git, curl, rsync, etc.)"
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
  read -rp "Do you agree to these terms? (yes/no): " agreement
  if [[ "$agreement" != "yes" ]]; then
    echo "Installation aborted by user."
    exit 1
  fi
}

ensure_packages() {
  echo "=== Updating package cache..."
  eval "$PKG_UPDATE" || true

  echo "=== Installing required packages..."
  local pkgs=(git curl wget rsync python3 python3-pip unzip)

  # Debian-only helper for venv package; RHEL typically doesn't need a separate venv rpm
  if [[ "$PKG_MANAGER" == "apt" ]]; then
    pkgs+=(python3-venv)
  fi

  # SQLite package name differs
  if [[ "$PKG_MANAGER" == "apt" ]]; then
    pkgs+=(sqlite3)
  else
    pkgs+=(sqlite)
  fi

  # Tools that help with SELinux/firewalld on RHEL-based
  if [[ "$PKG_MANAGER" == "dnf" || "$PKG_MANAGER" == "yum" ]]; then
    pkgs+=(policycoreutils-python-utils firewalld) || true
  fi

  eval "$PKG_INSTALL ${pkgs[*]}"
}

ensure_user() {
  echo "=== Creating system user ($APP_USER) if needed..."
  if id "$APP_USER" &>/dev/null; then
    echo "User $APP_USER already exists."
    if [[ "$AUTO_YES" != true ]]; then
      read -rp "Reuse existing user $APP_USER? (yes/no): " reuse
      [[ "$reuse" != "yes" ]] && exit 1
    fi
  else
    if command -v adduser >/dev/null 2>&1; then
      adduser --system --home "$APP_HOME" --group "$APP_USER"
    else
      # RHEL-friendly
      useradd -r -m -d "$APP_HOME" -s /sbin/nologin -U "$APP_USER"
    fi
    echo "Created system user: $APP_USER"
  fi
}

clone_or_stage_project() {
  echo "=== Preparing application directory: $APP_DIR"
  mkdir -p "$APP_DIR"
  chown -R "$APP_USER":"$APP_USER" "$APP_HOME"

  local TMP_CLONE_DIR="/tmp/retroiptvguide"
  cd /tmp

  if [[ ! -f requirements.txt ]]; then
    if command -v git >/dev/null 2>&1; then
      echo "Project files not found locally — cloning RetroIPTVGuide (dev branch)..."
      rm -rf "$TMP_CLONE_DIR"
      git clone --depth 1 -b dev https://github.com/thehack904/RetroIPTVGuide.git "$TMP_CLONE_DIR"
      SCRIPT_DIR=$(realpath "$TMP_CLONE_DIR")
    else
      echo "ERROR: requirements.txt not found and git is not installed."
      echo "Please install git or run this script from within a cloned RetroIPTVGuide repo."
      exit 1
    fi
  else
    SCRIPT_DIR=$(realpath "$(pwd)")
  fi

  echo "Copying project files from: $SCRIPT_DIR"
  rsync -a --delete --exclude 'venv' "$SCRIPT_DIR/" "$APP_DIR/" || {
    echo "❌ ERROR: rsync failed to copy project files."; exit 1; }
  chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
}

make_venv_and_install() {
  echo "=== Ensuring Python virtual environment..."
  if [[ -d "$APP_DIR/venv" && "$AUTO_YES" == true ]]; then
    echo "Existing venv detected — auto-reusing (--yes)."
  else
    if sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv" 2>/dev/null; then
      :
    else
      echo "⚠️  python3 -m venv failed — attempting virtualenv via pip."
      sudo -u "$APP_USER" python3 -m pip install --user --upgrade virtualenv
      sudo -u "$APP_USER" "$APP_HOME/.local/bin/virtualenv" "$APP_DIR/venv"
    fi
  fi

  echo "=== Installing Python dependencies..."
  sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
  sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
}

write_systemd_service() {
  echo "=== Writing systemd service: $SYSTEMD_FILE"
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
}

rhel_network_adjustments() {
  # Firewalld & SELinux helpers for RHEL-family
  if systemctl is-active --quiet firewalld; then
    echo "=== Configuring firewalld (opening TCP/5000)"
    firewall-cmd --permanent --add-port=5000/tcp || true
    firewall-cmd --reload || true
  fi

  if command -v getenforce >/dev/null 2>&1 && [[ $(getenforce) == "Enforcing" ]]; then
    echo "=== Configuring SELinux for TCP/5000"
    if command -v semanage >/dev/null 2>&1; then
      semanage port -a -t http_port_t -p tcp 5000 2>/dev/null || \
      semanage port -m -t http_port_t -p tcp 5000 || true
    else
      echo "⚠️  'semanage' not available. Install policycoreutils-python-utils if needed."
    fi
  fi
}

start_service_and_verify() {
  echo "=== Enabling and starting service..."
  systemctl daemon-reload
  systemctl enable ${SERVICE_NAME}.service
  systemctl restart ${SERVICE_NAME}.service

  echo "\nVerifying service status..."
  sleep 3
  if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "✅ Service is active."
    echo "Waiting for web interface to start..."
    local wait_time=0
    local max_wait=15

    if command -v curl >/dev/null 2>&1; then
      while [[ $wait_time -lt $max_wait ]]; do
        if curl -fs http://127.0.0.1:5000 >/dev/null 2>&1; then
          echo "✅ Web interface responding on port 5000 (after ${wait_time}s)." | tee -a "$LOGFILE"
          break
        fi
        sleep 2; wait_time=$((wait_time+2))
      done
    elif command -v wget >/dev/null 2>&1; then
      while [[ $wait_time -lt $max_wait ]]; do
        if wget -q --spider http://127.0.0.1:5000 2>/dev/null; then
          echo "✅ Web interface responding on port 5000 (after ${wait_time}s)." | tee -a "$LOGFILE"
          break
        fi
        sleep 2; wait_time=$((wait_time+2))
      done
    else
      echo "⚠️  Neither curl nor wget found; skipping HTTP check."; wait_time=$max_wait
    fi

    if [[ $wait_time -ge $max_wait ]]; then
      echo "⚠️  Service active, but no HTTP response after ${max_wait}s. Check logs in $LOGFILE." | tee -a "$LOGFILE"
      echo "⚠️  Possible slow startup on first run (SQLite or dependencies still initializing)." | tee -a "$LOGFILE"
    fi
  else
    echo "❌ Service not active. Run: sudo systemctl status ${SERVICE_NAME}"
  fi
}

install_linux() {
  agree_terms
  ensure_packages
  ensure_user
  clone_or_stage_project
  make_venv_and_install
  write_systemd_service
  # RHEL-specific network tweaks if we're on dnf/yum systems
  if [[ "$PKG_MANAGER" == "dnf" || "$PKG_MANAGER" == "yum" ]]; then
    rhel_network_adjustments
  fi
  start_service_and_verify

  # --- Install management script globally ---
  local LOCAL_SCRIPT_PATH="/usr/local/bin/retroiptv_linux.sh"
  echo "\n=== Installing management script to $LOCAL_SCRIPT_PATH ..."
  if [[ -f "$0" ]]; then
    cp "$0" "$LOCAL_SCRIPT_PATH"
  else
    curl -sSLo "$LOCAL_SCRIPT_PATH" "https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/refs/heads/dev/retroiptv_linux.sh"
  fi
  chmod +x "$LOCAL_SCRIPT_PATH"; chown root:root "$LOCAL_SCRIPT_PATH"
  ln -sf "$LOCAL_SCRIPT_PATH" /usr/local/bin/retroiptv

  echo "✅ Installed management script globally. You can now run:"
  echo "   sudo retroiptv install --agree --yes"
  echo "   sudo retroiptv update"
  echo "   sudo retroiptv uninstall --yes"

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
  echo "=== Stopping and disabling ${SERVICE_NAME}.service ..."
  systemctl stop ${SERVICE_NAME}.service 2>/dev/null || true
  systemctl disable ${SERVICE_NAME}.service 2>/dev/null || true

  echo "=== Removing systemd unit ..."
  if [[ -f "$SYSTEMD_FILE" ]]; then
    rm -f "$SYSTEMD_FILE"
    systemctl daemon-reload
  fi

  echo "=== Removing logs and user..."
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

update_linux() {
  echo "\n=== Updating RetroIPTVGuide from GitHub ==="
  echo "Working directory: $APP_DIR"
  if [[ ! -d "$APP_DIR/.git" ]]; then
    echo "❌ ERROR: $APP_DIR is not a valid Git repository."
    echo "Cannot update automatically. Please reinstall or clone manually."
    exit 1
  fi

  echo "Fetching latest code from origin/main..."
  sudo -u "$APP_USER" bash -H -c "cd '$APP_DIR' && git fetch --all && git reset --hard origin/main" | tee -a "$LOGFILE"

  echo "Reloading and restarting service..."
  systemctl daemon-reload
  systemctl restart "$SERVICE_NAME".service

  if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Update complete. Service restarted successfully."
  else
    echo "⚠️  Update applied but service is not active. Run: sudo systemctl status $SERVICE_NAME"
  fi

  echo "\nFull log saved to: $LOGFILE\n"
}

case "$ACTION" in
  install) install_linux ;;
  uninstall) uninstall_linux ;;
  update) update_linux ;;
  -h|--help|help) usage ;;
  *) usage ;;
}

echo "End time: $(date)"

