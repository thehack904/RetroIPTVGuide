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
from typing import Any, Dict, List, Tuple

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
    ALLOWED_LOGS["startup"] = os.path.join(log_dir, "startup.log")


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


def _build_bundle_viewer_html(
    generated_at: str,
    sections: "Dict[str, Any]",
    log_texts: "Dict[str, str]",
) -> str:
    """Generate a fully self-contained HTML diagnostic viewer.

    All JSON data and log text are embedded inline so the file opens in any
    browser without network access or extra software.  The viewer uses native
    ``<details>``/``<summary>`` elements for collapsing sections and a small
    inline script for JSON syntax highlighting.

    Parameters
    ----------
    generated_at:
        ISO-8601 timestamp string shown in the page header.
    sections:
        Mapping of section label → data object (will be JSON-serialised and
        embedded).  Keys become section headings.
    log_texts:
        Mapping of filename → plain-text log content.
    """
    import json as _json

    def _js_safe(obj: object) -> str:
        """Serialise *obj* to JSON and escape ``</script>`` sequences."""
        return _json.dumps(obj, indent=2, default=str).replace("</", "<\\/")

    sections_js = _js_safe(sections)
    logs_js = _js_safe(log_texts)
    generated_at_js = _js_safe(generated_at)

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"UTF-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        "<title>RetroIPTVGuide Support Bundle</title>\n"
        "<style>\n"
        "  *{box-sizing:border-box}\n"
        "  body{background:#080d1e;color:#c0cbdf;font:14px/1.6 'Consolas','Liberation Mono','Courier New',monospace;margin:0;padding:16px 20px}\n"
        "  h1{color:#5bc0f8;margin:0 0 4px;font-size:1.5em;letter-spacing:.5px}\n"
        "  .meta{color:#6a7a9a;font-size:.85em;margin-bottom:20px;border-bottom:1px solid #1a2040;padding-bottom:12px}\n"
        "  h2{color:#5bc0f8;font-size:1em;margin:20px 0 6px;text-transform:uppercase;letter-spacing:1px}\n"
        "  details{border:1px solid #1e2a50;border-radius:5px;margin:6px 0;background:#0c1228}\n"
        "  summary{background:#111830;padding:9px 14px;cursor:pointer;user-select:none;"
        "font-weight:600;color:#a0c0e8;list-style:none;display:flex;align-items:center;gap:6px}\n"
        "  summary::-webkit-details-marker{display:none}\n"
        "  summary::before{content:'\\25B6';font-size:.7em;color:#5bc0f8;transition:transform .15s}\n"
        "  details[open]>summary::before{transform:rotate(90deg)}\n"
        "  summary:hover{background:#172040}\n"
        "  details[open]>summary{border-bottom:1px solid #1e2a50}\n"
        "  .section-body{padding:10px 14px;overflow-x:auto}\n"
        "  pre{margin:0;white-space:pre-wrap;word-break:break-word;font-size:12.5px;line-height:1.5}\n"
        "  .log-body{max-height:420px;overflow-y:auto}\n"
        "  .badge{display:inline-block;padding:1px 8px;border-radius:3px;font-size:.75em;font-weight:700;margin-left:8px;vertical-align:middle}\n"
        "  .pass{background:#0d3320;color:#4cca78}.fail{background:#3a0d1e;color:#f06080}.warn{background:#3a2e0d;color:#f0c840}\n"
        "  .jk{color:#79b8f8}.js{color:#b0d8ff}.jn{color:#f8c555}.jb{color:#f97583}.jnull{color:#f97583}\n"
        "  .note{color:#6a7a9a;font-size:.85em;margin-top:6px}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        "<h1>&#x1F527; RetroIPTVGuide Support Bundle</h1>\n"
        "<p class=\"meta\">"
        "<strong>Generated:</strong> <span id=\"ts\"></span>"
        " &nbsp;&mdash;&nbsp; "
        "Open this file in any browser to review contents before sending."
        "</p>\n"
        "<div id=\"root\"></div>\n"
        "<script>\n"
        f"var GENERATED={generated_at_js};\n"
        f"var SECTIONS={sections_js};\n"
        f"var LOGS={logs_js};\n"
        "document.getElementById('ts').textContent=GENERATED;\n"
        "function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}\n"
        "function highlight(json){\n"
        "  return json.replace(\n"
        "    /(\"(?:\\\\[\\s\\S]|[^\\\\\"])*\"(?=\\s*:))|"
        "(\"(?:\\\\[\\s\\S]|[^\\\\\"])*\")|"
        "(\\b-?(?:0|[1-9]\\d*)(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b)|"
        "(\\btrue\\b|\\bfalse\\b)|(\\bnull\\b)/g,\n"
        "    function(m,key,str,num,bool,nl){\n"
        "      if(key)return'<span class=\"jk\">'+esc(m)+'</span>';\n"
        "      if(str)return'<span class=\"js\">'+esc(m)+'</span>';\n"
        "      if(num!==undefined)return'<span class=\"jn\">'+esc(m)+'</span>';\n"
        "      if(bool)return'<span class=\"jb\">'+esc(m)+'</span>';\n"
        "      if(nl)return'<span class=\"jnull\">'+esc(m)+'</span>';\n"
        "      return esc(m);\n"
        "    }\n"
        "  );\n"
        "}\n"
        "function badge(status){\n"
        "  if(!status)return'';\n"
        "  var c=status==='PASS'?'pass':status==='FAIL'?'fail':'warn';\n"
        "  return'<span class=\"badge '+c+'\">'+esc(status)+'</span>';\n"
        "}\n"
        "function renderSection(label,data,icons){\n"
        "  var status=data&&typeof data==='object'?data.status:null;\n"
        "  var pretty=JSON.stringify(data,null,2);\n"
        "  return'<details><summary>'+esc(icons+' '+label)+badge(status)+'</summary>'"
        "+'<div class=\"section-body\"><pre>'+highlight(pretty)+'</pre></div></details>';\n"
        "}\n"
        "function renderLog(fname,text){\n"
        "  var lines=text?text.split('\\n').length:0;\n"
        "  return'<details><summary>'+esc('\U0001f4c4 '+fname)"
        "+'<span class=\"note\" style=\"margin-left:auto;font-weight:400\">'+(lines)+' lines</span></summary>'"
        "+'<div class=\"section-body log-body\"><pre>'+esc(text||'(empty)')+'</pre></div></details>';\n"
        "}\n"
        "var root=document.getElementById('root');\n"
        "var icons={'health.json':'\u2764','system.json':'\U0001f4bb','tuners.json':'\U0001f4e1',"
        "'cache_state.json':'\U0001f5c3','config.json':'\u2699','startup.json':'\U0001f680'};\n"
        "var html='';\n"
        "if(Object.keys(SECTIONS).length){\n"
        "  html+='<h2>&#x1F4CA; Diagnostic Sections</h2>';\n"
        "  for(var k in SECTIONS){\n"
        "    html+=renderSection(k,SECTIONS[k],icons[k]||'\U0001f4c4');\n"
        "  }\n"
        "}\n"
        "if(Object.keys(LOGS).length){\n"
        "  html+='<h2>&#x1F4DD; Log Files</h2>';\n"
        "  for(var lk in LOGS){html+=renderLog(lk,LOGS[lk]);}\n"
        "}\n"
        "if(!html)html='<p>No data available.</p>';\n"
        "root.innerHTML=html;\n"
        "</script>\n"
        "</body>\n"
        "</html>\n"
    )


