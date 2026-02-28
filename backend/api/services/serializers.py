"""Data serialization helpers: DataFrame to JSON, numpy to list, dataclass to dict.

Bridges the gap between cataclysm's internal data types (DataFrames,
numpy arrays, dataclasses) and Pydantic API schemas.

All functions are stubs awaiting Phase 1 implementation.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from cataclysm.constants import MPS_TO_MPH


def dataframe_to_columnar(df: pd.DataFrame, columns: list[str]) -> dict[str, list[float]]:
    """Convert selected DataFrame columns to a columnar JSON-ready dict.

    Each key maps to a list of float values. Handles numpy types by
    converting to native Python floats.
    """
    result: dict[str, list[float]] = {}
    for col in columns:
        if col in df.columns:
            result[col] = df[col].tolist()
    return result


def numpy_to_list(arr: np.ndarray) -> list[float]:
    """Convert a numpy array to a plain Python list of floats."""
    return arr.tolist()  # type: ignore[no-any-return]


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Recursively convert a dataclass to a JSON-serializable dict.

    Handles nested dataclasses, numpy arrays, and pandas DataFrames.
    """
    from dataclasses import fields

    if not hasattr(obj, "__dataclass_fields__"):
        return {"value": obj}

    result: dict[str, Any] = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        if isinstance(value, np.ndarray):
            result[f.name] = value.tolist()
        elif isinstance(value, pd.DataFrame):
            result[f.name] = value.to_dict(orient="list")
        elif hasattr(value, "__dataclass_fields__"):
            result[f.name] = dataclass_to_dict(value)
        elif isinstance(value, dict):
            result[f.name] = {
                k: dataclass_to_dict(v) if hasattr(v, "__dataclass_fields__") else v
                for k, v in value.items()
            }
        elif isinstance(value, list):
            result[f.name] = [
                dataclass_to_dict(item) if hasattr(item, "__dataclass_fields__") else item
                for item in value
            ]
        else:
            result[f.name] = value

    return result


def mps_to_mph(speed_mps: float) -> float:
    """Convert meters per second to miles per hour."""
    return speed_mps * MPS_TO_MPH
