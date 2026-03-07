"""Admin Diagnostics Blueprint for RetroIPTVGuide.

Routes (ALL GET, admin-only, login required):
  GET  /admin/diagnostics                 – tabbed diagnostics page (HTML)
  GET  /admin/diagnostics/logs            – view log (HTML, ?key=app|activity)
  GET  /admin/diagnostics/logs/tail       – last N lines JSON  (?key=…&n=200)
  GET  /admin/diagnostics/logs/download   – download log file  (?key=…)
  GET  /admin/diagnostics/health          – health checks JSON
  GET  /admin/diagnostics/system          – system info JSON
  GET  /admin/diagnostics/issue-draft     – pre-formatted GitHub issue draft JSON
  GET  /admin/diagnostics/support         – download support bundle (ZIP)

Security:
  * Admin-only via ``current_user.username == 'admin'`` check.
  * All log access goes through ``utils.log_reading`` — hard allowlist, no
    arbitrary paths, read-only, resource-capped, HTML-escaped, secrets redacted.
  * No POST / PUT / DELETE routes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

import io

logger = logging.getLogger(__name__)

admin_diagnostics_bp = Blueprint(
    "admin_diagnostics",
    __name__,
    url_prefix="/admin/diagnostics",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_admin():
    """Abort with 403 if the current user is not the admin."""
    if not current_user.is_authenticated or current_user.username != "admin":
        abort(403)


def _get_config():
    """Retrieve config values, reading DB paths from the app module at call time.

    Reading DATABASE / TUNER_DB directly from the ``app`` module (rather than
    from ``app.config``) ensures that pytest monkeypatching of those module-
    level globals is respected inside the blueprint routes.
    """
    import app as app_module  # noqa: PLC0415 – intentional late import

    cfg = current_app.config
    return (
        cfg.get("DIAG_DATA_DIR", app_module.DATA_DIR),
        app_module.DATABASE,
        app_module.TUNER_DB,
        cfg.get("DIAG_APP_VERSION", app_module.APP_VERSION),
        cfg.get("DIAG_APP_START_TIME", app_module.APP_START_TIME),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@admin_diagnostics_bp.route("", methods=["GET"])
@admin_diagnostics_bp.route("/", methods=["GET"])
@login_required
def diagnostics_index():
    """Main diagnostics page with tabs."""
    _require_admin()
    from utils.log_reading import ALLOWED_LOGS
    from utils.issue_draft import GITHUB_ISSUES_URL
    log_keys = list(ALLOWED_LOGS.keys())
    return render_template(
        "admin_diagnostics.html",
        log_keys=log_keys,
        active_tab=request.args.get("tab", "tuners"),
        github_issues_url=GITHUB_ISSUES_URL,
    )


@admin_diagnostics_bp.route("/logs", methods=["GET"])
@login_required
def diagnostics_logs():
    """View a log file.  Returns JSON ``{lines, error}``."""
    _require_admin()
    from utils.log_reading import read_log, MAX_LINES

    key = request.args.get("key", "app")
    try:
        n = min(int(request.args.get("n", MAX_LINES)), MAX_LINES)
    except (ValueError, TypeError):
        n = MAX_LINES

    lines, error = read_log(key, max_lines=n)
    if error and not lines:
        # Unknown key → 404
        if "Unknown log key" in error:
            abort(404)
    return jsonify({"lines": lines, "error": error, "key": key, "count": len(lines)})


@admin_diagnostics_bp.route("/logs/tail", methods=["GET"])
@login_required
def diagnostics_logs_tail():
    """Return the last N lines of a log file as JSON."""
    _require_admin()
    from utils.log_reading import tail_log, TAIL_LINES, MAX_LINES

    key = request.args.get("key", "app")
    try:
        n = min(int(request.args.get("n", TAIL_LINES)), MAX_LINES)
    except (ValueError, TypeError):
        n = TAIL_LINES

    lines, error = tail_log(key, n=n)
    if error and not lines and "Unknown log key" in error:
        abort(404)
    return jsonify({"lines": lines, "error": error, "key": key, "count": len(lines)})


@admin_diagnostics_bp.route("/logs/download", methods=["GET"])
@login_required
def diagnostics_logs_download():
    """Download a single log file (plain text, secrets redacted)."""
    _require_admin()
    from utils.log_reading import get_log_download_data

    key = request.args.get("key", "app")
    data, error = get_log_download_data(key)
    if data is None:
        if "Unknown log key" in error:
            abort(404)
        abort(500)

    filename = f"retroiptv-{key}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.log"
    return send_file(
        io.BytesIO(data),
        mimetype="text/plain",
        as_attachment=True,
        download_name=filename,
    )


@admin_diagnostics_bp.route("/health", methods=["GET"])
@login_required
def diagnostics_health():
    """Run all health checks and return structured JSON."""
    _require_admin()
    from utils.health_checks import run_all_checks

    data_dir, db_path, tuner_db_path, _, _ = _get_config()
    result = run_all_checks(data_dir, db_path, tuner_db_path)
    return jsonify(result)


@admin_diagnostics_bp.route("/tuners", methods=["GET"])
@login_required
def diagnostics_tuners():
    """Deep per-tuner connectivity check: URL probes, DNS, HTTP status, channel count."""
    _require_admin()
    from utils.health_checks import check_tuner_connectivity

    _, _, tuner_db_path, _, _ = _get_config()
    result = check_tuner_connectivity(tuner_db_path)
    return jsonify(result)


@admin_diagnostics_bp.route("/cache", methods=["GET"])
@login_required
def diagnostics_cache():
    """Return runtime cache / EPG state (active tuner, channel count, sample channels)."""
    _require_admin()
    from utils.health_checks import check_cache_state

    _, _, tuner_db_path, _, _ = _get_config()
    result = check_cache_state(tuner_db_path)
    return jsonify(result)


@admin_diagnostics_bp.route("/config", methods=["GET"])
@login_required
def diagnostics_config():
    """Return application configuration diagnostics as JSON.

    Covers: user accounts, virtual channel config, external service
    reachability (weather API + news RSS), and system resource usage.
    """
    _require_admin()
    from utils.app_config_diag import run_config_checks

    _, db_path, tuner_db_path, _, _ = _get_config()
    result = run_config_checks(db_path, tuner_db_path)
    return jsonify(result)


@admin_diagnostics_bp.route("/startup", methods=["GET"])
@login_required
def diagnostics_startup():
    """Return full startup event log (admin-only).

    Unlike the public /startup-status endpoint, this returns the complete
    event list including error details and tracebacks.
    """
    _require_admin()
    from utils.startup_diag import get_startup_summary
    return jsonify(get_startup_summary())


@admin_diagnostics_bp.route("/tuner-parse", methods=["GET"])
@login_required
def diagnostics_tuner_parse():
    """Run a live parse-trace for a named tuner and return structured JSON.

    Query params:
        name   – tuner name (required)
    """
    _require_admin()
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "Missing 'name' query parameter"}), 400

    from utils.tuner_diag import parse_tuner_with_trace
    _, _, tuner_db_path, _, _ = _get_config()
    result = parse_tuner_with_trace(name, tuner_db_path)
    return jsonify(result)


@admin_diagnostics_bp.route("/system", methods=["GET"])
@login_required
def diagnostics_system():
    """Return sanitised system/runtime information as JSON."""
    _require_admin()
    from utils.system_info import get_system_info

    data_dir, _, _, app_version, app_start_time = _get_config()
    info = get_system_info(app_version, app_start_time, data_dir)
    return jsonify(info)


@admin_diagnostics_bp.route("/issue-draft", methods=["GET"])
@login_required
def diagnostics_issue_draft():
    """Build a pre-formatted GitHub issue draft from all current diagnostics.

    Query params:
        description – optional free-text problem description (URL-encoded)

    Returns JSON:
        suggested_title – auto-generated issue title
        body_markdown   – full GitHub issue body (Markdown)
        github_new_url  – URL to open a pre-filled GitHub new issue
        generated_at    – ISO-8601 timestamp
        error_count     – number of FAIL health checks
        warn_count      – number of WARN health checks
    """
    _require_admin()
    import urllib.parse
    from utils.health_checks import run_all_checks, check_tuner_connectivity, check_cache_state
    from utils.system_info import get_system_info
    from utils.app_config_diag import run_config_checks
    from utils.startup_diag import get_startup_summary
    from utils.log_reading import tail_log
    from utils.issue_draft import build_issue_draft, GITHUB_ISSUES_URL

    user_description = request.args.get("description", "").strip()

    data_dir, db_path, tuner_db_path, app_version, app_start_time = _get_config()

    health_data = run_all_checks(data_dir, db_path, tuner_db_path)
    system_data = get_system_info(app_version, app_start_time, data_dir)
    tuner_data = check_tuner_connectivity(tuner_db_path)
    cache_data = check_cache_state(tuner_db_path)
    config_data = run_config_checks(db_path, tuner_db_path)
    startup_data = get_startup_summary()
    log_lines, _ = tail_log("app", n=200)

    draft = build_issue_draft(
        system_data=system_data,
        health_data=health_data,
        tuner_data=tuner_data if isinstance(tuner_data, list) else [],
        cache_data=cache_data if isinstance(cache_data, dict) else {},
        startup_data=startup_data if isinstance(startup_data, dict) else {},
        config_data=config_data if isinstance(config_data, dict) else {},
        recent_log_lines=log_lines,
        user_description=user_description,
    )

    # Build the GitHub "new issue" URL with pre-filled title + body.
    # We URL-encode the full body; browsers and GitHub handle long URLs fine.
    title_enc = urllib.parse.quote(draft["suggested_title"])
    body_enc = urllib.parse.quote(draft["body_markdown"])
    draft["github_new_url"] = f"{GITHUB_ISSUES_URL}?title={title_enc}&body={body_enc}"

    return jsonify(draft)


@admin_diagnostics_bp.route("/support", methods=["GET"])
@login_required
def diagnostics_support():
    """Generate and download a support bundle ZIP."""
    _require_admin()
    from utils.health_checks import run_all_checks, check_tuner_connectivity, check_cache_state
    from utils.log_reading import build_support_bundle
    from utils.system_info import get_system_info
    from utils.app_config_diag import run_config_checks
    from utils.startup_diag import get_startup_summary

    data_dir, db_path, tuner_db_path, app_version, app_start_time = _get_config()

    health_data = run_all_checks(data_dir, db_path, tuner_db_path)
    system_data = get_system_info(app_version, app_start_time, data_dir)
    tuner_data = check_tuner_connectivity(tuner_db_path)
    cache_data = check_cache_state(tuner_db_path)
    config_data = run_config_checks(db_path, tuner_db_path)
    startup_data = get_startup_summary()

    try:
        zip_bytes = build_support_bundle(
            data_dir, health_data, system_data,
            extra={
                "tuners.json": tuner_data,
                "cache_state.json": cache_data,
                "config.json": config_data,
                "startup.json": startup_data,
            },
        )
    except Exception as exc:
        logger.exception("Failed to build support bundle: %s", exc)
        abort(500)

    filename = f"retroiptv-support-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
    return send_file(
        io.BytesIO(zip_bytes),
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )
