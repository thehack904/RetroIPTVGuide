"""Secure, read-only log access utilities for the Diagnostics subsystem.

Security guarantees
-------------------
* Only files listed in ``ALLOWED_LOGS`` can be accessed — no arbitrary path reads.
* Files are opened in ``"r"`` (text, read-only) mode.
* Each request is capped at ``MAX_BYTES`` bytes and ``MAX_LINES`` lines.
* All returned lines are HTML-escaped.
* Obvious secrets are redacted before any output leaves this module.
"""

from __future__ import annotations

import glob as _glob
import html
import io
import os
import re
import zipfile
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Resource limits
# ---------------------------------------------------------------------------
MAX_BYTES: int = 2 * 1024 * 1024   # 2 MB per request
MAX_LINES: int = 2_000              # maximum log lines returned per request
TAIL_LINES: int = 200               # default for "tail" endpoint

# ---------------------------------------------------------------------------
# Secret-redaction patterns
# (case-insensitive; value after the key separator is replaced with "***")
# ---------------------------------------------------------------------------
_REDACT_PATTERNS: List[re.Pattern] = [
    re.compile(r"(Authorization\s*:\s*)\S+", re.IGNORECASE),
    re.compile(r"(token\s*=\s*)\S+", re.IGNORECASE),
    re.compile(r"(password\s*=\s*)\S+", re.IGNORECASE),
    re.compile(r"(api_key\s*=\s*)\S+", re.IGNORECASE),
    re.compile(r"(secret\s*=\s*)\S+", re.IGNORECASE),
]


def _redact(line: str) -> str:
    """Replace sensitive values with ``***`` in a single log line."""
    for pat in _REDACT_PATTERNS:
        line = pat.sub(r"\1***", line)
    return line


def _safe_line(raw: str) -> str:
    """Redact then HTML-escape a single raw log line."""
    return html.escape(_redact(raw.rstrip("\n")))


# ---------------------------------------------------------------------------
# Allowed-log registry
# The DATA_DIR is resolved at application startup and injected into
# ``configure_allowed_logs()``.
# ---------------------------------------------------------------------------
ALLOWED_LOGS: Dict[str, str] = {}  # populated by configure_allowed_logs()


def configure_allowed_logs(data_dir: str) -> None:
    """Populate the allowlist with well-known log paths under *data_dir*.

    Call once at startup after DATA_DIR is resolved.
    """
    log_dir = os.path.join(data_dir, "logs")
    ALLOWED_LOGS["app"] = os.path.join(log_dir, "retroiptvguide.log")
    ALLOWED_LOGS["activity"] = os.path.join(log_dir, "activity.log")


def _resolve_log_path(log_key: str) -> str | None:
    """Return the filesystem path for *log_key* or ``None`` if not allowed."""
    return ALLOWED_LOGS.get(log_key)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_log(log_key: str, max_lines: int = MAX_LINES) -> Tuple[List[str], str]:
    """Return up to *max_lines* HTML-escaped lines from the named log.

    Parameters
    ----------
    log_key:
        Key that must exist in ``ALLOWED_LOGS`` (e.g. ``"app"``).
    max_lines:
        Hard cap on the number of lines returned (must be ≤ ``MAX_LINES``).

    Returns
    -------
    (lines, error_message)
        *lines* is a list of safe, HTML-escaped strings.
        *error_message* is ``""`` on success or a human-readable problem description.
    """
    max_lines = min(max_lines, MAX_LINES)
    path = _resolve_log_path(log_key)
    if path is None:
        return [], "Unknown log key."

    if not os.path.exists(path):
        return [], "Log file not found."

    try:
        lines: List[str] = []
        bytes_read = 0
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                bytes_read += len(raw.encode("utf-8", errors="replace"))
                if bytes_read > MAX_BYTES:
                    lines.append(
                        "[… output truncated at 2 MB limit …]"
                    )
                    break
                lines.append(_safe_line(raw))
                if len(lines) >= max_lines:
                    lines.append(
                        f"[… output truncated at {max_lines}-line limit …]"
                    )
                    break
        return lines, ""
    except (PermissionError, OSError) as exc:
        return [], f"Could not read log: {exc}"


