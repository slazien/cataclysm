"""Claude API integration for AI-powered driving coaching."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from cataclysm.causal_chains import SessionCausalAnalysis, format_causal_context_for_prompt
from cataclysm.coaching_validator import CoachingValidator
from cataclysm.constants import MPS_TO_MPH
from cataclysm.corner_analysis import SessionCornerAnalysis
from cataclysm.corner_line import (
    CornerLineProfile,
    format_line_analysis_for_prompt,
    format_session_line_summary_for_prompt,
    summarize_session_lines,
)
from cataclysm.corners import Corner
from cataclysm.corners_gained import CornersGainedResult, format_corners_gained_for_prompt
from cataclysm.driver_archetypes import ArchetypeResult, format_archetype_for_prompt
from cataclysm.driving_physics import COACHING_SYSTEM_PROMPT
from cataclysm.engine import LapSummary
from cataclysm.equipment import EquipmentProfile, SessionConditions
from cataclysm.flow_lap import FlowLapResult
from cataclysm.gains import GainEstimate
from cataclysm.kb_selector import select_kb_snippets
from cataclysm.landmarks import (
    _BRAKE_PREFERRED_TYPES,
    Landmark,
    find_nearest_landmark,
    format_corner_landmarks,
)
from cataclysm.optimal_comparison import OptimalComparisonResult
from cataclysm.skill_detection import SkillAssessment, format_skill_for_prompt
from cataclysm.topic_guardrail import TOPIC_RESTRICTION_PROMPT
from cataclysm.track_db import TrackLayout, get_key_corners, get_peculiarities

logger = logging.getLogger(__name__)

_SPEED_MARKER_RE = re.compile(r"\{\{speed:([\d.]+)\}\}")


def resolve_speed_markers(text: str, *, metric: bool = False) -> str:
    """Resolve ``{{speed:N}}`` markers to display text.  N is always mph."""

    def _replace(m: re.Match[str]) -> str:
        val = m.group(1)
        try:
            mph = float(val)
        except ValueError:
            return val
        if metric:
            dec = len(val.split(".")[1]) if "." in val else 0
            return f"{mph * 1.60934:.{dec}f} km/h"
        return f"{val} mph"

    return _SPEED_MARKER_RE.sub(_replace, text)


_validator: CoachingValidator | None = None


def _get_validator() -> CoachingValidator:
    global _validator  # noqa: PLW0603
    if _validator is None:
        _validator = CoachingValidator()
    return _validator


# Anthropic client settings for resilience against transient API errors (429, 529, 5xx)
_API_MAX_RETRIES = 4  # 5 total attempts with exponential backoff + jitter
_API_TIMEOUT_S = 120.0  # generous timeout for overloaded periods

SkillLevel = str  # "novice", "intermediate", "advanced"

_SKILL_PROMPTS: dict[str, str] = {
    "novice": (
        "\n## Skill Level: Novice (HPDE Group 1-2)\n"
        "This driver is new to track driving. Adapt your coaching style:\n\n"
        "**Content focus:**\n"
        "- Line consistency: are they hitting the same line each lap?\n"
        "- Smooth inputs: abrupt braking/throttle transitions hurt novices most\n"
        "- Basic braking: are they braking in a straight line before turn-in?\n"
        "- Limit to 1-2 priorities TOTAL (not per corner) — information overload is the "
        "#1 mistake coaches make with novices\n"
        "- Do NOT discuss trail braking, threshold braking, or advanced techniques\n"
        "- Grade trail_braking as 'N/A' for novices\n\n"
        "**Communication style:**\n"
        "- Use SHORT sentences with MINIMAL jargon. 'The car doesn't want to turn' "
        "not 'you have excessive understeer'\n"
        "- Use SENSORY language: 'feel the nose dip', 'squeeze the brake like a sponge'\n"
        "- Give REFERENCE POINTS, not reactive commands: 'Brake at the 3-board' "
        "not 'brake later'\n"
        "- Frame FORWARD only — never dwell on past mistakes, only what to do next lap\n"
        "- Celebrate what they're doing well — confidence building is critical\n"
        "- Use metaphors: 'dance with the car', 'unwind the steering like unwinding a spring', "
        "'the tires are a pie — braking and turning share the same slice'\n"
    ),
    "intermediate": (
        "\n## Skill Level: Intermediate (HPDE Group 3)\n"
        "This driver has solid fundamentals and may be hitting a plateau. "
        "Adapt your coaching style:\n\n"
        "**Content focus:**\n"
        "- Trail braking: are they carrying brake into the corner entry?\n"
        "- Brake point optimization: can they brake later or release more gradually?\n"
        "- Throttle timing: are they getting on throttle at the right point?\n"
        "- 'No dead time': is there coast between brake release and throttle? Eliminate it\n"
        "- Consistency: compare their best corner executions vs typical ones\n"
        "- Show all metrics and be specific about what to work on\n\n"
        "**Communication style:**\n"
        "- Use SOCRATIC questioning: 'Your T5 on L7 was 50 mph — what were you doing "
        "differently than the other laps at 47 mph?' This builds self-coaching ability\n"
        "- Compare against THEIR OWN data: 'You already carried that speed on L7 — "
        "the potential is proven'\n"
        "- Frame as EXPERIMENTS: 'Try anchoring to the 2-board for 3 laps, then compare'\n"
        "- Reframe abstract metrics to tangible ones: '0.1s = 10 inches at this speed'\n"
        "- Plateau-breaking techniques: isolate ONE variable, exaggerate it, then dial back\n"
    ),
    "advanced": (
        "\n## Skill Level: Advanced (HPDE Group 4+ / Instructor)\n"
        "This driver has strong technique and is hunting marginal gains. "
        "Adapt your coaching style:\n\n"
        "**Content focus:**\n"
        "- Corner EXIT speed is king: 1 mph more at exit compounds down the straight\n"
        "- Brake release PROFILE: shape of the release curve, not just brake point\n"
        "- Micro-sector analysis: where are tenths hiding in the data?\n"
        "- Consistency as the primary metric: variance analysis, not just best-lap speed\n"
        "- Setup correlation hints: do certain corners suggest car balance issues?\n"
        "- Trail brake modulation, weight transfer management, rotation technique\n\n"
        "**Communication style:**\n"
        "- Use PRECISE technical language — this driver knows the vocabulary\n"
        "- Reference mini-sector splits and exact distances/speeds\n"
        "- Frame as analysis, not instruction: 'The data shows your brake release in T5 "
        "has a 0.3G/s rate vs 0.5G/s on L4 — the progressive release on L4 gave 0.8 mph "
        "more through the apex'\n"
        "- Discuss ROTATION vs oversteer: deliberate rotation is a tool, not a problem\n"
        "- Support mental programming: trigger words, trust in subconscious execution\n"
    ),
}

_DRILL_TEMPLATES: dict[str, str] = {
    "brake_consistency": (
        "Brake marker drill: Pick a fixed reference point "
        "(cone, crack, shadow) for T{corner} braking. Spend "
        "3 laps hitting that exact point every time — "
        "consistency before speed."
    ),
    "trail_braking": (
        "Trail brake drill for T{corner}: Spend 2 laps "
        "focusing on slowly releasing brake pressure after "
        "turn-in. Feel the front load helping the car rotate. "
        "Brake trace should taper gradually, not drop off a "
        "cliff."
    ),
    "throttle_timing": (
        "Throttle commit drill for T{corner}: On your next "
        "3 laps, deliberately wait until you feel the car "
        "rotating before applying throttle. Start with light "
        "throttle and progressively squeeze to full power as "
        "you unwind steering."
    ),
    "min_speed": (
        "Corner speed drill for T{corner}: This lap, focus "
        "on carrying {{speed:2}}-{{speed:3}} more through the apex by braking "
        "a touch earlier and trailing off smoothly. The goal "
        "is a rounder, faster arc — not a V-shaped speed trace."
    ),
    "line_consistency": (
        "Line consistency drill for T{corner}: Pick 3 visual "
        "references — turn-in point, apex curb, and track-out "
        "point. Spend 3 laps hitting all three every time. "
        "Consistent line before fast line."
    ),
    "smoothness": (
        "Smoothness drill for T{corner}: Spend 2 laps at 80% "
        "pace focusing purely on smooth transitions — gradual "
        "brake release, gentle turn-in, progressive throttle. "
        "Smooth is fast; jerky inputs cost grip."
    ),
}

_FOLLOWUP_SYSTEM = (
    COACHING_SYSTEM_PROMPT
    + "\nThe driver is asking follow-up questions about their telemetry data and your "
    "coaching report. Be specific, practical, and encouraging. "
    "Reference corner numbers. For speeds, use {{speed:N}} markers where N is mph."
    + TOPIC_RESTRICTION_PROMPT
)


@dataclass
class CornerGrade:
    """Per-corner technique grades."""

    corner: int
    braking: str
    trail_braking: str
    min_speed: str
    throttle: str
    notes: str


@dataclass
class CoachingReport:
    """Structured coaching report from the AI."""

    summary: str
    priority_corners: list[dict[str, object]]
    corner_grades: list[CornerGrade]
    patterns: list[str]
    primary_focus: str = ""
    drills: list[str] = field(default_factory=list)
    raw_response: str = ""
    validation_failed: bool = False
    validation_violations: list[str] = field(default_factory=list)


@dataclass
class CoachingContext:
    """Maintains conversation context for follow-up questions."""

    messages: list[dict[str, str]] = field(default_factory=list)


def _format_lap_summaries(summaries: list[LapSummary]) -> str:
    """Format lap summaries into text for the prompt."""
    lines = ["Lap | Time | Max Speed (mph)"]
    lines.append("--- | --- | ---")
    for s in summaries:
        mph = s.max_speed_mps * MPS_TO_MPH
        minutes = int(s.lap_time_s // 60)
        seconds = s.lap_time_s % 60
        lines.append(f"L{s.lap_number} | {minutes}:{seconds:05.2f} | {mph:.1f}")
    return "\n".join(lines)


def _resolve_brake_ref(
    distance_m: float | None,
    landmarks: list[Landmark] | None,
) -> str:
    """Resolve a brake point distance to a landmark reference string."""
    if distance_m is None:
        return "—"
    if landmarks:
        ref = find_nearest_landmark(distance_m, landmarks, preferred_types=_BRAKE_PREFERRED_TYPES)
        if ref is not None:
            return ref.format_reference()
    return f"{distance_m:.0f}m"


def _resolve_throttle_ref(
    distance_m: float | None,
    landmarks: list[Landmark] | None,
) -> str:
    """Resolve a throttle commit distance to a landmark reference string."""
    if distance_m is None:
        return "—"
    if landmarks:
        ref = find_nearest_landmark(distance_m, landmarks)
        if ref is not None:
            return ref.format_reference()
    return f"{distance_m:.0f}m"


def _format_all_laps_corners(
    all_lap_corners: dict[int, list[Corner]],
    best_lap: int,
    *,
    landmarks: list[Landmark] | None = None,
) -> str:
    """Format corner KPIs for every lap in the session."""
    if landmarks:
        brake_col = "Brake Ref"
        throttle_col = "Throttle Ref"
    else:
        brake_col = "Brake Pt (m)"
        throttle_col = "Throttle (m)"

    lines = [
        f"Lap | Corner | Min Speed (mph) | {brake_col} | Peak Brake (G) | {throttle_col} | Apex"
    ]
    lines.append("--- | --- | --- | --- | --- | --- | ---")

    for lap_num in sorted(all_lap_corners):
        tag = " *" if lap_num == best_lap else ""
        for c in all_lap_corners[lap_num]:
            speed = f"{c.min_speed_mps * MPS_TO_MPH:.1f}"
            brake = _resolve_brake_ref(c.brake_point_m, landmarks)
            peak_g = f"{c.peak_brake_g:.2f}" if c.peak_brake_g is not None else "—"
            throttle = _resolve_throttle_ref(c.throttle_commit_m, landmarks)
            lines.append(
                f"L{lap_num}{tag} | T{c.number} | {speed} | {brake} "
                f"| {peak_g} | {throttle} | {c.apex_type}"
            )

    return "\n".join(lines)


def _format_gains_for_prompt(gains: GainEstimate) -> str:
    """Format gains data into text for the coaching prompt."""
    lines = [
        "## Gain Estimation",
        "",
        "These metrics quantify how much lap time the driver can recover by "
        "improving consistency and combining their best sector performances.",
        "",
        f"- **Consistency gain: {gains.consistency.total_gain_s:.2f}s** "
        "(difference between average lap and best lap, broken down by corner. "
        "Shows where the driver loses time vs their own best execution.)",
        f"- **Composite gain: {gains.composite.gain_s:.2f}s** "
        "(difference between best lap and a composite of best-ever sectors. "
        "Shows additional time available if the driver combines all personal-best corners.)",
        f"- **Theoretical best gain: {gains.theoretical.gain_s:.2f}s** "
        "(fine-grained micro-sector analysis limit.)",
        "",
        "### Per-Corner Consistency Gains (avg -> best, sorted by opportunity)",
    ]

    corner_gains = [
        sg for sg in gains.consistency.segment_gains if sg.segment.is_corner and sg.gain_s >= 0.01
    ]
    corner_gains.sort(key=lambda sg: sg.gain_s, reverse=True)

    for sg in corner_gains:
        lines.append(f"- {sg.segment.name}: {sg.gain_s:.2f}s")

    if not corner_gains:
        lines.append("- (all corners below 0.01s threshold)")

    return "\n".join(lines)


def _format_optimal_comparison(result: OptimalComparisonResult) -> str:
    """Format optimal comparison data for the coaching prompt."""
    lines = [
        "## Physics-Optimal Analysis",
        "",
        f"- **Theoretical optimal lap time: {result.optimal_lap_time_s:.2f}s**",
        f"- **Driver's actual lap time: {result.actual_lap_time_s:.2f}s**",
        f"- **Total gap: {result.total_gap_s:.2f}s**",
        "",
        "### Per-Corner Speed Gaps (sorted by time cost)",
    ]

    for opp in result.corner_opportunities[:10]:  # top 10
        brake_info = ""
        if opp.brake_gap_m is not None:
            brake_info = f", brakes {opp.brake_gap_m:.0f}m early"
        lines.append(
            f"- T{opp.corner_number}: {opp.speed_gap_mph:+.1f} mph gap"
            f" ({opp.time_cost_s:.3f}s cost{brake_info})"
        )

    if not result.corner_opportunities:
        lines.append("- (no corner data available)")

    return "\n".join(lines)


def _format_landmark_context(
    all_lap_corners: dict[int, list[Corner]],
    landmarks: list[Landmark],
) -> str:
    """Build a visual landmarks section for the coaching prompt.

    Uses the best lap's corner data (first lap in the dict) to resolve
    landmark references for brake, apex, and throttle points.
    """
    if not landmarks:
        return ""

    # Use corners from any lap (they share the same positions)
    corners = next(iter(all_lap_corners.values()), [])
    if not corners:
        return ""

    lines = [
        "\n## Visual Landmarks",
        "Use these cockpit-visible references instead of raw meter distances.",
        "Drivers cannot see meter distances on track.\n",
    ]

    for corner in corners:
        refs = format_corner_landmarks(corner, landmarks)
        if refs:
            lines.append(f"T{corner.number}:")
            lines.append(refs)

    return "\n".join(lines)


def _format_corner_analysis(
    analysis: SessionCornerAnalysis,
    *,
    landmarks: list[Landmark] | None = None,
) -> str:
    """Format pre-computed corner analysis into prompt text."""
    lines = [
        "## Pre-Computed Corner Analysis (sorted by time opportunity)",
        f"Best lap: L{analysis.best_lap} | "
        f"Total consistency gain: {analysis.total_consistency_gain_s:.2f}s | "
        f"Laps analyzed: {analysis.n_laps_analyzed}",
        "",
    ]

    for ca in analysis.corners:
        header = f"### T{ca.corner_number} ({ca.recommendation.corner_type}"
        header += f", gain: {ca.recommendation.gain_s:.2f}s"
        header += f", {ca.n_laps} laps)"
        lines.append(header)

        # Corner character hint for the LLM
        if ca.recommendation.character == "flat":
            lines.append(
                "  Character: FLAT (typically taken without braking — focus on line/speed carry)"
            )
        elif ca.recommendation.character == "lift":
            lines.append(
                "  Character: LIFT (typically taken with a lift, not heavy braking "
                "— focus on smooth carry)"
            )

        # Enriched coaching context
        rec = ca.recommendation
        if rec.elevation_trend and rec.elevation_trend != "flat":
            grad = f" ({rec.gradient_pct:.1f}%)" if rec.gradient_pct else ""
            lines.append(f"  Elevation: {rec.elevation_trend.upper()}{grad}")
        if rec.corner_type_hint:
            lines.append(f"  Type: {rec.corner_type_hint}")
        if rec.blind:
            lines.append("  Visibility: BLIND — trust reference points, not visual apex")
        if rec.camber and rec.camber not in ("positive", None):
            lines.append(f"  Camber: {rec.camber}")
        if rec.coaching_notes:
            lines.append(f"  Coach tip: {rec.coaching_notes}")

        # Min speed
        ms = ca.stats_min_speed
        lines.append(f"  Min speed: best={ms.best:.1f} mean={ms.mean:.1f} std={ms.std:.1f} mph")

        # Brake point
        if ca.stats_brake_point is not None:
            bp = ca.stats_brake_point
            brake_ref = _resolve_brake_ref(bp.best, landmarks)
            lines.append(f"  Brake pt: {brake_ref} (best), spread \u00b1{bp.std:.1f}m")

        # Peak brake g
        if ca.stats_peak_brake_g is not None:
            pg = ca.stats_peak_brake_g
            lines.append(f"  Peak brake: best={pg.best:.2f} mean={pg.mean:.2f}G")

        # Throttle commit
        if ca.stats_throttle_commit is not None:
            tc = ca.stats_throttle_commit
            throttle_ref = _resolve_throttle_ref(tc.best, landmarks)
            lines.append(f"  Throttle: {throttle_ref} (best), spread \u00b1{tc.std:.1f}m")

        # Apex distribution
        apex_parts = [
            f"{count}/{ca.n_laps} {atype}" for atype, count in sorted(ca.apex_distribution.items())
        ]
        if apex_parts:
            lines.append(f"  Apex: {', '.join(apex_parts)}")

        # Target brake landmark
        if ca.recommendation.target_brake_landmark is not None:
            ref = ca.recommendation.target_brake_landmark.format_reference()
            lines.append(f"  Target brake: {ref}")
        elif ca.recommendation.target_brake_m is not None:
            lines.append(f"  Target brake: {ca.recommendation.target_brake_m:.0f}m")

        # Target min speed
        lines.append(f"  Target min speed: {ca.recommendation.target_min_speed_mph:.1f} mph")

        # Time value
        if ca.time_value is not None:
            tv = ca.time_value
            lines.append(
                f"  Approach speed: {tv.approach_speed_mph:.0f} mph, "
                f"time/m: {tv.time_per_meter_ms:.1f}ms"
            )
            lines.append(f"  Brake variance time cost: ~{tv.brake_variance_time_cost_s:.3f}s")

        # Correlations
        for corr in ca.correlations:
            lines.append(
                f"  Corr {corr.kpi_x} vs {corr.kpi_y}: "
                f"r={corr.r:.2f} ({corr.strength}, n={corr.n_points})"
            )

        lines.append("")

    return "\n".join(lines)


def _format_equipment_context(
    profile: EquipmentProfile | None,
    conditions: SessionConditions | None,
) -> str:
    """Format equipment and conditions as context for the coaching prompt."""
    if profile is None and conditions is None:
        return ""

    lines = ["\n## Vehicle Equipment & Conditions"]
    if profile is not None:
        lines.append(f"**Tires:** {profile.tires.model} ({profile.tires.compound_category.value})")
        lines.append(
            f"  - Grip coefficient (mu): {profile.tires.estimated_mu:.2f}"
            f" [{profile.tires.mu_source.value}]"
        )
        if profile.tires.pressure_psi is not None:
            lines.append(f"  - Pressure: {profile.tires.pressure_psi} psi")
        if profile.brakes is not None and profile.brakes.compound:
            lines.append(f"**Brakes:** {profile.brakes.compound}")
    if conditions is not None:
        lines.append(f"**Track condition:** {conditions.track_condition.value}")
        if conditions.ambient_temp_c is not None:
            lines.append(f"**Ambient temp:** {conditions.ambient_temp_c:.0f}\u00b0C")
        if conditions.humidity_pct is not None:
            lines.append(f"**Humidity:** {conditions.humidity_pct:.0f}%")

    return "\n".join(lines)


def _format_weather_context(
    weather: SessionConditions | None,
) -> str:
    """Format weather conditions as context for the coaching prompt."""
    if weather is None:
        return ""

    lines = ["\n## Weather Conditions"]
    lines.append(f"**Track condition:** {weather.track_condition.value}")
    if weather.ambient_temp_c is not None:
        lines.append(f"**Ambient temp:** {weather.ambient_temp_c:.0f}\u00b0C")
    if weather.humidity_pct is not None:
        lines.append(f"**Humidity:** {weather.humidity_pct:.0f}%")
    if weather.wind_speed_kmh is not None:
        lines.append(f"**Wind:** {weather.wind_speed_kmh:.0f} km/h")
    if weather.precipitation_mm is not None and weather.precipitation_mm > 0:
        lines.append(f"**Precipitation:** {weather.precipitation_mm:.1f}mm")
    return "\n".join(lines)


def _format_cross_condition_context(
    weather_a: SessionConditions | None,
    weather_b: SessionConditions | None,
) -> str:
    """Format cross-condition context when comparing sessions in different weather."""
    if weather_a is None or weather_b is None:
        return ""

    condition_differs = weather_a.track_condition != weather_b.track_condition
    temp_a = weather_a.ambient_temp_c
    temp_b = weather_b.ambient_temp_c
    temp_differs = temp_a is not None and temp_b is not None and abs(temp_a - temp_b) >= 5.0

    if not condition_differs and not temp_differs:
        return ""

    lines = [
        "\n## Cross-Condition Warning",
        "These sessions were driven in DIFFERENT conditions:",
        f"- Session A: {weather_a.track_condition.value}"
        + (f", {temp_a:.0f}\u00b0C" if temp_a is not None else ""),
        f"- Session B: {weather_b.track_condition.value}"
        + (f", {temp_b:.0f}\u00b0C" if temp_b is not None else ""),
        "",
        "IMPORTANT coaching adjustments:",
        "- Factor weather differences into your analysis",
        "- Do NOT attribute condition-related time loss to driver technique",
        "- Explicitly note which time differences are likely weather-related vs technique-related",
    ]

    if condition_differs:
        lines.append(
            "- Wet/damp conditions reduce grip significantly — slower corner speeds are expected"
        )
    if temp_differs:
        lines.append("- Temperature differences affect tire grip — colder temps mean less grip")

    return "\n".join(lines)


def _format_flow_laps_for_prompt(result: FlowLapResult | None) -> str:
    """Format flow lap detection results for injection into the coaching prompt."""
    if result is None or not result.flow_laps:
        return ""
    lines = ["\n## Flow Laps (Peak Performance)"]
    lines.append(
        f"Flow laps identified: {', '.join(f'L{lap}' for lap in result.flow_laps[:5])} "
        f"(threshold: {result.threshold:.0%})"
    )
    if result.best_flow_lap is not None:
        score = result.scores.get(result.best_flow_lap, 0.0)
        lines.append(f"Best flow lap: L{result.best_flow_lap} (score: {score:.0%})")
    lines.append(
        "Flow laps show when the driver was 'in the zone' — balanced technique, "
        "near-PB pace, and smooth execution. Reference these laps as positive examples "
        "and study what the driver did differently on non-flow laps."
    )
    return "\n".join(lines)


def _format_corner_priorities(profiles: list[CornerLineProfile]) -> str:
    """Format corner priority rankings as XML for the coaching prompt.

    Returns "" for empty list.  Sorts by priority_rank ascending
    so the most important corners appear first.
    """
    if not profiles:
        return ""

    sorted_profiles = sorted(profiles, key=lambda p: p.priority_rank)
    lines = ["<corner_priorities>"]
    for p in sorted_profiles:
        if p.allen_berg_type == "A":
            priority_label = "Highest priority" if p.priority_rank == 1 else "High priority"
            desc = f"Exit speed carries for {p.straight_after_m:.0f}m. {priority_label}."
        elif p.allen_berg_type == "B":
            desc = "Entry speed corner — maximize speed at end of preceding straight."
        else:
            desc = "Linking corner — balance line to serve adjacent corners."

        lines.append(
            f'  <corner number="{p.corner_number}" type="{p.allen_berg_type}" '
            f'rank="{p.priority_rank}" straight_after="{p.straight_after_m:.0f}m">'
            f"{desc}</corner>"
        )
    lines.append("</corner_priorities>")
    return "\n".join(lines)


def build_track_introduction(layout: TrackLayout | None) -> str:
    """Build a track introduction XML block for novice drivers.

    Returns "" for None layout or empty corners list.
    Includes overview, corner guide, key corners (Type A by gap analysis),
    peculiarities (blind, off-camber, crests, compressions), and landmarks.
    """
    if layout is None or not layout.corners:
        return ""

    length_str = f"{layout.length_m:.0f}m" if layout.length_m else "unknown length"
    elev_str = f"{layout.elevation_range_m:.0f}m" if layout.elevation_range_m else "unknown"

    lines = [
        "<track_introduction>",
        "<overview>",
        f"  {layout.name} | {length_str} | elevation range: {elev_str}",
        "</overview>",
        "<corner_guide>",
    ]

    for c in layout.corners:
        attrs: list[str] = [f'number="{c.number}"', f'name="{c.name}"']
        if c.direction:
            attrs.append(f'direction="{c.direction}"')
        if c.corner_type:
            attrs.append(f'type="{c.corner_type}"')
        if c.elevation_trend:
            attrs.append(f'elevation="{c.elevation_trend}"')
        if c.blind:
            attrs.append('blind="true"')
        lines.append(f"  <corner {' '.join(attrs)}>")
        if c.character:
            lines.append(f"    <character>{c.character}</character>")
        if c.coaching_notes:
            lines.append(f"    <coaching_notes>{c.coaching_notes}</coaching_notes>")
        lines.append("  </corner>")

    lines.append("</corner_guide>")

    # Key corners: Type A corners where exit speed is critical (long straight after)
    key_corners = get_key_corners(layout)
    if key_corners:
        lines.append("<key_corners>")
        for c, gap_m in key_corners:
            lines.append(
                f'  <corner number="{c.number}" name="{c.name}" '
                f'straight_after="{gap_m:.0f}m">Type A — exit speed critical</corner>'
            )
        lines.append("</key_corners>")

    # Peculiarities: blind corners, off-camber, crests, compressions
    peculiarities = get_peculiarities(layout)
    if peculiarities:
        lines.append("<peculiarities>")
        for c, desc in peculiarities:
            lines.append(f"  T{c.number} ({c.name}): {desc}")
        lines.append("</peculiarities>")

    # Landmarks
    if layout.landmarks:
        lines.append("<landmark_guide>")
        for lm in layout.landmarks:
            desc_part = f" — {lm.description}" if lm.description else ""
            lines.append(
                f'  <landmark name="{lm.name}" type="{lm.landmark_type.value}" '
                f'distance="{lm.distance_m:.0f}m">{lm.name}{desc_part}</landmark>'
            )
        lines.append("</landmark_guide>")

    lines.append("</track_introduction>")
    return "\n".join(lines)


def _build_coaching_prompt(
    summaries: list[LapSummary],
    all_lap_corners: dict[int, list[Corner]],
    track_name: str,
    *,
    gains: GainEstimate | None = None,
    skill_level: SkillLevel = "intermediate",
    landmarks: list[Landmark] | None = None,
    optimal_comparison: OptimalComparisonResult | None = None,
    corner_analysis: SessionCornerAnalysis | None = None,
    causal_analysis: SessionCausalAnalysis | None = None,
    archetype: ArchetypeResult | None = None,
    skill_assessment: SkillAssessment | None = None,
    equipment_profile: EquipmentProfile | None = None,
    conditions: SessionConditions | None = None,
    weather: SessionConditions | None = None,
    corners_gained: CornersGainedResult | None = None,
    flow_laps: FlowLapResult | None = None,
    line_profiles: list[CornerLineProfile] | None = None,
    track_layout: TrackLayout | None = None,
) -> str:
    """Build the full coaching prompt for Claude."""
    lap_text = _format_lap_summaries(summaries)
    best = min(summaries, key=lambda s: s.lap_time_s)
    best_min = int(best.lap_time_s // 60)
    best_sec = best.lap_time_s % 60
    corner_text = _format_all_laps_corners(all_lap_corners, best.lap_number, landmarks=landmarks)

    gains_section = ""
    gains_instruction = ""
    if gains is not None:
        gains_section = f"\n{_format_gains_for_prompt(gains)}\n"
        gains_instruction = (
            "\nReference these computed gains when discussing priority corners. "
            "The consistency gain shows where the driver loses time vs their own best.\n"
        )

    # Use auto-detected final_level when available, falling back to user-declared.
    effective_skill = (
        skill_assessment.final_level
        if skill_assessment is not None and skill_assessment.final_level is not None
        else skill_level
    )
    skill_section = _SKILL_PROMPTS.get(effective_skill, _SKILL_PROMPTS["intermediate"])

    track_intro_section = ""
    track_intro_instruction = ""
    if effective_skill == "novice" and track_layout is not None:
        track_intro_section = build_track_introduction(track_layout)
        track_intro_instruction = (
            "\nA TRACK INTRODUCTION is provided. In your summary, help the driver "
            "understand the track layout and which corners to prioritize. Frame this as "
            "'here\\'s what matters most at this track' rather than an exhaustive tour "
            "of every corner. Reference key corners by name.\n"
        )

    landmark_section = ""
    landmark_instruction = ""
    if landmarks:
        landmark_section = _format_landmark_context(all_lap_corners, landmarks)
        landmark_instruction = (
            "\nIMPORTANT: Use visual landmarks instead of raw meter distances in your tips. "
            "Drivers cannot see meter distances on track — reference brake boards, structures, "
            "and curbing that they can actually see from the cockpit.\n"
        )

    optimal_section = ""
    optimal_instruction = ""
    if optimal_comparison is not None:
        optimal_section = f"\n{_format_optimal_comparison(optimal_comparison)}\n"
        optimal_instruction = (
            "\nThe physics-optimal analysis shows the theoretical fastest "
            "lap based on the car's grip limits. Reference specific corner "
            "speed gaps when coaching. Larger gaps indicate the driver is "
            "leaving more time on the table.\n"
        )

    equipment_section = _format_equipment_context(equipment_profile, conditions)
    weather_section = _format_weather_context(weather)
    causal_section = (
        format_causal_context_for_prompt(causal_analysis) if causal_analysis is not None else ""
    )
    archetype_section = format_archetype_for_prompt(archetype)
    skill_section_auto = format_skill_for_prompt(skill_assessment)
    corners_gained_section = format_corners_gained_for_prompt(corners_gained)
    flow_laps_section = _format_flow_laps_for_prompt(flow_laps)
    line_analysis_section = format_line_analysis_for_prompt(line_profiles or [])
    session_line_summary = format_session_line_summary_for_prompt(
        summarize_session_lines(line_profiles or [])
    )
    corner_priorities_section = _format_corner_priorities(line_profiles or [])

    line_instruction = ""
    if line_analysis_section:
        line_instruction = (
            "\nWhen LINE ANALYSIS data is present, integrate it with speed/brake analysis. "
            "A corner with good brake data but an early apex error costs time on the exit — "
            "report these together as one issue, not two separate observations.\n"
        )
    if corner_priorities_section:
        line_instruction += (
            "\nWeight coaching emphasis proportionally to corner priority rank. "
            "Type A corners (before long straights) should receive the most detailed advice. "
            "When a driver's line is inconsistent at a Type A corner, flag this as high-impact "
            "because exit speed compounds across the following straight.\n"
        )

    corner_analysis_section = ""
    corner_analysis_instruction = ""
    if corner_analysis is not None and corner_analysis.corners:
        corner_analysis_section = (
            f"\n{_format_corner_analysis(corner_analysis, landmarks=landmarks)}\n"
        )
        corner_analysis_instruction = (
            "\nIMPORTANT: Use the pre-computed corner analysis above as your primary data source. "
            "The statistics, correlations, and recommendations are already computed — "
            "DO NOT re-derive them. Your job is to:\n"
            "1. Write narrative coaching advice explaining WHY these patterns matter\n"
            "2. Prioritize corners by the pre-computed gain values\n"
            "3. Reference the target brake/speed values in your tips\n"
            "4. Use correlation insights to explain cause-effect relationships\n"
            "5. Use data insights to inform your coaching — but translate numbers into "
            "driver-friendly language (never raw stats like std, r-values, or ±)\n"
            "The raw KPI table below is for lap-specific citations only.\n"
        )

    # Determine the number of corners from the data to constrain the AI output.
    num_corners = len(next(iter(all_lap_corners.values()), []))

    # Determine priority corner count by skill level
    _max_priority_map = {"novice": 2, "intermediate": 3, "advanced": 4}
    max_priorities = _max_priority_map.get(effective_skill, 3)

    return f"""<session_data>
