"""Selective knowledge base injection based on telemetry patterns and skill level."""

from __future__ import annotations

import statistics

from cataclysm.corners import Corner
from cataclysm.gains import GainEstimate

MPS_TO_MPH = 2.23694

# Maximum tokens of KB context to inject into the prompt.
MAX_INJECTION_TOKENS = 2000
# Approximate tokens-per-character ratio for English text.
CHARS_PER_TOKEN = 4.0

# ---------------------------------------------------------------------------
# Condensed coaching-ready KB snippets keyed by section ID.
# Each snippet is a tight 2-4 sentence reference the AI coach can draw on.
# ---------------------------------------------------------------------------
KB_SNIPPETS: dict[str, str] = {
    # --- Skill-level: novice ---
    "8.4": (
        "Finding the limit safely: reject the myth that you must spin to know the limit. "
        "Instead, take small bites — a little more entry speed, a little earlier throttle. "
        "Check exit speed on the tach to judge whether added speed is actually faster. "
        "Loss of control is evidence of failure, not progress."
    ),
    "8.5": (
        "Incremental speed building: never make a giant leap of faith in speed. "
        "Move brake points closer in 3-foot increments. Increase corner speed 1 mph at a time. "
        "Ten small nibbles are safer and faster than two big bites."
    ),
    "8.10": (
        "Confidence through accuracy: accuracy and car control are prerequisites for working "
        "on tenths. If you are spinning, missing apexes, or driving sloppily, there is no way "
        "to shave time. Aim for 50+ laps without a significant departure before chasing speed."
    ),
    "1.1": (
        "Reference points: identify concrete physical markers for turn-in, apex, and track-out "
        "(pavement cracks, curbing edges, signs). A 12-inch miss at turn-in can cost 0.7 mph of "
        "cornering speed, which over a 20-second straight translates to two car lengths lost. "
        "Consistency comes from hitting the same marks lap after lap."
    ),
    # --- Skill-level: intermediate ---
    "2.5": (
        "The Procedure for optimizing braking: (1) find threshold first — brake harder on "
        "successive laps until occasional lockup. (2) Once at threshold, move the brake point "
        "closer in small increments. (3) If entry speed pushes you off-line or delays throttle, "
        "back up. Critical: find braking force FIRST, then move the point later."
    ),
    "3.6": (
        "Brake-to-throttle transition effects: a slow, gradual transition maintains balance. "
        "An abrupt transition delivers instant full cornering traction to the front, causing "
        "aggressive rotation. An intentional pause creates trailing-throttle oversteer for extra "
        "yaw. Match the style to the corner: extra rotation for tight corners, smooth for sweepers."
    ),
    "5.2": (
        "Throttle corrections for understeer: when the car understeers at corner exit, surrender "
        "some throttle to transfer load back to the front tires. More steering lock actually makes "
        "understeer worse by exceeding optimal slip angle. Adjust the throttle, not the steering."
    ),
    # --- Skill-level: advanced ---
    "5.4": (
        "Rotation magnitude and velocity: as a car enters a corner it must rotate from zero yaw "
        "to its target angle. Under-rotation creates understeer; over-rotation causes oversteer "
        "requiring correction. Advanced drivers manage not just yaw angle but rotational velocity."
    ),
    "5.5": (
        "Yaw angle vs slip angle: yaw is the angle between the car's centerline and "
        "direction of travel. Excessive yaw scrubs speed — racers need 'just enough' yaw. "
        "Slip angle is per-tire while yaw is whole-car; they are distinct concepts."
    ),
    "A.1": (
        "Coefficient of friction decreases with load: CF drops as download increases (e.g. 1.75 at "
        "150 lbs to 1.25 at 450 lbs). Total grip still increases but at a diminishing rate. This "
        "is why lighter cars achieve higher cornering Gs and minimizing load transfer is critical."
    ),
    # --- Per-corner pattern triggers ---
    "4.1": (
        "Early apex corrections: the primary symptom is needing MORE steering past the apex. "
        "At racing speed you should ALWAYS be unwinding steering at corner exit. Early apex is "
        "the single most common cause of spins and going off at corner exit. Fix: delay turn-in, "
        "use a later apex, and check that steering unwinds through exit."
    ),
    "2.7": (
        "Brake points as variable references: brake points are not fixed — they vary with speed, "
        "conditions, and traffic. Establish a brake point for every corner and then work off that "
        "reference. Creative reference points (number boards, pavement cracks, curbing changes) "
        "improve consistency."
    ),
    "3.5": (
        "Throttle application point varies with corner angle: 75-degree corner at 55 mph has a "
        "brake-turn zone of barely 30 feet. 90-degree: 86 feet. 135-degree: exceeds 240 feet. "
        "Lower-powered cars have earlier throttle points. Throttle also moves earlier as corner "
        "speed increases due to aerodynamic drag."
    ),
    "5.3": (
        "The 'never lift' trap: drivers who refuse to lift in fast corners that generate "
        "understeer often spin at exit. They add steering lock while the car plows, then "
        "finally lift abruptly causing snap oversteer. A small breathe early would restore "
        "front grip. The 'never lift' philosophy is frequently slower than a slight lift."
    ),
    "8.8": (
        "Red mist / focus effort: when frustrated with lap time, resist increasing aggressiveness "
        "everywhere. Data shows even a driver 2 seconds off pace performs well in many places. "
        "Identify the specific corners where you are losing time and focus exclusively there."
    ),
    "10.4": (
        "Short corner strategy: short corners require minimal trail braking. Trail-brake only "
        "briefly past turn-in, then give quick aggressive throttle. Get braking done, make a quick "
        "direction change, and get on full throttle as soon as possible."
    ),
    "10.3": (
        "When NOT to trail-brake: for corners with very small speed losses (1-4 mph), "
        "trail braking is inappropriate — insufficient time for a smooth transition. "
        "Any abrupt lift while cornering creates oversteer. Better to do the speed loss "
        "on the straight with a breathe before turn-in."
    ),
    "10.5": (
        "Long-radius carousel strategy: start at threshold, then maintain a lower but constant "
        "braking level deep into the corner until the brake-throttle transition. The long distance "
        "between turn-in and throttle allows using the early corner portion to slow the car while "
        "turning."
    ),
}

