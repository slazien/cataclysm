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
    _format_all_laps_corners,
    _format_gains_for_prompt,
    _format_lap_summaries,
    _parse_coaching_response,
    ask_followup,
    generate_coaching_report,
)
from cataclysm.corners import Corner
from cataclysm.engine import LapSummary
from cataclysm.gains import (
    CompositeGainResult,
    ConsistencyGainResult,
    GainEstimate,
    SegmentDefinition,
    SegmentGain,
    TheoreticalBestResult,
)


@pytest.fixture
def sample_summaries() -> list[LapSummary]:
    return [
        LapSummary(
            lap_number=1,
            lap_time_s=92.5,
            lap_distance_m=3800.0,
            max_speed_mps=45.0,
        ),
        LapSummary(
            lap_number=2,
            lap_time_s=94.2,
            lap_distance_m=3810.0,
            max_speed_mps=44.0,
        ),
        LapSummary(
            lap_number=3,
            lap_time_s=93.1,
            lap_distance_m=3805.0,
            max_speed_mps=44.5,
        ),
    ]


@pytest.fixture
def sample_corners() -> list[Corner]:
    return [
        Corner(
            1,
            200.0,
            350.0,
            280.0,
            22.0,
            150.0,
            -0.8,
            370.0,
            "mid",
        ),
        Corner(
            2,
            800.0,
            950.0,
            870.0,
            18.0,
            750.0,
            -1.0,
            970.0,
            "late",
        ),
    ]


@pytest.fixture
def sample_all_lap_corners(
    sample_corners: list[Corner],
) -> dict[int, list[Corner]]:
    """Corner data for 3 laps — lap 1 is best, laps 2-3 vary slightly."""
    return {
        1: sample_corners,
        2: [
            Corner(1, 200.0, 350.0, 285.0, 21.0, 148.0, -0.75, 375.0, "mid"),
            Corner(2, 800.0, 950.0, 875.0, 17.5, 745.0, -0.95, 975.0, "late"),
        ],
        3: [
            Corner(1, 200.0, 350.0, 282.0, 21.5, 152.0, -0.82, 368.0, "mid"),
            Corner(2, 800.0, 950.0, 868.0, 17.0, 755.0, -1.05, 965.0, "mid"),
        ],
    }


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
    def test_includes_all_laps(self, sample_summaries: list[LapSummary]) -> None:
        text = _format_lap_summaries(sample_summaries)
        assert "L1" in text
        assert "L2" in text
        assert "L3" in text

    def test_includes_time(self, sample_summaries: list[LapSummary]) -> None:
        text = _format_lap_summaries(sample_summaries)
        assert "1:32" in text  # 92.5s = 1:32.50

    def test_includes_speed_in_mph(self, sample_summaries: list[LapSummary]) -> None:
        text = _format_lap_summaries(sample_summaries)
        # 45 m/s = ~100.7 mph
        assert "100" in text