<session_info>
Track: {track_name}
Best Lap: L{best.lap_number} ({best_min}:{best_sec:05.2f})
Total laps: {len(summaries)}
Number of corners: {num_corners} (T1 through T{num_corners})
</session_info>

<corner_analysis note="pre-computed statistics, sorted by time opportunity">
{corner_analysis_section}
</corner_analysis>

<lap_times>
{lap_text}
</lap_times>

<corner_kpis note="all laps, best lap marked with *">
{corner_text}
</corner_kpis>
{gains_section}{optimal_section}{landmark_section}{skill_section}\
{equipment_section}{weather_section}{causal_section}{archetype_section}{skill_section_auto}\
{corners_gained_section}{flow_laps_section}
{line_analysis_section}
{session_line_summary}
{corner_priorities_section}
{track_intro_section}
</session_data>

<instructions>
{corner_analysis_instruction}\
{landmark_instruction}\
{line_instruction}\
{track_intro_instruction}\
Analyze the FULL session. Look at every lap's data for each corner to identify:
- Consistency: which corners are repeatable vs high-variance across laps
- Trends: whether the driver improved or degraded through the session AND WHY \
(diagnose the cause: technique ceiling, fatigue, tire degradation, confidence plateau, etc.)
- Best-vs-rest gaps: where the best lap gained time vs the driver's typical performance
- Technique patterns: brake point consistency, apex type shifts, min-speed spread
{gains_instruction}{optimal_instruction}

