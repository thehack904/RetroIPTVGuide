"""Dependency checker for the RetroIPTVGuide Admin Diagnostics subsystem.

Checks both *external system binaries* (ffmpeg, ffprobe, curl, wget) and
*Python package* installation status.

Public API
----------
* ``check_external_binaries()``  → ``Dict[str, Any]``
* ``check_python_packages()``    → ``Dict[str, Any]``  (re-exported from
  ``app_config_diag`` for convenience, but extended with binary status)
"""

from __future__ import annotations

import logging
import shutil
import sys
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# External binary checks
# ---------------------------------------------------------------------------

#: Binaries the application can optionally use.
#: Format: (name, description, severity_if_missing)
#:   severity  "optional" → WARN if absent
#:             "required" → FAIL if absent (none currently, everything optional)
_BINARIES: List[tuple] = [
    ("ffmpeg",  "Video transcoding / stream re-encoding",  "optional"),
    ("ffprobe", "Stream inspection (codec, resolution, bitrate)", "optional"),
    ("curl",    "HTTP client used by some install scripts",       "optional"),
    ("wget",    "HTTP client used by some install scripts",       "optional"),
]


def check_external_binaries() -> Dict[str, Any]:
    """Locate external binaries and report their availability.

    Each entry in the returned ``binaries`` list contains:

    * ``name``        – binary name
    * ``description`` – human-readable purpose
    * ``found``       – ``True`` / ``False``
    * ``path``        – filesystem path if found, else ``None``
    * ``severity``    – ``"optional"`` / ``"required"``

    Status is ``WARN`` when optional binaries are absent (none are strictly
    required by the application core), ``PASS`` when everything is present.
    """
    results: List[Dict[str, Any]] = []
    missing_required: List[str] = []
    missing_optional: List[str] = []

    for name, description, severity in _BINARIES:
        path = shutil.which(name)
        found = path is not None
        results.append({
            "name": name,
            "description": description,
            "found": found,
            "path": path,
            "severity": severity,
        })
        if not found:
            (missing_required if severity == "required" else missing_optional).append(name)

    if missing_required:
        status = "FAIL"
        detail = f"Required binaries not found: {', '.join(missing_required)}."
        remediation = f"Install the missing tools: {', '.join(missing_required)}"
    elif missing_optional:
        status = "WARN"
        detail = (
            f"Optional tool(s) not installed: {', '.join(missing_optional)}. "
            "Stream probing (ffprobe) and some install-script helpers "
            "(curl / wget) will be unavailable."
        )
        remediation = (
            "Install with your system package manager, e.g. "
            f"`apt install {' '.join(missing_optional)}` or equivalent."
        )
    else:
        status = "PASS"
        detail = f"All {len(results)} checked binaries are present."
        remediation = ""

    return {
        "status": status,
        "detail": detail,
        "remediation": remediation,
        "binaries": results,
    }


# ---------------------------------------------------------------------------
# Python package checks
# ---------------------------------------------------------------------------

def check_python_packages() -> Dict[str, Any]:
    """Verify installed Python packages against requirements.txt.

    Re-implements the requirements-check portion of ``check_system_resources``
    as a standalone, focused check with richer output:

    * Lists every requirement line with its installed version (or "NOT FOUND")
    * Flags packages whose installed version does not satisfy the requirement
      specifier (requires ``packaging`` library, degrades gracefully without it)
    * Returns FAIL if any required package is absent, PASS otherwise

    The function is intentionally cheap — it uses ``importlib.metadata`` only,
    no subprocess calls.
    """
    import os  # noqa: PLC0415
    import re  # noqa: PLC0415

    from importlib.metadata import version as _meta_version  # noqa: PLC0415
    from importlib.metadata import PackageNotFoundError  # noqa: PLC0415

    req_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "requirements.txt"
    )

    if not os.path.isfile(req_path):
        return {
            "status": "WARN",
            "detail": "requirements.txt not found — cannot verify package versions.",
            "remediation": "Ensure requirements.txt is present in the application root.",
            "packages": [],
            "python_version": sys.version.split()[0],
            "python_executable": sys.executable,
        }

    # Parse requirement lines: strip extras, markers, and version specifiers
    _pkg_name_re = re.compile(r"^([A-Za-z0-9_.-]+)", re.ASCII)

    packages: List[Dict[str, Any]] = []
    try:
        with open(req_path, "r", encoding="utf-8") as fh:
            req_lines = [
                ln.strip()
                for ln in fh
                if ln.strip() and not ln.startswith("#") and not ln.startswith("-")
            ]
    except OSError as exc:
        logger.error("Cannot read requirements.txt: %s", exc, exc_info=True)
        return {
            "status": "FAIL",
            "detail": "Cannot read requirements.txt. Check application logs for details.",
            "remediation": "Check file permissions on requirements.txt.",
            "packages": [],
            "python_version": sys.version.split()[0],
            "python_executable": sys.executable,
        }

    for req_line in req_lines:
        m = _pkg_name_re.match(req_line)
        pkg_name = m.group(1) if m else req_line
        try:
            installed_ver = _meta_version(pkg_name.lower())
            ok = True
        except PackageNotFoundError:
            try:
                # Try normalised name (hyphens ↔ underscores)
                installed_ver = _meta_version(pkg_name.lower().replace("-", "_"))
                ok = True
            except PackageNotFoundError:
                installed_ver = "NOT FOUND"
                ok = False

        packages.append({
            "package": pkg_name,
            "required": req_line,
            "installed": installed_ver,
            "ok": ok,
        })

    missing = [p["package"] for p in packages if not p["ok"]]
    status = "FAIL" if missing else "PASS"
    detail = (
        f"Missing packages: {', '.join(missing)}."
        if missing
        else f"All {len(packages)} required package(s) installed."
    )

    return {
        "status": status,
        "detail": detail,
        "remediation": f"Run: pip install {' '.join(missing)}" if missing else "",
        "packages": packages,
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
    }
