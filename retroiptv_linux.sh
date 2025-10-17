#!/usr/bin/env bash
# retroiptv_linux.sh — Unified installer/updater/uninstaller for RetroIPTVGuide (Linux only)
# License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)

set -euo pipefail
VERSION="3.4.0-testing"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOGFILE="retroiptv_${TIMESTAMP}.log"
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

ACTION="${1:-}"; shift || true
AGREE_TERMS=false; AUTO_YES=false
for arg in "$@"; do
  case "$arg" in
    --agree|-a) AGREE_TERMS=true ;;
    --yes|-y) AUTO_YES=true ;;
  esac
done
[[ $(id -u) -ne 0 ]] && { echo "Run as root (sudo)."; exit 1; }

APP_USER="iptv"; APP_HOME="/home/$APP_USER"; APP_DIR=""
SERVICE_NAME="iptv-server"; SYSTEMD_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
LOG_DIR_LINUX="/var/log/iptv"

# --- OS detection ------------------------------------------------------------
DISTRO_ID=""
[[ -f /etc/os-release ]] && . /etc/os-release && DISTRO_ID=${ID,,}

case "$DISTRO_ID" in
  ubuntu|debian|raspbian)
    PKG_MANAGER="apt"; PKG_INSTALL="apt-get install -y"; PKG_UPDATE="apt-get update -y"; APP_DIR_DEFAULT="$APP_HOME/iptv-server" ;;
  rhel|centos|rocky|almalinux|fedora)
    PKG_MANAGER=$(command -v dnf >/dev/null 2>&1 && echo dnf || echo yum)
    PKG_INSTALL="$PKG_MANAGER install -y"; PKG_UPDATE="$PKG_MANAGER -y makecache && $PKG_MANAGER upgrade -y || true"
    APP_DIR_DEFAULT="/opt/retroiptvguide" ;;
  *) PKG_MANAGER=$(command -v apt-get >/dev/null 2>&1 && echo apt || echo dnf)
     PKG_INSTALL="$PKG_MANAGER install -y"; PKG_UPDATE="$PKG_MANAGER -y makecache || true"
     APP_DIR_DEFAULT="/opt/retroiptvguide" ;;
esac
APP_DIR="$APP_DIR_DEFAULT"

# --- Utility Functions -------------------------------------------------------
usage(){ echo "Usage: sudo $0 [install|update|uninstall] [--agree|-a] [--yes|-y]"; }

ensure_packages(){
  echo "Installing base packages..."
  local pkgs=(git curl wget rsync python3 python3-pip unzip)
  [[ "$PKG_MANAGER" == apt ]] && pkgs+=(python3-venv sqlite3) || pkgs+=(sqlite)
  [[ "$PKG_MANAGER" =~ dnf|yum ]] && pkgs+=(policycoreutils-python-utils firewalld)
  eval "$PKG_UPDATE"; eval "$PKG_INSTALL ${pkgs[*]}"
}

ensure_user(){
  echo "Ensuring system user..."
  NOLOGIN=$(command -v nologin 2>/dev/null || echo /usr/sbin/nologin)
  getent group "$APP_USER" >/dev/null || groupadd --system "$APP_USER"
  if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd -r -m -d "$APP_HOME" -s "$NOLOGIN" -g "$APP_USER" "$APP_USER"
  fi
  chmod 755 "$APP_HOME" || true
}

clone_or_stage_project(){
  mkdir -p "$APP_DIR"; chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
  TMP="/tmp/retroiptvguide"; rm -rf "$TMP"
  git clone --depth 1 -b dev https://github.com/thehack904/RetroIPTVGuide.git "$TMP"
  rsync -a --delete --exclude 'venv' "$TMP/" "$APP_DIR/"
  chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
}

make_venv_and_install(){
  echo "Setting up virtualenv..."
  sudo -u "$APP_USER" python3 -m ensurepip --upgrade 2>/dev/null || true
  sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv" || \
    { sudo -u "$APP_USER" python3 -m pip install --user virtualenv; sudo -u "$APP_USER" "$APP_HOME/.local/bin/virtualenv" "$APP_DIR/venv"; }
  sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
  sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
}

write_systemd_service(){
  echo "Creating systemd service..."
  local PYEXEC="$APP_DIR/venv/bin/python"; [[ -x "$APP_DIR/venv/bin/python3" ]] && PYEXEC="$APP_DIR/venv/bin/python3"
  cat >"$SYSTEMD_FILE"<<EOF
[Unit]
Description=IPTV Flask Server (RetroIPTVGuide)
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$PYEXEC app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
}

rhel_firewall_selinux(){
  [[ "$PKG_MANAGER" =~ dnf|yum ]] || return 0
  if systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-port=5000/tcp || true
    firewall-cmd --reload || true
  fi
  if command -v semanage >/dev/null 2>&1; then
    semanage port -a -t http_port_t -p tcp 5000 2>/dev/null || semanage port -m -t http_port_t -p tcp 5000
  fi
}

start_and_verify(){
  systemctl daemon-reload
  systemctl enable --now "$SERVICE_NAME"
  sleep 3
  if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Service active."
  else
    echo "❌ Service failed. See: sudo journalctl -u $SERVICE_NAME"
  fi
}

install_linux(){
  ensure_packages; ensure_user; clone_or_stage_project; make_venv_and_install; write_systemd_service
  rhel_firewall_selinux; start_and_verify
  echo "Installed to: $APP_DIR"
  echo "Access at: http://$(hostname -I | awk '{print $1}'):5000"
}

update_linux(){
  echo "Updating app..."
  sudo -u "$APP_USER" bash -c "cd '$APP_DIR' && git fetch --all && git reset --hard origin/main"
  systemctl daemon-reload; systemctl restart "$SERVICE_NAME"
  echo "✅ Updated and restarted."
}

uninstall_linux(){
  echo "Stopping and disabling service..."
  systemctl stop "$SERVICE_NAME" 2>/dev/null || true
  systemctl disable "$SERVICE_NAME" 2>/dev/null || true
  [[ -f "$SYSTEMD_FILE" ]] && rm -f "$SYSTEMD_FILE" && systemctl daemon-reload

  echo "Removing files..."
  rm -rf "$LOG_DIR_LINUX" 2>/dev/null || true
  [[ -d "/opt/retroiptvguide" ]] && { echo "Removing /opt/retroiptvguide ..."; rm -rf /opt/retroiptvguide; }
  [[ -d "$APP_HOME/iptv-server" ]] && { echo "Removing $APP_HOME/iptv-server ..."; rm -rf "$APP_HOME/iptv-server"; }

  echo "Removing user/group..."
  id "$APP_USER" &>/dev/null && userdel -r "$APP_USER" 2>/dev/null || true
  getent group "$APP_USER" >/dev/null && groupdel "$APP_USER" 2>/dev/null || true

  echo "✅ Uninstall complete. Logs saved to $LOGFILE."
}

case "$ACTION" in
  install) install_linux ;;
  update) update_linux ;;
  uninstall) uninstall_linux ;;
  -h|--help|help|"") usage ;;
  *) usage ;;
esac
echo "End time: $(date)"
