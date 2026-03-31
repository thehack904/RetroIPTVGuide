"""Security diagnostics for the RetroIPTVGuide Admin Diagnostics subsystem.

Checks application-level security configuration and flags known-weak settings
before they become vulnerabilities.

Checks performed
----------------
1. **SECRET_KEY strength** — is the Flask secret key long enough and random-
   looking?  A default or short key lets session cookies be forged.
2. **Admin password hash** — is the admin account using a modern hash scheme
   (scrypt / pbkdf2 / bcrypt)?  A plain-text or MD5 password is critical.
3. **Debug mode** — is Flask running with ``DEBUG=True``?  Debug mode enables
   the interactive debugger and exposes internal state over HTTP.
4. **Bind address** — is the application server configured to listen on
   ``0.0.0.0`` (all interfaces)?  On an internal device this is usually fine,
   but it should at least be acknowledged.

Public API
----------
* ``run_security_checks(db_path, secret_key, debug_mode, bind_host)``
  → ``Dict[str, Any]``
"""

from __future__ import annotations

import logging
import math
import sqlite3
import string
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Minimum acceptable length for SECRET_KEY (bytes/characters).
SECRET_KEY_MIN_LEN: int = 24

#: Hash algorithm prefixes produced by Werkzeug's ``generate_password_hash``.
#: Any prefix NOT in this set is treated as weak/unknown.
_STRONG_HASH_PREFIXES = ("scrypt:", "pbkdf2:", "bcrypt$", "argon2")


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_secret_key(secret_key: str) -> Dict[str, Any]:
    """Evaluate the Flask SECRET_KEY for length and apparent randomness."""
    if not secret_key:
        return {
            "name": "secret_key",
            "status": "FAIL",
            "detail": "SECRET_KEY is empty — sessions are insecure.",
            "remediation": (
                "Set a long random SECRET_KEY in your environment or config, e.g. "
                "``python -c 'import secrets; print(secrets.token_hex(32))'``."
            ),
        }

    key_len = len(secret_key)

    # Entropy estimate: Shannon entropy over character set
    freq: Dict[str, int] = {}
    for ch in secret_key:
        freq[ch] = freq.get(ch, 0) + 1
    entropy = 0.0
    for count in freq.values():
        p = count / key_len
        entropy -= p * math.log2(p)

    # Obvious default/weak values
    _WEAK_DEFAULTS = {
        "dev", "development", "secret", "secretkey", "secret_key",
        "mysecretkey", "changeme", "change_me", "insecure", "default",
        "retroiptv", "flask", "app_secret",
    }
    if secret_key.lower().strip() in _WEAK_DEFAULTS:
        return {
            "name": "secret_key",
            "status": "FAIL",
            "detail": "SECRET_KEY appears to be a well-known default value.",
            "remediation": "Replace with a cryptographically random key (≥32 characters).",
        }

    if key_len < SECRET_KEY_MIN_LEN:
        return {
            "name": "secret_key",
            "status": "WARN",
            "detail": f"SECRET_KEY is only {key_len} characters — recommended minimum is {SECRET_KEY_MIN_LEN}.",
            "remediation": "Use a randomly generated key of at least 32 characters.",
        }

    # Low entropy — all-same characters or trivial patterns
    if entropy < 2.0 and key_len < 48:
        return {
            "name": "secret_key",
            "status": "WARN",
            "detail": "SECRET_KEY has low character variety — it may be predictable.",
            "remediation": "Replace with a high-entropy random string.",
        }

    return {
        "name": "secret_key",
        "status": "PASS",
        "detail": f"SECRET_KEY length {key_len} with adequate entropy.",
        "remediation": "",
    }


def _check_admin_password_hash(db_path: str) -> Dict[str, Any]:
    """Verify the admin password uses a strong modern hash algorithm."""
    try:
        with sqlite3.connect(db_path, timeout=5) as conn:
            row = conn.execute(
                "SELECT password FROM users WHERE username = 'admin' LIMIT 1"
            ).fetchone()
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not read admin password hash: %s", exc, exc_info=True)
        return {
            "name": "admin_password_hash",
            "status": "WARN",
            "detail": "Could not read admin password hash. Check application logs for details.",
            "remediation": "Check database integrity.",
        }

    if row is None:
        return {
            "name": "admin_password_hash",
            "status": "WARN",
            "detail": "No admin account found in the database.",
            "remediation": "Restart the application to create the default admin account.",
        }

    pw_hash: str = row[0] or ""

    if not pw_hash:
        return {
            "name": "admin_password_hash",
            "status": "FAIL",
            "detail": "Admin account has an empty password hash.",
            "remediation": "Set a strong password for the admin account immediately.",
        }

    # Check for modern strong hash prefix
    if any(pw_hash.startswith(prefix) for prefix in _STRONG_HASH_PREFIXES):
        return {
            "name": "admin_password_hash",
            "status": "PASS",
            "detail": "Admin password uses a strong hash algorithm.",
            "remediation": "",
        }

    # Looks like a plain MD5/SHA1 hash (hex string, no colons)
    if len(pw_hash) in (32, 40, 64) and all(c in string.hexdigits for c in pw_hash):
        return {
            "name": "admin_password_hash",
            "status": "FAIL",
            "detail": "Admin password appears to use a weak hash (MD5/SHA1/SHA-256 hex).",
            "remediation": (
                "Log in and change the admin password. "
                "The application will re-hash it using scrypt/pbkdf2."
            ),
        }

    # Unknown hash format — warn conservatively
    return {
        "name": "admin_password_hash",
        "status": "WARN",
        "detail": "Admin password hash format is unrecognised — could not verify algorithm strength.",
        "remediation": "Change the admin password to ensure it is stored with a modern algorithm.",
    }


