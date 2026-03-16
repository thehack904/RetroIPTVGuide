"""Centralised logging configuration for RetroIPTVGuide.

Sets up:
  - A rotating file handler  (10 MB, keep 5) writing to DATA_DIR/logs/retroiptvguide.log
  - A console (stderr) stream handler
  - An unhandled-exception hook so crash tracebacks land in the log file

Call ``configure_logging()`` once at application startup, before the first
``logging.getLogger(...)`` call, to activate the handlers.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def configure_logging(data_dir: str, log_level: int = logging.INFO) -> logging.Logger:
    """Configure rotating file + console logging and return the root logger.

    Parameters
    ----------
    data_dir:
        The resolved DATA_DIR path (must already exist or be create-able).
    log_level:
        Minimum log level for all handlers (default: INFO).
    """
    log_dir = os.path.join(data_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "retroiptvguide.log")

    root_logger = logging.getLogger()
    # Avoid adding duplicate handlers when configure_logging is called more than once
    if root_logger.handlers:
        return root_logger

    root_logger.setLevel(log_level)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- rotating file handler ---
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)
    except (PermissionError, OSError) as exc:
        # If we cannot write the log file, warn on stderr but keep running.
        print(
            f"[RetroIPTVGuide] WARNING: cannot open log file {log_file!r}: {exc}",
            file=sys.stderr,
        )

    # --- console handler ---
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # --- unhandled-exception hook ---
    def _log_unhandled(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        root_logger.critical(
            "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb)
        )

    sys.excepthook = _log_unhandled

    return root_logger
