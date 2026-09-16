#!/usr/bin/env bash
# retroiptv_linux.sh — Unified installer/updater/uninstaller for RetroIPTVGuide (Linux only)
# License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)

set -euo pipefail
VERSION="4.9.9"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOGFILE="retroiptv_${TIMESTAMP}.log"
exec > >(tee -a "$LOGFILE") 2>&1

echo ""
echo "=============================="
echo "---* USING MAIN BRANCH *---"
echo "=============================="
echo ""

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

APP_USER="retroiptvguide"; APP_HOME="/var/lib/$APP_USER"
APP_DIR="/opt/retroiptvguide"; CONFIG_DIR="/etc/retroiptvguide"; STATE_DIR="/var/lib/retroiptvguide"
ENV_FILE="$CONFIG_DIR/retroiptvguide.env"; LOG_DIR_LINUX="$STATE_DIR/logs"; PYCACHE_DIR="$STATE_DIR/pycache"
UPLOAD_DIR="$STATE_DIR/uploads"; AUDIO_UPLOAD_DIR="$UPLOAD_DIR/audio"; LOGO_UPLOAD_DIR="$UPLOAD_DIR/logos/virtual"
CACHE_DIR="$STATE_DIR/cache"; ROADS_CACHE_DIR="$CACHE_DIR/roads"; BASEMAP_CACHE_DIR="$CACHE_DIR/traffic_demo"
RUNTIME_DIR="/run/retroiptvguide"; STAGING_TMP_DIR="/tmp/retroiptvguide"
SERVICE_NAME="retroiptvguide"; SYSTEMD_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
LEGACY_SERVICE_NAME="iptv-server"; LEGACY_SYSTEMD_FILE="/etc/systemd/system/${LEGACY_SERVICE_NAME}.service"
LEGACY_APP_USER="iptv"; LEGACY_APP_HOME="/home/$LEGACY_APP_USER"; LEGACY_APP_DIR="$LEGACY_APP_HOME/iptv-server"
LEGACY_CONFIG_DIR="$LEGACY_APP_DIR/config"; LEGACY_RUNTIME_DIR="$LEGACY_APP_DIR/runtime"; LEGACY_LOG_DIR="/var/log/iptv"
LEGACY_AUDIO_UPLOAD_DIR="$LEGACY_APP_DIR/static/audio"; LEGACY_LOGO_UPLOAD_DIR="$LEGACY_APP_DIR/static/logos/virtual"
LEGACY_ROADS_CACHE_DIR="$LEGACY_APP_DIR/data/roads_cache"; LEGACY_BASEMAP_CACHE_DIR="$LEGACY_APP_DIR/static/maps/traffic_demo"

# --- OS detection ------------------------------------------------------------
DISTRO_ID=""
[[ -f /etc/os-release ]] && . /etc/os-release && DISTRO_ID=${ID,,}

case "$DISTRO_ID" in
  ubuntu|debian|raspbian)
    PKG_MANAGER="apt"; PKG_INSTALL="apt-get install -y"; PKG_UPDATE="apt-get update -y" ;;
  rhel|centos|rocky|almalinux|fedora)
    PKG_MANAGER=$(command -v dnf >/dev/null 2>&1 && echo dnf || echo yum)
    PKG_INSTALL="$PKG_MANAGER install -y"; PKG_UPDATE="$PKG_MANAGER -y makecache && $PKG_MANAGER upgrade -y || true" ;;
  *) PKG_MANAGER=$(command -v apt-get >/dev/null 2>&1 && echo apt || echo dnf)
     PKG_INSTALL="$PKG_MANAGER install -y"; PKG_UPDATE="$PKG_MANAGER -y makecache || true" ;;
esac

# --- Utility Functions -------------------------------------------------------
usage(){ echo "Usage: sudo $0 [install|update|uninstall|purge] [--agree|-a] [--yes|-y]"; }

agree_terms() {
  # Skip if user pre-agreed
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
  echo "  - Detect whether you are running on Linux, WSL, or Git Bash"
  echo "  - On Linux/WSL:"
  echo "      * Ensure the script is run with sudo"
  echo "      * Create dedicated system user 'retroiptvguide' (if not already present)"
  echo "      * Ensure python3-venv package is installed"
  echo "      * Copy project files into /opt/retroiptvguide"
  echo "      * Store admin-managed environment overrides in /etc/retroiptvguide"
  echo "      * Store mutable state in /var/lib/retroiptvguide"
  echo "      * Create and configure a Python virtual environment"
  echo "      * Upgrade pip and install requirements"
  echo "      * Create and enable the retroiptvguide systemd service"
  echo "      * Start the retroiptvguide service"
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

ensure_packages(){
  echo "Installing base packages..."
  local pkgs=(git curl wget rsync python3 python3-pip unzip)
  [[ "$PKG_MANAGER" == apt ]] && pkgs+=(python3-venv sqlite3) || pkgs+=(sqlite)
  [[ "$PKG_MANAGER" =~ dnf|yum ]] && pkgs+=(policycoreutils-python-utils firewalld)
  eval "$PKG_UPDATE"; eval "$PKG_INSTALL ${pkgs[*]}"
}

require_command(){
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "Required command '$cmd' is missing. Install it and re-run this script."
    exit 1
  }
}

ensure_user(){
  echo "Ensuring system user..."
  NOLOGIN=$(command -v nologin 2>/dev/null || echo /usr/sbin/nologin)
  getent group "$APP_USER" >/dev/null || groupadd --system "$APP_USER"
  if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd -r -M -d "$APP_HOME" -s "$NOLOGIN" -g "$APP_USER" "$APP_USER"
  fi
}