Respond in JSON with this exact structure:
{{
  "primary_focus": "The ONE most impactful change for the driver's next session. \
This is the single highest-leverage action — not a list, not vague, but one specific \
experiment the driver can practice next time out. Frame it as what the CAR should do, \
not what the body should do. Include a 'because' clause with data.",
  "summary": "2-3 sentence overview — START with 2-3 data-backed strengths, \
then transition to the biggest opportunity. End with one reflective question \
referencing specific telemetry patterns.",
  "priority_corners": [
    {{
      "corner": <number>,
      "time_cost_s": <estimated avg time lost vs best lap at this corner>,
      "issue": "<what the data shows across all laps — include root cause chain>",
      "tip": "<actionable advice with 'because' clause and what the driver will FEEL>"
    }}
  ],
  "corner_grades": [
    {{
      "corner": <number>,
      "braking": "<A-F>",
      "trail_braking": "<A-F>",
      "min_speed": "<A-F>",
      "throttle": "<A-F>",
      "notes": "<ONE sentence a trackside coach would say. Embed key data naturally — \
e.g. 'Your best lap carried {{{{speed:3}}}} more and gained 0.3s on the straight' — \
but NEVER dump raw stats (std=, r=, ±), restate grades, or echo thresholds. \
Focus on what to DO or what's working, with one concrete data point as evidence.>"
    }}
  ],
  "patterns": [
    "<session-wide pattern with root cause chain>",
    "<pattern 2 with why>",
    "<pattern 3>"
  ],
  "drills": [
    "<specific practice drill for weakness 1>",
    "<specific practice drill for weakness 2>"
  ]
}}

