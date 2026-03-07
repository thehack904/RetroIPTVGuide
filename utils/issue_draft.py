"""Issue draft builder for the RetroIPTVGuide Admin Diagnostics panel.

Aggregates output from every existing diagnostic utility and renders a
pre-filled GitHub issue body in Markdown.  The draft gives the project
maintainer exactly the information needed to reproduce and diagnose the
reported problem — without exposing secrets or network-topology details.

Sanitization
------------
All text written into the issue body is passed through
``utils.draft_sanitizer.sanitize_text``, which:

* Replaces IP addresses (private **and** public) with ``[IP-REDACTED]``
* Replaces the server hostname with ``[HOSTNAME]``
* Strips URL credentials (``user:pass@``) → ``[CREDENTIALS]@``
* Abbreviates home-directory paths (``/home/user/…`` → ``~/…``)
* Redacts secret key=value patterns (token=, password=, api_key=, …)

The admin Diagnostics panel itself is **not** affected — only the text
that ends up in the exported issue body is sanitized.

Public API
----------
* ``build_issue_draft(**kwargs)``  → ``dict`` (body_markdown, suggested_title, …)
* ``GITHUB_REPO``                  → repository slug
* ``GITHUB_ISSUES_URL``            → base URL for the "new issue" form
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from utils.draft_sanitizer import sanitize_hostname, sanitize_text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_REPO = "thehack904/RetroIPTVGuide"
GITHUB_ISSUES_URL = f"https://github.com/{GITHUB_REPO}/issues/new"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_issue_draft(
    *,
    system_data: Dict[str, Any],
    health_data: Dict[str, Any],
    tuner_data: List[Dict[str, Any]],
    cache_data: Dict[str, Any],
    startup_data: Dict[str, Any],
    config_data: Dict[str, Any],
    recent_log_lines: List[str],
    user_description: str = "",
) -> Dict[str, Any]:
    """Return a dict with the issue body and metadata.

    Parameters
    ----------
    system_data:
        Output of ``utils.system_info.get_system_info``.
    health_data:
        Output of ``utils.health_checks.run_all_checks``
        (dict of named check dicts, each with ``status`` / ``detail``).
    tuner_data:
        Output of ``utils.health_checks.check_tuner_connectivity``
        (list of tuner connectivity dicts).
    cache_data:
        Output of ``utils.health_checks.check_cache_state``.
    startup_data:
        Output of ``utils.startup_diag.get_startup_summary``.
    config_data:
        Output of ``utils.app_config_diag.run_config_checks``.
    recent_log_lines:
        Recent lines from the application log (e.g. last 200 lines from
        ``utils.log_reading.tail_log``).
    user_description:
        Free-text description provided by the user (may be empty).
    """
    title = _generate_title(health_data, tuner_data, startup_data, system_data)
    body = _format_body(
        system_data=system_data,
        health_data=health_data,
        tuner_data=tuner_data,
        cache_data=cache_data,
        startup_data=startup_data,
        config_data=config_data,
        recent_log_lines=recent_log_lines,
        user_description=user_description,
    )

    health_list = _flatten_health(health_data)
    fail_count = sum(1 for c in health_list if c.get("status") == "FAIL")
    warn_count = sum(1 for c in health_list if c.get("status") == "WARN")

    return {
        "suggested_title": title,
        "body_markdown": body,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "error_count": fail_count,
        "warn_count": warn_count,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _flatten_health(health_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert the nested ``run_all_checks`` result into a flat list of
    check dicts, injecting a ``name`` key equal to the original dict key."""
    items: List[Dict[str, Any]] = []
    if not isinstance(health_data, dict):
        return items
    for key, val in health_data.items():
        if isinstance(val, dict) and "status" in val:
            items.append({"name": key, **val})
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and "status" in item:
                    items.append(item)
    return items