# ---------------------------------------------------------------------------
# Trigger mappings
# ---------------------------------------------------------------------------
_SKILL_SNIPPETS: dict[str, list[str]] = {
    "novice": ["8.4", "8.5", "8.10", "1.1"],
    "intermediate": ["2.5", "3.6", "5.2"],
    "advanced": ["5.4", "5.5", "A.1"],
}

# Per-corner pattern thresholds
_EARLY_APEX_FRACTION = 0.50  # >50% of laps have early apex
_BRAKE_VARIANCE_M = 8.0  # std(brake_point_m) threshold
_LOW_BRAKE_G = 0.4  # mean(peak_brake_g) < this
_LATE_THROTTLE_M = 30.0  # throttle_commit - apex > this
_MIN_SPEED_VARIANCE_MPH = 3.0  # std(min_speed) in mph
_LARGE_GAIN_S = 0.3  # gain_s threshold for consistency gain
_SHORT_CORNER_MPH = 8.0  # entry - min speed < this
_LONG_CORNER_MPH = 25.0  # entry - min speed > this


def _estimate_char_budget() -> int:
    """Return the character budget corresponding to MAX_INJECTION_TOKENS."""
    return int(MAX_INJECTION_TOKENS * CHARS_PER_TOKEN)


def _corner_pattern_snippets(
    all_lap_corners: dict[int, list[Corner]],
    gains: GainEstimate | None,
) -> list[tuple[str, float]]:
    """Detect per-corner telemetry patterns and return (snippet_id, priority) pairs.

    Priority is the estimated gain in seconds for that corner (higher = inject first).
    Falls back to 0.1 when gain data is unavailable.
    """
    if not all_lap_corners:
        return []

    # Build per-corner-number data across laps
    corner_nums: set[int] = set()
    for corners in all_lap_corners.values():
        for c in corners:
            corner_nums.add(c.number)

    # Build a gain lookup: corner number -> gain_s
    gain_lookup: dict[int, float] = {}
    if gains is not None:
        for sg in gains.consistency.segment_gains:
            if sg.segment.is_corner:
                # Extract corner number from name like "T5"
                try:
                    cnum = int(sg.segment.name[1:])
                    gain_lookup[cnum] = sg.gain_s
                except (ValueError, IndexError):
                    pass

    results: list[tuple[str, float]] = []

    for cnum in sorted(corner_nums):
        corner_data = [
            c for lap_corners in all_lap_corners.values() for c in lap_corners if c.number == cnum
        ]
        if not corner_data:
            continue

        priority = gain_lookup.get(cnum, 0.1)

        # Early apex dominant
        early_count = sum(1 for c in corner_data if c.apex_type == "early")
        if early_count / len(corner_data) > _EARLY_APEX_FRACTION:
            results.append(("4.1", priority))

        # High brake variance
        brake_pts = [c.brake_point_m for c in corner_data if c.brake_point_m is not None]
        if len(brake_pts) >= 2 and statistics.stdev(brake_pts) > _BRAKE_VARIANCE_M:
            results.append(("2.7", priority))

        # Low peak brake G
        brake_gs = [abs(c.peak_brake_g) for c in corner_data if c.peak_brake_g is not None]
        if brake_gs and statistics.mean(brake_gs) < _LOW_BRAKE_G:
            results.append(("2.5", priority))

        # Late throttle commit
        throttle_offsets = [
            c.throttle_commit_m - c.apex_distance_m
            for c in corner_data
            if c.throttle_commit_m is not None
        ]
        if throttle_offsets and statistics.median(throttle_offsets) > _LATE_THROTTLE_M:
            results.append(("3.5", priority))
            results.append(("5.3", priority))

        # High min-speed variance
        speeds_mph = [c.min_speed_mps * MPS_TO_MPH for c in corner_data]
        if len(speeds_mph) >= 2 and statistics.stdev(speeds_mph) > _MIN_SPEED_VARIANCE_MPH:
            results.append(("8.10", priority))

        # Large consistency gain
        if gain_lookup.get(cnum, 0.0) > _LARGE_GAIN_S:
            results.append(("8.8", priority))

        # Short corner (small speed loss) — estimate via kinematics
        speed_losses_mph: list[float] = []
        for c in corner_data:
            if (
                c.brake_point_m is not None
                and c.peak_brake_g is not None
                and c.exit_distance_m > c.entry_distance_m
            ):
                brake_dist = c.entry_distance_m - c.brake_point_m
                # v^2 = v0^2 - 2*a*d
                decel_mps2 = abs(c.peak_brake_g) * 9.81
                entry_speed_mps = (
                    c.min_speed_mps**2 + 2 * decel_mps2 * max(brake_dist, 0)
                ) ** 0.5
                speed_losses_mph.append(
                    (entry_speed_mps - c.min_speed_mps) * MPS_TO_MPH
                )

        if speed_losses_mph:
            median_loss = statistics.median(speed_losses_mph)
            if median_loss < _SHORT_CORNER_MPH:
                results.append(("10.4", priority))
                results.append(("10.3", priority))
            elif median_loss > _LONG_CORNER_MPH:
                results.append(("10.5", priority))

    return results