Include exactly {num_corners} entries in corner_grades \
(one per corner, T1 through T{num_corners}). \
Do NOT include corners beyond T{num_corners}.

Include 1-2 specific practice drills tailored to the driver's weakest areas. \
Each drill should reference a specific corner number and give the driver \
something concrete to practice on their next session. \
Structure each drill with markdown: use a bold title, then separate paragraphs \
(use \\n\\n within the JSON string) for focus areas and measurable targets. \
Keep each paragraph to 1-2 sentences. Never write a wall of text.

Sort priority_corners by time_cost_s descending (biggest avg time loss first).
Identify the {max_priorities} corners with the largest improvement opportunity. \
For each, provide ONE specific actionable change with a "because" clause explaining why. \
Do NOT include more than {max_priorities} priorities in priority_corners. \
If fewer corners have meaningful improvement potential, include only those.

Grading criteria (evidence-anchored):
  BRAKING: A = std < 3m + peak G within 0.05G of best |
    B = std < 6m | C = std < 10m | D = std < 15m | F = std > 15m
  TRAIL BRAKING: A = present 90%+ laps | B = 70-89% |
    C = 50-69% | D = < 50% | N/A = kinks/lifts
  MIN SPEED: A = std < 1.0 mph + within 1 mph of target |
    B = std < 2.0 | C = std < 3.0 | D = std < 5.0 | F = > 5.0
  THROTTLE: A = commit std < 5m + progressive |
    B = std < 8m | C = std < 12m | D = std > 12m or abrupt