def _generate_title(
    health_data: Dict[str, Any],
    tuner_data: List[Dict[str, Any]],
    startup_data: Dict[str, Any],
    system_data: Dict[str, Any],
) -> str:
    """Generate a descriptive, one-line issue title from the most prominent
    detected problem."""

    # Startup errors are the most critical — the app may not even be running
    if isinstance(startup_data, dict) and startup_data.get("error_count", 0) > 0:
        errors = startup_data.get("errors", [])
        if errors:
            cat = errors[0].get("category", "startup")
            return f"Startup error [{cat}]"
        return "App failed to start"

    # Health check FAILs
    for check in _flatten_health(health_data):
        if check.get("status") == "FAIL":
            name = check.get("name") or check.get("check") or "check"
            return f"Health check failure: {name}"

    # Tuner connectivity FAILs
    if isinstance(tuner_data, list):
        for tuner in tuner_data:
            if isinstance(tuner, dict) and tuner.get("overall_status") == "FAIL":
                return f"Tuner connectivity failure: {tuner.get('name', 'unknown')}"

    version = system_data.get("app_version", "unknown") if isinstance(system_data, dict) else "unknown"
    os_name = system_data.get("os_name", "unknown") if isinstance(system_data, dict) else "unknown"
    return f"Issue report — {version} on {os_name}"


