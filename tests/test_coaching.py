"""Tests for cataclysm.coaching."""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from cataclysm.coaching import (
    CoachingContext,
    CoachingReport,
    _build_coaching_prompt,
    _format_corner_comparison,
    _format_lap_summaries,
    _parse_coaching_response,
    ask_followup,
    generate_coaching_report,
)
from cataclysm.corners import Corner
from cataclysm.delta import CornerDelta
from cataclysm.engine import LapSummary


@pytest.fixture
def sample_summaries() -> list[LapSummary]:
    return [
        LapSummary(
            lap_number=1, lap_time_s=92.5,
            lap_distance_m=3800.0, max_speed_mps=45.0,
        ),
        LapSummary(
            lap_number=2, lap_time_s=94.2,
            lap_distance_m=3810.0, max_speed_mps=44.0,
        ),
        LapSummary(
            lap_number=3, lap_time_s=93.1,
            lap_distance_m=3805.0, max_speed_mps=44.5,
        ),
    ]


@pytest.fixture
def sample_corners() -> list[Corner]:
    return [
        Corner(
            1, 200.0, 350.0, 280.0, 22.0,
            150.0, -0.8, 370.0, "mid",
        ),
        Corner(
            2, 800.0, 950.0, 870.0, 18.0,
            750.0, -1.0, 970.0, "late",
        ),
    ]


@pytest.fixture
def sample_deltas() -> list[CornerDelta]:
    return [
        CornerDelta(corner_number=1, delta_s=0.15),
        CornerDelta(corner_number=2, delta_s=0.32),
    ]


def _make_mock_anthropic(
    response_text: str,
) -> MagicMock:
    """Create a mock anthropic module with a mock client."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=response_text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    mock_module = MagicMock()
    mock_module.Anthropic.return_value = mock_client
    return mock_module


class TestFormatLapSummaries:
    def test_includes_all_laps(
        self, sample_summaries: list[LapSummary]
    ) -> None:
        text = _format_lap_summaries(sample_summaries)
        assert "L1" in text
        assert "L2" in text
        assert "L3" in text

    def test_includes_time(
        self, sample_summaries: list[LapSummary]
    ) -> None:
        text = _format_lap_summaries(sample_summaries)
        assert "1:32" in text  # 92.5s = 1:32.50

    def test_includes_speed_in_mph(
        self, sample_summaries: list[LapSummary]
    ) -> None:
        text = _format_lap_summaries(sample_summaries)
        # 45 m/s = ~100.7 mph
        assert "100" in text


class TestFormatCornerComparison:
    def test_includes_corner_numbers(
        self,
        sample_corners: list[Corner],
        sample_deltas: list[CornerDelta],
    ) -> None:
        text = _format_corner_comparison(
            sample_corners, sample_corners, sample_deltas
        )
        assert "T1" in text
        assert "T2" in text

    def test_includes_speed_in_mph(
        self,
        sample_corners: list[Corner],
        sample_deltas: list[CornerDelta],
    ) -> None:
        text = _format_corner_comparison(
            sample_corners, sample_corners, sample_deltas
        )
        # 22 m/s = ~49.2 mph
        assert "49" in text


class TestParseCoachingResponse:
    def test_parses_valid_json(self) -> None:
        data = {
            "summary": "Good session.",
            "priority_corners": [
                {"corner": 2, "time_cost_s": 0.3,
                 "issue": "late", "tip": "brake earlier"},
            ],
            "corner_grades": [
                {"corner": 1, "braking": "B",
                 "trail_braking": "C", "min_speed": "A",
                 "throttle": "B", "notes": "ok"},
            ],
            "patterns": ["Late apexes"],
        }
        response = json.dumps(data)
        report = _parse_coaching_response(response)
        assert report.summary == "Good session."
        assert len(report.priority_corners) == 1
        assert len(report.corner_grades) == 1
        assert report.patterns == ["Late apexes"]

    def test_parses_json_in_code_block(self) -> None:
        inner = json.dumps({
            "summary": "Test", "priority_corners": [],
            "corner_grades": [], "patterns": [],
        })
        response = f"```json\n{inner}\n```"
        report = _parse_coaching_response(response)
        assert report.summary == "Test"

    def test_handles_invalid_json(self) -> None:
        report = _parse_coaching_response("not json at all")
        assert "Could not parse" in report.summary
        assert report.priority_corners == []

    def test_handles_partial_json(self) -> None:
        response = json.dumps({
            "summary": "Partial", "patterns": ["one"],
        })
        report = _parse_coaching_response(response)
        assert report.summary == "Partial"
        assert report.corner_grades == []


class TestBuildCoachingPrompt:
    def test_includes_track_name(
        self,
        sample_summaries: list[LapSummary],
        sample_corners: list[Corner],
        sample_deltas: list[CornerDelta],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries, sample_corners,
            sample_corners, sample_deltas, "Barber",
        )
        assert "Barber" in prompt

    def test_includes_json_structure(
        self,
        sample_summaries: list[LapSummary],
        sample_corners: list[Corner],
        sample_deltas: list[CornerDelta],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries, sample_corners,
            sample_corners, sample_deltas, "Test",
        )
        assert "priority_corners" in prompt
        assert "corner_grades" in prompt


class TestGenerateCoachingReport:
    def test_no_api_key_returns_message(
        self,
        sample_summaries: list[LapSummary],
        sample_corners: list[Corner],
        sample_deltas: list[CornerDelta],
    ) -> None:
        with patch.dict("os.environ", {}, clear=True):
            report = generate_coaching_report(
                sample_summaries, sample_corners,
                sample_corners, sample_deltas, "Test",
            )
        assert "ANTHROPIC_API_KEY" in report.summary

    def test_calls_api_with_key(
        self,
        sample_summaries: list[LapSummary],
        sample_corners: list[Corner],
        sample_deltas: list[CornerDelta],
    ) -> None:
        mock_anthropic = _make_mock_anthropic(json.dumps({
            "summary": "AI says hi",
            "priority_corners": [],
            "corner_grades": [],
            "patterns": [],
        }))

        with (
            patch.dict(
                "os.environ", {"ANTHROPIC_API_KEY": "sk-test"}
            ),
            patch.dict(
                sys.modules, {"anthropic": mock_anthropic}
            ),
        ):
            report = generate_coaching_report(
                sample_summaries, sample_corners,
                sample_corners, sample_deltas, "Test",
            )
        assert report.summary == "AI says hi"


class TestAskFollowup:
    def test_no_api_key(self) -> None:
        ctx = CoachingContext()
        report = CoachingReport("x", [], [], [])
        with patch.dict("os.environ", {}, clear=True):
            answer = ask_followup(ctx, "How do I brake?", report)
        assert "ANTHROPIC_API_KEY" in answer

    def test_maintains_context(self) -> None:
        mock_anthropic = _make_mock_anthropic(
            "Brake later into T5."
        )

        ctx = CoachingContext()
        report = CoachingReport(
            "summary", [], [], [],
            raw_response="report text",
        )

        with (
            patch.dict(
                "os.environ", {"ANTHROPIC_API_KEY": "sk-test"}
            ),
            patch.dict(
                sys.modules, {"anthropic": mock_anthropic}
            ),
        ):
            answer = ask_followup(
                ctx, "How do I brake?", report
            )

        assert answer == "Brake later into T5."
        # assistant context + user + assistant
        assert len(ctx.messages) == 3
        assert ctx.messages[0]["role"] == "assistant"
        assert ctx.messages[1]["role"] == "user"
        assert ctx.messages[2]["role"] == "assistant"
