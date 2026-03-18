"""Tests for assessment aggregation."""

from __future__ import annotations

from evaluation.aggregate import aggregate
from evaluation.types import DimensionResult, Verdict


def _dim(name: str, score: float, verdict: Verdict = Verdict.PASS) -> DimensionResult:
    return DimensionResult(name=name, score=score, verdict=verdict)


def test_hard_gate_fail_short_circuits() -> None:
    result = aggregate(
        "test-1",
        hard_gate_results=[_dim("json_valid", 0.0, Verdict.FAIL)],
        soft_results=[_dim("citation_grounding", 1.0)],
        judge_results=[_dim("physics_accuracy", 1.0)],
    )
    assert result.verdict == Verdict.FAIL
    assert not result.hard_gate_passed


def test_all_pass_with_high_scores() -> None:
    result = aggregate(
        "test-2",
        hard_gate_results=[_dim("json_valid", 1.0), _dim("required_fields", 1.0)],
        soft_results=[_dim("citation_grounding", 0.9), _dim("because_clauses", 0.8)],
        judge_results=[
            _dim("physics_accuracy", 0.85),
            _dim("voice_quality", 0.80),
            _dim("coherence", 0.75),
            _dim("actionability", 0.70),
        ],
    )
    assert result.verdict == Verdict.PASS
    assert result.weighted_score > 0.7


def test_below_minimum_fails() -> None:
    result = aggregate(
        "test-3",
        hard_gate_results=[_dim("json_valid", 1.0)],
        soft_results=[_dim("citation_grounding", 0.3)],
        judge_results=[_dim("physics_accuracy", 0.9)],
    )
    assert result.verdict == Verdict.FAIL
    assert "Below minimums" in result.error


def test_skipped_judges_excluded_from_scoring() -> None:
    """WARN/0.0 judges (deepeval missing) must not drag score or trigger minimums."""
    result = aggregate(
        "test-skip",
        hard_gate_results=[_dim("json_valid", 1.0)],
        soft_results=[_dim("citation_grounding", 0.9), _dim("because_clauses", 0.8)],
        judge_results=[
            _dim("physics_accuracy", 0.0, Verdict.WARN),
            _dim("voice_quality", 0.0, Verdict.WARN),
        ],
    )
    assert result.verdict == Verdict.PASS
    assert result.weighted_score > 0.7
    assert result.error == ""


def test_low_weighted_score_fails() -> None:
    result = aggregate(
        "test-4",
        hard_gate_results=[_dim("json_valid", 1.0)],
        soft_results=[_dim("citation_grounding", 0.7)],
        judge_results=[
            _dim("physics_accuracy", 0.3),
            _dim("voice_quality", 0.3),
        ],
        pass_threshold=0.7,
    )
    assert result.verdict == Verdict.FAIL