def _format_body(
    *,
    system_data: Dict[str, Any],
    health_data: Dict[str, Any],
    tuner_data: List[Dict[str, Any]],
    cache_data: Dict[str, Any],
    startup_data: Dict[str, Any],
    config_data: Dict[str, Any],
    recent_log_lines: List[str],
    user_description: str,
) -> str:
    lines: List[str] = []

    # Extract the server hostname once so it can be stripped from every
    # text value in the body.
    server_hostname: str = (
        system_data.get("hostname", "") if isinstance(system_data, dict) else ""
    ) or ""

    def _s(value: Any) -> str:
        """Sanitize *value* and return a safe string."""
        return sanitize_text(value, server_hostname=server_hostname)

    # ── Description ──────────────────────────────────────────────────────────
    desc = user_description.strip() if user_description else ""
    lines += [
        "## Description",
        "",
        desc if desc else (
            "<!-- Replace this with a description of what happened "
            "and what you were doing when it occurred. -->"
        ),
        "",
    ]

    # ── Environment ──────────────────────────────────────────────────────────
    lines += ["## Environment", ""]
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    env_fields = [
        ("app_version",    "App Version"),
        ("install_mode",   "Install Mode"),
        ("python_version", "Python"),
        ("os_info",        "OS"),
        ("architecture",   "Architecture"),
        ("uptime",         "Uptime"),
    ]
    for key, label in env_fields:
        val = system_data.get(key, "—") if isinstance(system_data, dict) else "—"
        lines.append(f"| {label} | `{_s(val)}` |")
    # Hostname is always replaced — never expose the actual machine name
    lines.append(f"| Hostname | `{sanitize_hostname(server_hostname)}` |")
    lines.append("")

    # ── Health Check Summary ─────────────────────────────────────────────────
    health_list = _flatten_health(health_data)
    fails = [c for c in health_list if c.get("status") == "FAIL"]
    warns = [c for c in health_list if c.get("status") == "WARN"]
    lines += ["## Health Check Summary", ""]
    if not fails and not warns:
        lines.append("✅ All health checks passed.")
    else:
        if fails:
            lines.append("### ❌ FAIL")
            for c in fails:
                name = c.get("name") or c.get("check") or "unknown"
                detail = _s(c.get("detail", ""))
                lines.append(f"- **{name}**: {detail}")
            lines.append("")
        if warns:
            lines.append("### ⚠️ WARN")
            for c in warns:
                name = c.get("name") or c.get("check") or "unknown"
                detail = _s(c.get("detail", ""))
                lines.append(f"- **{name}**: {detail}")
    lines.append("")

    # ── Tuner & Cache Status ─────────────────────────────────────────────────
    lines += ["## Tuner Status", ""]
    if isinstance(cache_data, dict):
        lines.append(f"- **Active Tuner**: {_s(cache_data.get('active_tuner', '(none)'))}")
        lines.append(f"- **Channels in cache**: {cache_data.get('channel_count', '?')}")
        lines.append(f"- **EPG channels**: {cache_data.get('epg_channel_count', '?')}")
        lines.append(f"- **EPG entries**: {cache_data.get('epg_entry_count', '?')}")
    lines.append("")

    if isinstance(tuner_data, list):
        problem_tuners = [
            t for t in tuner_data
            if isinstance(t, dict) and t.get("overall_status") in ("FAIL", "WARN")
        ]
        if problem_tuners:
            lines.append("### Tuners with connectivity issues")
            for t in problem_tuners:
                st = t.get("overall_status", "?")
                name = t.get("name", "?")
                # Sanitize error messages — they may contain resolved IPs
                m3u_err = _s((t.get("m3u_probe") or {}).get("error", ""))
                xml_err = _s((t.get("xml_probe") or {}).get("error", ""))
                parts = []
                if m3u_err:
                    parts.append(f"M3U: {m3u_err}")
                if xml_err:
                    parts.append(f"XML: {xml_err}")
                detail = " | ".join(parts) if parts else "(see tuner connectivity)"
                lines.append(f"- **{name}** [{st}]: {detail}")
            lines.append("")

    # ── Startup Events ───────────────────────────────────────────────────────
    lines += ["## Startup Events", ""]
    if isinstance(startup_data, dict):
        startup_status = startup_data.get("status", "unknown")
        startup_errors = startup_data.get("errors", [])
        lines.append(f"Startup status: **{startup_status}**")
        if startup_errors:
            lines.append("")
            lines.append("### Startup Errors")
            lines.append("```")
            for e in startup_errors[:10]:
                detail = _s(e.get("detail", ""))
                lines.append(f"[{e.get('category', '?')}] {e.get('ts', '')}  {detail}")
            if len(startup_errors) > 10:
                lines.append(f"... and {len(startup_errors) - 10} more")
            lines.append("```")
        else:
            lines.append("No startup errors recorded.")
    else:
        lines.append("Startup data not available.")
    lines.append("")

    # ── Configuration Issues ─────────────────────────────────────────────────
    config_problems = _extract_config_problems(config_data, sanitize=_s)
    if config_problems:
        lines += ["## Configuration Issues", ""]
        for section, items in config_problems.items():
            lines.append(f"### {section}")
            for item in items:
                lines.append(f"- {item}")
        lines.append("")

    # ── Recent Log Errors ────────────────────────────────────────────────────
    lines += ["## Recent Log Errors (last 30 WARN/ERROR lines)", ""]
    error_lines = [
        ln for ln in (recent_log_lines or [])
        if re.search(r"\b(ERROR|WARNING|WARN|CRITICAL)\b", ln, re.IGNORECASE)
    ]
    if error_lines:
        lines.append("```")
        lines.extend(_s(ln) for ln in error_lines[-30:])
        lines.append("```")
    else:
        lines.append("No WARN/ERROR lines found in recent log.")
    lines.append("")

    # ── Steps / Expected / Actual ────────────────────────────────────────────
    lines += [
        "## Steps to Reproduce",
        "",
        "<!-- 1. Go to ...\n2. Click ...\n3. See error ... -->",
        "",
        "## Expected Behavior",
        "",
        "<!-- What should happen? -->",
        "",
        "## Actual Behavior",
        "",
        "<!-- What actually happened? Paste any error messages here. -->",
        "",
        "---",
        "",
        f"*Auto-generated by RetroIPTVGuide Diagnostics — "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}*",
        "*Sensitive fields (IP addresses, hostname, credentials, home paths) "
        "have been automatically redacted.*",
    ]
    return "\n".join(lines)


def _extract_config_problems(
    config_data: Any,
    sanitize=None,
) -> Dict[str, List[str]]:
    """Extract FAIL/WARN items from the ``run_config_checks`` result.

    Parameters
    ----------
    config_data:
        Raw output of ``utils.app_config_diag.run_config_checks``.
    sanitize:
        Optional callable applied to each detail/remediation string before
        it is stored.  Defaults to identity (no sanitization).
    """
    if sanitize is None:
        sanitize = lambda x: x  # noqa: E731
    problems: Dict[str, List[str]] = {}
    if not isinstance(config_data, dict):
        return problems
    for section_key, section_val in config_data.items():
        if not isinstance(section_val, dict):
            continue
        status = section_val.get("status")
        if status in ("FAIL", "WARN"):
            items: List[str] = []
            detail = sanitize(section_val.get("detail", ""))
            remediation = sanitize(section_val.get("remediation", ""))
            if detail:
                items.append(detail)
            if remediation:
                items.append(f"💡 {remediation}")
            if items:
                label = section_key.replace("_", " ").title()
                problems[label] = items
    return problems