def build_support_bundle(
    data_dir: str,
    health_data: dict,
    system_data: dict,
    extra: "dict | None" = None,
    include: "set[str] | None" = None,
) -> bytes:
    """Create an in-memory ZIP support bundle.

    The bundle contains:
    - index.html  – self-contained browser viewer (open to review without extra software)
    - health.json
    - system.json
    - Any additional JSON files passed via ``extra`` (e.g. tuners.json)
    - Application log (+ available rotated copies)
    - activity.log (+ available rotated copies)

    Nothing outside the strict ``ALLOWED_LOGS`` allowlist is included for
    log files.  Secrets are redacted from log files.

    Parameters
    ----------
    data_dir:
        Resolved DATA_DIR (used to discover rotated log files).
    health_data:
        The dict returned by ``utils.health_checks.run_all_checks()``.
    system_data:
        The dict returned by ``utils.system_info.get_system_info()``.
    extra:
        Optional mapping of ``filename → data`` for additional JSON files to
        include in the bundle root (e.g. ``{"tuners.json": {...}}``).
    include:
        Optional set of file/section keys to include.  Each key is either a
        JSON filename (e.g. ``"health.json"``) or a log key (``"logs/app"``,
        ``"logs/activity"``, ``"logs/startup"``).  When ``None`` (default) all
        available sections and log files are included, preserving the original
        behaviour.  Passing an empty set produces a bundle with only
        ``index.html``.
    """
    import json
    from datetime import datetime, timezone

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def _should_include(key: str) -> bool:
        """Return True when *key* should be included."""
        return include is None or key in include

    # Build sections dict for the viewer (order matters for display)
    sections: Dict[str, object] = {}
    if _should_include("health.json"):
        sections["health.json"] = health_data
    if _should_include("system.json"):
        sections["system.json"] = system_data
    for fname, fdata in (extra or {}).items():
        if _should_include(fname):
            sections[fname] = fdata

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # --- health.json ---
        if _should_include("health.json"):
            zf.writestr("health.json", json.dumps(health_data, indent=2, default=str))

        # --- system.json ---
        if _should_include("system.json"):
            zf.writestr("system.json", json.dumps(system_data, indent=2, default=str))

        # --- extra JSON files (tuners.json, cache_state.json, …) ---
        for fname, fdata in (extra or {}).items():
            if _should_include(fname):
                zf.writestr(fname, json.dumps(fdata, indent=2, default=str))

        # --- log files ---
        # Collect plain-text versions for the HTML viewer while writing to ZIP.
        log_texts: Dict[str, str] = {}
        for log_key, base_path in ALLOWED_LOGS.items():
            if not _should_include(f"logs/{log_key}"):
                continue
            # Include the base log and any rotated copies (.1, .2 …)
            candidates = [base_path] + sorted(
                _glob.glob(f"{base_path}.*")
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
                    content = "".join(redacted_lines)
                    zf.writestr(arcname, content)
                    log_texts[os.path.basename(candidate)] = content
                except (PermissionError, OSError):
                    pass  # skip unreadable files silently

        # --- index.html — self-contained viewer ---
        viewer_html = _build_bundle_viewer_html(generated_at, sections, log_texts)
        zf.writestr("index.html", viewer_html)

    return buf.getvalue()
