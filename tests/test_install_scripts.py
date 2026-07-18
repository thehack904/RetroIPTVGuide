from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_linux_installer_uses_product_specific_service_name():
    script = (REPO_ROOT / "retroiptv_linux.sh").read_text()

    assert 'SERVICE_NAME="retroiptvguide"' in script
    assert 'LEGACY_SERVICE_NAME="iptv-server"' in script


def test_linux_installer_only_cleans_legacy_service_when_owned_by_retroiptvguide():
    script = (REPO_ROOT / "retroiptv_linux.sh").read_text()

    assert "service_unit_belongs_to_retroiptvguide()" in script
    assert 'grep -Fq "RetroIPTVGuide" "$unit_file"' in script
    assert 'Leaving legacy $LEGACY_SERVICE_NAME service untouched because it is not owned by RetroIPTVGuide.' in script


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


def test_linux_updater_rewrites_current_service_before_legacy_cleanup():
    script = (REPO_ROOT / "retroiptv_linux.sh").read_text()

    update_section = script.split("update_linux(){", 1)[1].split("uninstall_linux(){", 1)[0]

    assert "write_systemd_service" in update_section
    assert update_section.index("write_systemd_service") < update_section.index("cleanup_legacy_service_if_owned")
