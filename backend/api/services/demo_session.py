"""Demo session constants and helpers.

A single well-known session is pre-loaded at startup so visitors can explore
the full app experience without uploading or signing up.  The demo session
is stored in PostgreSQL like a regular session but belongs to a sentinel
user (``__demo__``) and is protected from LRU eviction.
"""

from __future__ import annotations

DEMO_SESSION_ID = "barber_motorsports_p_20260222_b101ba9c"
DEMO_USER_ID = "__demo__"


def is_demo_session(session_id: str) -> bool:
    """Return True if *session_id* is the well-known demo session."""
    return session_id == DEMO_SESSION_ID
