#!/usr/bin/env python3
"""
bump_version.py - automate version bumps for RetroIPTVGuide

Usage:
    python bump_version.py 2.4.0
    python bump_version.py 2.4.0 --commit
"""

import sys
import re
from datetime import datetime
import subprocess
from pathlib import Path

APP_FILE = Path("app.py")
CHANGELOG_FILE = Path("CHANGELOG.md")
INSTALL_WIN = Path("install_windows.ps1")
UNINSTALL_WIN = Path("uninstall_windows.ps1")
UNINSTALL_SH = Path("uninstall.sh")

def update_app_py(new_version: str):
    """Update APP_VERSION in app.py, add if missing"""
    content = APP_FILE.read_text().splitlines()
    updated = []
    found = False
    for line in content:
        if line.strip().startswith("APP_VERSION"):
            updated.append(f'APP_VERSION = "v{new_version}"')
            found = True
        else:
            updated.append(line)
    if not found:
        updated.insert(0, f'APP_VERSION = "v{new_version}"')
        print("ℹ️  APP_VERSION not found in app.py, added at top")
    APP_FILE.write_text("\n".join(updated) + "\n")
    print(f"✅ Updated app.py to v{new_version}")

def update_changelog(new_version: str):
    """Insert new version section after the Unreleased block"""
    changelog = CHANGELOG_FILE.read_text().splitlines()
    today = datetime.today().strftime("%Y-%m-%d")

    new_block = [
        f"## v{new_version} - {today}",
        "### Added",
        "- (empty)",
        "",
        "### Fixed",
        "- (empty)",
        "",
        "---",
        "",
    ]

    updated = []
    inserted = False
    for i, line in enumerate(changelog):
        updated.append(line)
        if line.strip() == "---" and not inserted:
            if any("## [Unreleased]" in l for l in changelog[:i]):
                updated.append("")  # spacing
                updated.extend(new_block)
                inserted = True

    if not inserted:
        print("⚠️ Could not find end of [Unreleased] section in CHANGELOG.md")
        sys.exit(1)

    CHANGELOG_FILE.write_text("\n".join(updated) + "\n")
    print(f"✅ Inserted v{new_version} section into CHANGELOG.md")

def update_script_version(file: Path, new_version: str, is_bash: bool):
    """Update or insert version string in shell or PowerShell scripts"""
    if not file.exists():
        print(f"⚠️ {file} not found, skipping")
        return

    content = file.read_text().splitlines()
    updated = []
    found = False

    # Regex for version line
    if is_bash:
        pattern = re.compile(r'^\s*VERSION\s*=\s*".*"')
        replacement = f'VERSION="{new_version}"'
    else:  # PowerShell
        pattern = re.compile(r'^\s*\$?VERSION\s*=\s*".*"')
        replacement = f'$VERSION = "{new_version}"'

    for line in content:
        if pattern.match(line):
            updated.append(replacement)
            found = True
        else:
            updated.append(line)

    if not found:
        # Insert at top
        updated.insert(0, replacement)
        print(f"ℹ️  VERSION not found in {file}, added at top")

    file.write_text("\n".join(updated) + "\n")
    print(f"✅ Updated {file} to v{new_version}")

def git_commit(new_version: str):
    """Commit changes with git"""
    try:
        subprocess.run(
            ["git", "add", str(APP_FILE), str(CHANGELOG_FILE),
             str(INSTALL_WIN), str(UNINSTALL_WIN), str(UNINSTALL_SH)],
            check=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"Bump version to v{new_version}"],
            check=True
        )
        print("✅ Changes committed to git")
    except subprocess.CalledProcessError:
        print("⚠️ Git commit failed (maybe no repo?)")

def main():
    if len(sys.argv) < 2:
        print("Usage: python bump_version.py <new_version> [--commit]")
        sys.exit(1)

    new_version = sys.argv[1].lstrip("v")
    do_commit = "--commit" in sys.argv

    update_app_py(new_version)
    update_changelog(new_version)

    # Update other scripts
    update_script_version(INSTALL_WIN, new_version, is_bash=False)
    update_script_version(UNINSTALL_WIN, new_version, is_bash=False)
    update_script_version(UNINSTALL_SH, new_version, is_bash=True)

    if do_commit:
        git_commit(new_version)

if __name__ == "__main__":
    main()