ensure_layout_dirs(){
  echo "Ensuring application layout..."
  install -d -m 755 -o root -g root "$APP_DIR"
  install -d -m 755 -o root -g root "$CONFIG_DIR"
  install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$STATE_DIR"
  install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$LOG_DIR_LINUX"
  install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$PYCACHE_DIR"
  install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$AUDIO_UPLOAD_DIR"
  install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$LOGO_UPLOAD_DIR"
  install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$ROADS_CACHE_DIR"
  install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$BASEMAP_CACHE_DIR"
}

write_environment_file(){
  if [[ -f "$ENV_FILE" ]]; then
    if grep -Eq '^RETROIPTV_DATA_DIR=' "$ENV_FILE"; then
      sed -i "s|^RETROIPTV_DATA_DIR=.*$|RETROIPTV_DATA_DIR=$STATE_DIR|" "$ENV_FILE"
    else
      printf '\nRETROIPTV_DATA_DIR=%s\n' "$STATE_DIR" >>"$ENV_FILE"
    fi
  else
    cat >"$ENV_FILE"<<EOF
# RetroIPTVGuide environment overrides
RETROIPTV_DATA_DIR=$STATE_DIR
EOF
  fi
  chown root:root "$ENV_FILE"
  chmod 640 "$ENV_FILE"
}

MIGRATION_MARKER="$STATE_DIR/.migration_v4.9.9"
MIGRATION_BACKUP_DIR="/var/backups/retroiptvguide-migration-${TIMESTAMP}"
MIGRATION_EXPECTED_STATE_MANIFEST="$MIGRATION_BACKUP_DIR/expected-state-files.txt"
MIGRATION_CONFLICT_DIR="$STATE_DIR/migration-conflicts/v4.9.9-${TIMESTAMP}"
MIGRATION_CONFLICT_MANIFEST="$MIGRATION_BACKUP_DIR/conflicted-state-files.txt"
MIGRATION_DETECTED=false
MIGRATION_MARKER_WRITTEN=false

migration_marker_is_valid(){
  [[ -f "$MIGRATION_MARKER" ]] && grep -Fqx "migration_version=$VERSION" "$MIGRATION_MARKER"
}

record_expected_legacy_state(){
  : > "$MIGRATION_EXPECTED_STATE_MANIFEST"
  record_expected_directory "$LEGACY_CONFIG_DIR" ""
  record_expected_directory "$LEGACY_RUNTIME_DIR" "runtime"
  record_expected_directory "$LEGACY_AUDIO_UPLOAD_DIR" "uploads/audio"
  record_expected_directory "$LEGACY_LOGO_UPLOAD_DIR" "uploads/logos/virtual"
  record_expected_directory "$LEGACY_ROADS_CACHE_DIR" "cache/roads"
  record_expected_directory "$LEGACY_BASEMAP_CACHE_DIR" "cache/traffic_demo"
}

record_expected_directory(){
  local source_dir="$1" target_prefix="$2"
  [[ -d "$source_dir" ]] || return 0
  while IFS= read -r -d '' legacy_file; do
    [[ "$source_dir" == "$LEGACY_LOGO_UPLOAD_DIR" && "$legacy_file" == "$LEGACY_LOGO_UPLOAD_DIR/icon_pack/"* ]] && continue
    local rel_path="${legacy_file#"$source_dir"/}"
    printf '%s\n' "${target_prefix:+$target_prefix/}$rel_path" >> "$MIGRATION_EXPECTED_STATE_MANIFEST"
  done < <(find "$source_dir" -type f -print0 2>/dev/null)
}

preserve_legacy_directory_conflicts(){
  local source_dir="$1" target_dir="$2" target_prefix="$3"
  [[ -d "$source_dir" ]] || return 0
  while IFS= read -r -d '' legacy_file; do
    local rel_path dest_path conflict_path
    [[ "$source_dir" == "$LEGACY_LOGO_UPLOAD_DIR" && "$legacy_file" == "$LEGACY_LOGO_UPLOAD_DIR/icon_pack/"* ]] && continue
    rel_path="${legacy_file#"$source_dir"/}"
    dest_path="$target_dir/$rel_path"

    if [[ -e "$dest_path" || -L "$dest_path" ]]; then
      conflict_path="$MIGRATION_CONFLICT_DIR/${target_prefix:+$target_prefix/}$rel_path"
      install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$(dirname "$conflict_path")"
      cp -p "$legacy_file" "$conflict_path"
      printf '%s\n' "${target_prefix:+$target_prefix/}$rel_path" >> "$MIGRATION_CONFLICT_MANIFEST"
      echo "⚠️  Migration conflict for $dest_path — keeping the existing destination file and preserving the legacy copy at $conflict_path."
    fi
  done < <(find "$source_dir" -type f -print0 2>/dev/null)
}

write_migration_marker(){
  printf 'migration_version=%s\ntimestamp=%s\nbackup_dir=%s\n' \
    "$VERSION" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$MIGRATION_BACKUP_DIR" > "$MIGRATION_MARKER"
  chown "$APP_USER":"$APP_USER" "$MIGRATION_MARKER"
  MIGRATION_MARKER_WRITTEN=true
  echo "✅ Migration marker written: $MIGRATION_MARKER"
}

cleanup_legacy_installation_if_migration_complete(){
  if migration_marker_is_valid; then
    cleanup_legacy_service_if_owned
    cleanup_legacy_app_dir_if_unshared
  elif [[ "$MIGRATION_DETECTED" == true ]]; then
    echo "Skipping legacy cleanup because the migration did not complete successfully."
  fi
}

