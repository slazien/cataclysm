"""Rate limiting for anonymous (unauthenticated) uploads."""

from __future__ import annotations

import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

# Max anonymous sessions per IP per 24 hours
MAX_ANON_PER_IP: int = 3
# Global daily budget for anonymous reports
MAX_ANON_GLOBAL_DAILY: int = 50
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


def check_anon_rate_limit(ip: str) -> tuple[bool, str]:
    """Check if an anonymous upload from this IP is allowed.

    Returns (allowed, reason). If not allowed, reason explains why.
    """
    now = time.time()

    # Check global budget
    _global_timestamps[:] = _cleanup_old(_global_timestamps, now)
    if len(_global_timestamps) >= MAX_ANON_GLOBAL_DAILY:
        return False, "We're at capacity for anonymous sessions. Sign in for guaranteed access."

    # Check per-IP limit
    _ip_timestamps[ip] = _cleanup_old(_ip_timestamps[ip], now)
    if len(_ip_timestamps[ip]) >= MAX_ANON_PER_IP:
        return False, "Anonymous session limit reached (3 per day). Sign in to analyze more."

    return True, ""


def record_anon_upload(ip: str) -> None:
    """Record a successful anonymous upload for rate limiting."""
    now = time.time()
    _ip_timestamps[ip].append(now)
    _global_timestamps.append(now)
