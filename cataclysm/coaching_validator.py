"""Adaptive sampling validator for AI coaching outputs.

Periodically judges coaching reports with a rubric-based LLM check.
Tracks pass/fail history and adapts the sampling interval: fewer failures
lead to less frequent checks; more failures tighten checks.
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

from cataclysm.coaching_judge import build_judge_prompt, parse_judge_response
from cataclysm.llm_gateway import call_text_completion, is_task_available

logger = logging.getLogger(__name__)

# ── Adaptive interval parameters ──────────────────────────────────────
DEFAULT_INTERVAL = 5
MIN_INTERVAL = 5
MAX_INTERVAL = 200
WINDOW_SIZE = 10
FAILURE_RATE_INCREASE = 0.0  # 0% failures in window → grow interval
FAILURE_RATE_DECREASE = 0.20  # >20% failures in window → shrink interval


@dataclass
class ValidationRecord:
    """Single validation check result."""

    timestamp: str
    passed: bool
    violations: list[str] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)
    skill_level_checked: str = "intermediate"
    forbidden_pattern_violations: list[str] = field(default_factory=list)


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
    """Adaptive sampling validator for coaching report quality."""

    def __init__(self, state_path: Path | None = None) -> None:
        self.state_path = state_path or Path("data/coaching_validation.json")
        self.state = self._load()

    # ── Public API ────────────────────────────────────────────────────

    def record_and_maybe_validate(
        self,
        report_text: str,
        *,
        skill_level: str = "intermediate",
    ) -> ValidationRecord | None:
        """Record a coaching output; validate if the interval has elapsed."""
        self.state.total_outputs += 1
        self.state.outputs_since_check += 1

        if self.state.outputs_since_check < self.state.current_interval:
            self._save()
            return None

        self.state.outputs_since_check = 0
        record = self._validate(report_text, skill_level=skill_level)
        self.state.total_checks += 1
        if not record.passed:
            self.state.total_failures += 1
        self.state.checks.append(record)
        self._adjust_interval()
        self._save()
        return record

    def force_validate(
        self,
        report_text: str,
        *,
        skill_level: str = "intermediate",
    ) -> ValidationRecord:
        """Validate unconditionally (e.g., retry check after a failed sample)."""
        record = self._validate(report_text, skill_level=skill_level)
        self.state.total_checks += 1
        if not record.passed:
            self.state.total_failures += 1
        self.state.checks.append(record)
        self._adjust_interval()
        self._save()
        return record

    @property
    def summary(self) -> dict[str, object]:
        """Return a compact summary of validation history."""
        recent = self.state.checks[-WINDOW_SIZE:]
        recent_failures = sum(1 for record in recent if not record.passed)
        return {
            "total_outputs": self.state.total_outputs,
            "total_checks": self.state.total_checks,
            "total_failures": self.state.total_failures,
            "current_interval": self.state.current_interval,
            "recent_failure_rate": (recent_failures / len(recent) if recent else 0.0),
            "next_check_in": (self.state.current_interval - self.state.outputs_since_check),
        }

    @property
    def dashboard(self) -> dict[str, object]:
        """Return dashboard-friendly quality aggregates."""
        checks = self.state.checks
        if not checks:
            return {
                "summary": self.summary,
                "failure_types": {},
                "grounding_trend": [],
                "forbidden_composites": {},
            }

        failure_types: dict[str, int] = {}
        forbidden_composites: dict[str, int] = {}
        grounding_trend: list[dict[str, object]] = []

        for record in checks:
            for violation in record.violations:
                failure_types[violation] = failure_types.get(violation, 0) + 1
            for phrase in record.forbidden_pattern_violations:
                forbidden_composites[phrase] = forbidden_composites.get(phrase, 0) + 1
            if "data_relevance" in record.scores:
                grounding_trend.append(
                    {
                        "timestamp": record.timestamp,
                        "data_relevance": record.scores["data_relevance"],
                    }
                )

        return {
            "summary": self.summary,
            "failure_types": failure_types,
            "grounding_trend": grounding_trend[-50:],
            "forbidden_composites": forbidden_composites,
        }

    # ── Validation ────────────────────────────────────────────────────

    def _validate(self, report_text: str, *, skill_level: str) -> ValidationRecord:
        """Run rubric-based validation via a lightweight LLM call."""
        now = datetime.now(UTC).isoformat()

        if not is_task_available("coaching_validator", default_provider="anthropic"):
            logger.debug("Skipping coaching validation — no API key")
            return ValidationRecord(timestamp=now, passed=True, skill_level_checked=skill_level)

        prompt = build_judge_prompt(report_text, skill_level)

        try:
            result = call_text_completion(
                task="coaching_validator",
                user_content=prompt,
                system=None,
                max_tokens=800,
                temperature=0.0,
                default_provider="anthropic",
                default_model="claude-sonnet-4-6",
            )
            text = result.text
        except Exception:
            logger.warning("Coaching validation API call failed", exc_info=True)
            return ValidationRecord(timestamp=now, passed=True, skill_level_checked=skill_level)

        return self._parse_validation(text, now, skill_level=skill_level)

    @staticmethod
    def _coerce_passed_value(value: Any) -> bool:
        """Coerce legacy 'passed' values to bool with fail-open default."""
        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False

        return True

    @staticmethod
    def _parse_validation(
        text: str,
        timestamp: str,
        *,
        skill_level: str = "intermediate",
    ) -> ValidationRecord:
        """Parse validator response into a ValidationRecord."""
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1]
            clean = clean.rsplit("```", 1)[0]

        data: dict[str, Any] | None = None
        with contextlib.suppress(json.JSONDecodeError):
            parsed = json.loads(clean.strip())
            if isinstance(parsed, dict):
                data = parsed

        if data is None:
            start = clean.find("{")
            end = clean.rfind("}")
            if start != -1 and end > start:
                with contextlib.suppress(json.JSONDecodeError):
                    parsed = json.loads(clean[start : end + 1])
                    if isinstance(parsed, dict):
                        data = parsed

        if data is None:
            logger.warning("Could not parse validation response: %s", clean[:200])
            return ValidationRecord(
                timestamp=timestamp, passed=True, skill_level_checked=skill_level
            )

        # Backward compatibility with the old validator format.
        if "passed" in data and "violations" in data:
            violations = data.get("violations", [])
            return ValidationRecord(
                timestamp=timestamp,
                passed=CoachingValidator._coerce_passed_value(data.get("passed", True)),
                violations=violations if isinstance(violations, list) else [],
                skill_level_checked=skill_level,
            )

        judge = parse_judge_response(clean, skill_level)
        scores = {
            "topic_gating": judge.topic_gating,
            "communication_fit": judge.communication_fit,
            "data_relevance": judge.data_relevance,
            "causal_reasoning": judge.causal_reasoning,
            "actionability": judge.actionability,
        }
        threshold_violations = [
            f"{name} score {score} < 3" for name, score in scores.items() if score < 3
        ]
        violations = judge.forbidden_pattern_violations + [
            item for item in threshold_violations if item not in judge.forbidden_pattern_violations
        ]

        return ValidationRecord(
            timestamp=timestamp,
            passed=judge.overall_pass,
            violations=violations,
            scores=scores,
            skill_level_checked=judge.skill_level_checked,
            forbidden_pattern_violations=judge.forbidden_pattern_violations,
        )

    # ── Adaptive interval ─────────────────────────────────────────────

    def _adjust_interval(self) -> None:
        """Adjust sampling interval based on recent failure rate."""
        recent = self.state.checks[-WINDOW_SIZE:]
        if len(recent) < 3:
            return

        failure_rate = sum(1 for record in recent if not record.passed) / len(recent)

        if failure_rate <= FAILURE_RATE_INCREASE and len(recent) >= WINDOW_SIZE:
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
            checks = [ValidationRecord(**record) for record in raw.pop("checks", [])]
            return ValidationState(**raw, checks=checks)
        except Exception:
            logger.warning("Could not load validation state, starting fresh", exc_info=True)
            return ValidationState()

    def _save(self) -> None:
        """Atomically persist state to disk."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self.state)
        fd, tmp = tempfile.mkstemp(dir=self.state_path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(data, handle, indent=2)
            Path(tmp).replace(self.state_path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