def _check_debug_mode(debug_mode: bool) -> Dict[str, Any]:
    """Warn if Flask debug mode is enabled."""
    if debug_mode:
        return {
            "name": "debug_mode",
            "status": "FAIL",
            "detail": (
                "Flask DEBUG mode is ON. "
                "The interactive debugger exposes server internals and allows arbitrary code execution."
            ),
            "remediation": (
                "Set FLASK_DEBUG=0 (or remove the environment variable) "
                "and restart the application for production use."
            ),
        }
    return {
        "name": "debug_mode",
        "status": "PASS",
        "detail": "Flask debug mode is disabled.",
        "remediation": "",
    }


def _check_bind_address(bind_host: str) -> Dict[str, Any]:
    """Note if the server is listening on all interfaces."""
    if bind_host in ("0.0.0.0", "::"):
        return {
            "name": "bind_address",
            "status": "WARN",
            "detail": (
                f"Application server is bound to {bind_host!r} (all network interfaces). "
                "If this host is internet-facing, the admin panel is publicly reachable."
            ),
            "remediation": (
                "Consider binding to a specific interface (e.g. 127.0.0.1) "
                "and using a reverse proxy (nginx / Caddy) in front of the application."
            ),
        }
    if bind_host in ("127.0.0.1", "::1", "localhost"):
        return {
            "name": "bind_address",
            "status": "PASS",
            "detail": f"Application server is bound to loopback ({bind_host!r}) only.",
            "remediation": "",
        }
    return {
        "name": "bind_address",
        "status": "PASS",
        "detail": f"Application server bind address: {bind_host!r}.",
        "remediation": "",
    }


# ---------------------------------------------------------------------------
# Aggregate runner
# ---------------------------------------------------------------------------

def run_security_checks(
    *,
    db_path: str,
    secret_key: str,
    debug_mode: bool = False,
    bind_host: str = "0.0.0.0",
) -> Dict[str, Any]:
    """Run all security checks and return a combined result dict.

    Parameters
    ----------
    db_path:
        Path to the users SQLite database (to inspect the admin password hash).
    secret_key:
        The Flask ``SECRET_KEY`` value.
    debug_mode:
        ``True`` if Flask's debug flag is enabled.
    bind_host:
        Hostname/IP the WSGI server is listening on (e.g. ``"0.0.0.0"``).

    Returns
    -------
    dict with keys:

    ``status``
        Worst-case status across all checks (``PASS`` / ``WARN`` / ``FAIL``).
    ``detail``
        One-line summary of findings.
    ``checks``
        List of individual check result dicts (one per check).
    ``remediation``
        Combined remediation advice for all non-PASS checks.
    """
    checks: List[Dict[str, Any]] = [
        _check_secret_key(secret_key),
        _check_admin_password_hash(db_path),
        _check_debug_mode(debug_mode),
        _check_bind_address(bind_host),
    ]

    # Worst-case status
    _priority = {"FAIL": 2, "WARN": 1, "PASS": 0}
    worst = max(checks, key=lambda c: _priority.get(c["status"], 0))
    status = worst["status"]

    fail_checks = [c for c in checks if c["status"] == "FAIL"]
    warn_checks = [c for c in checks if c["status"] == "WARN"]

    if fail_checks:
        detail = f"{len(fail_checks)} critical security issue(s) found."
    elif warn_checks:
        detail = f"{len(warn_checks)} security warning(s)."
    else:
        detail = "No security issues detected."

    remediation_items = [c["remediation"] for c in checks if c.get("remediation")]
    remediation = "  ".join(remediation_items) if remediation_items else ""

    return {
        "status": status,
        "detail": detail,
        "checks": checks,
        "remediation": remediation,
    }
