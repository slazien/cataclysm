"""Shared types for the quality assessment framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


@dataclass(slots=True)
class DimensionResult:
    """Result for a single assessment dimension."""

    name: str
    score: float  # 0.0-1.0
    verdict: Verdict
    details: str = ""


@dataclass(slots=True)
class AssessmentResult:
    """Aggregated assessment result for a single coaching output."""

    case_id: str
    hard_gate_passed: bool
    dimensions: list[DimensionResult] = field(default_factory=list)
    weighted_score: float = 0.0
    verdict: Verdict = Verdict.FAIL
    error: str = ""

    @property
    def passed(self) -> bool:
        return self.verdict == Verdict.PASS
