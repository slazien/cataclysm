"""Tests for cataclysm.coaching_validator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cataclysm.coaching_validator import (
    DEFAULT_INTERVAL,
    MAX_INTERVAL,
    MIN_INTERVAL,
    WINDOW_SIZE,
    CoachingValidator,
    ValidationRecord,
)


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    return tmp_path / "validation.json"


@pytest.fixture
def validator(state_path: Path) -> CoachingValidator:
    return CoachingValidator(state_path=state_path)


# ── State persistence ─────────────────────────────────────────────────


def test_fresh_state_defaults(validator: CoachingValidator) -> None:
    """A brand-new validator starts with default interval and zero counts."""
    s = validator.state
    assert s.current_interval == DEFAULT_INTERVAL
    assert s.outputs_since_check == 0
    assert s.total_outputs == 0
    assert s.total_checks == 0
    assert s.total_failures == 0
    assert s.checks == []


def test_state_persists_across_instances(state_path: Path) -> None:
    """State survives creating a new CoachingValidator from the same path."""
    v1 = CoachingValidator(state_path=state_path)
    v1.state.total_outputs = 42
    v1.state.current_interval = 50
    v1._save()

    v2 = CoachingValidator(state_path=state_path)
    assert v2.state.total_outputs == 42
    assert v2.state.current_interval == 50


def test_corrupt_state_file_resets(state_path: Path) -> None:
    """A corrupted state file should result in fresh defaults."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("not valid json!!!")
    v = CoachingValidator(state_path=state_path)
    assert v.state.current_interval == DEFAULT_INTERVAL


# ── Counting without validation ───────────────────────────────────────


def test_no_validation_before_interval(validator: CoachingValidator) -> None:
    """Outputs before the interval elapses should not trigger validation."""
    for _ in range(DEFAULT_INTERVAL - 1):
        result = validator.record_and_maybe_validate("some report text")
        assert result is None
    assert validator.state.total_outputs == DEFAULT_INTERVAL - 1
    assert validator.state.outputs_since_check == DEFAULT_INTERVAL - 1
    assert validator.state.total_checks == 0


# ── Validation triggers ──────────────────────────────────────────────


@patch("cataclysm.coaching_validator.CoachingValidator._create_client")
def test_validation_triggers_at_interval(
    mock_client_factory: MagicMock,
    validator: CoachingValidator,
) -> None:
    """Validation fires exactly when outputs_since_check reaches the interval."""
    # Mock the API call to return a passing result
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"passed": true, "violations": []}')]
    mock_client.messages.create.return_value = mock_response
    mock_client_factory.return_value = mock_client

    # Burn through interval - 1 outputs (no validation)
    for _ in range(DEFAULT_INTERVAL - 1):
        assert validator.record_and_maybe_validate("text") is None

    # The Nth output should trigger validation
    result = validator.record_and_maybe_validate("text")
    assert result is not None
    assert result.passed is True
    assert validator.state.total_checks == 1
    assert validator.state.outputs_since_check == 0


