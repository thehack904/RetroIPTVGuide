#!/usr/bin/env python3
"""
bump_version.py - automate version bumps for RetroIPTVGuide

Usage:
    python bump_version.py 4.3.0
    python bump_version.py v4.3.0 --commit
"""

import sys
import re
from datetime import datetime
from pathlib import Path
import subprocess

# Target files
APP_FILE = Path("app.py")
CHANGELOG_FILE = Path("CHANGELOG.md")
INSTALL_MD = Path("INSTALL.md")
README_MD = Path("README.md")
ROADMAP_MD = Path("ROADMAP.md")
LINUX_SH = Path("retroiptv_linux.sh")
RPI_SH = Path("retroiptv_rpi.sh")
WIN_BAT = Path("retroiptv_windows.bat")
WIN_PS1 = Path("retroiptv_windows.ps1")


def normalize_version(raw: str) -> tuple[str, str]:
    """
    Returns (base_version, v_version)
    raw may be "4.3.0" or "v4.3.0"
    """
    base = raw.lstrip("vV").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", base):
        raise SystemExit(f"Invalid version '{raw}'. Expected format: 4.3.0 or v4.3.0")
    return base, f"v{base}"


def update_app_py(base_version: str, v_version: str, date_str: str) -> None:
    if not APP_FILE.exists():
        print(f"[-] {APP_FILE} not found, skipping")
        return

    text = APP_FILE.read_text(encoding="utf-8")
    # APP_VERSION line
    if "APP_VERSION" in text:
        text, n = re.subn(
            r'^APP_VERSION\s*=.*$',
            f'APP_VERSION = "{v_version}"',
            text,
            flags=re.MULTILINE,
        )
    else:
        text = f'APP_VERSION = "{v_version}"\n' + text
        n = 1
    print(f"[+] app.py: set APP_VERSION = \"{v_version}\" (updated {n} line{'s' if n != 1 else ''})")

    # APP_RELEASE_DATE line
    if "APP_RELEASE_DATE" in text:
        text, n2 = re.subn(
            r'^APP_RELEASE_DATE\s*=.*$',
            f'APP_RELEASE_DATE = "{date_str}"',
            text,
            flags=re.MULTILINE,
        )
    else:
        # insert just after APP_VERSION
        text = re.sub(
            r'^(APP_VERSION\s*=.*\n)',
            rf'\1APP_RELEASE_DATE = "{date_str}"\n',
            text,
            count=1,
            flags=re.MULTILINE,
        )
        n2 = 1
    print(f"[+] app.py: set APP_RELEASE_DATE = \"{date_str}\" (updated {n2} line{'s' if n2 != 1 else ''})")

    APP_FILE.write_text(text, encoding="utf-8")


def update_changelog(base_version: str, v_version: str, date_str: str) -> None:
    if not CHANGELOG_FILE.exists():
        print(f"[-] {CHANGELOG_FILE} not found, skipping")
        return

    lines = CHANGELOG_FILE.read_text(encoding="utf-8").splitlines()
    try:
        idx = next(i for i, line in enumerate(lines) if line.strip() == "---")
    except StopIteration:
        raise SystemExit("Could not find top '---' separator in CHANGELOG.md")

    new_block = [
        "",
        f"## {v_version} - {date_str}",
        "",
        "### Added",
        "- (empty)",
        "",
        "### Changed",
        "- (empty)",
        "",
        "### Fixed",
        "- (empty)",
        "",
        "---",
    ]

    # Insert immediately after the first '---'
    updated = lines[: idx + 1] + new_block + lines[idx + 1 :]
    CHANGELOG_FILE.write_text("\n".join(updated) + "\n", encoding="utf-8")
    print(f"[+] CHANGELOG.md: inserted section for {v_version} - {date_str}")


def update_install_md(v_version: str) -> None:
    if not INSTALL_MD.exists():
        print(f"[-] {INSTALL_MD} not found, skipping")
        return

    text = INSTALL_MD.read_text(encoding="utf-8")
    new_text, n = re.subn(
        r'^\*\*Version:\*\* v\d+\.\d+\.\d+',
        f"**Version:** {v_version}",
        text,
        flags=re.MULTILINE,
    )
    if n == 0:
        print("[!] INSTALL.md: no '**Version:** vX.Y.Z' line found (no change)")
    else:
        INSTALL_MD.write_text(new_text, encoding="utf-8")
        print(f"[+] INSTALL.md: updated version line to {v_version}")


def update_readme_md(v_version: str) -> None:
    if not README_MD.exists():
        print(f"[-] {README_MD} not found, skipping")
        return

    text = README_MD.read_text(encoding="utf-8")

    # Header line
    text, n1 = re.subn(
        r'^(# 📺 RetroIPTVGuide )v\d+\.\d+\.\d+',
        rf"\g<1>{v_version}",
        text,
        flags=re.MULTILINE,
    )

    # Version badge
    text, n2 = re.subn(
        r'(version-)v\d+\.\d+\.\d+(-blue)',
        rf"\1{v_version}\2",
        text,
    )

    README_MD.write_text(text, encoding="utf-8")
    print(f"[+] README.md: updated header ({n1} line) and badge ({n2} match{'es' if n2 != 1 else ''})")


