"""AI-generated coaching notes draft for track corners."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)


@dataclass
class CornerCoachingDraft:
    """Single coaching note draft for a track corner."""

    corner_number: int
    corner_name: str
    coaching_note: str


async def generate_coaching_drafts(
    corners: list[dict[str, object]],
    *,
    track_name: str,
    track_length_m: float | None = None,
) -> list[CornerCoachingDraft]:
    """Generate coaching note drafts for each corner using Claude Haiku.

    Each corner dict should have: number, name, direction, corner_type,
    elevation_trend, camber, fraction.

    Returns a coaching draft per corner. Notes are actionable,
    driver-focused, and < 2 sentences each.
    """
    if not corners:
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping coaching draft generation")
        return []

    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Build a single prompt for all corners (batch for efficiency)
    corner_descriptions: list[str] = []
    for c in corners:
        desc = f"Corner {c.get('number', '?')}: {c.get('name', 'Unknown')}"
        if c.get("direction"):
            desc += f", {c['direction']}-hander"
        if c.get("corner_type"):
            desc += f", {c['corner_type']}"
        if c.get("elevation_trend"):
            desc += f", {c['elevation_trend']}"
        if c.get("camber"):
            desc += f", {c['camber']} camber"
        corner_descriptions.append(desc)

    corners_text = "\n".join(corner_descriptions)

    system_prompt = (
        "You are an expert motorsport driving coach. Generate concise, actionable "
        "coaching notes for each corner. Each note must be 1-2 sentences, focused on "
        "what the driver should DO (brake point, turn-in, throttle application, line). "
        "Reference the corner's specific characteristics (direction, type, elevation, camber). "
        "Output ONLY a JSON array of objects with 'number' and 'note' keys."
    )

    user_prompt = f"Track: {track_name}"
    if track_length_m:
        user_prompt += f" ({track_length_m:.0f}m)"
    user_prompt += f"\n\nCorners:\n{corners_text}\n\nGenerate coaching notes for each corner."

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        block = response.content[0]
        text: str = block.text  # type: ignore[union-attr]
        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        notes: list[dict[str, object]] = json.loads(text.strip())

        # Build lookup for corner names
        corner_lookup = {c.get("number"): c.get("name", f"T{c.get('number')}") for c in corners}

        drafts: list[CornerCoachingDraft] = []
        for item in notes:
            num = item.get("number")
            note = str(item.get("note", ""))
            name = str(corner_lookup.get(num, f"T{num}"))
            drafts.append(
                CornerCoachingDraft(
                    corner_number=int(str(num)) if num is not None else 0,
                    corner_name=name,
                    coaching_note=note,
                )
            )

        return drafts

    except Exception:
        logger.warning("Failed to generate coaching drafts", exc_info=True)
        return []