@patch("cataclysm.coaching_validator.CoachingValidator._create_client")
def test_failed_validation_recorded(
    mock_client_factory: MagicMock,
    validator: CoachingValidator,
) -> None:
    """A failing validation increments the failure counter."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(
            text=json.dumps(
                {
                    "passed": False,
                    "violations": ["Said early turn-in causes early apex"],
                }
            )
        )
    ]
    mock_client.messages.create.return_value = mock_response
    mock_client_factory.return_value = mock_client

    # Reach the interval
    for _ in range(DEFAULT_INTERVAL - 1):
        validator.record_and_maybe_validate("text")

    result = validator.record_and_maybe_validate("text")
    assert result is not None
    assert result.passed is False
    assert result.violations == ["Said early turn-in causes early apex"]
    assert validator.state.total_failures == 1


@patch("cataclysm.coaching_validator.CoachingValidator._create_client")
def test_no_api_key_skips_validation(
    mock_client_factory: MagicMock,
    validator: CoachingValidator,
) -> None:
    """Without an API key, validation is skipped (passes by default)."""
    mock_client_factory.return_value = None

    for _ in range(DEFAULT_INTERVAL - 1):
        validator.record_and_maybe_validate("text")

    result = validator.record_and_maybe_validate("text")
    assert result is not None
    assert result.passed is True


# ── Response parsing ──────────────────────────────────────────────────


def test_parse_validation_pass() -> None:
    text = '{"passed": true, "violations": []}'
    rec = CoachingValidator._parse_validation(text, "2024-01-01T00:00:00Z")
    assert rec.passed is True
    assert rec.violations == []


def test_parse_validation_fail() -> None:
    text = '{"passed": false, "violations": ["wrong physics"]}'
    rec = CoachingValidator._parse_validation(text, "2024-01-01T00:00:00Z")
    assert rec.passed is False
    assert rec.violations == ["wrong physics"]


def test_parse_validation_markdown_fenced() -> None:
    text = '```json\n{"passed": true, "violations": []}\n```'
    rec = CoachingValidator._parse_validation(text, "2024-01-01T00:00:00Z")
    assert rec.passed is True


def test_parse_validation_with_surrounding_text() -> None:
    text = 'Here is my analysis:\n{"passed": false, "violations": ["bad"]}\nDone.'
    rec = CoachingValidator._parse_validation(text, "2024-01-01T00:00:00Z")
    assert rec.passed is False
    assert rec.violations == ["bad"]


def test_parse_validation_garbage_defaults_to_pass() -> None:
    """Unparseable responses default to pass (fail-open, don't block coaching)."""
    text = "I don't understand"
    rec = CoachingValidator._parse_validation(text, "2024-01-01T00:00:00Z")
    assert rec.passed is True


# ── Adaptive interval ─────────────────────────────────────────────────


def test_interval_doubles_after_clean_window(state_path: Path) -> None:
    """A full window of passes should double the interval."""
    v = CoachingValidator(state_path=state_path)
    v.state.current_interval = 20

    # Seed a full window of passing checks
    for i in range(WINDOW_SIZE):
        v.state.checks.append(ValidationRecord(timestamp=f"t{i}", passed=True))

    v._adjust_interval()
    assert v.state.current_interval == 40


def test_interval_caps_at_max(state_path: Path) -> None:
    """Interval growth is capped at MAX_INTERVAL."""
    v = CoachingValidator(state_path=state_path)
    v.state.current_interval = MAX_INTERVAL

    for i in range(WINDOW_SIZE):
        v.state.checks.append(ValidationRecord(timestamp=f"t{i}", passed=True))

    v._adjust_interval()
    assert v.state.current_interval == MAX_INTERVAL


def test_interval_halves_on_high_failure_rate(state_path: Path) -> None:
    """Failure rate above threshold should halve the interval."""
    v = CoachingValidator(state_path=state_path)
    v.state.current_interval = 40

    # 3 failures out of 10 = 30% > 20% threshold
    for i in range(WINDOW_SIZE):
        v.state.checks.append(
            ValidationRecord(
                timestamp=f"t{i}",
                passed=(i >= 3),  # first 3 fail
            )
        )

    v._adjust_interval()
    assert v.state.current_interval == 20


def test_interval_floors_at_min(state_path: Path) -> None:
    """Interval shrinkage is floored at MIN_INTERVAL."""
    v = CoachingValidator(state_path=state_path)
    v.state.current_interval = MIN_INTERVAL

    # All failures
    for i in range(WINDOW_SIZE):
        v.state.checks.append(ValidationRecord(timestamp=f"t{i}", passed=False))

    v._adjust_interval()
    assert v.state.current_interval == MIN_INTERVAL


def test_interval_unchanged_with_moderate_failures(state_path: Path) -> None:
    """1 failure in 10 checks (10%) → no change (between thresholds)."""
    v = CoachingValidator(state_path=state_path)
    v.state.current_interval = 20

    for i in range(WINDOW_SIZE):
        v.state.checks.append(
            ValidationRecord(
                timestamp=f"t{i}",
                passed=(i != 5),  # 1 failure
            )
        )

    v._adjust_interval()
    assert v.state.current_interval == 20


def test_no_adjustment_with_few_checks(state_path: Path) -> None:
    """Fewer than 3 checks → no adjustment."""
    v = CoachingValidator(state_path=state_path)
    v.state.current_interval = 20
    v.state.checks.append(ValidationRecord(timestamp="t0", passed=False))
    v._adjust_interval()
    assert v.state.current_interval == 20


# ── force_validate ────────────────────────────────────────────────────


@patch("cataclysm.coaching_validator.CoachingValidator._create_client")
def test_force_validate_always_runs(
    mock_client_factory: MagicMock,
    validator: CoachingValidator,
) -> None:
    """force_validate runs regardless of output counter."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"passed": true, "violations": []}')]
    mock_client.messages.create.return_value = mock_response
    mock_client_factory.return_value = mock_client

    # No outputs recorded — force_validate should still run
    result = validator.force_validate("some report")
    assert result.passed is True
    assert validator.state.total_checks == 1
    # output counter should not have changed
    assert validator.state.outputs_since_check == 0
    assert validator.state.total_outputs == 0


@patch("cataclysm.coaching_validator.CoachingValidator._create_client")
def test_force_validate_records_failure(
    mock_client_factory: MagicMock,
    validator: CoachingValidator,
) -> None:
    """force_validate failure is tracked in history."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"passed": false, "violations": ["bad physics"]}')]
    mock_client.messages.create.return_value = mock_response
    mock_client_factory.return_value = mock_client

    result = validator.force_validate("bad report")
    assert result.passed is False
    assert validator.state.total_failures == 1
    assert len(validator.state.checks) == 1


# ── Summary ───────────────────────────────────────────────────────────


def test_summary_returns_useful_info(validator: CoachingValidator) -> None:
    s = validator.summary
    assert s["total_outputs"] == 0
    assert s["current_interval"] == DEFAULT_INTERVAL
    assert s["next_check_in"] == DEFAULT_INTERVAL
    assert s["recent_failure_rate"] == 0.0
