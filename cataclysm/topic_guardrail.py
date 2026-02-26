"""Off-topic guardrail for the coaching follow-up chat.

Implements a multi-layered approach (Anthropic best-practice pattern):
  Layer 0 — System prompt hardening (always active, zero cost)
  Layer 1 — Lightweight Haiku classifier pre-screen (~$0.001/check)

The classifier uses Claude Haiku with structured JSON output to
determine if a user's follow-up question is relevant to motorsport
driving, telemetry analysis, or vehicle performance.

References:
  - Anthropic "Mitigate jailbreaks" docs (harmlessness screen pattern)
  - arXiv:2411.12946 "Off-Topic Prompt Detection" methodology
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ── Layer 0: System prompt hardening ──────────────────────────────────

TOPIC_RESTRICTION_PROMPT = (
    "\n\n## Topic Restriction\n"
    "You are EXCLUSIVELY a motorsport driving coach. You may ONLY discuss:\n"
    "- Driving technique (braking, throttle, steering, racing line)\n"
    "- Telemetry data analysis (speed, g-forces, lap times, corner KPIs)\n"
    "- Vehicle dynamics (grip, tire management, weight transfer, setup)\n"
    "- Track-specific knowledge (corners, landmarks, surface conditions)\n"
    "- Race craft (overtaking, defending, pit strategy)\n"
    "- Driver fitness, mental preparation, and safety as it relates to driving\n"
    "\n"
    "If the user asks about ANYTHING unrelated to motorsport, driving, cars, "
    "or vehicle performance, respond ONLY with:\n"
    '"I\'m your motorsport driving coach — I can only help with driving '
    "technique, telemetry analysis, and track performance. "
    'What would you like to know about your driving?"\n'
    "\n"
    "Do NOT answer off-topic questions even if the user insists. "
    "Do NOT acknowledge the off-topic content. "
    "Always redirect to driving topics.\n"
)

# ── Layer 1: Haiku classifier pre-screen ──────────────────────────────

_CLASSIFIER_PROMPT = """\
You are a topic classifier for a motorsport driving coaching chatbot.

Determine if the user's message is relevant to ANY of these topics:
- Driving technique, racing, track days, car control
- Telemetry data, lap times, speed, g-forces, braking
- Vehicle dynamics, setup, tires, suspension
- Track knowledge, corners, racing lines
- Race craft, overtaking, pit strategy
- Driver fitness, safety, mental preparation for driving
- Car maintenance or modifications for track use
- General motorsport questions (F1, GT, karting, etc.)

A message is ON-TOPIC if it relates to ANY of the above, even tangentially.
A message is OFF-TOPIC if it has NO connection to driving or motorsport.

Respond ONLY with JSON: {{"on_topic": true}} or {{"on_topic": false}}

User message: {message}"""

# Haiku is recommended by Anthropic as a lightweight pre-screen classifier
_CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"
_CLASSIFIER_MAX_TOKENS = 32
_CLASSIFIER_TIMEOUT_S = 10.0

# Canned decline response when off-topic is detected
OFF_TOPIC_RESPONSE = (
    "I'm your motorsport driving coach — I can only help with driving "
    "technique, telemetry analysis, and track performance. "
    "What would you like to know about your driving?"
)


@dataclass
class TopicClassification:
    """Result of the topic classifier."""

    on_topic: bool
    source: str  # "classifier", "fallback", "no_api_key"


def _create_classifier_client() -> Any:
    """Create a lightweight Anthropic client for classification."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    return anthropic.Anthropic(
        api_key=api_key,
        max_retries=1,
        timeout=_CLASSIFIER_TIMEOUT_S,
    )


def classify_topic(message: str) -> TopicClassification:
    """Classify whether a user message is on-topic for motorsport coaching.

    Uses a lightweight Haiku call with structured output (Anthropic's
    recommended "harmlessness screen" pattern).

    Falls back to on_topic=True if the API is unavailable, to avoid
    blocking legitimate users. The system prompt hardening (Layer 0)
    still protects against off-topic responses in that case.

    Parameters
    ----------
    message:
        The user's follow-up chat message.

    Returns
    -------
    TopicClassification with on_topic bool and source indicator.
    """
    if not message.strip():
        return TopicClassification(on_topic=False, source="empty")

    client = _create_classifier_client()
    if client is None:
        # No API key — fall back to permissive (Layer 0 still protects)
        return TopicClassification(on_topic=True, source="no_api_key")

    prompt = _CLASSIFIER_PROMPT.format(message=message)

    try:
        response = client.messages.create(
            model=_CLASSIFIER_MODEL,
            max_tokens=_CLASSIFIER_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        logger.warning("Topic classifier API call failed", exc_info=True)
        # Fail open — Layer 0 system prompt still protects
        return TopicClassification(on_topic=True, source="fallback")

    block = response.content[0]
    text = block.text if hasattr(block, "text") else str(block)

    return _parse_classification(text)


def _parse_classification(text: str) -> TopicClassification:
    """Parse the classifier's JSON response."""
    text = text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()

    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from surrounding text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            with contextlib.suppress(json.JSONDecodeError):
                data = json.loads(text[start : end + 1])

    if data is None:
        logger.warning("Could not parse topic classification: %s", text[:100])
        # Fail open
        return TopicClassification(on_topic=True, source="fallback")

    on_topic = bool(data.get("on_topic", True))
    return TopicClassification(on_topic=on_topic, source="classifier")
