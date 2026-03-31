"""Track HTTP request activity so background tasks can go idle.

Background tasks (runtime-settings sync, weather backfill, LLM usage worker)
poll the ``is_idle()`` function and skip work when the service has had no
inbound HTTP traffic for ``IDLE_THRESHOLD_S`` seconds (default 600 = 10 min).
This lets Railway detect true idle and sleep the container.
"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)

IDLE_THRESHOLD_S: float = float(os.environ.get("IDLE_THRESHOLD_S", "600"))

# Initialise to now so background tasks run normally during startup.
_last_activity: float = time.monotonic()

# How long idle tasks sleep before re-checking (seconds).
IDLE_POLL_S: float = 60.0


def record_activity() -> None:
    """Stamp the current time as the most recent HTTP request."""
    global _last_activity
    _last_activity = time.monotonic()


def is_idle() -> bool:
    """Return True when no HTTP request has arrived for IDLE_THRESHOLD_S."""
    return (time.monotonic() - _last_activity) > IDLE_THRESHOLD_S


def seconds_since_last_activity() -> float:
    """Seconds elapsed since the last recorded HTTP request."""
    return time.monotonic() - _last_activity