def update_roadmap_md(v_version: str, date_str: str) -> None:
    if not ROADMAP_MD.exists():
        print(f"[-] {ROADMAP_MD} not found, skipping")
        return

    text = ROADMAP_MD.read_text(encoding="utf-8")

    # Current Version line
    text, n1 = re.subn(
        r'^# Current Version: \*\*v\d+\.\d+\.\d+ \(\d{4}-\d{2}-\d{2}\)\*\*',
        f"# Current Version: **{v_version} ({date_str})**",
        text,
        flags=re.MULTILINE,
    )

    # "Release tagged as" line
    text, n2 = re.subn(
        r'Release tagged as \*\*v\d+\.\d+\.\d+\*\*',
        f"Release tagged as **{v_version}**",
        text,
        count=1,
    )

    ROADMAP_MD.write_text(text, encoding="utf-8")
    print(f"[+] ROADMAP.md: updated current version line ({n1}) and release tag ({n2})")


def update_shell_script(path: Path, base_version: str) -> None:
    if not path.exists():
        print(f"[-] {path} not found, skipping")
        return

    text = path.read_text(encoding="utf-8")
    new_text, n = re.subn(
        r'^VERSION="\d+\.\d+\.\d+"',
        f'VERSION="{base_version}"',
        text,
        flags=re.MULTILINE,
    )
    if n == 0:
        print(f"[!] {path}: no VERSION=\"X.Y.Z\" line found (no change)")
    else:
        path.write_text(new_text, encoding="utf-8")
        print(f"[+] {path}: set VERSION=\"{base_version}\"")


def update_win_ps1(base_version: str) -> None:
    if not WIN_PS1.exists():
        print(f"[-] {WIN_PS1} not found, skipping")
        return

    # Windows script may not be UTF-8; use latin-1 to be safe
    text = WIN_PS1.read_text(encoding="latin-1")

    # Header Version: X.Y.Z
    text, n1 = re.subn(
        r'^(Version:\s*)\d+\.\d+\.\d+',
        rf"\g<1>{base_version}",
        text,
        flags=re.MULTILINE,
    )

    # $VERSION = "X.Y.Z"
    text, n2 = re.subn(
        r'^\$VERSION\s*=\s*"\d+\.\d+\.\d+"',
        f'$VERSION = "{base_version}"',
        text,
        flags=re.MULTILINE,
    )

    WIN_PS1.write_text(text, encoding="latin-1")
    print(f"[+] {WIN_PS1}: updated header Version ({n1}) and $VERSION ({n2})")


def update_win_bat(base_version: str, v_version: str) -> None:
    if not WIN_BAT.exists():
        print(f"[-] {WIN_BAT} not found, skipping")
        return

    # Same encoding concern as PS1
    text = WIN_BAT.read_text(encoding="latin-1")

    # REM Version: vX.Y.Z
    text, n1 = re.subn(
        r'^(REM Version:\s*)v\d+\.\d+\.\d+',
        rf"\g<1>{v_version}",
        text,
        flags=re.MULTILINE,
    )

    # set "VERSION=X.Y.Z"
    text, n2 = re.subn(
        r'^(set\s+"VERSION=)\d+\.\d+\.\d+"',
        rf'\g<1>{base_version}"',
        text,
        flags=re.MULTILINE,
    )

    WIN_BAT.write_text(text, encoding="latin-1")
    print(f"[+] {WIN_BAT}: updated REM Version ({n1}) and set VERSION ({n2})")


def git_commit(v_version: str) -> None:
    files = [
        APP_FILE,
        CHANGELOG_FILE,
        INSTALL_MD,
        README_MD,
        ROADMAP_MD,
        LINUX_SH,
        RPI_SH,
        WIN_BAT,
        WIN_PS1,
    ]
    existing = [str(f) for f in files if f.exists()]
    if not existing:
        print("[!] No files to add to git")
        return

    try:
        subprocess.run(["git", "add", *existing], check=True)
        subprocess.run(["git", "commit", "-m", f"Bump version to {v_version}"], check=True)
        print("[+] Git commit created")
    except subprocess.CalledProcessError:
        print("[!] Git commit failed (is this a git repo?)")


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print("Usage: python bump_version.py <new_version> [--commit]")
        raise SystemExit(1)

    raw_version = argv[1]
    do_commit = "--commit" in argv[2:]

    base_version, v_version = normalize_version(raw_version)
    date_str = datetime.today().strftime("%Y-%m-%d")

    print("== RetroIPTVGuide version bump ==")
    print(f"   New version: {base_version} ({v_version})")
    print(f"   Release date: {date_str}")
    print("")

    update_app_py(base_version, v_version, date_str)
    update_changelog(base_version, v_version, date_str)
    update_install_md(v_version)
    update_readme_md(v_version)
    update_roadmap_md(v_version, date_str)
    update_shell_script(LINUX_SH, base_version)
    update_shell_script(RPI_SH, base_version)
    update_win_ps1(base_version)
    update_win_bat(base_version, v_version)

    if do_commit:
        git_commit(v_version)


if __name__ == "__main__":
    main(sys.argv)

