"""Selective knowledge base injection based on telemetry patterns and skill level."""

from __future__ import annotations

import statistics

from cataclysm.constants import MPS_TO_MPH
from cataclysm.corners import Corner
from cataclysm.gains import GainEstimate

# Maximum tokens of KB context to inject into the prompt.
MAX_INJECTION_TOKENS = 3000
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
    # --- Load Transfer (LT) ---
    "LT.1": (
        "Load transfer under braking: at 1g braking in a typical 3000lb track car, approximately "
        "625 lbs transfers to the front tires — the front carries 71% of total vehicle weight. "
        "This is why front tire grip increases dramatically under braking, enabling trail braking "
        "to tighten your line."
    ),
    "LT.2": (
        "Lateral load transfer: at 1g cornering, the outside tires carry approximately 65-70% of "
        "total weight. Higher CG = more transfer = less total grip. Lowering the car or adding "
        "wider tires reduces this effect."
    ),
    # --- Brake Trace Patterns (BR) ---
    "BR.1": (
        "Optimal brake trace has 4 phases: (1) rapid initial application (0.1-0.2s), (2) peak "
        "maintenance near threshold, (3) progressive release as speed drops, (4) trail braking at "
        "5-10% pressure into the corner. Common problems: 'staircase' pattern (fear of lockup), "
        "plateau too low (not reaching max decel), abrupt release (no trail braking, causes weight "
        "shift instability)."
    ),
    # --- Survival Reactions (SR) ---
    "SR.1": (
        "Throttle lift mid-corner is the most dangerous survival reaction. If speed through a "
        "corner feels scary, the instinct is to lift — but this transfers weight forward, unloads "
        "the rear, and can cause snap oversteer. A small, deliberate breathe is safe; an abrupt "
        "panic lift is not. If you notice yourself lifting, the root issue is usually entering too "
        "fast. Address it at the brake point, not mid-corner."
    ),
    "SR.2": (
        "The $10 attention budget: you have limited mental bandwidth. If $8 goes to fear "
        "and survival reactions, only $2 is available for driving technique. As corners "
        "become automatic through practice, attention frees up for refinement. Focus on "
        "mastering one corner at a time rather than trying to be fast everywhere."
    ),
    # --- Drivetrain-Specific (DT) ---
    "DT.1": (
        "FWD-specific: understeer is the natural limit behavior. Throttle mid-corner "
        "pulls the front tires toward the exit, increasing understeer. Technique: "
        "throttle application should be earlier and more progressive than RWD. Trail "
        "braking is the primary rotation tool since throttle doesn't create oversteer."
    ),
    "DT.2": (
        "RWD-specific: oversteer is the natural limit behavior on throttle. Too much throttle too "
        "early causes the rear to step out. Technique: wait for the car to rotate, then apply "
        "throttle progressively as steering unwinds. The throttle-to-steering relationship is your "
        "primary balance control."
    ),
    "DT.3": (
        "AWD-specific: behaves like FWD at entry (front-biased torque split) and like RWD at exit "
        "(rear receives more torque under acceleration). Technique: can be more aggressive with "
        "entry speed but must manage understeer on initial throttle. Trail braking window is "
        "shorter because AWD rotates less under braking."
    ),
    # --- Wet Weather (WET) ---
    "WET.1": (
        "Wet line differs from dry line: avoid rubber-laid racing line (it's the most slippery "
        "surface when wet). Drive off-line on rougher pavement for more grip. Brake points move "
        "50-100m earlier. Steering and throttle inputs must be 30-50% more gradual. All grip "
        "thresholds drop to 40-60% of dry levels."
    ),
    # --- Vision & Mental Focus (VIS) ---
    "VIS.1": (
        "Look where you want to go, not where you are. Expert drivers show 2x more head rotation "
        "than novices (van Leeuwen 2017). At corner entry, eyes should already be on the apex. At "
        "the apex, eyes should be on the exit. Vision leads the car by 1-2 seconds. If you're "
        "looking at the apex when you arrive there, you're late."
    ),
    # --- Aero effects at high speed ---
    "AERO.1": (
        "Above 80 mph, aerodynamic forces become significant. Downforce increases grip "
        "quadratically with speed — a car with modest aero produces 50-100 lbs of "
        "downforce at 80 mph but 200-400 lbs at 120 mph. In fast corners, trust the "
        "grip from aero: reduce steering input and carry speed. Abrupt speed changes in "
        "aero-dependent corners cause sudden grip loss."
    ),
}

