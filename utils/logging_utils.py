"""Structured application logging (timestamp, user, role, action, status, duration)."""

import logging
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_logger = logging.getLogger("airline_ai")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    handler = logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    _logger.addHandler(console)


def log_event(user_id, role, action, status, duration_ms=None, error=None):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts = [
        ts,
        f"USER: {user_id}",
        f"ROLE: {role}",
        f"ACTION: {action}",
        f"STATUS: {status}",
    ]
    if duration_ms is not None:
        parts.append(f"DURATION: {int(duration_ms)}ms")
    if error:
        parts.append(f"ERROR: {error}")
    _logger.info(" | ".join(parts))
    if status != "SUCCESS":
        _logger.warning(" | ".join(parts))
