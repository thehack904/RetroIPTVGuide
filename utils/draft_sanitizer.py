"""Sanitization helpers for the issue-draft builder.

Removes or masks personally-identifying and network-topology information
from diagnostic text before it is placed into a public GitHub issue body.

What is sanitized
-----------------
* **IPv4 addresses** — any dotted-quad (private *and* public) → ``[IP-REDACTED]``
* **IPv6 addresses** — any colon-hex group → ``[IP-REDACTED]``
* **Server hostname** — the actual machine name (``platform.node()``) → ``[HOSTNAME]``
* **URL credentials** — ``http://user:pass@host`` → ``http://[CREDENTIALS]@host``
* **Home-directory paths** — ``/home/alice/…`` or ``C:\\Users\\Alice\\…`` → ``~/…``
* **Secret patterns** — tokens, passwords, API keys → ``***``
  (mirrors ``utils.log_reading._REDACT_PATTERNS`` for non-log text)
* **GPS coordinates** — ``latitude=``/``longitude=``/``lat=``/``lon=`` in URL query
  strings and error messages → ``[LOCATION-REDACTED]``; dict values whose key is
  ``lat``, ``lon``, ``latitude``, or ``longitude`` are also replaced via
  :func:`sanitize_data`.

What is NOT sanitized
---------------------
* Tuner *names* (user-defined, non-identifying)
* App version, Python version, OS name/release, architecture
* Uptime, install mode
* Error category names and status codes
* Log *structure* (timestamps, levels, categories)
* ``location_name`` (human-readable label set by the user, not a precise coordinate)

Usage
-----
::

    from utils.draft_sanitizer import sanitize_text, sanitize_hostname, sanitize_data

    clean = sanitize_text(raw_string, server_hostname=platform.node())
    safe_host = sanitize_hostname(platform.node())   # always "[HOSTNAME]"
    safe_obj = sanitize_data(nested_dict, server_hostname=platform.node())
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# IPv4: validate each octet is in the 0-255 range so that version strings
# like "3.11.2" (only two dots) and strings like "999.999.999.1" (invalid)
# are never falsely redacted.
_IPV4_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)"
_IPV4_RE = re.compile(
    r"(?<!\d)" + r"(?:" + _IPV4_OCTET + r"\." + r"){3}" + _IPV4_OCTET + r"(?!\d)"
)

# IPv6 ``::``-compressed addresses (covers loopback ``::1``, ``::`` unspecified,
# and middle-compressed forms like ``2001:db8::8a2e:370:7334``).
# Pattern: optional prefix groups, optional hex, ``::`` anchor, optional hex,
#           optional suffix groups.
_IPV6_COMPRESSED_RE = re.compile(
    r"(?<!\w)"
    r"(?:[0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{0,4}::[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{1,4})*"
    r"(?!\w)"
)

# IPv6 full (non-compressed) addresses — at least two colon-separated hex
# groups with no ``::`` present.  The end lookahead uses ``(?![\w.])`` to
# avoid blocking on a trailing ``:`` in partially consumed strings.
_IPV6_RE = re.compile(
    r"(?<![:\w])"
    r"(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{0,4}"
    r"(?![\w.])"
)
# URL credentials: http(s)://user:pass@host
_URL_CREDS_RE = re.compile(
    r"(https?://)[^/\s:@]+:[^/\s@]+@",
    re.IGNORECASE,
)

# Absolute Unix home paths: /home/username/ or /Users/username/
_UNIX_HOME_RE = re.compile(
    r"/(?:home|Users)/[^/\s]+",
    re.IGNORECASE,
)

# Absolute Windows home paths: C:\Users\Username or C:/Users/Username
_WIN_HOME_RE = re.compile(
    r"[A-Za-z]:[/\\][Uu]sers[/\\][^/\\\s]+",
    re.IGNORECASE,
)

# Secret key=value patterns (mirrors log_reading._REDACT_PATTERNS)
_SECRET_PATTERNS = [
    re.compile(r"(Authorization\s*:\s*)\S+", re.IGNORECASE),
    re.compile(r"(token\s*=\s*)\S+", re.IGNORECASE),
    re.compile(r"(password\s*=\s*)\S+", re.IGNORECASE),
    re.compile(r"(api_key\s*=\s*)\S+", re.IGNORECASE),
    re.compile(r"(secret\s*=\s*)\S+", re.IGNORECASE),
]

# GPS coordinate key=value patterns — catches occurrences in URL query strings
# (``latitude=51.5074``) and error messages (``lat=51.5074``).
# The value pattern accepts an optional leading ``-`` and requires at least one
# digit, with an optional decimal part.  No range validation is applied; we
# prefer to over-redact (any number after these keys) rather than risk missing
# out-of-range or unusual coordinate representations.
_COORD_FLOAT = r"-?[0-9]+(?:\.[0-9]+)?"
_LOCATION_PATTERNS = [
    re.compile(r"(latitude\s*=\s*)" + _COORD_FLOAT, re.IGNORECASE),
    re.compile(r"(longitude\s*=\s*)" + _COORD_FLOAT, re.IGNORECASE),
    re.compile(r"(\blat\s*=\s*)" + _COORD_FLOAT, re.IGNORECASE),
    re.compile(r"(\blon\s*=\s*)" + _COORD_FLOAT, re.IGNORECASE),
]

# Dict keys whose values are GPS coordinates and must be redacted by
# sanitize_data() regardless of whether they appear in a ``key=value`` string.
_COORDINATE_KEYS: frozenset[str] = frozenset({"lat", "lon", "latitude", "longitude"})


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def sanitize_hostname(hostname: Any) -> str:
    """Always return ``[HOSTNAME]`` — never expose the actual machine name."""
    return "[HOSTNAME]"


def sanitize_text(text: Any, *, server_hostname: str = "") -> str:
    """Apply all sanitization rules to *text* and return the cleaned string.

    Parameters
    ----------
    text:
        Any value; will be coerced to ``str`` if it is not already.
    server_hostname:
        The actual machine hostname (``platform.node()`` value).  When
        provided, any whole-word occurrence of it in *text* is replaced
        with ``[HOSTNAME]`` before IP/credential redaction.
    """
    if not isinstance(text, str):
        text = str(text)

    # 1. Redact URL credentials first (changes the URL shape before IP scan)
    text = _URL_CREDS_RE.sub(r"\1[CREDENTIALS]@", text)

    # 2. Redact key=value secrets
    for pat in _SECRET_PATTERNS:
        text = pat.sub(r"\1***", text)

    # 3. Redact GPS coordinates embedded in strings (URL query params / error messages)
    for pat in _LOCATION_PATTERNS:
        text = pat.sub(r"\1[LOCATION-REDACTED]", text)

    # 4. Redact the literal server hostname (whole-word, case-insensitive)
    if server_hostname and server_hostname.strip():
        escaped = re.escape(server_hostname.strip())
        text = re.sub(
            r"(?<![.\w])" + escaped + r"(?![.\w])",
            "[HOSTNAME]",
            text,
            flags=re.IGNORECASE,
        )

    # 5. Redact IPv6 before IPv4 (IPv4-mapped IPv6 contains dotted-quads).
    #    Compressed (``::``-based) forms are matched first in one pass; then
    #    fully-expanded forms without ``::`` are caught by the second regex.
    text = _IPV6_COMPRESSED_RE.sub("[IP-REDACTED]", text)
    text = _IPV6_RE.sub("[IP-REDACTED]", text)

    # 6. Redact IPv4
    text = _IPV4_RE.sub("[IP-REDACTED]", text)

    # 7. Abbreviate home-directory paths
    text = _UNIX_HOME_RE.sub("~", text)
    text = _WIN_HOME_RE.sub("~", text)

    return text


def sanitize_data(data: Any, *, server_hostname: str = "") -> Any:
    """Recursively sanitize all string values inside *data*.

    Walks dicts, lists, and tuples, applying :func:`sanitize_text` to every
    ``str`` leaf value.  Non-string scalars (``int``, ``float``, ``bool``,
    ``None``) are returned unchanged so that JSON structure is preserved,
    **except** for dict values whose key is a known GPS coordinate field
    (``lat``, ``lon``, ``latitude``, ``longitude``), which are replaced with
    ``"[LOCATION-REDACTED]"`` regardless of their type.

    Parameters
    ----------
    data:
        Any JSON-serialisable value (dict, list, str, int, …).
    server_hostname:
        Passed through to :func:`sanitize_text` so the machine name is
        replaced with ``[HOSTNAME]`` wherever it appears.
    """
    if isinstance(data, str):
        return sanitize_text(data, server_hostname=server_hostname)
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            # Redact GPS coordinate values by key name, but preserve
            # sentinel strings like "(not set)" and empty/None values that
            # carry no location information.
            if (
                isinstance(k, str)
                and k.lower() in _COORDINATE_KEYS
                and v not in (None, "", "(not set)")
            ):
                result[k] = "[LOCATION-REDACTED]"
            else:
                result[k] = sanitize_data(v, server_hostname=server_hostname)
        return result
    if isinstance(data, (list, tuple)):
        sanitized = [sanitize_data(item, server_hostname=server_hostname) for item in data]
        return type(data)(sanitized)
    # int, float, bool, None — leave untouched
    return data
