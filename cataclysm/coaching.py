"""Claude API integration for AI-powered driving coaching."""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass, field

from cataclysm.corners import Corner
from cataclysm.driving_physics import COACHING_SYSTEM_PROMPT
from cataclysm.engine import LapSummary

MPS_TO_MPH = 2.23694

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
    raw_response: str = ""


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


def _build_coaching_prompt(
    summaries: list[LapSummary],
    all_lap_corners: dict[int, list[Corner]],
    track_name: str,
) -> str:
    """Build the full coaching prompt for Claude."""
    lap_text = _format_lap_summaries(summaries)
    best = min(summaries, key=lambda s: s.lap_time_s)
    best_min = int(best.lap_time_s // 60)
    best_sec = best.lap_time_s % 60
    corner_text = _format_all_laps_corners(all_lap_corners, best.lap_number)

    return f"""Track: {track_name}
Best Lap: L{best.lap_number} ({best_min}:{best_sec:05.2f})
Total laps: {len(summaries)}

## Lap Times
{lap_text}

## Corner KPIs — All Laps (best lap marked with *)
{corner_text}

Analyze the FULL session. Look at every lap's data for each corner to identify:
- Consistency: which corners are repeatable vs high-variance across laps
- Trends: whether the driver improved or degraded through the session (fatigue, tire wear, learning)
- Best-vs-rest gaps: where the best lap gained time vs the driver's typical performance
- Technique patterns: brake point consistency, apex type shifts, min-speed spread

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
  "patterns": ["<session-wide pattern 1>", "<session-wide pattern 2>", "<pattern 3>"]
}}

Sort priority_corners by time_cost_s descending (biggest avg time loss first).
Grades reflect consistency across ALL laps, not just one comparison:
  A = very consistent, close to best-lap performance every lap
  B = mostly consistent with minor variance
  C = moderate variance or a clear technique gap on some laps
  D = high variance, inconsistent execution
  F = major issue across most laps
Be encouraging but honest. Focus on the 2-3 biggest improvements."""


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

    return CoachingReport(
        summary=data.get("summary", ""),
        priority_corners=data.get("priority_corners", []),
        corner_grades=grades,
        patterns=data.get("patterns", []),
        raw_response=text,
    )


def generate_coaching_report(
    summaries: list[LapSummary],
    all_lap_corners: dict[int, list[Corner]],
    track_name: str,
) -> CoachingReport:
    """Generate an AI coaching report using the Claude API.

    Analyzes corner KPIs across ALL laps in the session.

    Requires ANTHROPIC_API_KEY environment variable.
    Returns a CoachingReport. If the API key is not set, returns a report
    with a message explaining how to enable coaching.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return CoachingReport(
            summary="Set ANTHROPIC_API_KEY environment variable to enable AI coaching.",
            priority_corners=[],
            corner_grades=[],
            patterns=[],
        )

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_coaching_prompt(summaries, all_lap_corners, track_name)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=COACHING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        return CoachingReport(
            summary=f"AI coaching error: {e}",
            priority_corners=[],
            corner_grades=[],
            patterns=[],
        )

    block = message.content[0]
    response_text = block.text if hasattr(block, "text") else str(block)
    report = _parse_coaching_response(response_text)
    return report


def ask_followup(
    context: CoachingContext,
    question: str,
    coaching_report: CoachingReport,
) -> str:
    """Ask a follow-up question to the AI coach.

    Maintains conversation context for multi-turn chat.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "Set ANTHROPIC_API_KEY to enable AI coaching chat."

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    if not context.messages:
        # First follow-up: include the coaching report as context
        context.messages.append(
            {
                "role": "assistant",
                "content": f"Here is my coaching report:\n\n{coaching_report.raw_response}",
            }
        )

    context.messages.append({"role": "user", "content": question})

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_FOLLOWUP_SYSTEM,
            messages=context.messages,  # type: ignore[arg-type]
        )
    except Exception as e:
        return f"AI coaching error: {e}"

    followup_block = message.content[0]
    response_text = followup_block.text if hasattr(followup_block, "text") else str(followup_block)
    context.messages.append({"role": "assistant", "content": response_text})
    return response_text