# ---------------------------------------------------------------------------
# _migration_backup — create a timestamped tar.gz backup of all legacy paths
# before any migration step modifies or removes them.
# ---------------------------------------------------------------------------
_migration_backup(){
  echo "Creating pre-migration backup in $MIGRATION_BACKUP_DIR ..."
  install -d -m 700 -o root -g root "$MIGRATION_BACKUP_DIR"
  record_expected_legacy_state
  : > "$MIGRATION_CONFLICT_MANIFEST"

  local backup_paths=()
  [[ -d "$LEGACY_APP_DIR" ]]      && backup_paths+=("$LEGACY_APP_DIR")
  [[ -f "$LEGACY_SYSTEMD_FILE" ]] && backup_paths+=("$LEGACY_SYSTEMD_FILE")
  [[ -d "$LEGACY_LOG_DIR" ]]      && backup_paths+=("$LEGACY_LOG_DIR")

  if [[ "${#backup_paths[@]}" -eq 0 ]]; then
    echo "No legacy paths found; skipping backup."
    return
  fi

  # Tar preserves ownership, permissions, and timestamps (-p).
  if ! tar -czp \
    --exclude="$LEGACY_APP_DIR/venv" \
    -f "$MIGRATION_BACKUP_DIR/legacy-state.tar.gz" \
    "${backup_paths[@]}" 2>/dev/null; then
    echo "❌ Pre-migration backup creation failed. Migration aborted; the legacy installation was left untouched."
    return 1
  fi

  if [[ ! -s "$MIGRATION_BACKUP_DIR/legacy-state.tar.gz" ]]; then
    echo "❌ Pre-migration backup failed or produced an empty archive. Migration aborted; the legacy installation was left untouched."
    return 1
  fi

  if [[ -f "$SYSTEMD_FILE" ]]; then
    cp -p "$SYSTEMD_FILE" "$MIGRATION_BACKUP_DIR/retroiptvguide.service.bak" 2>/dev/null || true
  fi

  echo "✅ Pre-migration backup saved to $MIGRATION_BACKUP_DIR"
  echo "   Rollback: tar -xzp -f $MIGRATION_BACKUP_DIR/legacy-state.tar.gz -C /"
}

# ---------------------------------------------------------------------------
# _validate_migration — verify the target layout contains the essentials that
# were present in the legacy tree before marking the migration complete.
# ---------------------------------------------------------------------------
_validate_migration(){
  local errors=0

  [[ -d "$STATE_DIR" ]] || { echo "❌ Validation: $STATE_DIR missing."; (( errors++ )) || true; }
  [[ -f "$APP_DIR/app.py" ]] || { echo "❌ Validation: $APP_DIR/app.py missing."; (( errors++ )) || true; }
  [[ -f "$APP_DIR/requirements.txt" ]] || { echo "❌ Validation: $APP_DIR/requirements.txt missing."; (( errors++ )) || true; }
  [[ -x "$APP_DIR/venv/bin/python3" || -x "$APP_DIR/venv/bin/python" ]] || \
    { echo "❌ Validation: no Python executable found under $APP_DIR/venv/bin/."; (( errors++ )) || true; }
  [[ -f "$ENV_FILE" ]] || { echo "❌ Validation: $ENV_FILE missing."; (( errors++ )) || true; }

  # If a legacy DB existed, verify it landed in STATE_DIR.
  local legacy_db="$LEGACY_CONFIG_DIR/users.db"
  if [[ -f "$legacy_db" ]]; then
    [[ -f "$STATE_DIR/users.db" ]] || \
      { echo "❌ Validation: legacy users.db was not copied to $STATE_DIR/users.db."; (( errors++ )) || true; }
  fi

  legacy_db="$LEGACY_CONFIG_DIR/tuners.db"
  if [[ -f "$legacy_db" ]]; then
    [[ -f "$STATE_DIR/tuners.db" ]] || \
      { echo "❌ Validation: legacy tuners.db was not copied to $STATE_DIR/tuners.db."; (( errors++ )) || true; }
  fi

  if [[ -f "$MIGRATION_EXPECTED_STATE_MANIFEST" ]]; then
    while IFS= read -r rel_path; do
      local expected_path preserved_conflict_path
      [[ -n "$rel_path" ]] || continue
      expected_path="$STATE_DIR/$rel_path"
      preserved_conflict_path="$MIGRATION_CONFLICT_DIR/$rel_path"
      if [[ ! -e "$expected_path" && ! -e "$preserved_conflict_path" ]]; then
        echo "❌ Validation: expected migrated state '$rel_path' is missing from $STATE_DIR and no preserved conflict copy was found."
        (( errors++ )) || true
      fi
    done < "$MIGRATION_EXPECTED_STATE_MANIFEST"
  fi

  if [[ "$errors" -gt 0 ]]; then
    echo "Migration validation found $errors error(s). Aborting."
    echo "Restore the backup with:"
    echo "  tar -xzp -f $MIGRATION_BACKUP_DIR/legacy-state.tar.gz -C /"
    return 1
  fi

  echo "✅ Migration validation passed."
}

