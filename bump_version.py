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

def update_app_py(new_version: str):
    """Update APP_VERSION in app.py"""
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
        print("⚠️ APP_VERSION not found in app.py")
        sys.exit(1)
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
        # Find the first --- *after* the Unreleased section
        if line.strip() == "---" and not inserted:
            # Look back: did we already pass Unreleased?
            if any("## [Unreleased]" in l for l in changelog[:i]):
                updated.append("")  # spacing
                updated.extend(new_block)
                inserted = True

    if not inserted:
        print("⚠️ Could not find end of [Unreleased] section in CHANGELOG.md")
        sys.exit(1)

    CHANGELOG_FILE.write_text("\n".join(updated) + "\n")
    print(f"✅ Inserted v{new_version} section into CHANGELOG.md")

def git_commit(new_version: str):
    """Commit changes with git"""
    try:
        subprocess.run(
            ["git", "add", str(APP_FILE), str(CHANGELOG_FILE)],
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

    new_version = sys.argv[1].lstrip("v")  # allow 'v2.4.0' or '2.4.0'
    do_commit = "--commit" in sys.argv

    update_app_py(new_version)
    update_changelog(new_version)

    if do_commit:
        git_commit(new_version)

if __name__ == "__main__":
    main()

