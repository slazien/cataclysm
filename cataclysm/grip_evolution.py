"""Session-level grip evolution model.

Models how track surface grip increases as rubber is laid down during a session.
Per-compound buildup parameters derived from iRacing/Assetto Corsa research.
"""

from __future__ import annotations

# (grip_buildup, n_saturation) per compound category.
# grip_buildup: magnitude of initial grip deficit (higher = more room to gain).
# n_saturation: number of laps until track is fully rubbered.
_COMPOUND_PARAMS: dict[str, tuple[float, int]] = {
    "street": (0.08, 5),
    "endurance_200tw": (0.05, 4),
    "super_200tw": (0.04, 4),
    "100tw": (0.03, 3),
    "r_comp": (0.03, 3),
    "slick": (0.02, 2),
}

_DEFAULT_PARAMS: tuple[float, int] = (0.05, 4)


def compute_grip_factor(lap_number: int, compound_category: str) -> float:
    """Return grip scaling factor in (0, 1].

    1.0 means the track is fully rubbered-in. Values below 1.0 represent
    reduced grip early in a session before sufficient rubber is laid down.

    Args:
        lap_number: 1-based lap index within the session.
        compound_category: Tire compound key (e.g. "street", "slick").

    Returns:
        Grip factor between (0, 1].

    Raises:
        ValueError: If lap_number < 1.
    """
    if lap_number < 1:
        raise ValueError(f"lap_number must be >= 1, got {lap_number}")

    buildup, n_sat = _COMPOUND_PARAMS.get(compound_category, _DEFAULT_PARAMS)

    if lap_number >= n_sat:
        return 1.0

    deficit = buildup / (1.0 + buildup)
    factor = 1.0 - deficit * max(0.0, 1.0 - lap_number / n_sat)
    return factor
