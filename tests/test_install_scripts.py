from pathlib import Path
import re
import subprocess
import textwrap


REPO_ROOT = Path(__file__).resolve().parents[1]
LINUX_INSTALLER = REPO_ROOT / "retroiptv_linux.sh"
PYTHON_CI = REPO_ROOT / ".github" / "workflows" / "python-app.yml"


def _section(script: str, start: str, end: str) -> str:
    return script.split(start, 1)[1].split(end, 1)[0]


def _linux_function_block() -> str:
    script = LINUX_INSTALLER.read_text()
    return script[script.index("usage(){"):script.index('case "$ACTION" in')]


def _write_fake_command(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


def _run_linux_function_harness(tmp_path: Path, command: str, tar_mode: str = "success") -> subprocess.CompletedProcess[str]:
    root = tmp_path / "root"
    bin_dir = tmp_path / "bin"
    root.mkdir()
    bin_dir.mkdir()

    rsync_script = """#!/usr/bin/env bash
set -euo pipefail
ignore_existing=false
args=()
skip_next=false
excludes=()
for arg in "$@"; do
  if [[ "$skip_next" == true ]]; then
    excludes+=("$arg")
    skip_next=false
    continue
  fi
  case "$arg" in
    -a) ;;
    --ignore-existing) ignore_existing=true ;;
    --exclude) skip_next=true ;;
    *) args+=("$arg") ;;
  esac
done
src="${args[0]%/}"
dst="${args[1]%/}"
mkdir -p "$dst"
if [[ -d "$src" ]]; then
  filtered_src=$(mktemp -d)
  cp -a "$src"/. "$filtered_src"/
  for exclude in "${excludes[@]+${excludes[@]}}"; do
    rm -rf "$filtered_src/${exclude%/}"
  done
  if [[ "$ignore_existing" == true ]]; then
    cp -a -n "$filtered_src"/. "$dst"/
  else
    cp -a "$filtered_src"/. "$dst"/
  fi
  rm -rf "$filtered_src"
else
  cp -a "$src" "$dst"
fi
"""
    _write_fake_command(bin_dir / "rsync", rsync_script)

    if tar_mode == "success":
        tar_script = """#!/usr/bin/env bash
set -euo pipefail
archive=""
prev=""
for arg in "$@"; do
  if [[ "$prev" == "f" ]]; then
    archive="$arg"
    prev=""
    continue
  fi
  [[ "$arg" == "-f" ]] && prev="f"
done
printf 'legacy-backup' > "$archive"
"""
    elif tar_mode == "empty":
        tar_script = """#!/usr/bin/env bash
set -euo pipefail
archive=""
prev=""
for arg in "$@"; do
  if [[ "$prev" == "f" ]]; then
    archive="$arg"
    prev=""
    continue
  fi
  [[ "$arg" == "-f" ]] && prev="f"
done
: > "$archive"
"""
    else:
        tar_script = "#!/usr/bin/env bash\nexit 1\n"
    _write_fake_command(bin_dir / "tar", tar_script)

    bash_script = textwrap.dedent(
        f"""
        set -euo pipefail
        VERSION="4.9.9"
        TIMESTAMP="2026-08-07_00-00-00"
        APP_USER="retroiptvguide"
        APP_HOME="{root}/var/lib/retroiptvguide-user"
        APP_DIR="{root}/opt/retroiptvguide"
        CONFIG_DIR="{root}/etc/retroiptvguide"
        STATE_DIR="{root}/var/lib/retroiptvguide"
        ENV_FILE="$CONFIG_DIR/retroiptvguide.env"
        LOG_DIR_LINUX="$STATE_DIR/logs"
        PYCACHE_DIR="$STATE_DIR/pycache"
        RUNTIME_DIR="{root}/run/retroiptvguide"
        STAGING_TMP_DIR="{root}/tmp/retroiptvguide"
        SERVICE_NAME="retroiptvguide"
        SYSTEMD_FILE="{root}/etc/systemd/system/retroiptvguide.service"
        LEGACY_SERVICE_NAME="iptv-server"
        LEGACY_SYSTEMD_FILE="{root}/etc/systemd/system/iptv-server.service"
        LEGACY_APP_USER="iptv"
        LEGACY_APP_HOME="{root}/home/iptv"
        LEGACY_APP_DIR="$LEGACY_APP_HOME/iptv-server"
        LEGACY_CONFIG_DIR="$LEGACY_APP_DIR/config"
        LEGACY_RUNTIME_DIR="$LEGACY_APP_DIR/runtime"
        LEGACY_LOG_DIR="{root}/var/log/iptv"
        LEGACY_AUDIO_UPLOAD_DIR="$LEGACY_APP_DIR/static/audio"
        LEGACY_LOGO_UPLOAD_DIR="$LEGACY_APP_DIR/static/logos/virtual"
        LEGACY_ROADS_CACHE_DIR="$LEGACY_APP_DIR/data/roads_cache"
        LEGACY_BASEMAP_CACHE_DIR="$LEGACY_APP_DIR/static/maps/traffic_demo"
        UPLOAD_DIR="$STATE_DIR/uploads"
        AUDIO_UPLOAD_DIR="$UPLOAD_DIR/audio"
        LOGO_UPLOAD_DIR="$UPLOAD_DIR/logos/virtual"
        CACHE_DIR="$STATE_DIR/cache"
        ROADS_CACHE_DIR="$CACHE_DIR/roads"
        BASEMAP_CACHE_DIR="$CACHE_DIR/traffic_demo"
        PATH="{bin_dir}:$PATH"
        mkdir -p "$APP_DIR" "$CONFIG_DIR" "$STATE_DIR" "$LOG_DIR_LINUX" "$PYCACHE_DIR" "$(dirname "$SYSTEMD_FILE")" "$LEGACY_CONFIG_DIR" "$LEGACY_RUNTIME_DIR" "$LEGACY_LOG_DIR"
        install() {{
          if [[ "${{1:-}}" == "-d" ]]; then
            mkdir -p "${{@: -1}}"
          else
            command install "$@"
          fi
        }}
        chown() {{ :; }}
        systemctl() {{ :; }}
        {_linux_function_block()}
        MIGRATION_BACKUP_DIR="{root}/var/backups/retroiptvguide-migration-${{TIMESTAMP}}"
        MIGRATION_EXPECTED_STATE_MANIFEST="$MIGRATION_BACKUP_DIR/expected-state-files.txt"
        MIGRATION_CONFLICT_DIR="$STATE_DIR/migration-conflicts/v4.9.9-${{TIMESTAMP}}"
        MIGRATION_CONFLICT_MANIFEST="$MIGRATION_BACKUP_DIR/conflicted-state-files.txt"
        {command}
        """
    )
    return subprocess.run(["bash", "-lc", bash_script], capture_output=True, text=True)


def test_linux_installer_uses_dedicated_layout_and_account():
    script = LINUX_INSTALLER.read_text()

    assert 'APP_USER="retroiptvguide"' in script
    assert 'APP_DIR="/opt/retroiptvguide"' in script
    assert 'CONFIG_DIR="/etc/retroiptvguide"' in script
    assert 'STATE_DIR="/var/lib/retroiptvguide"' in script
    assert 'LEGACY_APP_DIR="$LEGACY_APP_HOME/iptv-server"' in script


def test_linux_installer_only_cleans_legacy_service_when_owned_by_retroiptvguide():
    script = LINUX_INSTALLER.read_text()

    assert "service_unit_belongs_to_retroiptvguide()" in script
    assert 'grep -Fq "RetroIPTVGuide" "$unit_file"' in script
    assert 'Leaving legacy $LEGACY_SERVICE_NAME service untouched because it is not owned by RetroIPTVGuide.' in script


def test_linux_installer_generated_systemd_service_uses_target_layout():
    script = LINUX_INSTALLER.read_text()
    service_section = _section(script, "write_systemd_service(){", "service_unit_belongs_to_retroiptvguide(){")

    assert "User=$APP_USER" in service_section
    assert "Group=$APP_USER" in service_section
    assert "WorkingDirectory=$APP_DIR" in service_section
    assert "Environment=RETROIPTV_DATA_DIR=$STATE_DIR" in service_section
    assert "Environment=PYTHONPYCACHEPREFIX=$PYCACHE_DIR" in service_section
    assert "EnvironmentFile=-$ENV_FILE" in service_section
    assert "BindPaths=" not in service_section
    assert "RuntimeDirectory=$SERVICE_NAME" in service_section
    assert "ProtectSystem=strict" in service_section
    assert "ReadWritePaths=$STATE_DIR" in service_section
    assert "$RUNTIME_DIR" not in service_section
    assert "ExecStart=$PYEXEC app.py" in service_section


def test_linux_installer_preserves_admin_environment_overrides():
    script = LINUX_INSTALLER.read_text()
    env_section = _section(script, "write_environment_file(){", "migrate_legacy_state_if_present(){")

    assert 'if [[ -f "$ENV_FILE" ]]' in env_section
    assert "grep -Eq '^RETROIPTV_DATA_DIR='" in env_section
    assert 'sed -i "s|^RETROIPTV_DATA_DIR=.*$|RETROIPTV_DATA_DIR=$STATE_DIR|"' in env_section
    assert "printf '\\nRETROIPTV_DATA_DIR=%s\\n' \"$STATE_DIR\" >>\"$ENV_FILE\"" in env_section
    assert 'chown root:root "$ENV_FILE"' in env_section


def test_linux_installer_fresh_install_does_not_fail_when_no_legacy_state_exists():
    script = LINUX_INSTALLER.read_text()
    migration_section = _section(script, "migrate_legacy_state_if_present(){", "clone_or_stage_project(){")

    assert 'if [[ "$migrated" == true ]]; then' in migration_section
    assert 'chown -R "$APP_USER":"$APP_USER" "$STATE_DIR"' in migration_section
    assert '[[ "$migrated" == true ]] && chown -R "$APP_USER":"$APP_USER" "$STATE_DIR"' not in migration_section


def test_linux_installer_keeps_app_and_config_root_owned_but_state_writable_by_service_user():
    script = LINUX_INSTALLER.read_text()
    layout_section = _section(script, "ensure_layout_dirs(){", "write_environment_file(){")

    assert 'install -d -m 755 -o root -g root "$APP_DIR"' in layout_section
    assert 'install -d -m 755 -o root -g root "$CONFIG_DIR"' in layout_section
    assert 'install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$STATE_DIR"' in layout_section
    assert 'install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$PYCACHE_DIR"' in layout_section
    assert 'install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$AUDIO_UPLOAD_DIR"' in layout_section
    assert 'install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$ROADS_CACHE_DIR"' in layout_section


def test_linux_installer_stages_code_and_virtualenv_without_app_user_write_access():
    script = LINUX_INSTALLER.read_text()
    stage_section = _section(script, "clone_or_stage_project(){", "make_venv_and_install(){")
    venv_section = _section(script, "make_venv_and_install(){", "write_systemd_service(){")

    assert 'install -d -m 755 -o root -g root "$APP_DIR"' in stage_section
    assert "link_mutable_state_dirs" in stage_section
    assert 'chown -R root:root "$APP_DIR"' in stage_section
    assert 'if ! python3 -m venv "$APP_DIR/venv"; then' in venv_section
    assert 'command -v virtualenv >/dev/null 2>&1' in venv_section
    assert 'python3 -m virtualenv --version >/dev/null 2>&1' in venv_section
    assert 'virtualenv "$APP_DIR/venv" || { echo "virtualenv failed to create $APP_DIR/venv."; exit 1; }' in venv_section
    assert 'python3 -m virtualenv "$APP_DIR/venv" || { echo "python3 -m virtualenv failed to create $APP_DIR/venv."; exit 1; }' in venv_section
    assert "Install python3-virtualenv and re-run this script." in venv_section
    assert 'sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"' not in venv_section
    assert 'sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip"' not in venv_section
    assert 'python3 -m pip install virtualenv' not in venv_section


def test_linux_installer_refuses_to_overwrite_unverified_systemd_units():
    script = LINUX_INSTALLER.read_text()
    service_section = _section(script, "write_systemd_service(){", "service_unit_belongs_to_retroiptvguide(){")

    assert 'if [[ -f "$SYSTEMD_FILE" ]] && ! service_unit_belongs_to_retroiptvguide "$SYSTEMD_FILE"; then' in service_section
    assert "Refusing to overwrite existing systemd unit $SYSTEMD_FILE because it could not be verified as RetroIPTVGuide." in service_section


def test_linux_installer_legacy_execstart_regex_matches_supported_paths():
    execstart_pattern = re.compile(
        r"^\s*ExecStart=(/home/iptv/iptv-server|/opt/retroiptvguide)/venv/bin/(python|python3)(\s+-\S+)*\s+app\.py(\s+.*)?$"
    )

    assert execstart_pattern.match("ExecStart=/home/iptv/iptv-server/venv/bin/python app.py")
    assert execstart_pattern.match("ExecStart=/home/iptv/iptv-server/venv/bin/python3 -u app.py")
    assert execstart_pattern.match("  ExecStart=/opt/retroiptvguide/venv/bin/python3 app.py --port 5000")
    assert not execstart_pattern.match("ExecStart=/srv/otherapp/venv/bin/python3 app.py")


def test_linux_installer_workingdirectory_regex_matches_supported_paths():
    working_directory_pattern = re.compile(
        r"^\s*WorkingDirectory=(/home/iptv/iptv-server|/opt/retroiptvguide)\s*$"
    )

    assert working_directory_pattern.match("WorkingDirectory=/home/iptv/iptv-server")
    assert working_directory_pattern.match("  WorkingDirectory=/opt/retroiptvguide  ")
    assert not working_directory_pattern.match("WorkingDirectory=/srv/otherapp")


def test_linux_install_and_update_migrate_legacy_state_before_service_cutover():
    script = LINUX_INSTALLER.read_text()

    install_section = _section(script, "install_linux(){", "update_linux(){")
    update_section = _section(script, "update_linux(){", "uninstall_linux(){")

    assert install_section.index("migrate_legacy_state_if_present") < install_section.index("write_systemd_service")
    assert install_section.index("_validate_migration") < install_section.index("write_migration_marker")
    assert install_section.index("start_and_verify") < install_section.index("cleanup_legacy_installation_if_migration_complete")
    assert update_section.index("migrate_legacy_state_if_present") < update_section.index("write_systemd_service")
    assert update_section.index("_validate_migration") < update_section.index("write_migration_marker")
    assert update_section.index('systemctl daemon-reload; systemctl enable "$SERVICE_NAME"; systemctl restart "$SERVICE_NAME"') < update_section.index("cleanup_legacy_installation_if_migration_complete")


def test_linux_installer_reowns_existing_repo_before_root_git_updates():
    script = LINUX_INSTALLER.read_text()
    update_section = _section(script, "update_linux(){", "uninstall_linux(){")

    assert 'chown -R root:root "$APP_DIR"' in update_section
    assert update_section.index('chown -R root:root "$APP_DIR"') < update_section.index("git fetch --all && git reset --hard origin/main")


def test_linux_installer_reuses_virtualenv_fallback_for_update_repairs():
    script = LINUX_INSTALLER.read_text()
    update_section = _section(script, "update_linux(){", "uninstall_linux(){")

    assert "create_virtualenv(){" in script
    assert "create_virtualenv" in update_section
    assert update_section.count('"$APP_DIR/venv/bin/pip" install --upgrade pip') == 1
    assert update_section.count('"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"') == 1


def test_linux_installer_preserves_legacy_tree_for_rollback_and_safe_uninstall():
    script = LINUX_INSTALLER.read_text()
    install_section = _section(script, "install_linux(){", "update_linux(){")
    uninstall_section = _section(script, "uninstall_linux(){", "purge_linux(){")

    assert 'cleanup_legacy_installation_if_migration_complete' in install_section
    assert "revert_firewall_selinux" in uninstall_section
    assert 'remove_unit_file_if_verified "$SERVICE_NAME" "$SYSTEMD_FILE"' in uninstall_section
    assert 'cleanup_legacy_service_if_owned' not in uninstall_section
    assert 'retained_summary+="  - $CONFIG_DIR"' in uninstall_section
    assert 'retained_summary+="  - $STATE_DIR"' in uninstall_section
    assert 'retained_summary+="  - user/group: $APP_USER"' in uninstall_section
    assert 'rm -rf "$STATE_DIR"' not in uninstall_section
    assert 'rm -rf "$CONFIG_DIR"' not in uninstall_section


def test_linux_installer_purge_is_explicit_and_targeted():
    script = LINUX_INSTALLER.read_text()
    purge_section = _section(script, "purge_linux(){", 'case "$ACTION" in')

    assert "uninstall_linux" not in purge_section
    assert "revert_firewall_selinux" in purge_section
    assert 'rm -rf "$CONFIG_DIR"' in purge_section
    assert 'rm -rf "$STATE_DIR"' in purge_section
    assert 'rm -rf "$LEGACY_APP_DIR"' in purge_section
    assert "safe_to_remove_dedicated_user" in purge_section
    assert 'userdel "$APP_USER"' in purge_section
    assert 'rm -rf "$LEGACY_LOG_DIR"' not in purge_section
    assert "Legacy shared account '$LEGACY_APP_USER' is left untouched." in purge_section


def test_linux_installer_contains_no_broad_user_wide_kill_or_delete_operations():
    script = LINUX_INSTALLER.read_text()

    assert "pkill -u" not in script
    assert "killall " not in script
    assert "userdel -r" not in script
    assert "rm -rf /home" not in script


def test_linux_installer_uninstall_and_purge_do_not_stop_or_disable_legacy_service_names():
    script = LINUX_INSTALLER.read_text()
    uninstall_section = _section(script, "uninstall_linux(){", "purge_linux(){")
    purge_section = _section(script, "purge_linux(){", 'case "$ACTION" in')

    assert 'systemctl stop "$LEGACY_SERVICE_NAME"' not in uninstall_section
    assert 'systemctl disable "$LEGACY_SERVICE_NAME"' not in uninstall_section
    assert 'systemctl stop "$LEGACY_SERVICE_NAME"' not in purge_section
    assert 'systemctl disable "$LEGACY_SERVICE_NAME"' not in purge_section


def test_linux_installer_guards_dedicated_user_removal_with_process_and_file_checks():
    script = LINUX_INSTALLER.read_text()
    guard_section = _section(script, "safe_to_remove_dedicated_user(){", "print_cleanup_summary(){")

    assert 'getent passwd "$APP_USER"' in guard_section
    assert 'pgrep -u "$APP_USER"' in guard_section
    assert 'find /opt /etc /var/lib /var/log /run /tmp -xdev -user "$APP_USER"' in guard_section


def test_linux_installer_legacy_only_uninstall_removes_verified_legacy_project_and_warns_shared_resources():
    script = LINUX_INSTALLER.read_text()
    uninstall_section = _section(script, "uninstall_linux(){", "purge_linux(){")

    assert 'legacy_only_resources_present=true' in uninstall_section
    assert 'remove_unit_file_if_verified "$LEGACY_SERVICE_NAME" "$LEGACY_SYSTEMD_FILE"' in uninstall_section
    assert 'rm -rf "$LEGACY_APP_DIR"' in uninstall_section
    assert "Legacy shared user/group/home resources were not deleted automatically" in uninstall_section


def test_linux_installer_checks_for_rsync_before_migration_or_staging():
    script = LINUX_INSTALLER.read_text()

    assert "require_command(){" in script
    assert "require_command rsync" in script


def test_linux_installer_never_targets_sibling_service_names_or_directories():
    script = LINUX_INSTALLER.read_text()

    # The script may *detect* sibling services to avoid breaking them, but must
    # never issue destructive operations (rm -rf, systemctl stop/disable) that
    # directly target those sibling service names or directories.
    for name in ("retrostation-mc", "retrostation_mc", "retrostationmc", "/home/iptv/RetroStationMC"):
        # Detection (grep/find/test) is fine; destructive commands are not.
        for bad_prefix in (f"rm -rf {name}", f"systemctl stop {name}", f"systemctl disable {name}"):
            assert bad_prefix not in script, f"Script must not destructively target: {bad_prefix}"


def test_linux_ci_workflow_runs_install_layout_guardrails():
    workflow = PYTHON_CI.read_text()

    assert "pytest tests/test_install_scripts.py" in workflow


def test_linux_migration_backup_requires_nonempty_archive(tmp_path):
    result = _run_linux_function_harness(
        tmp_path,
        """
        printf 'legacy-user-db' > "$LEGACY_CONFIG_DIR/users.db"
        _migration_backup
        test -s "$MIGRATION_BACKUP_DIR/legacy-state.tar.gz"
        """,
    )

    assert result.returncode == 0, result.stderr


def test_linux_migration_backup_failure_aborts_before_copy_or_marker(tmp_path):
    root = tmp_path / "root"
    result = _run_linux_function_harness(
        tmp_path,
        """
        printf 'legacy-user-db' > "$LEGACY_CONFIG_DIR/users.db"
        migrate_legacy_state_if_present
        """,
        tar_mode="fail",
    )

    assert result.returncode != 0
    assert "Migration aborted" in result.stdout
    assert not (root / "var/lib/retroiptvguide/users.db").exists()
    assert not (root / "var/lib/retroiptvguide/.migration_v4.9.9").exists()
    assert (root / "home/iptv/iptv-server/config/users.db").exists()


def test_linux_migration_empty_backup_archive_aborts(tmp_path):
    root = tmp_path / "root"
    result = _run_linux_function_harness(
        tmp_path,
        """
        printf 'legacy-user-db' > "$LEGACY_CONFIG_DIR/users.db"
        migrate_legacy_state_if_present
        """,
        tar_mode="empty",
    )

    assert result.returncode != 0
    assert "empty archive" in result.stdout
    assert not (root / "var/lib/retroiptvguide/users.db").exists()
    assert not (root / "var/lib/retroiptvguide/.migration_v4.9.9").exists()


def test_linux_migration_successfully_migrates_dbs_and_writes_marker(tmp_path):
    root = tmp_path / "root"
    result = _run_linux_function_harness(
        tmp_path,
        """
        printf 'legacy-user-db' > "$LEGACY_CONFIG_DIR/users.db"
        printf 'legacy-tuner-db' > "$LEGACY_CONFIG_DIR/tuners.db"
        printf '{"theme":"retro"}' > "$LEGACY_CONFIG_DIR/preferences.json"
        printf 'print("ok")\\n' > "$APP_DIR/app.py"
        printf 'flask\\n' > "$APP_DIR/requirements.txt"
        mkdir -p "$APP_DIR/venv/bin"
        printf '#!/usr/bin/env bash\\nexit 0\\n' > "$APP_DIR/venv/bin/python3"
        chmod +x "$APP_DIR/venv/bin/python3"
        printf 'RETROIPTV_DATA_DIR=%s\\n' "$STATE_DIR" > "$ENV_FILE"
        printf '[Unit]\\nDescription=RetroIPTVGuide\\n' > "$SYSTEMD_FILE"
        migrate_legacy_state_if_present
        _validate_migration
        write_migration_marker
        """,
    )

    assert result.returncode == 0, result.stderr
    assert (root / "var/lib/retroiptvguide/users.db").read_text() == "legacy-user-db"
    assert (root / "var/lib/retroiptvguide/tuners.db").read_text() == "legacy-tuner-db"
    assert (root / "var/lib/retroiptvguide/preferences.json").read_text() == '{"theme":"retro"}'
    marker = root / "var/lib/retroiptvguide/.migration_v4.9.9"
    assert marker.exists()
    assert "migration_version=4.9.9" in marker.read_text()


def test_linux_failed_validation_does_not_create_marker_or_cleanup_legacy_tree(tmp_path):
    root = tmp_path / "root"
    result = _run_linux_function_harness(
        tmp_path,
        """
        printf 'legacy-user-db' > "$LEGACY_CONFIG_DIR/users.db"
        printf 'print("ok")\\n' > "$APP_DIR/app.py"
        printf 'flask\\n' > "$APP_DIR/requirements.txt"
        mkdir -p "$APP_DIR/venv/bin"
        printf '#!/usr/bin/env bash\\nexit 0\\n' > "$APP_DIR/venv/bin/python3"
        chmod +x "$APP_DIR/venv/bin/python3"
        printf 'RETROIPTV_DATA_DIR=%s\\n' "$STATE_DIR" > "$ENV_FILE"
        printf '[Unit]\\nDescription=RetroIPTVGuide\\n' > "$SYSTEMD_FILE"
        migrate_legacy_state_if_present
        rm -f "$STATE_DIR/users.db"
        if _validate_migration; then
          write_migration_marker
          cleanup_legacy_installation_if_migration_complete
        fi
        """,
    )

    assert result.returncode == 0, result.stderr
    assert "Validation: legacy users.db was not copied" in result.stdout
    assert not (root / "var/lib/retroiptvguide/.migration_v4.9.9").exists()
    assert (root / "home/iptv/iptv-server").exists()


def test_linux_migration_preserves_existing_target_db_and_conflict_copy(tmp_path):
    root = tmp_path / "root"
    result = _run_linux_function_harness(
        tmp_path,
        """
        printf 'legacy-user-db' > "$LEGACY_CONFIG_DIR/users.db"
        printf 'modern-user-db' > "$STATE_DIR/users.db"
        migrate_legacy_state_if_present
        """,
    )

    assert result.returncode == 0, result.stderr
    assert (root / "var/lib/retroiptvguide/users.db").read_text() == "modern-user-db"
    conflict_copy = root / "var/lib/retroiptvguide/migration-conflicts/v4.9.9-2026-08-07_00-00-00/users.db"
    assert conflict_copy.read_text() == "legacy-user-db"
    assert "Migration conflict" in result.stdout


def test_linux_migration_moves_legacy_uploads_and_caches(tmp_path):
    root = tmp_path / "root"
    result = _run_linux_function_harness(
        tmp_path,
        """
        mkdir -p "$LEGACY_AUDIO_UPLOAD_DIR" "$LEGACY_LOGO_UPLOAD_DIR" "$LEGACY_ROADS_CACHE_DIR" "$LEGACY_BASEMAP_CACHE_DIR"
        printf 'audio' > "$LEGACY_AUDIO_UPLOAD_DIR/theme.mp3"
        printf 'logo' > "$LEGACY_LOGO_UPLOAD_DIR/custom.png"
        printf 'roads' > "$LEGACY_ROADS_CACHE_DIR/city_1.json"
        printf 'map' > "$LEGACY_BASEMAP_CACHE_DIR/demo.png"
        migrate_legacy_state_if_present
        """,
    )

    assert result.returncode == 0, result.stderr
    assert (root / "var/lib/retroiptvguide/uploads/audio/theme.mp3").read_text() == "audio"
    assert (root / "var/lib/retroiptvguide/uploads/logos/virtual/custom.png").read_text() == "logo"
    assert (root / "var/lib/retroiptvguide/cache/roads/city_1.json").read_text() == "roads"
    assert (root / "var/lib/retroiptvguide/cache/traffic_demo/demo.png").read_text() == "map"


def test_linux_installer_links_mutable_app_paths_to_isolated_state():
    script = LINUX_INSTALLER.read_text()
    link_section = _section(script, "link_mutable_state_dirs(){", "make_venv_and_install(){")

    assert '"$APP_DIR/static/audio:$AUDIO_UPLOAD_DIR"' in link_section
    assert '"$APP_DIR/static/logos/virtual/uploads:$LOGO_UPLOAD_DIR"' in link_section
    assert '"$APP_DIR/data/roads_cache:$ROADS_CACHE_DIR"' in link_section
    assert '"$APP_DIR/static/maps/traffic_demo:$BASEMAP_CACHE_DIR"' in link_section
    assert "--exclude 'icon_pack/' --exclude 'uploads/'" in link_section
    assert 'install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$state_path"' in link_section
    assert 'rsync -a --ignore-existing "$app_path/" "$state_path/"' in link_section
    assert 'rm -rf -- "$app_path"' in link_section
    assert 'install -d -m 755 -o root -g root "$(dirname "$app_path")"' in link_section
    assert 'ln -s "$state_path" "$app_path"' in link_section


def test_linux_installer_moves_bundled_mutable_files_into_state_before_linking(tmp_path):
    root = tmp_path / "root"
    result = _run_linux_function_harness(
        tmp_path,
        """
        mkdir -p "$APP_DIR/static/audio" "$APP_DIR/static/maps/traffic_demo"
        printf 'audio' > "$APP_DIR/static/audio/theme.mp3"
        printf 'map' > "$APP_DIR/static/maps/traffic_demo/city.png"
        link_mutable_state_dirs
        test -L "$APP_DIR/static/audio"
        test -L "$APP_DIR/static/maps/traffic_demo"
        """,
    )

    assert result.returncode == 0, result.stderr
    assert (root / "var/lib/retroiptvguide/uploads/audio/theme.mp3").read_text() == "audio"
    assert (root / "var/lib/retroiptvguide/cache/traffic_demo/city.png").read_text() == "map"


def test_linux_installer_moves_legacy_loose_logo_uploads_without_icon_pack(tmp_path):
    root = tmp_path / "root"
    result = _run_linux_function_harness(
        tmp_path,
        """
        mkdir -p "$APP_DIR/static/logos/virtual/icon_pack"
        printf 'custom' > "$APP_DIR/static/logos/virtual/custom.png"
        printf 'bundled' > "$APP_DIR/static/logos/virtual/icon_pack/news.png"
        link_mutable_state_dirs
        """,
    )

    assert result.returncode == 0, result.stderr
    assert (root / "var/lib/retroiptvguide/uploads/logos/virtual/custom.png").read_text() == "custom"
    assert not (root / "var/lib/retroiptvguide/uploads/logos/virtual/icon_pack/news.png").exists()


def test_linux_cleanup_preserves_shared_iptv_resources(tmp_path):
    root = tmp_path / "root"
    result = _run_linux_function_harness(
        tmp_path,
        """
        mkdir -p "$LEGACY_APP_HOME/RetroStationMC"
        printf 'migration_version=%s\\n' "$VERSION" > "$MIGRATION_MARKER"
        cleanup_legacy_installation_if_migration_complete
        """,
    )

    assert result.returncode == 0, result.stderr
    assert (root / "home/iptv/iptv-server").exists()
    assert "retaining" in result.stdout.lower()


def test_linux_migration_marker_keeps_second_run_idempotent(tmp_path):
    root = tmp_path / "root"
    result = _run_linux_function_harness(
        tmp_path,
        """
        printf 'migration_version=%s\\n' "$VERSION" > "$MIGRATION_MARKER"
        printf 'legacy-user-db' > "$LEGACY_CONFIG_DIR/users.db"
        printf 'modern-user-db' > "$STATE_DIR/users.db"
        migrate_legacy_state_if_present
        """,
    )

    assert result.returncode == 0, result.stderr
    assert (root / "var/lib/retroiptvguide/users.db").read_text() == "modern-user-db"
    assert "Skipping legacy state migration" in result.stdout


def test_app_legacy_path_warning_is_single_nonfatal_stderr_notice():
    app_source = (REPO_ROOT / "app.py").read_text()

    assert "warnings.warn" not in app_source
    assert "Running from deprecated legacy path" in app_source
    assert "/home/iptv/iptv-server" in app_source
