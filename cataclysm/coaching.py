"""Claude API integration for AI-powered driving coaching."""

from __future__ import annotations

import contextlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from cataclysm.coaching_validator import CoachingValidator
from cataclysm.corner_analysis import SessionCornerAnalysis
from cataclysm.corners import Corner
from cataclysm.driving_physics import COACHING_SYSTEM_PROMPT
from cataclysm.engine import LapSummary
from cataclysm.gains import GainEstimate
from cataclysm.kb_selector import select_kb_snippets
from cataclysm.landmarks import Landmark, format_corner_landmarks
from cataclysm.optimal_comparison import OptimalComparisonResult

logger = logging.getLogger(__name__)

MPS_TO_MPH = 2.23694

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
        "This driver is relatively new to track driving. "
        "Focus your coaching on:\n"
        "- Line consistency: are they hitting the same line each lap?\n"
        "- Smooth inputs: abrupt braking/throttle transitions hurt "
        "novices most\n"
        "- Basic braking: are they braking in a straight line before "
        "turn-in?\n"
        "- Limit advice to 1-2 priorities per corner — avoid "
        "information overload\n"
        "- Do NOT discuss trail braking, threshold braking, or "
        "advanced techniques\n"
        "- Grade trail_braking as 'N/A' for novices (not expected "
        "at this level)\n"
        "- Use encouraging language and celebrate what they're "
        "doing well\n"
    ),
    "intermediate": (
        "\n## Skill Level: Intermediate (HPDE Group 3)\n"
        "This driver has solid fundamentals and is ready for "
        "technique refinement:\n"
        "- Trail braking: are they carrying brake into the corner "
        "entry?\n"
        "- Brake point optimization: can they brake later or "
        "release more gradually?\n"
        "- Throttle timing: are they getting on throttle at the "
        "right point?\n"
        "- Consistency: compare their best corner executions vs "
        "typical ones\n"
        "- Show all metrics and be specific about what to work on\n"
    ),
    "advanced": (
        "\n## Skill Level: Advanced (HPDE Group 4+ / Instructor)\n"
        "This driver has strong technique and is looking for "
        "marginal gains:\n"
        "- Micro-optimization: tenths and hundredths at each "
        "corner\n"
        "- Composite/theoretical gap analysis: where are they "
        "leaving time?\n"
        "- Setup correlation hints: do certain corners suggest "
        "car balance issues?\n"
        "- Discuss advanced concepts: trail brake modulation, "
        "weight transfer mgmt\n"
        "- Be precise with distances and speed differentials\n"
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
        "on carrying 2-3 mph more through the apex by braking "
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
    "Reference corner numbers and speeds in mph."
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


def _format_all_laps_corners(
    all_lap_corners: dict[int, list[Corner]],
    best_lap: int,
) -> str:
    """Format corner KPIs for every lap in the session."""
    lines = ["Lap | Corner | Min Speed (mph) | Brake Pt (m) | Peak Brake (G) | Throttle (m) | Apex"]
    lines.append("--- | --- | --- | --- | --- | --- | ---")

    for lap_num in sorted(all_lap_corners):
        tag = " *" if lap_num == best_lap else ""
        for c in all_lap_corners[lap_num]:
            speed = f"{c.min_speed_mps * MPS_TO_MPH:.1f}"
            brake = f"{c.brake_point_m:.0f}" if c.brake_point_m is not None else "—"
            peak_g = f"{c.peak_brake_g:.2f}" if c.peak_brake_g is not None else "—"
            throttle = f"{c.throttle_commit_m:.0f}" if c.throttle_commit_m is not None else "—"
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


def _format_corner_analysis(analysis: SessionCornerAnalysis) -> str:
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

        # Min speed
        ms = ca.stats_min_speed
        lines.append(
            f"  Min speed: best={ms.best:.1f} mean={ms.mean:.1f} "
            f"std={ms.std:.1f} mph"
        )

        # Brake point
        if ca.stats_brake_point is not None:
            bp = ca.stats_brake_point
            lines.append(
                f"  Brake pt: best={bp.best:.0f} mean={bp.mean:.0f} "
                f"std={bp.std:.1f}m"
            )

        # Peak brake g
        if ca.stats_peak_brake_g is not None:
            pg = ca.stats_peak_brake_g
            lines.append(f"  Peak brake: best={pg.best:.2f} mean={pg.mean:.2f}G")

        # Throttle commit
        if ca.stats_throttle_commit is not None:
            tc = ca.stats_throttle_commit
            lines.append(
                f"  Throttle: best={tc.best:.0f} mean={tc.mean:.0f} "
                f"std={tc.std:.1f}m"
            )

        # Apex distribution
        apex_parts = [
            f"{count}/{ca.n_laps} {atype}"
            for atype, count in sorted(ca.apex_distribution.items())
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
        lines.append(
            f"  Target min speed: {ca.recommendation.target_min_speed_mph:.1f} mph"
        )

        # Time value
        if ca.time_value is not None:
            tv = ca.time_value
            lines.append(
                f"  Approach speed: {tv.approach_speed_mph:.0f} mph, "
                f"time/m: {tv.time_per_meter_ms:.1f}ms"
            )
            lines.append(
                f"  Brake variance time cost: ~{tv.brake_variance_time_cost_s:.3f}s"
            )

        # Correlations
        for corr in ca.correlations:
            lines.append(
                f"  Corr {corr.kpi_x} vs {corr.kpi_y}: "
                f"r={corr.r:.2f} ({corr.strength}, n={corr.n_points})"
            )

        lines.append("")

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
) -> str:
    """Build the full coaching prompt for Claude."""
    lap_text = _format_lap_summaries(summaries)
    best = min(summaries, key=lambda s: s.lap_time_s)
    best_min = int(best.lap_time_s // 60)
    best_sec = best.lap_time_s % 60
    corner_text = _format_all_laps_corners(all_lap_corners, best.lap_number)

    gains_section = ""
    gains_instruction = ""
    if gains is not None:
        gains_section = f"\n{_format_gains_for_prompt(gains)}\n"
        gains_instruction = (
            "\nReference these computed gains when discussing priority corners. "
            "The consistency gain shows where the driver loses time vs their own best.\n"
        )

    skill_section = _SKILL_PROMPTS.get(skill_level, _SKILL_PROMPTS["intermediate"])

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

    corner_analysis_section = ""
    corner_analysis_instruction = ""
    if corner_analysis is not None and corner_analysis.corners:
        corner_analysis_section = f"\n{_format_corner_analysis(corner_analysis)}\n"
        corner_analysis_instruction = (
            "\nIMPORTANT: Use the pre-computed corner analysis above as your primary data source. "
            "The statistics, correlations, and recommendations are already computed — "
            "DO NOT re-derive them. Your job is to:\n"
            "1. Write narrative coaching advice explaining WHY these patterns matter\n"
            "2. Prioritize corners by the pre-computed gain values\n"
            "3. Reference the target brake/speed values in your tips\n"
            "4. Use correlation insights to explain cause-effect relationships\n"
            "5. Cite the specific numbers from the analysis in your grades and notes\n"
            "The raw KPI table below is for lap-specific citations only.\n"
        )

    return f"""Track: {track_name}
Best Lap: L{best.lap_number} ({best_min}:{best_sec:05.2f})
Total laps: {len(summaries)}
{corner_analysis_section}\
## Lap Times
{lap_text}

## Corner KPIs — All Laps (best lap marked with *)
{corner_text}
{gains_section}{optimal_section}{landmark_section}{skill_section}
{corner_analysis_instruction}\
{landmark_instruction}\
Analyze the FULL session. Look at every lap's data for each corner to identify:
- Consistency: which corners are repeatable vs high-variance across laps
- Trends: whether the driver improved or degraded through the session AND WHY \
(diagnose the cause: technique ceiling, fatigue, tire degradation, confidence plateau, etc.)
- Best-vs-rest gaps: where the best lap gained time vs the driver's typical performance
- Technique patterns: brake point consistency, apex type shifts, min-speed spread
{gains_instruction}{optimal_instruction}
Respond in JSON with this exact structure:
{{
  "summary": "2-3 sentence overview — mention consistency, progression, key strengths",
  "priority_corners": [
    {{
      "corner": <number>,
      "time_cost_s": <estimated avg time lost vs best lap at this corner>,
      "issue": "<what the data shows across all laps>",
      "tip": "<actionable advice, max 20 words>"
    }}
  ],
  "corner_grades": [
    {{
      "corner": <number>,
      "braking": "<A-F>",
      "trail_braking": "<A-F>",
      "min_speed": "<A-F>",
      "throttle": "<A-F>",
      "notes": "<one sentence referencing lap-to-lap data>"
    }}
  ],
  "patterns": ["<session-wide pattern with root cause>", "<pattern 2 with why>", "<pattern 3>"],
  "drills": [
    "<specific practice drill for weakness 1>",
    "<specific practice drill for weakness 2>"
  ]
}}

Include 1-2 specific practice drills tailored to the driver's weakest areas. \
Each drill should reference a specific corner number and give the driver \
something concrete to practice on their next session.

Sort priority_corners by time_cost_s descending (biggest avg time loss first).
Grades reflect consistency across ALL laps, not just one comparison:
  A = very consistent, close to best-lap performance every lap
  B = mostly consistent with minor variance
  C = moderate variance or a clear technique gap on some laps
  D = high variance, inconsistent execution
  F = major issue across most laps
Be encouraging but honest. Focus on the 2-3 biggest improvements.
For each pattern, don't just describe WHAT happened — diagnose WHY. \
If lap times plateaued, explain whether it's a technique ceiling, \
fatigue, tire degradation, or confidence limit based on the data."""


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
    )

    system = COACHING_SYSTEM_PROMPT
    kb_context = select_kb_snippets(all_lap_corners, skill_level, gains=gains)
    if kb_context:
        system += "\n\n" + kb_context

    def _call_coaching_api() -> tuple[str, CoachingReport]:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=16384,
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

    return report


def ask_followup(
    context: CoachingContext,
    question: str,
    coaching_report: CoachingReport,
    *,
    all_lap_corners: dict[int, list[Corner]] | None = None,
    skill_level: str = "intermediate",
    gains: GainEstimate | None = None,
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