migrate_legacy_state_if_present(){
  local migrated=false mapping legacy_source target_dir
  require_command rsync

  # Idempotency: skip if the migration marker already exists and is current.
  if migration_marker_is_valid; then
    echo "Migration marker found ($MIGRATION_MARKER). Skipping legacy state migration."
    return
  elif [[ -f "$MIGRATION_MARKER" ]]; then
    echo "⚠️  Ignoring invalid migration marker at $MIGRATION_MARKER and retrying the legacy migration."
    rm -f "$MIGRATION_MARKER"
  fi

  # Detect whether any legacy source paths are present.
  if [[ ! -d "$LEGACY_CONFIG_DIR" && ! -d "$LEGACY_RUNTIME_DIR" && ! -d "$LEGACY_LOG_DIR" && \
        ! -d "$LEGACY_AUDIO_UPLOAD_DIR" && ! -d "$LEGACY_LOGO_UPLOAD_DIR" && \
        ! -d "$LEGACY_ROADS_CACHE_DIR" && ! -d "$LEGACY_BASEMAP_CACHE_DIR" ]]; then
    return
  fi

  MIGRATION_DETECTED=true
  echo "Legacy installation detected under $LEGACY_APP_DIR. Starting migration..."

  # Stop only the retroiptvguide service before touching files.
  echo "Stopping $SERVICE_NAME before migration..."
  systemctl stop "$SERVICE_NAME" 2>/dev/null || true

  # Backup everything before making any changes.
  _migration_backup
  preserve_legacy_directory_conflicts "$LEGACY_CONFIG_DIR" "$STATE_DIR" ""
  preserve_legacy_directory_conflicts "$LEGACY_RUNTIME_DIR" "$STATE_DIR/runtime" "runtime"
  preserve_legacy_directory_conflicts "$LEGACY_AUDIO_UPLOAD_DIR" "$AUDIO_UPLOAD_DIR" "uploads/audio"
  preserve_legacy_directory_conflicts "$LEGACY_LOGO_UPLOAD_DIR" "$LOGO_UPLOAD_DIR" "uploads/logos/virtual"
  preserve_legacy_directory_conflicts "$LEGACY_ROADS_CACHE_DIR" "$ROADS_CACHE_DIR" "cache/roads"
  preserve_legacy_directory_conflicts "$LEGACY_BASEMAP_CACHE_DIR" "$BASEMAP_CACHE_DIR" "cache/traffic_demo"

  if [[ -d "$LEGACY_CONFIG_DIR" ]]; then
    echo "Migrating legacy state from $LEGACY_CONFIG_DIR to $STATE_DIR ..."
    rsync -a --ignore-existing "$LEGACY_CONFIG_DIR/" "$STATE_DIR/"
    migrated=true
  fi

  if [[ -d "$LEGACY_RUNTIME_DIR" ]]; then
    echo "Migrating legacy runtime files from $LEGACY_RUNTIME_DIR to $STATE_DIR/runtime ..."
    install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$STATE_DIR/runtime"
    rsync -a --ignore-existing "$LEGACY_RUNTIME_DIR/" "$STATE_DIR/runtime/"
    migrated=true
  fi

  if [[ -d "$LEGACY_LOG_DIR" ]]; then
    echo "Migrating legacy logs from $LEGACY_LOG_DIR to $LOG_DIR_LINUX ..."
    rsync -a --ignore-existing "$LEGACY_LOG_DIR/" "$LOG_DIR_LINUX/"
    migrated=true
  fi

  for mapping in \
    "$LEGACY_AUDIO_UPLOAD_DIR:$AUDIO_UPLOAD_DIR" \
    "$LEGACY_LOGO_UPLOAD_DIR:$LOGO_UPLOAD_DIR" \
    "$LEGACY_ROADS_CACHE_DIR:$ROADS_CACHE_DIR" \
    "$LEGACY_BASEMAP_CACHE_DIR:$BASEMAP_CACHE_DIR"; do
    legacy_source="${mapping%%:*}"
    target_dir="${mapping#*:}"
    if [[ -d "$legacy_source" ]]; then
      echo "Migrating legacy mutable files from $legacy_source to $target_dir ..."
      if [[ "$legacy_source" == "$LEGACY_LOGO_UPLOAD_DIR" ]]; then
        rsync -a --ignore-existing --exclude 'icon_pack/' "$legacy_source/" "$target_dir/"
      else
        rsync -a --ignore-existing "$legacy_source/" "$target_dir/"
      fi
      migrated=true
    fi
  done

  if [[ "$migrated" == true ]]; then
   chown -R "$APP_USER":"$APP_USER" "$STATE_DIR"
  fi
}

clone_or_stage_project(){
  # Resolve the directory that contains this script
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  require_command rsync

  install -d -m 755 -o root -g root "$APP_DIR"

  # If the full release is already present locally (ZIP download or git clone),
  # use those files directly instead of cloning from GitHub.
  if [[ -f "$SCRIPT_DIR/app.py" && -f "$SCRIPT_DIR/requirements.txt" ]]; then
    echo "✅ Full release detected in '$SCRIPT_DIR'. Using local files."
    # Only rsync if source and destination differ; syncing a directory to itself
    # with --delete would erroneously remove files.
    if [[ "$(realpath "$SCRIPT_DIR")" != "$(realpath "$APP_DIR")" ]]; then
      rsync -a --delete --exclude 'venv' --exclude 'config' --exclude 'runtime' --exclude '*.log' "$SCRIPT_DIR/" "$APP_DIR/"
    fi
    chown -R root:root "$APP_DIR"
    link_mutable_state_dirs
    chmod 744 "$APP_DIR/retroiptv_linux.sh" "$APP_DIR/retroiptv_rpi.sh" 2>/dev/null || true
    return
  fi

  # Full repo not found locally — ask the user before cloning.
  echo ""
  echo "ℹ️  The full RetroIPTVGuide repository was not detected in the current directory."
  echo "   The installer needs to clone it from GitHub into /tmp/retroiptvguide."
  echo ""
  if [[ "$AUTO_YES" == true ]]; then
    echo "Auto-yes flag set. Proceeding with clone."
  else
    read -rp "Proceed with cloning from GitHub? (yes/no): " clone_confirm
    if [[ "$clone_confirm" != "yes" ]]; then
      echo "Installation aborted by user."
      exit 1
    fi
  fi

  TMP="/tmp/retroiptvguide"; rm -rf "$TMP"
  git clone --depth 1 -b main https://github.com/thehack904/RetroIPTVGuide.git "$TMP"
  rsync -a --delete --exclude 'venv' --exclude 'config' --exclude 'runtime' --exclude '*.log' "$TMP/" "$APP_DIR/"
  chown -R root:root "$APP_DIR"
  link_mutable_state_dirs
  chmod 744 "$APP_DIR/retroiptv_linux.sh" "$APP_DIR/retroiptv_rpi.sh" 2>/dev/null || true
}

