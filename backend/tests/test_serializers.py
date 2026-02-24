"""Tests for serialization helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.api.services.serializers import (
    dataclass_to_dict,
    dataframe_to_columnar,
    mps_to_mph,
    numpy_to_list,
)


def test_dataframe_to_columnar_basic() -> None:
    """Convert DataFrame columns to columnar dict."""
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0], "c": [7.0, 8.0, 9.0]})
    result = dataframe_to_columnar(df, ["a", "b"])
    assert "a" in result
    assert "b" in result
    assert "c" not in result
    assert result["a"] == [1.0, 2.0, 3.0]


def test_dataframe_to_columnar_missing_column() -> None:
    """Missing columns are skipped silently."""
    df = pd.DataFrame({"a": [1.0]})
    result = dataframe_to_columnar(df, ["a", "nonexistent"])
    assert "a" in result
    assert "nonexistent" not in result


def test_numpy_to_list() -> None:
    """Convert numpy array to Python list."""
    arr = np.array([1.0, 2.5, 3.7])
    result = numpy_to_list(arr)
    assert result == [1.0, 2.5, 3.7]
    assert isinstance(result, list)


def test_mps_to_mph() -> None:
    """Convert m/s to mph."""
    result = mps_to_mph(10.0)
    assert abs(result - 22.3694) < 0.001


@dataclass
class Inner:
    """Test inner dataclass."""

    x: int
    y: float


@dataclass
class Outer:
    """Test outer dataclass with nested types."""

    name: str
    inner: Inner
    items: list[Inner]
    mapping: dict[str, Inner]
    array: np.ndarray
    df: pd.DataFrame


def test_dataclass_to_dict_simple() -> None:
    """Convert a simple dataclass to dict."""
    obj = Inner(x=1, y=2.5)
    result = dataclass_to_dict(obj)
    assert result == {"x": 1, "y": 2.5}


def test_dataclass_to_dict_nested() -> None:
    """Convert nested dataclass with arrays and DataFrames."""
    obj = Outer(
        name="test",
        inner=Inner(x=1, y=2.5),
        items=[Inner(x=2, y=3.5), Inner(x=3, y=4.5)],
        mapping={"a": Inner(x=4, y=5.5)},
        array=np.array([1.0, 2.0]),
        df=pd.DataFrame({"col": [1, 2, 3]}),
    )
    result = dataclass_to_dict(obj)
    assert result["name"] == "test"
    assert result["inner"] == {"x": 1, "y": 2.5}
    assert result["items"] == [{"x": 2, "y": 3.5}, {"x": 3, "y": 4.5}]
    assert result["mapping"] == {"a": {"x": 4, "y": 5.5}}
    assert result["array"] == [1.0, 2.0]
    assert result["df"] == {"col": [1, 2, 3]}


def test_dataclass_to_dict_non_dataclass() -> None:
    """Non-dataclass objects get wrapped in a value dict."""
    result = dataclass_to_dict("hello")
    assert result == {"value": "hello"}
