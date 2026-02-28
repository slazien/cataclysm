"""Shared constants for the cataclysm telemetry engine.

Centralises conversion factors and magic numbers used across multiple modules.
"""

from __future__ import annotations

# Speed conversion: meters per second → miles per hour
MPS_TO_MPH: float = 2.23694
MPH_TO_MPS: float = 1.0 / MPS_TO_MPH

# Speed conversion: meters per second → kilometers per hour
MPS_TO_KPH: float = 3.6
KPH_TO_MPS: float = 1.0 / MPS_TO_KPH