link_mutable_state_dirs(){
  local app_path state_path mapping
  local legacy_loose_logo_dir="$APP_DIR/static/logos/virtual"
  local mutable_paths=(
    "$APP_DIR/static/audio:$AUDIO_UPLOAD_DIR"
    "$APP_DIR/static/logos/virtual/uploads:$LOGO_UPLOAD_DIR"
    "$APP_DIR/data/roads_cache:$ROADS_CACHE_DIR"
    "$APP_DIR/static/maps/traffic_demo:$BASEMAP_CACHE_DIR"
  )

  if [[ -d "$legacy_loose_logo_dir" && ! -L "$legacy_loose_logo_dir" ]]; then
    rsync -a --ignore-existing --exclude 'icon_pack/' --exclude 'uploads/' \
      "$legacy_loose_logo_dir/" "$LOGO_UPLOAD_DIR/"
  fi

  for mapping in "${mutable_paths[@]}"; do
    app_path="${mapping%%:*}"
    state_path="${mapping#*:}"
    [[ -n "$APP_DIR" && "$app_path" == "$APP_DIR/"* ]] || {
      echo "Refusing to replace mutable path outside $APP_DIR: $app_path"
      exit 1
    }
    install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$state_path"
    if [[ -d "$app_path" && ! -L "$app_path" ]]; then
      rsync -a --ignore-existing "$app_path/" "$state_path/"
    fi
    rm -rf -- "$app_path"
    install -d -m 755 -o root -g root "$(dirname "$app_path")"
    ln -s "$state_path" "$app_path"
  done
}

make_venv_and_install(){
  echo "Setting up virtualenv..."
  # Fedora/RHEL may need ensurepip to activate venv properly; Debian doesn't
  if [[ ! "$DISTRO_ID" =~ (debian|ubuntu|raspbian) ]]; then
    python3 -m ensurepip --upgrade 2>/dev/null || true
  fi
  create_virtualenv
  "$APP_DIR/venv/bin/pip" install --upgrade pip
  "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
  chown -R root:root "$APP_DIR"
}

create_virtualenv(){
  if ! python3 -m venv "$APP_DIR/venv"; then
    if command -v virtualenv >/dev/null 2>&1; then
      virtualenv "$APP_DIR/venv" || { echo "virtualenv failed to create $APP_DIR/venv."; exit 1; }
    elif python3 -m virtualenv --version >/dev/null 2>&1; then
      python3 -m virtualenv "$APP_DIR/venv" || { echo "python3 -m virtualenv failed to create $APP_DIR/venv."; exit 1; }
    else
      echo "python3 -m venv failed and no virtualenv fallback is installed. Install python3-virtualenv and re-run this script."
      exit 1
    fi
  fi
}

write_systemd_service(){
  echo "Creating systemd service..."
  local PYEXEC="$APP_DIR/venv/bin/python"; [[ -x "$APP_DIR/venv/bin/python3" ]] && PYEXEC="$APP_DIR/venv/bin/python3"
  if [[ -f "$SYSTEMD_FILE" ]] && ! service_unit_belongs_to_retroiptvguide "$SYSTEMD_FILE"; then
    echo "Refusing to overwrite existing systemd unit $SYSTEMD_FILE because it could not be verified as RetroIPTVGuide."
    exit 1
  fi
  cat >"$SYSTEMD_FILE"<<EOF
[Unit]
Description=IPTV Flask Server (RetroIPTVGuide)
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=RETROIPTV_DATA_DIR=$STATE_DIR
Environment=PYTHONPYCACHEPREFIX=$PYCACHE_DIR
EnvironmentFile=-$ENV_FILE
RuntimeDirectory=$SERVICE_NAME
ProtectSystem=strict
ReadWritePaths=$STATE_DIR
ExecStart=$PYEXEC app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
}

service_unit_belongs_to_retroiptvguide(){
  local unit_file="$1"
  [[ -f "$unit_file" ]] || return 1
  grep -Fq "RetroIPTVGuide" "$unit_file" || \
    grep -Eq '^[[:space:]]*WorkingDirectory=(/home/iptv/iptv-server|/opt/retroiptvguide)[[:space:]]*$' "$unit_file" || \
    grep -Eq '^[[:space:]]*ExecStart=(/home/iptv/iptv-server|/opt/retroiptvguide)/venv/bin/(python|python3)([[:space:]]+-[^[:space:]]+)*[[:space:]]+app\.py([[:space:]].*)?$' "$unit_file"
}

remove_unit_file_if_verified(){
  local unit_name="$1"
  local unit_file="$2"

  [[ -f "$unit_file" ]] || return 1
  if service_unit_belongs_to_retroiptvguide "$unit_file"; then
    rm -f "$unit_file"
    systemctl daemon-reload
    echo "Removed verified systemd unit: ${unit_name}.service"
    return 0
  fi

  echo "⚠️  Skipping unit removal for ${unit_name}.service because ownership could not be verified."
  return 1
}

