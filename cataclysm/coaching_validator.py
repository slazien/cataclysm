"""Adaptive sampling validator for AI coaching outputs.

Periodically checks coaching reports against physics guardrails using a
lightweight LLM call.  Tracks pass/fail history and adapts the sampling
interval: fewer failures → less frequent checks; more failures → more
frequent checks.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cataclysm.driving_physics import PHYSICS_GUARDRAILS

logger = logging.getLogger(__name__)

# ── Adaptive interval parameters ──────────────────────────────────────
DEFAULT_INTERVAL = 20
MIN_INTERVAL = 5
MAX_INTERVAL = 200
WINDOW_SIZE = 10
FAILURE_RATE_INCREASE = 0.0  # 0% failures in window → grow interval
FAILURE_RATE_DECREASE = 0.20  # >20% failures in window → shrink interval

# ── Validation prompt ─────────────────────────────────────────────────
_VALIDATION_PROMPT = """\
Below are physics guardrails that a motorsport coaching report must NEVER contradict:

{guardrails}

Now check this coaching report for contradictions:

{report}

For each guardrail, verify whether ANY statement in the report contradicts it.
Respond ONLY with JSON (no markdown, no explanation):
{{"passed": true, "violations": []}}
if no contradictions, or:
{{"passed": false, "violations": ["brief description of each contradiction"]}}"""


@dataclass
class ValidationRecord:
    """Single validation check result."""

    timestamp: str
    passed: bool
    violations: list[str] = field(default_factory=list)


@dataclass
class ValidationState:
    """Persistent state for the adaptive validator."""

    current_interval: int = DEFAULT_INTERVAL
    outputs_since_check: int = 0
    total_outputs: int = 0
    total_checks: int = 0
    total_failures: int = 0
    checks: list[ValidationRecord] = field(default_factory=list)


class CoachingValidator:
    """Adaptive sampling validator for coaching report quality.

    Counts coaching outputs and runs a validation check every
    ``current_interval`` outputs.  After each check the interval is
    adjusted based on recent failure rate.
    """

    def __init__(self, state_path: Path | None = None) -> None:
        self.state_path = state_path or Path("data/coaching_validation.json")
        self.state = self._load()

    # ── Public API ────────────────────────────────────────────────────

    def record_and_maybe_validate(self, report_text: str) -> ValidationRecord | None:
        """Record a coaching output; validate if the interval has elapsed.

        Returns the ValidationRecord if a check ran, otherwise None.
        """
        self.state.total_outputs += 1
        self.state.outputs_since_check += 1

        if self.state.outputs_since_check < self.state.current_interval:
            self._save()
            return None

        # Time to validate
        self.state.outputs_since_check = 0
        record = self._validate(report_text)
        self.state.total_checks += 1
        if not record.passed:
            self.state.total_failures += 1
        self.state.checks.append(record)
        self._adjust_interval()
        self._save()
        return record

    def force_validate(self, report_text: str) -> ValidationRecord:
        """Validate unconditionally (e.g. on retry after a failure).

        Records the result in history but does not affect the output counter.
        """
        record = self._validate(report_text)
        self.state.total_checks += 1
        if not record.passed:
            self.state.total_failures += 1
        self.state.checks.append(record)
        self._adjust_interval()
        self._save()
        return record

    @property
    def summary(self) -> dict[str, object]:
        """Return a human-readable summary of validation history."""
        recent = self.state.checks[-WINDOW_SIZE:]
        recent_failures = sum(1 for r in recent if not r.passed)
        return {
            "total_outputs": self.state.total_outputs,
            "total_checks": self.state.total_checks,
            "total_failures": self.state.total_failures,
            "current_interval": self.state.current_interval,
            "recent_failure_rate": (recent_failures / len(recent) if recent else 0.0),
            "next_check_in": (self.state.current_interval - self.state.outputs_since_check),
        }

    # ── Validation ────────────────────────────────────────────────────

    def _validate(self, report_text: str) -> ValidationRecord:
        """Run a guardrail compliance check via a lightweight LLM call."""
        now = datetime.now(UTC).isoformat()

        client = self._create_client()
        if client is None:
            logger.debug("Skipping coaching validation — no API key")
            return ValidationRecord(timestamp=now, passed=True)

        prompt = _VALIDATION_PROMPT.format(
            guardrails=PHYSICS_GUARDRAILS,
            report=report_text,
        )

        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception:
            logger.warning("Coaching validation API call failed", exc_info=True)
            return ValidationRecord(timestamp=now, passed=True)

        block = message.content[0]
        text = block.text if hasattr(block, "text") else str(block)
        return self._parse_validation(text, now)

    @staticmethod
    def _parse_validation(text: str, timestamp: str) -> ValidationRecord:
        """Parse the validator LLM response into a ValidationRecord."""
        text = text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0]

        data: dict | None = None
        try:
            data = json.loads(text.strip())
        except json.JSONDecodeError:
            # Try to extract JSON from surrounding text
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                with contextlib.suppress(json.JSONDecodeError):
                    data = json.loads(text[start : end + 1])

        if data is None:
            logger.warning("Could not parse validation response: %s", text[:200])
            return ValidationRecord(timestamp=timestamp, passed=True)

        return ValidationRecord(
            timestamp=timestamp,
            passed=bool(data.get("passed", True)),
            violations=data.get("violations", []),
        )

    # ── Adaptive interval ─────────────────────────────────────────────

    def _adjust_interval(self) -> None:
        """Adjust sampling interval based on recent failure rate."""
        recent = self.state.checks[-WINDOW_SIZE:]
        if len(recent) < 3:
            return  # Not enough data to adjust

        failure_rate = sum(1 for r in recent if not r.passed) / len(recent)

        if failure_rate <= FAILURE_RATE_INCREASE and len(recent) >= WINDOW_SIZE:
            # Clean track record → relax checks
            new = min(MAX_INTERVAL, self.state.current_interval * 2)
            if new != self.state.current_interval:
                logger.info(
                    "Coaching validation: 0 failures in last %d checks, interval %d → %d",
                    WINDOW_SIZE,
                    self.state.current_interval,
                    new,
                )
                self.state.current_interval = new
        elif failure_rate > FAILURE_RATE_DECREASE:
            # Too many failures → tighten checks
            new = max(MIN_INTERVAL, self.state.current_interval // 2)
            if new != self.state.current_interval:
                logger.info(
                    "Coaching validation: %.0f%% failure rate, interval %d → %d",
                    failure_rate * 100,
                    self.state.current_interval,
                    new,
                )
                self.state.current_interval = new

    # ── Persistence ───────────────────────────────────────────────────

    def _load(self) -> ValidationState:
        """Load state from disk, or return defaults."""
        if not self.state_path.exists():
            return ValidationState()
        try:
            raw = json.loads(self.state_path.read_text())
            checks = [ValidationRecord(**c) for c in raw.pop("checks", [])]
            return ValidationState(**raw, checks=checks)
        except Exception:
            logger.warning("Could not load validation state, starting fresh", exc_info=True)
            return ValidationState()

    def _save(self) -> None:
        """Atomically persist state to disk."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self.state)
        # Atomic write: write to temp file then rename
        fd, tmp = tempfile.mkstemp(dir=self.state_path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            Path(tmp).replace(self.state_path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    @staticmethod
    def _create_client() -> Any:
        """Create a lightweight Anthropic client for validation calls."""
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None
        return anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=30.0)