def select_kb_snippets(
    all_lap_corners: dict[int, list[Corner]],
    skill_level: str,
    gains: GainEstimate | None = None,
) -> str:
    """Select relevant Going Faster KB sections based on telemetry patterns.

    Returns a formatted string to append to the system prompt.
    Caps total injection at ~2,000 tokens to avoid prompt bloat.
    """
    char_budget = _estimate_char_budget()
    selected_ids: list[str] = []

    # 1. Skill-level snippets (always first priority)
    skill_ids = _SKILL_SNIPPETS.get(skill_level, _SKILL_SNIPPETS["intermediate"])
    for sid in skill_ids:
        if sid not in selected_ids:
            selected_ids.append(sid)

    # 2. Per-corner pattern triggers, sorted by gain (biggest opportunity first)
    pattern_triggers = _corner_pattern_snippets(all_lap_corners, gains)
    # Sort by priority descending, deduplicate
    pattern_triggers.sort(key=lambda x: x[1], reverse=True)
    for snippet_id, _ in pattern_triggers:
        if snippet_id not in selected_ids:
            selected_ids.append(snippet_id)

    # 3. Build output within token budget
    sections: list[str] = []
    total_chars = 0
    header = "## Additional Coaching Knowledge (from Going Faster! reference)\n"
    total_chars += len(header)

    for sid in selected_ids:
        snippet = KB_SNIPPETS.get(sid)
        if snippet is None:
            continue
        entry = f"- **[{sid}]** {snippet}"
        entry_chars = len(entry) + 1  # +1 for newline
        if total_chars + entry_chars > char_budget:
            break
        sections.append(entry)
        total_chars += entry_chars

    if not sections:
        return ""

    return header + "\n".join(sections)