cleanup_legacy_service_if_owned(){
  [[ -f "$LEGACY_SYSTEMD_FILE" ]] || return 0

  if service_unit_belongs_to_retroiptvguide "$LEGACY_SYSTEMD_FILE"; then
    echo "Removing legacy $LEGACY_SERVICE_NAME service owned by RetroIPTVGuide..."
    systemctl stop "$LEGACY_SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$LEGACY_SERVICE_NAME" 2>/dev/null || true
    rm -f "$LEGACY_SYSTEMD_FILE"
    systemctl daemon-reload
  else
    echo "Leaving legacy $LEGACY_SERVICE_NAME service untouched because it is not owned by RetroIPTVGuide."
  fi
}

# Returns 0 (true) if any service other than retroiptvguide is still using the
# legacy 'iptv' user or known RetroStation MC directories, meaning we must not
# delete the shared home directory tree.
legacy_iptv_dir_is_shared(){
  local rsmc_services=("retrostation-mc" "retrostation_mc" "retrostationmc" "retrostation")
  for svc in "${rsmc_services[@]}"; do
    [[ -f "/etc/systemd/system/${svc}.service" ]] && return 0
  done

  while IFS= read -r -d '' svcfile; do
    local svcname
    svcname=$(basename "$svcfile" .service)
    if [[ "$svcname" != "retroiptvguide" && "$svcname" != "$LEGACY_SERVICE_NAME" ]]; then
      grep -Eq '^[[:space:]]*User=iptv[[:space:]]*$' "$svcfile" 2>/dev/null && return 0
    fi
  done < <(find /etc/systemd/system -maxdepth 1 -name "*.service" -print0 2>/dev/null)

  local rsmc_dirs=(
    "$LEGACY_APP_HOME/RetroStationMC"
    "$LEGACY_APP_HOME/retrostation-mc"
    "$LEGACY_APP_HOME/retrostation_mc"
    "$LEGACY_APP_HOME/retrostation"
  )
  for dir in "${rsmc_dirs[@]}"; do [[ -d "$dir" ]] && return 0; done

  return 1
}

# Remove the legacy app dir and legacy log dir after state has been migrated,
# but only when no other service is sharing the 'iptv' user/home.
cleanup_legacy_app_dir_if_unshared(){
  [[ -d "$LEGACY_APP_DIR" ]] || return 0

  if legacy_iptv_dir_is_shared; then
    echo "⚠️  Another service is using the '$LEGACY_APP_USER' account — retaining $LEGACY_APP_DIR."
  else
    echo "Removing legacy app directory $LEGACY_APP_DIR (state already migrated)..."
    rm -rf "$LEGACY_APP_DIR"
    [[ -d "$LEGACY_LOG_DIR" ]] && { echo "Removing legacy log directory $LEGACY_LOG_DIR ..."; rm -rf "$LEGACY_LOG_DIR"; }
    echo "✅ Legacy directories removed."
  fi
}

safe_to_remove_dedicated_user(){
  local passwd_entry user_home remaining_owned_file
  passwd_entry=$(getent passwd "$APP_USER" 2>/dev/null || true)
  [[ -n "$passwd_entry" ]] || return 1

  user_home=$(printf '%s' "$passwd_entry" | cut -d: -f6)
  if [[ "$user_home" != "$APP_HOME" && "$user_home" != "$STATE_DIR" ]]; then
    echo "⚠️  Refusing to remove user '$APP_USER': unexpected home path '$user_home'."
    return 1
  fi

  if pgrep -u "$APP_USER" >/dev/null 2>&1; then
    echo "⚠️  Refusing to remove user '$APP_USER': active processes still running."
    return 1
  fi

  remaining_owned_file=$(find /opt /etc /var/lib /var/log /run /tmp -xdev -user "$APP_USER" -print -quit 2>/dev/null || true)
  if [[ -n "$remaining_owned_file" ]]; then
    echo "⚠️  Refusing to remove user '$APP_USER': files still owned by this account exist (e.g. $remaining_owned_file)."
    return 1
  fi

  return 0
}

