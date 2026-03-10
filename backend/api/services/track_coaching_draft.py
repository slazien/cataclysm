"""AI-generated coaching notes draft for track corners."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass

from cataclysm.llm_gateway import call_text_completion, is_task_available

logger = logging.getLogger(__name__)


@dataclass
class CornerCoachingDraft:
    """Single coaching note draft for a track corner."""

    corner_number: int
    corner_name: str
    coaching_note: str


def _coerce_corner_number(value: object) -> int | None:
    """Normalize corner identifiers from LLM output to integer numbers."""
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value) if value.is_integer() else None

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            numeric = float(stripped)
        except ValueError:
            return None
        return int(numeric) if numeric.is_integer() else None

    return None


def _coerce_corner_name(value: object, corner_number: int) -> str:
    """Normalize corner names while guaranteeing a stable fallback."""
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return f"T{corner_number}"


def _clean_note_text(value: object) -> str | None:
    """Normalize model note text; return None for empty/invalid values."""
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _coerce_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _build_fallback_note(corner: dict[str, object], *, corner_number: int) -> str:
    """Deterministic fallback note when LLM output is unavailable/incomplete."""
    direction = _coerce_optional_text(corner.get("direction"))
    corner_type = _coerce_optional_text(corner.get("corner_type"))
    elevation_trend = _coerce_optional_text(corner.get("elevation_trend"))
    camber = _coerce_optional_text(corner.get("camber"))

    if direction is not None and direction.lower() in {"left", "right"}:
        sentence_one = (
            f"Brake in a straight line before turn-in for this {direction.lower()}-hander "
            "and commit to one clean steering input."
        )
    else:
        sentence_one = (
            "Brake in a straight line before turn-in and commit to one clean steering input."
        )

    if corner_type is not None:
        sentence_two = (
            f"Treat this as a {corner_type.lower()}: prioritize a late apex, unwind steering "
            "progressively, and add throttle only once the car points to exit."
        )
    else:
        sentence_two = (
            "Prioritize a late apex, unwind steering progressively, and add throttle only once the "
            "car points to exit."
        )

    nuance_parts: list[str] = []
    if elevation_trend is not None:
        nuance_parts.append(f"the {elevation_trend.lower()} profile")
    if camber is not None:
        nuance_parts.append(f"{camber.lower()} camber")
    if nuance_parts:
        sentence_two = sentence_two[:-1] + f", while accounting for {' and '.join(nuance_parts)}."

    return f"{sentence_one} {sentence_two}"


def _extract_note_items(raw_text: str) -> list[dict[str, object]]:
    """Extract parsed note objects from raw LLM text."""
    text = raw_text
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]

    parsed = json.loads(text.strip())
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _build_strict_drafts(
    corners: list[dict[str, object]],
    note_items: list[dict[str, object]],
) -> list[CornerCoachingDraft]:
    """Build exactly one draft per input corner in input order."""
    normalized_corners: list[tuple[int, str, dict[str, object]]] = []
    for index, corner in enumerate(corners, start=1):
        corner_number = _coerce_corner_number(corner.get("number"))
        if corner_number is None:
            corner_number = index
        corner_name = _coerce_corner_name(corner.get("name"), corner_number)
        normalized_corners.append((corner_number, corner_name, corner))

    notes_by_corner: dict[int, list[str]] = {}
    for item in note_items:
        corner_number = _coerce_corner_number(item.get("number"))
        note_text = _clean_note_text(item.get("note"))
        if corner_number is None or note_text is None:
            continue
        notes_by_corner.setdefault(corner_number, []).append(note_text)

    drafts: list[CornerCoachingDraft] = []
    for corner_number, corner_name, corner in normalized_corners:
        note_candidates = notes_by_corner.get(corner_number, [])
        if note_candidates:
            coaching_note = note_candidates.pop(0)
        else:
            coaching_note = _build_fallback_note(corner, corner_number=corner_number)
        drafts.append(
            CornerCoachingDraft(
                corner_number=corner_number,
                corner_name=corner_name,
                coaching_note=coaching_note,
            )
        )

    return drafts


async def generate_coaching_drafts(
    corners: list[dict[str, object]],
    *,
    track_name: str,
    track_length_m: float | None = None,
) -> list[CornerCoachingDraft]:
    """Generate coaching note drafts for each corner using Claude Haiku.

    Each corner dict should have: number, name, direction, corner_type,
    elevation_trend, camber, fraction.

    Returns exactly one coaching draft per input corner in input order.
    Missing/invalid LLM entries are deterministically backfilled.
    """
    if not corners:
        return []

    normalized_corners: list[tuple[int, str, dict[str, object]]] = []
    for index, corner in enumerate(corners, start=1):
        corner_number = _coerce_corner_number(corner.get("number"))
        if corner_number is None:
            corner_number = index
        corner_name = _coerce_corner_name(corner.get("name"), corner_number)
        normalized_corners.append((corner_number, corner_name, corner))

    if not is_task_available("track_draft", default_provider="anthropic"):
        logger.warning("No LLM key configured for track draft generation")
        return _build_strict_drafts(corners, note_items=[])

    # Build a single prompt for all corners (batch for efficiency)
    corner_descriptions: list[str] = []
    for corner_number, corner_name, corner in normalized_corners:
        desc = f"Corner {corner_number}: {corner_name}"
        if corner.get("direction"):
            desc += f", {corner['direction']}-hander"
        if corner.get("corner_type"):
            desc += f", {corner['corner_type']}"
        if corner.get("elevation_trend"):
            desc += f", {corner['elevation_trend']}"
        if corner.get("camber"):
            desc += f", {corner['camber']} camber"
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
        result = await asyncio.to_thread(
            call_text_completion,
            task="track_draft",
            user_content=user_prompt,
            system=system_prompt,
            max_tokens=1024,
            temperature=0.3,
            default_provider="anthropic",
            default_model="claude-haiku-4-5-20251001",
        )
        note_items = _extract_note_items(result.text)
        return _build_strict_drafts(corners, note_items=note_items)

    except Exception:
        logger.warning("Failed to generate coaching drafts", exc_info=True)
        return _build_strict_drafts(corners, note_items=[])
