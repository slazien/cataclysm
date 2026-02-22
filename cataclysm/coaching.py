"""Claude API integration for AI-powered driving coaching."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from cataclysm.corners import Corner
from cataclysm.delta import CornerDelta
from cataclysm.engine import LapSummary

MPS_TO_MPH = 2.23694


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


def _format_corner_comparison(
    best_corners: list[Corner],
    comp_corners: list[Corner],
    deltas: list[CornerDelta],
) -> str:
    """Format corner KPI comparison between best and comparison laps."""
    delta_map = {d.corner_number: d.delta_s for d in deltas}
    comp_map = {c.number: c for c in comp_corners}

    lines = [
        "Corner | Best Min Speed | Comp Min Speed | Best Brake Pt | Comp Brake Pt "
        "| Corner Delta(s) | Best Apex | Comp Apex"
    ]
    lines.append("--- | --- | --- | --- | --- | --- | --- | ---")

    for bc in best_corners:
        cc = comp_map.get(bc.number)
        delta = delta_map.get(bc.number, 0.0)

        best_speed = f"{bc.min_speed_mps * MPS_TO_MPH:.1f}"
        comp_speed = f"{cc.min_speed_mps * MPS_TO_MPH:.1f}" if cc else "N/A"

        best_brake = f"{bc.brake_point_m:.0f}m" if bc.brake_point_m is not None else "N/A"
        comp_brake = f"{cc.brake_point_m:.0f}m" if cc and cc.brake_point_m is not None else "N/A"

        lines.append(
            f"T{bc.number} | {best_speed} mph | {comp_speed} mph | {best_brake} | "
            f"{comp_brake} | {delta:+.3f}s | {bc.apex_type} | "
            f"{cc.apex_type if cc else 'N/A'}"
        )

    return "\n".join(lines)


def _build_coaching_prompt(
    summaries: list[LapSummary],
    best_corners: list[Corner],
    comp_corners: list[Corner],
    deltas: list[CornerDelta],
    track_name: str,
) -> str:
    """Build the full coaching prompt for Claude."""
    lap_text = _format_lap_summaries(summaries)
    corner_text = _format_corner_comparison(best_corners, comp_corners, deltas)

    best = min(summaries, key=lambda s: s.lap_time_s)
    best_min = int(best.lap_time_s // 60)
    best_sec = best.lap_time_s % 60

    return f"""You are an expert motorsport driving coach analyzing telemetry data from a track day.
The driver is an enthusiast at an HPDE (High Performance Driving Education) event.
Give practical, actionable advice. Be specific about distances and speeds.

Track: {track_name}
Best Lap: L{best.lap_number} ({best_min}:{best_sec:05.2f})

## Lap Times
{lap_text}

## Corner-by-Corner Comparison (Best Lap vs Median Lap)
{corner_text}

Respond in JSON with this exact structure:
{{
  "summary": "2-3 sentence overview of the session",
  "priority_corners": [
    {{
      "corner": <number>,
      "time_cost_s": <float>,
      "issue": "<brief description>",
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
      "notes": "<one sentence>"
    }}
  ],
  "patterns": ["<global pattern 1>", "<global pattern 2>"]
}}

Sort priority_corners by time_cost_s descending (biggest time loss first).
Grade A = excellent consistency between best and comparison laps.
Grade F = major inconsistency or clear technique error.
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

    try:
        data = json.loads(json_text.strip())
    except json.JSONDecodeError:
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
    best_corners: list[Corner],
    comp_corners: list[Corner],
    deltas: list[CornerDelta],
    track_name: str,
) -> CoachingReport:
    """Generate an AI coaching report using the Claude API.

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
    prompt = _build_coaching_prompt(summaries, best_corners, comp_corners, deltas, track_name)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        return CoachingReport(
            summary=f"AI coaching error: {e}",
            priority_corners=[],
            corner_grades=[],
            patterns=[],
        )

    response_text = message.content[0].text
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
        context.messages.append({
            "role": "assistant",
            "content": f"Here is my coaching report:\n\n{coaching_report.raw_response}",
        })

    context.messages.append({"role": "user", "content": question})

    system = (
        "You are an expert motorsport driving coach. The driver is asking follow-up "
        "questions about their telemetry data and your coaching report. Be specific, "
        "practical, and encouraging. Reference corner numbers and speeds in mph."
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=context.messages,
        )
    except Exception as e:
        return f"AI coaching error: {e}"

    response_text = str(message.content[0].text)
    context.messages.append({"role": "assistant", "content": response_text})
    return response_text
