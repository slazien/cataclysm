"""Rate limiting for anonymous (unauthenticated) uploads."""

from __future__ import annotations

import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

# Max anonymous sessions per IP per 24 hours
MAX_ANON_PER_IP: int = 3
# Global daily budget for anonymous reports
MAX_ANON_GLOBAL_DAILY: int = 1000
# Window in seconds (24 hours)
WINDOW_SECONDS: int = 86400

# Track per-IP anonymous upload timestamps
_ip_timestamps: dict[str, list[float]] = defaultdict(list)
# Track global anonymous upload count
_global_timestamps: list[float] = []


def _cleanup_old(timestamps: list[float], now: float) -> list[float]:
    """Remove timestamps older than the window."""
    cutoff = now - WINDOW_SECONDS
    return [t for t in timestamps if t > cutoff]


def check_and_record_anon_upload(ip: str) -> tuple[bool, str]:
    """Atomically check rate limits and record the upload if allowed.

    Returns (allowed, reason). If allowed, the upload is recorded immediately
    to prevent TOCTOU races from concurrent requests.
    """
    now = time.time()

    # Check global budget
    _global_timestamps[:] = _cleanup_old(_global_timestamps, now)
    if len(_global_timestamps) >= MAX_ANON_GLOBAL_DAILY:
        return False, "We're at capacity for anonymous sessions. Sign in for guaranteed access."

    # Check per-IP limit (prune empty keys to prevent memory leak)
    recent = _cleanup_old(_ip_timestamps[ip], now)
    if not recent:
        del _ip_timestamps[ip]
    else:
        _ip_timestamps[ip] = recent
    if len(_ip_timestamps.get(ip, [])) >= MAX_ANON_PER_IP:
        return False, "Anonymous session limit reached (3 per day). Sign in to analyze more."

    # Record immediately (atomic with check) to prevent concurrent bypass
    _ip_timestamps[ip].append(now)
    _global_timestamps.append(now)

    return True, ""
