"""Minimal test stub for environments without pymap3d installed."""

from __future__ import annotations

import numpy as np


def geodetic2enu(lat, lon, alt, lat0, lon0, alt0):
    lat_arr = np.asarray(lat, dtype=np.float64)
    alt_arr = np.asarray(alt, dtype=np.float64)
    zeros = np.zeros_like(lat_arr, dtype=np.float64)
    return zeros, zeros.copy(), np.zeros_like(alt_arr, dtype=np.float64)