Grade distribution should approximate a bell curve around B/C for a typical driver. \
All-A or all-B reports are almost certainly grade-inflated. \
First cite the evidence (numbers), THEN assign the grade — not the reverse.

CORNER NOTES RULES — write like a trackside coach, not a data analyst:
- NEVER use raw statistics: "std=1.1 mph", "±6.8m", "r=-0.63", "commit std=0.3m"
- NEVER restate what the grade fields already show (e.g. "Braking N/A because it's a kink")
- NEVER echo grading thresholds (e.g. "A-grade, within 1 mph of target")
- DO embed one concrete data point naturally: lap numbers, speed values, distances
- DO focus on the single most coaching-relevant insight for this corner
- DO frame as what to DO or what's WORKING
GOOD: "Your best lap carried {{{{speed:3}}}} more through the apex — trust the grip"
GOOD: "Same throttle spot every lap (L7 nailed it) — this corner is dialed in"
GOOD: "Getting on power early here costs you into T4 — hold an extra beat"
BAD: "Min speed std=1.1 mph. Throttle scatter ±6.8m. Correlation r=-0.63"
BAD: "Braking N/A (kink, no braking). Min speed B because std=1.9 mph"

For each pattern, trace the root cause chain: don't just describe WHAT happened — \
diagnose WHY by tracing entry cause -> mid-corner effect -> exit consequence. \
If lap times plateaued, explain whether it's a technique ceiling, \
fatigue, tire degradation, or confidence limit based on the data.