print_cleanup_summary(){
  local title="$1"
  local removed_paths="$2"
  local retained_paths="$3"
  local warnings="$4"

  echo ""
  echo "============================================================"
  echo " $title "
  echo "============================================================"
  echo "Removed paths/resources:"
  [[ -n "$removed_paths" ]] && printf '%s\n' "$removed_paths" || echo "  (none)"
  echo "Retained paths/resources:"
  [[ -n "$retained_paths" ]] && printf '%s\n' "$retained_paths" || echo "  (none)"
  if [[ -n "$warnings" ]]; then
    echo "Warnings:"
    printf '%s\n' "$warnings"
  fi
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

revert_firewall_selinux(){
  echo "Reverting firewall and SELinux changes (if applicable)..."

  if command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld; then
    echo " - Removing TCP port 5000 rule from firewalld"
    firewall-cmd --permanent --remove-port=5000/tcp 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
  fi

  if command -v ufw >/dev/null 2>&1; then
    if ufw status | grep -q "5000/tcp"; then
      echo " - Removing TCP port 5000 rule from UFW"
      ufw delete allow 5000/tcp >/dev/null 2>&1 || true
    fi
  fi

  if command -v semanage >/dev/null 2>&1; then
    echo " - Removing SELinux http_port_t mapping for TCP/5000"
    semanage port -d -t http_port_t -p tcp 5000 2>/dev/null || true
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
  agree_terms
  ensure_packages; ensure_user; ensure_layout_dirs; migrate_legacy_state_if_present; clone_or_stage_project
  make_venv_and_install; write_environment_file; write_systemd_service; _validate_migration
  [[ "$MIGRATION_DETECTED" == true ]] && write_migration_marker
  rhel_firewall_selinux; start_and_verify
  cleanup_legacy_installation_if_migration_complete
  echo "Installed to: $APP_DIR"
  echo "Configuration directory: $CONFIG_DIR"
  echo "State directory: $STATE_DIR"
  echo "End time: $(date)"
  echo "Access at: http://$(hostname -I | awk '{print $1}'):5000"
  echo "Default login: admin / strongpassword123"
  echo "Security Notice: Do not expose this service directly to the public internet."
  echo "Installation complete!"
}

update_linux(){
  echo "Updating app..."
  ensure_user; ensure_layout_dirs
  migrate_legacy_state_if_present
  if [[ -d "$APP_DIR/.git" ]]; then
    chown -R root:root "$APP_DIR"
    bash -c "cd '$APP_DIR' && git fetch --all && git reset --hard origin/main"
    link_mutable_state_dirs
  else
    clone_or_stage_project
  fi
  write_environment_file
  echo "Updating Python dependencies..."
  if [[ -d "$APP_DIR/venv" ]]; then
    :
  else
    echo "⚠️  No venv found -- recreating..."
    create_virtualenv
  fi
  "$APP_DIR/venv/bin/pip" install --upgrade pip
  "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
  chown -R root:root "$APP_DIR"
  write_systemd_service
  _validate_migration
  [[ "$MIGRATION_DETECTED" == true ]] && write_migration_marker
  systemctl daemon-reload; systemctl enable "$SERVICE_NAME"; systemctl restart "$SERVICE_NAME"
  cleanup_legacy_installation_if_migration_complete
  echo "✅ Updated and restarted."
}

uninstall_linux(){
  local removed_summary="" retained_summary="" warning_summary=""
  local modern_resources_present=false legacy_only_resources_present=false

  [[ -d "$APP_DIR" || -f "$SYSTEMD_FILE" ]] && modern_resources_present=true
  [[ "$modern_resources_present" == false && ( -d "$LEGACY_APP_DIR" || -f "$LEGACY_SYSTEMD_FILE" ) ]] && legacy_only_resources_present=true

  echo "Stopping and disabling service..."
  systemctl stop "$SERVICE_NAME" 2>/dev/null || true
  systemctl disable "$SERVICE_NAME" 2>/dev/null || true
  if remove_unit_file_if_verified "$SERVICE_NAME" "$SYSTEMD_FILE"; then
    removed_summary+="  - $SYSTEMD_FILE"$'\n'
  elif [[ -f "$SYSTEMD_FILE" ]]; then
    retained_summary+="  - $SYSTEMD_FILE"$'\n'
    warning_summary+="  - Could not verify ownership of $SYSTEMD_FILE; left untouched."$'\n'
  fi

  echo "Removing files..."
  if [[ -d "$APP_DIR" ]]; then
    echo "Removing $APP_DIR ..."
    rm -rf "$APP_DIR"
    removed_summary+="  - $APP_DIR"$'\n'
  fi
  if [[ -d "$RUNTIME_DIR" ]]; then
    echo "Removing runtime directory $RUNTIME_DIR ..."
    rm -rf "$RUNTIME_DIR"
    removed_summary+="  - $RUNTIME_DIR"$'\n'
  fi
  if [[ -d "$STAGING_TMP_DIR" ]]; then
    echo "Removing staging directory $STAGING_TMP_DIR ..."
    rm -rf "$STAGING_TMP_DIR"
    removed_summary+="  - $STAGING_TMP_DIR"$'\n'
  fi

  if [[ "$legacy_only_resources_present" == true ]]; then
    if remove_unit_file_if_verified "$LEGACY_SERVICE_NAME" "$LEGACY_SYSTEMD_FILE"; then
      removed_summary+="  - $LEGACY_SYSTEMD_FILE"$'\n'
    elif [[ -f "$LEGACY_SYSTEMD_FILE" ]]; then
      retained_summary+="  - $LEGACY_SYSTEMD_FILE"$'\n'
      warning_summary+="  - Could not verify ownership of $LEGACY_SYSTEMD_FILE; left untouched."$'\n'
    fi

    if [[ -d "$LEGACY_APP_DIR" ]]; then
      echo "Removing legacy project directory $LEGACY_APP_DIR ..."
      rm -rf "$LEGACY_APP_DIR"
      removed_summary+="  - $LEGACY_APP_DIR"$'\n'
    fi
    warning_summary+="  - Legacy shared user/group/home resources were not deleted automatically; review $LEGACY_APP_HOME manually."$'\n'
  elif [[ -d "$LEGACY_APP_DIR" || -f "$LEGACY_SYSTEMD_FILE" ]]; then
    [[ -d "$LEGACY_APP_DIR" ]] && retained_summary+="  - $LEGACY_APP_DIR"$'\n'
    [[ -f "$LEGACY_SYSTEMD_FILE" ]] && retained_summary+="  - $LEGACY_SYSTEMD_FILE"$'\n'
  fi

  revert_firewall_selinux
  removed_summary+="  - firewall/SELinux TCP 5000 allowances (if present)"$'\n'

  [[ -d "$CONFIG_DIR" ]] && retained_summary+="  - $CONFIG_DIR"$'\n'
  [[ -d "$STATE_DIR" ]] && retained_summary+="  - $STATE_DIR"$'\n'
  retained_summary+="  - user/group: $APP_USER"$'\n'
  [[ -d "$LEGACY_APP_HOME" ]] && retained_summary+="  - $LEGACY_APP_HOME"$'\n'
  [[ -d "$LEGACY_LOG_DIR" ]] && retained_summary+="  - $LEGACY_LOG_DIR"$'\n'

  print_cleanup_summary "Uninstallation Complete" "$removed_summary" "$retained_summary" "$warning_summary"
  echo "✅ Uninstall complete. Full log saved to $LOGFILE."
}

purge_linux(){
  local removed_summary="" retained_summary="" warning_summary=""
  local modern_resources_present=false legacy_resources_present=false
  local app_group_pre_exists=false

  [[ -d "$APP_DIR" || -f "$SYSTEMD_FILE" ]] && modern_resources_present=true
  [[ -d "$LEGACY_APP_DIR" || -f "$LEGACY_SYSTEMD_FILE" ]] && legacy_resources_present=true

  echo "Stopping and disabling service..."
  systemctl stop "$SERVICE_NAME" 2>/dev/null || true
  systemctl disable "$SERVICE_NAME" 2>/dev/null || true
  if remove_unit_file_if_verified "$SERVICE_NAME" "$SYSTEMD_FILE"; then
    removed_summary+="  - $SYSTEMD_FILE"$'\n'
  elif [[ -f "$SYSTEMD_FILE" ]]; then
    retained_summary+="  - $SYSTEMD_FILE"$'\n'
    warning_summary+="  - Could not verify ownership of $SYSTEMD_FILE; left untouched."$'\n'
  fi
  revert_firewall_selinux
  removed_summary+="  - firewall/SELinux TCP 5000 allowances (if present)"$'\n'

  echo "Purging persisted configuration and state..."
  if [[ -d "$CONFIG_DIR" ]]; then
    echo "Removing $CONFIG_DIR ..."
    rm -rf "$CONFIG_DIR"
    removed_summary+="  - $CONFIG_DIR"$'\n'
  fi
  if [[ -d "$STATE_DIR" ]]; then
    echo "Removing $STATE_DIR ..."
    rm -rf "$STATE_DIR"
    removed_summary+="  - $STATE_DIR"$'\n'
  fi
  if [[ -d "$APP_DIR" ]]; then
    echo "Removing $APP_DIR ..."
    rm -rf "$APP_DIR"
    removed_summary+="  - $APP_DIR"$'\n'
  fi
  if [[ -d "$RUNTIME_DIR" ]]; then
    echo "Removing runtime directory $RUNTIME_DIR ..."
    rm -rf "$RUNTIME_DIR"
    removed_summary+="  - $RUNTIME_DIR"$'\n'
  fi
  if [[ -d "$STAGING_TMP_DIR" ]]; then
    echo "Removing staging directory $STAGING_TMP_DIR ..."
    rm -rf "$STAGING_TMP_DIR"
    removed_summary+="  - $STAGING_TMP_DIR"$'\n'
  fi

  if [[ "$legacy_resources_present" == true ]]; then
    if remove_unit_file_if_verified "$LEGACY_SERVICE_NAME" "$LEGACY_SYSTEMD_FILE"; then
      removed_summary+="  - $LEGACY_SYSTEMD_FILE"$'\n'
    elif [[ -f "$LEGACY_SYSTEMD_FILE" ]]; then
      retained_summary+="  - $LEGACY_SYSTEMD_FILE"$'\n'
      warning_summary+="  - Could not verify ownership of $LEGACY_SYSTEMD_FILE; left untouched."$'\n'
    fi

    if [[ -d "$LEGACY_APP_DIR" ]]; then
      echo "Removing legacy project directory $LEGACY_APP_DIR ..."
      rm -rf "$LEGACY_APP_DIR"
      removed_summary+="  - $LEGACY_APP_DIR"$'\n'
    fi
    warning_summary+="  - Legacy shared user/group/home/log resources were not deleted automatically; review $LEGACY_APP_HOME and $LEGACY_LOG_DIR manually."$'\n'
  fi

  echo "Removing dedicated service account..."
  getent group "$APP_USER" >/dev/null 2>&1 && app_group_pre_exists=true
  if id "$APP_USER" &>/dev/null; then
    if safe_to_remove_dedicated_user; then
      userdel "$APP_USER" 2>/dev/null || true
      removed_summary+="  - user: $APP_USER"$'\n'
    else
      retained_summary+="  - user: $APP_USER"$'\n'
      warning_summary+="  - Dedicated user $APP_USER was retained because cleanup safety checks did not pass."$'\n'
    fi
  fi
  if getent group "$APP_USER" >/dev/null 2>&1 && ! id "$APP_USER" >/dev/null 2>&1; then
    groupdel "$APP_USER" 2>/dev/null || true
    if getent group "$APP_USER" >/dev/null 2>&1; then
      retained_summary+="  - group: $APP_USER"$'\n'
    else
      removed_summary+="  - group: $APP_USER"$'\n'
    fi
  elif getent group "$APP_USER" >/dev/null 2>&1; then
    retained_summary+="  - group: $APP_USER"$'\n'
  elif [[ "$app_group_pre_exists" == true ]]; then
    removed_summary+="  - group: $APP_USER"$'\n'
  fi

  [[ -d "$LEGACY_APP_HOME" ]] && retained_summary+="  - shared user/group/home: $LEGACY_APP_USER / $LEGACY_APP_HOME"$'\n'
  [[ -d "$LEGACY_LOG_DIR" ]] && retained_summary+="  - shared legacy logs path: $LEGACY_LOG_DIR"$'\n'

  print_cleanup_summary "Purge Complete" "$removed_summary" "$retained_summary" "$warning_summary"
  echo "Legacy shared account '$LEGACY_APP_USER' is left untouched."
  echo "✅ Purge complete."
}


case "$ACTION" in
  install) install_linux ;;
  update) update_linux ;;
  uninstall) uninstall_linux ;;
  purge) purge_linux ;;
  -h|--help|help|"") usage ;;
  *) usage ;;
esac
echo "End time: $(date)"
