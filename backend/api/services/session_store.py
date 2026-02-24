"""Session lifecycle management: storage, retrieval, deletion.

Manages the mapping between session IDs and their stored data
(resampled DataFrames, metadata, snapshots).

All functions are stubs awaiting Phase 1 implementation.
"""

from __future__ import annotations


async def store_session_data(
    session_id: str,
    data: dict[str, object],
) -> None:
    """Persist processed session data to disk or object store.

    Stores resampled DataFrames as Parquet files and metadata as JSON
    under ``{session_data_dir}/{session_id}/``.
    """
    raise NotImplementedError


async def load_session_data(session_id: str) -> dict[str, object]:
    """Load stored session data from disk or object store.

    Returns a dict containing resampled_laps, lap_summaries,
    corners, and metadata.
    """
    raise NotImplementedError


async def delete_session_data(session_id: str) -> None:
    """Remove stored session data from disk or object store.

    Deletes all files under ``{session_data_dir}/{session_id}/``.
    """
    raise NotImplementedError


async def list_stored_sessions() -> list[str]:
    """List all session IDs with stored data on disk."""
    raise NotImplementedError