Motivational framing — use the driver's OWN best laps as the reference:
- Instead of "You need to brake later" → "You already braked at the 2-board on L7 — \
let's make that your target"
- Instead of "Your T5 is weak" → "T5 has the most time to gain — it's your biggest \
opportunity"
- Instead of "You're inconsistent" → "Your best laps show what you're capable of — \
let's close the gap to those"
- Frame improvement areas as OPPORTUNITIES, not deficiencies

SPEED FORMATTING: In ALL text fields \
(primary_focus, summary, issue, tip, notes, patterns, drills), \
wrap every speed value with the marker {{{{speed:N}}}} where N is the numeric value in mph. \
Example: "Carry {{{{speed:3}}}} more through the apex" or "Min speed was {{{{speed:42.5}}}}". \
Never write bare "mph" or "km/h" in text fields — always use {{{{speed:N}}}}.
</instructions>"""


def _parse_coaching_response(text: str) -> CoachingReport:
    """Parse Claude's JSON response into a CoachingReport."""
    # Extract JSON from response (may be wrapped in markdown code blocks)
    json_text = text.strip()
    if "```json" in json_text:
        json_text = json_text.split("```json", 1)[1]
        json_text = json_text.split("```", 1)[0]
    elif "```" in json_text:
        json_text = json_text.split("```", 1)[1]
        json_text = json_text.split("```", 1)[0]

    # Fallback: find outermost { ... } if code-block extraction didn't work
    data = None
    try:
        data = json.loads(json_text.strip())
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            with contextlib.suppress(json.JSONDecodeError):
                data = json.loads(text[start : end + 1])

    if data is None:
        return CoachingReport(
            summary="Could not parse AI coaching response.",
            priority_corners=[],
            corner_grades=[],
            patterns=[],
            raw_response=text,
        )

    grades = []
    for g in data.get("corner_grades", []):
        grades.append(
            CornerGrade(
                corner=g.get("corner", 0),
                braking=g.get("braking", "?"),
                trail_braking=g.get("trail_braking", "?"),
                min_speed=g.get("min_speed", "?"),
                throttle=g.get("throttle", "?"),
                notes=g.get("notes", ""),
            )
        )

    drills = data.get("drills", [])

    return CoachingReport(
        summary=data.get("summary", ""),
        priority_corners=data.get("priority_corners", []),
        corner_grades=grades,
        patterns=data.get("patterns", []),
        primary_focus=data.get("primary_focus", ""),
        drills=drills,
        raw_response=text,
    )