def tail_log(log_key: str, n: int = TAIL_LINES) -> Tuple[List[str], str]:
    """Return the last *n* lines of the named log (HTML-escaped).

    Uses an efficient reverse-read so large files aren't loaded entirely.
    """
    n = min(n, MAX_LINES)
    path = _resolve_log_path(log_key)
    if path is None:
        return [], "Unknown log key."

    if not os.path.exists(path):
        return [], "Log file not found."

    try:
        lines = _tail_file(path, n)
        return [_safe_line(ln) for ln in lines], ""
    except (PermissionError, OSError) as exc:
        return [], f"Could not read log: {exc}"


def _tail_file(path: str, n: int) -> List[str]:
    """Efficiently read the last *n* lines of a file."""
    buf_size = 8192
    with open(path, "rb") as fh:
        fh.seek(0, io.SEEK_END)
        file_size = fh.tell()
        if file_size == 0:
            return []

        collected: List[bytes] = []
        remaining = file_size
        while remaining > 0 and len(collected) <= n:
            chunk = min(buf_size, remaining)
            remaining -= chunk
            fh.seek(remaining)
            data = fh.read(chunk)
            collected.insert(0, data)

    all_lines = b"".join(collected).decode("utf-8", errors="replace").splitlines()
    return all_lines[-n:]


def get_log_download_data(log_key: str) -> Tuple[bytes | None, str]:
    """Return the raw (but redacted) bytes of the named log for download.

    Returns ``(None, error_message)`` on failure.
    """
    path = _resolve_log_path(log_key)
    if path is None:
        return None, "Unknown log key."

    if not os.path.exists(path):
        return None, "Log file not found."

    try:
        buf = io.BytesIO()
        bytes_read = 0
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                bytes_read += len(raw.encode("utf-8", errors="replace"))
                if bytes_read > MAX_BYTES:
                    buf.write(b"\n[... truncated at 2 MB limit ...]\n")
                    break
                safe = _redact(raw)
                buf.write(safe.encode("utf-8", errors="replace"))
        return buf.getvalue(), ""
    except (PermissionError, OSError) as exc:
        return None, f"Could not read log: {exc}"


def build_support_bundle(data_dir: str, health_data: dict, system_data: dict) -> bytes:
    """Create an in-memory ZIP support bundle.

    The bundle contains:
    - Application log (+ available rotated copies)
    - activity.log (+ available rotated copies)
    - health.json
    - system.json

    Nothing outside the strict ``ALLOWED_LOGS`` allowlist is included.
    Secrets are redacted from log files.

    Parameters
    ----------
    data_dir:
        Resolved DATA_DIR (used to discover rotated log files).
    health_data:
        The dict returned by ``utils.health_checks.run_all_checks()``.
    system_data:
        The dict returned by ``utils.system_info.get_system_info()``.

    Returns
    -------
    bytes
        Raw ZIP file content suitable for streaming to the browser.
    """
    import json

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # --- health.json ---
        zf.writestr("health.json", json.dumps(health_data, indent=2, default=str))

        # --- system.json ---
        zf.writestr("system.json", json.dumps(system_data, indent=2, default=str))

        # --- log files ---
        log_dir = os.path.join(data_dir, "logs")
        for _key, base_path in ALLOWED_LOGS.items():
            # Include the base log and any rotated copies (.1, .2 …)
            candidates = [base_path] + sorted(
                _glob.glob(base_path + ".*")
            )
            for candidate in candidates:
                if not os.path.isfile(candidate):
                    continue
                arcname = "logs/" + os.path.basename(candidate)
                try:
                    redacted_lines: List[str] = []
                    bytes_read = 0
                    with open(candidate, "r", encoding="utf-8", errors="replace") as fh:
                        for raw in fh:
                            bytes_read += len(raw.encode("utf-8", errors="replace"))
                            if bytes_read > MAX_BYTES:
                                redacted_lines.append("[... truncated at 2 MB limit ...]\n")
                                break
                            redacted_lines.append(_redact(raw))
                    zf.writestr(arcname, "".join(redacted_lines))
                except (PermissionError, OSError):
                    pass  # skip unreadable files silently

    return buf.getvalue()