class TestFormatAllLapsCorners:
    def test_includes_all_laps(
        self,
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        text = _format_all_laps_corners(sample_all_lap_corners, best_lap=1)
        assert "L1" in text
        assert "L2" in text
        assert "L3" in text

    def test_marks_best_lap(
        self,
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        text = _format_all_laps_corners(sample_all_lap_corners, best_lap=1)
        assert "L1 *" in text
        # Other laps should NOT be marked
        assert "L2 *" not in text

    def test_includes_corner_numbers(
        self,
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        text = _format_all_laps_corners(sample_all_lap_corners, best_lap=1)
        assert "T1" in text
        assert "T2" in text

    def test_includes_speed_in_mph(
        self,
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        text = _format_all_laps_corners(sample_all_lap_corners, best_lap=1)
        # 22 m/s = ~49.2 mph
        assert "49" in text


class TestParseCoachingResponse:
    def test_parses_valid_json(self) -> None:
        data = {
            "summary": "Good session.",
            "priority_corners": [
                {"corner": 2, "time_cost_s": 0.3, "issue": "late", "tip": "brake earlier"},
            ],
            "corner_grades": [
                {
                    "corner": 1,
                    "braking": "B",
                    "trail_braking": "C",
                    "min_speed": "A",
                    "throttle": "B",
                    "notes": "ok",
                },
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
        inner = json.dumps(
            {
                "summary": "Test",
                "priority_corners": [],
                "corner_grades": [],
                "patterns": [],
            }
        )
        response = f"```json\n{inner}\n```"
        report = _parse_coaching_response(response)
        assert report.summary == "Test"

    def test_handles_invalid_json(self) -> None:
        report = _parse_coaching_response("not json at all")
        assert "Could not parse" in report.summary
        assert report.priority_corners == []

    def test_handles_partial_json(self) -> None:
        response = json.dumps(
            {
                "summary": "Partial",
                "patterns": ["one"],
            }
        )
        report = _parse_coaching_response(response)
        assert report.summary == "Partial"
        assert report.corner_grades == []


class TestBuildCoachingPrompt:
    def test_includes_track_name(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Barber",
        )
        assert "Barber" in prompt

    def test_includes_json_structure(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test",
        )
        assert "priority_corners" in prompt
        assert "corner_grades" in prompt

    def test_includes_all_laps_data(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test",
        )
        assert "All Laps" in prompt
        assert "L1" in prompt
        assert "L2" in prompt
        assert "L3" in prompt

    def test_role_text_not_in_user_prompt(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test",
        )
        assert "You are an expert motorsport driving coach" not in prompt


class TestGenerateCoachingReport:
    def test_no_api_key_returns_message(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        with patch.dict("os.environ", {}, clear=True):
            report = generate_coaching_report(
                sample_summaries,
                sample_all_lap_corners,
                "Test",
            )
        assert "ANTHROPIC_API_KEY" in report.summary

    def test_calls_api_with_key(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        mock_anthropic = _make_mock_anthropic(
            json.dumps(
                {
                    "summary": "AI says hi",
                    "priority_corners": [],
                    "corner_grades": [],
                    "patterns": [],
                }
            )
        )

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_anthropic}),
        ):
            report = generate_coaching_report(
                sample_summaries,
                sample_all_lap_corners,
                "Test",
            )
        assert report.summary == "AI says hi"
        call_kwargs = mock_anthropic.Anthropic.return_value.messages.create.call_args
        assert "system" in call_kwargs.kwargs
        assert "traction circle" in call_kwargs.kwargs["system"].lower()


class TestAskFollowup:
    def test_no_api_key(self) -> None:
        ctx = CoachingContext()
        report = CoachingReport("x", [], [], [])
        with patch.dict("os.environ", {}, clear=True):
            answer = ask_followup(ctx, "How do I brake?", report)
        assert "ANTHROPIC_API_KEY" in answer

    def test_maintains_context(self) -> None:
        mock_anthropic = _make_mock_anthropic("Brake later into T5.")

        ctx = CoachingContext()
        report = CoachingReport(
            "summary",
            [],
            [],
            [],
            raw_response="report text",
        )

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_anthropic}),
        ):
            answer = ask_followup(ctx, "How do I brake?", report)

        assert answer == "Brake later into T5."
        # assistant context + user + assistant
        assert len(ctx.messages) == 3
        assert ctx.messages[0]["role"] == "assistant"
        assert ctx.messages[1]["role"] == "user"
        assert ctx.messages[2]["role"] == "assistant"
        call_kwargs = mock_anthropic.Anthropic.return_value.messages.create.call_args
        assert "system" in call_kwargs.kwargs
        assert "traction circle" in call_kwargs.kwargs["system"].lower()


def _make_seg(name: str, entry: float, exit_m: float, *, is_corner: bool) -> SegmentDefinition:
    return SegmentDefinition(
        name=name, entry_distance_m=entry, exit_distance_m=exit_m, is_corner=is_corner
    )


def _make_sg(
    seg: SegmentDefinition,
    best_time: float,
    avg_time: float,
    gain: float,
) -> SegmentGain:
    return SegmentGain(
        segment=seg,
        best_time_s=best_time,
        avg_time_s=avg_time,
        gain_s=gain,
        best_lap=1,
        lap_times_s={1: best_time, 2: avg_time},
    )


@pytest.fixture
def sample_gain_estimate() -> GainEstimate:
    t1 = _make_seg("T1", 200.0, 350.0, is_corner=True)
    t2 = _make_seg("T2", 800.0, 950.0, is_corner=True)
    s1 = _make_seg("S1", 350.0, 800.0, is_corner=False)

    cons_segments = [
        _make_sg(t1, 3.0, 3.4, 0.40),
        _make_sg(s1, 5.0, 5.1, 0.10),
        _make_sg(t2, 4.0, 4.6, 0.60),
    ]
    comp_segments = [
        _make_sg(t1, 3.0, 3.4, 0.15),
        _make_sg(s1, 5.0, 5.1, 0.05),
        _make_sg(t2, 4.0, 4.6, 0.25),
    ]

    return GainEstimate(
        consistency=ConsistencyGainResult(
            segment_gains=cons_segments,
            total_gain_s=1.10,
            avg_lap_time_s=94.0,
            best_lap_time_s=92.5,
        ),
        composite=CompositeGainResult(
            segment_gains=comp_segments,
            composite_time_s=92.0,
            best_lap_time_s=92.5,
            gain_s=0.45,
        ),
        theoretical=TheoreticalBestResult(
            sector_size_m=10.0,
            n_sectors=38,
            theoretical_time_s=91.7,
            best_lap_time_s=92.5,
            gain_s=0.30,
        ),
        clean_lap_numbers=[1, 2, 3],
        best_lap_number=1,
    )


class TestFormatGainsForPrompt:
    def test_includes_gain_estimation_header(self, sample_gain_estimate: GainEstimate) -> None:
        text = _format_gains_for_prompt(sample_gain_estimate)
        assert "Gain Estimation" in text

    def test_includes_consistency_gain(self, sample_gain_estimate: GainEstimate) -> None:
        text = _format_gains_for_prompt(sample_gain_estimate)
        assert "1.10" in text

    def test_includes_per_corner_gains(self, sample_gain_estimate: GainEstimate) -> None:
        text = _format_gains_for_prompt(sample_gain_estimate)
        assert "T1" in text
        assert "T2" in text

    def test_excludes_straights(self, sample_gain_estimate: GainEstimate) -> None:
        text = _format_gains_for_prompt(sample_gain_estimate)
        # S1 should not appear in the per-corner list (it's a straight)
        lines = text.split("\n")
        corner_lines = [ln for ln in lines if ln.startswith("- T") or ln.startswith("- S")]
        corner_names = [ln.split(":")[0].strip("- ") for ln in corner_lines]
        assert "S1" not in corner_names


class TestBuildCoachingPromptWithGains:
    def test_includes_gains_section(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
        sample_gain_estimate: GainEstimate,
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test",
            gains=sample_gain_estimate,
        )
        assert "Gain Estimation" in prompt
        assert "Consistency" in prompt

    def test_includes_gains_instruction(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
        sample_gain_estimate: GainEstimate,
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test",
            gains=sample_gain_estimate,
        )
        assert "Reference these computed gains" in prompt

    def test_no_gains_backward_compatible(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test",
        )
        assert "Gain Estimation" not in prompt


class TestGenerateCoachingReportWithGains:
    def test_passes_gains_to_prompt(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
        sample_gain_estimate: GainEstimate,
    ) -> None:
        mock_anthropic = _make_mock_anthropic(
            json.dumps(
                {
                    "summary": "Good with gains",
                    "priority_corners": [],
                    "corner_grades": [],
                    "patterns": [],
                }
            )
        )

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_anthropic}),
        ):
            report = generate_coaching_report(
                sample_summaries,
                sample_all_lap_corners,
                "Test",
                gains=sample_gain_estimate,
            )

        assert report.summary == "Good with gains"
        # Verify the prompt sent to the API includes gains data
        call_kwargs = mock_anthropic.Anthropic.return_value.messages.create.call_args
        prompt_text = call_kwargs.kwargs["messages"][0]["content"]
        assert "Gain Estimation" in prompt_text