def _create_client() -> Any:
    """Create an Anthropic client with resilient retry settings.

    Returns the client or None if the API key is not set.
    The SDK automatically retries on 429, 500, and 529 errors with
    exponential backoff + jitter.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    return anthropic.Anthropic(
        api_key=api_key,
        max_retries=_API_MAX_RETRIES,
        timeout=_API_TIMEOUT_S,
    )


def generate_coaching_report(
    summaries: list[LapSummary],
    all_lap_corners: dict[int, list[Corner]],
    track_name: str,
    *,
    gains: GainEstimate | None = None,
    skill_level: SkillLevel = "intermediate",
    landmarks: list[Landmark] | None = None,
    optimal_comparison: OptimalComparisonResult | None = None,
    corner_analysis: SessionCornerAnalysis | None = None,
    causal_analysis: SessionCausalAnalysis | None = None,
    archetype: ArchetypeResult | None = None,
    skill_assessment: SkillAssessment | None = None,
    equipment_profile: EquipmentProfile | None = None,
    conditions: SessionConditions | None = None,
    weather: SessionConditions | None = None,
    corners_gained: CornersGainedResult | None = None,
    flow_laps: FlowLapResult | None = None,
    line_profiles: list[CornerLineProfile] | None = None,
    track_layout: TrackLayout | None = None,
) -> CoachingReport:
    """Generate an AI coaching report using the Claude API.

    Analyzes corner KPIs across ALL laps in the session.

    Requires ANTHROPIC_API_KEY environment variable.
    Returns a CoachingReport. If the API key is not set, returns a report
    with a message explaining how to enable coaching.
    """
    client = _create_client()
    if client is None:
        return CoachingReport(
            summary="Set ANTHROPIC_API_KEY environment variable to enable AI coaching.",
            priority_corners=[],
            corner_grades=[],
            patterns=[],
        )

    prompt = _build_coaching_prompt(
        summaries,
        all_lap_corners,
        track_name,
        gains=gains,
        skill_level=skill_level,
        landmarks=landmarks,
        optimal_comparison=optimal_comparison,
        corner_analysis=corner_analysis,
        causal_analysis=causal_analysis,
        archetype=archetype,
        skill_assessment=skill_assessment,
        equipment_profile=equipment_profile,
        conditions=conditions,
        weather=weather,
        corners_gained=corners_gained,
        flow_laps=flow_laps,
        line_profiles=line_profiles,
        track_layout=track_layout,
    )

    system = COACHING_SYSTEM_PROMPT
    kb_context = select_kb_snippets(all_lap_corners, skill_level, gains=gains)
    if kb_context:
        system += "\n\n" + kb_context

    def _call_coaching_api() -> tuple[str, CoachingReport]:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=16384,
            temperature=0.3,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        blk = msg.content[0]
        text = blk.text if hasattr(blk, "text") else str(blk)
        return text, _parse_coaching_response(text)

    response_text, report = _call_coaching_api()

    # Adaptive sampling validation — checks every Nth output.
    # On failure: retry once (regenerate), then flag if still bad.
    validator = _get_validator()
    validation = validator.record_and_maybe_validate(response_text)
    if validation and not validation.passed:
        logger.warning(
            "Coaching guardrail violation detected, retrying: %s",
            validation.violations,
        )
        response_text, report = _call_coaching_api()
        retry_validation = validator.force_validate(response_text)
        if not retry_validation.passed:
            logger.warning(
                "Coaching guardrail violation persists after retry: %s",
                retry_validation.violations,
            )
            report.validation_failed = True
            report.validation_violations = retry_validation.violations

    # Filter out hallucinated corners beyond the actual corner count.
    num_corners = len(next(iter(all_lap_corners.values()), []))
    if num_corners > 0:
        valid = set(range(1, num_corners + 1))
        before_grades = len(report.corner_grades)
        report.corner_grades = [g for g in report.corner_grades if g.corner in valid]
        report.priority_corners = [
            pc
            for pc in report.priority_corners
            if isinstance(pc.get("corner"), int) and pc["corner"] in valid
        ]
        dropped = before_grades - len(report.corner_grades)
        if dropped:
            logger.warning(
                "Filtered %d hallucinated corner grade(s) (track has %d corners)",
                dropped,
                num_corners,
            )

    return report


def ask_followup(
    context: CoachingContext,
    question: str,
    coaching_report: CoachingReport,
    *,
    all_lap_corners: dict[int, list[Corner]] | None = None,
    skill_level: str = "intermediate",
    gains: GainEstimate | None = None,
    weather: SessionConditions | None = None,
) -> str:
    """Ask a follow-up question to the AI coach.

    Maintains conversation context for multi-turn chat.
    """
    client = _create_client()
    if client is None:
        return "Set ANTHROPIC_API_KEY to enable AI coaching chat."

    if not context.messages:
        # First follow-up: include the coaching report as context
        context.messages.append(
            {
                "role": "assistant",
                "content": f"Here is my coaching report:\n\n{coaching_report.raw_response}",
            }
        )

    context.messages.append({"role": "user", "content": question})

    system = _FOLLOWUP_SYSTEM
    weather_ctx = _format_weather_context(weather)
    if weather_ctx:
        system += f"\n\n{weather_ctx}"
    if all_lap_corners is not None:
        kb_context = select_kb_snippets(all_lap_corners, skill_level, gains=gains)
        if kb_context:
            system += "\n\n" + kb_context

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            messages=context.messages,  # type: ignore[arg-type]
        )
    except Exception as e:
        logger.warning("Follow-up chat API call failed after retries: %s", e)
        return (
            "AI coaching is temporarily unavailable (the service is overloaded). "
            "Please try again in a moment."
        )

    followup_block = message.content[0]
    response_text = followup_block.text if hasattr(followup_block, "text") else str(followup_block)
    context.messages.append({"role": "assistant", "content": response_text})
    return response_text