# ---------------------------------------------------------------------------
# Trigger mappings
# ---------------------------------------------------------------------------
_SKILL_SNIPPETS: dict[str, list[str]] = {
    "novice": ["8.4", "8.5", "8.10", "1.1", "VIS.1", "SR.2"],
    "intermediate": ["2.5", "3.6", "5.2", "LT.1", "BR.1"],
    "advanced": ["5.4", "5.5", "A.1", "LT.2"],
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

# Session-level pattern thresholds
_SURVIVAL_SPEED_DROP_MPH = 3.0  # sudden speed drop apex-to-exit
_LOW_COMBINED_G = 0.7  # peak combined G threshold
_SHORT_BRAKE_ZONE_M = 30.0  # brake-to-apex distance threshold
_HIGH_SPEED_CORNER_MPH = 80.0  # aero effects become relevant


def _estimate_char_budget() -> int:
    """Return the character budget corresponding to MAX_INJECTION_TOKENS."""
    return int(MAX_INJECTION_TOKENS * CHARS_PER_TOKEN)


def _session_level_snippets(
    all_lap_corners: dict[int, list[Corner]],
) -> list[tuple[str, float]]:
    """Detect session-wide telemetry patterns and return (snippet_id, priority) pairs.

    These patterns look at aggregate data across all corners and all laps,
    rather than per-corner analysis.  Priority is set to 0.15 (above default
    0.1 but below gain-driven corner triggers).
    """
    if not all_lap_corners:
        return []

    results: list[tuple[str, float]] = []
    session_priority = 0.15

    # Collect all corners across all laps
    all_corners: list[Corner] = [c for lap_corners in all_lap_corners.values() for c in lap_corners]

    if not all_corners:
        return []

    # --- Survival reaction: throttle lift mid-corner ---
    # Detect if any corner shows speed dropping >3 mph between apex and exit.
    # We approximate exit speed from the next corner's entry or use min_speed
    # as a proxy — if the apex speed is significantly higher than what kinematic
    # models predict for the corner geometry, it suggests a mid-corner lift.
    # Simpler proxy: look for corners where brake data shows braking *after* the apex.
    for _lap_num, lap_corners in all_lap_corners.items():
        for c in lap_corners:
            if c.throttle_commit_m is None:
                continue
            # If throttle commit is significantly past exit, the driver likely lifted
            if c.throttle_commit_m > c.exit_distance_m:
                results.append(("SR.1", session_priority))
                break
        else:
            continue
        break

    # --- Low grip utilization: peak combined G < 0.7g across session ---
    brake_gs = [abs(c.peak_brake_g) for c in all_corners if c.peak_brake_g is not None]
    if brake_gs and max(brake_gs) < _LOW_COMBINED_G:
        results.append(("LT.1", session_priority))

    # --- Short braking zone: brake-to-apex < 30m ---
    short_brake_count = 0
    total_brake_count = 0
    for c in all_corners:
        if c.brake_point_m is not None:
            total_brake_count += 1
            brake_to_apex = c.apex_distance_m - c.brake_point_m
            if 0 < brake_to_apex < _SHORT_BRAKE_ZONE_M:
                short_brake_count += 1
    if total_brake_count > 0 and short_brake_count / total_brake_count > 0.3:
        results.append(("BR.1", session_priority))

    # --- High speed corners: >80 mph min speed (aero effects relevant) ---
    high_speed_count = sum(
        1 for c in all_corners if c.min_speed_mps * MPS_TO_MPH > _HIGH_SPEED_CORNER_MPH
    )
    if high_speed_count > 0:
        results.append(("AERO.1", session_priority))

    return results


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
                entry_speed_mps = (c.min_speed_mps**2 + 2 * decel_mps2 * max(brake_dist, 0)) ** 0.5
                speed_losses_mph.append((entry_speed_mps - c.min_speed_mps) * MPS_TO_MPH)

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
    Caps total injection at ~3,000 tokens to avoid prompt bloat.

    Priority system when total snippets exceed the token budget:
    1. Top-3-gain corner snippets (highest priority)
    2. Skill-level base snippets
    3. Pattern-triggered snippets (per-corner, sorted by gain)
    4. Session-level pattern snippets (supplementary context)
    """
    char_budget = _estimate_char_budget()

    # --- Phase 1: Collect top-3-gain corner snippets (highest priority) ---
    top_gain_ids: list[str] = []
    pattern_triggers = _corner_pattern_snippets(all_lap_corners, gains)
    # Sort by priority descending (gain in seconds)
    pattern_triggers.sort(key=lambda x: x[1], reverse=True)
    # Take the top 3 unique snippet IDs from the highest-gain corners
    seen_top: set[str] = set()
    for snippet_id, _priority in pattern_triggers[:6]:  # scan extra for dedup
        if snippet_id not in seen_top:
            top_gain_ids.append(snippet_id)
            seen_top.add(snippet_id)
        if len(top_gain_ids) >= 3:
            break

    # --- Phase 2: Skill-level base snippets ---
    skill_ids = _SKILL_SNIPPETS.get(skill_level, _SKILL_SNIPPETS["intermediate"])

    # --- Phase 3: Remaining pattern-triggered snippets ---
    remaining_pattern_ids: list[str] = []
    for snippet_id, _ in pattern_triggers:
        if snippet_id not in seen_top:
            remaining_pattern_ids.append(snippet_id)

    # --- Phase 4: Session-level pattern snippets ---
    session_triggers = _session_level_snippets(all_lap_corners)
    session_ids = [sid for sid, _ in session_triggers]

    # --- Assemble final ordered list with deduplication ---
    selected_ids: list[str] = []
    seen: set[str] = set()

    def _add_unique(ids: list[str]) -> None:
        for sid in ids:
            if sid not in seen:
                selected_ids.append(sid)
                seen.add(sid)

    _add_unique(top_gain_ids)
    _add_unique(skill_ids)
    _add_unique(remaining_pattern_ids)
    _add_unique(session_ids)

    # --- Build output within token budget ---
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
