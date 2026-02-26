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
    _format_corner_analysis,
    _format_equipment_context,
    _format_gains_for_prompt,
    _format_landmark_context,
    _format_lap_summaries,
    _parse_coaching_response,
    ask_followup,
    generate_coaching_report,
)
from cataclysm.corner_analysis import (
    CornerAnalysis,
    CornerCorrelation,
    CornerRecommendation,
    CornerStats,
    SessionCornerAnalysis,
    TimeValue,
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
from cataclysm.landmarks import Landmark, LandmarkType


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
        # Use call_args_list[0] to get the coaching call, not the validator's call
        # (the validator may fire after enough outputs, and call_args returns the LAST call)
        call_kwargs = mock_anthropic.Anthropic.return_value.messages.create.call_args_list[0]
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
        call_kwargs = mock_anthropic.Anthropic.return_value.messages.create.call_args_list[0]
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
        # Use call_args_list[0] to get the coaching call, not the validator's call
        call_kwargs = mock_anthropic.Anthropic.return_value.messages.create.call_args_list[0]
        prompt_text = call_kwargs.kwargs["messages"][0]["content"]
        assert "Gain Estimation" in prompt_text


class TestSkillLevelPrompts:
    """Test skill-level prompt customization."""

    def test_novice_prompt_includes_skill_section(self) -> None:
        summaries = [
            LapSummary(lap_number=1, lap_time_s=90.0, lap_distance_m=500.0, max_speed_mps=40.0),
        ]
        corners_map: dict[int, list[Corner]] = {
            1: [
                Corner(
                    number=1,
                    entry_distance_m=100,
                    exit_distance_m=200,
                    apex_distance_m=150,
                    min_speed_mps=20.0,
                    brake_point_m=80.0,
                    peak_brake_g=-0.5,
                    throttle_commit_m=170.0,
                    apex_type="mid",
                ),
            ],
        }
        prompt = _build_coaching_prompt(summaries, corners_map, "Test Track", skill_level="novice")
        assert "Novice" in prompt
        assert "information overload" in prompt.lower() or "smooth inputs" in prompt.lower()

    def test_advanced_prompt_includes_skill_section(self) -> None:
        summaries = [
            LapSummary(lap_number=1, lap_time_s=90.0, lap_distance_m=500.0, max_speed_mps=40.0),
        ]
        corners_map: dict[int, list[Corner]] = {
            1: [
                Corner(
                    number=1,
                    entry_distance_m=100,
                    exit_distance_m=200,
                    apex_distance_m=150,
                    min_speed_mps=20.0,
                    brake_point_m=80.0,
                    peak_brake_g=-0.5,
                    throttle_commit_m=170.0,
                    apex_type="mid",
                ),
            ],
        }
        prompt = _build_coaching_prompt(
            summaries, corners_map, "Test Track", skill_level="advanced"
        )
        assert "Advanced" in prompt
        assert "marginal gains" in prompt.lower() or "micro-optimization" in prompt.lower()

    def test_default_is_intermediate(self) -> None:
        summaries = [
            LapSummary(lap_number=1, lap_time_s=90.0, lap_distance_m=500.0, max_speed_mps=40.0),
        ]
        corners_map: dict[int, list[Corner]] = {
            1: [
                Corner(
                    number=1,
                    entry_distance_m=100,
                    exit_distance_m=200,
                    apex_distance_m=150,
                    min_speed_mps=20.0,
                    brake_point_m=80.0,
                    peak_brake_g=-0.5,
                    throttle_commit_m=170.0,
                    apex_type="mid",
                ),
            ],
        }
        prompt = _build_coaching_prompt(summaries, corners_map, "Test Track")
        assert "Intermediate" in prompt

    def test_unknown_level_falls_back_to_intermediate(self) -> None:
        summaries = [
            LapSummary(lap_number=1, lap_time_s=90.0, lap_distance_m=500.0, max_speed_mps=40.0),
        ]
        corners_map: dict[int, list[Corner]] = {1: []}
        prompt = _build_coaching_prompt(summaries, corners_map, "Test Track", skill_level="bogus")
        assert "Intermediate" in prompt


class TestDrillsInPrompt:
    """Test that drill instructions appear in the prompt."""

    def test_prompt_includes_drills_schema(self) -> None:
        summaries = [
            LapSummary(lap_number=1, lap_time_s=90.0, lap_distance_m=500.0, max_speed_mps=40.0),
        ]
        corners_map: dict[int, list[Corner]] = {1: []}
        prompt = _build_coaching_prompt(summaries, corners_map, "Test Track")
        assert '"drills"' in prompt

    def test_prompt_includes_drill_instruction(self) -> None:
        summaries = [
            LapSummary(lap_number=1, lap_time_s=90.0, lap_distance_m=500.0, max_speed_mps=40.0),
        ]
        corners_map: dict[int, list[Corner]] = {1: []}
        prompt = _build_coaching_prompt(summaries, corners_map, "Test Track")
        assert "practice drill" in prompt.lower()


class TestParseDrills:
    """Test extraction of drills from coaching response."""

    def test_parses_drills_from_json(self) -> None:
        response = json.dumps(
            {
                "summary": "Good session.",
                "priority_corners": [],
                "corner_grades": [],
                "patterns": [],
                "drills": ["Practice trail braking at T5", "Work on throttle at T3"],
            }
        )
        report = _parse_coaching_response(response)
        assert len(report.drills) == 2
        assert "T5" in report.drills[0]

    def test_missing_drills_defaults_to_empty(self) -> None:
        response = json.dumps(
            {
                "summary": "Good session.",
                "priority_corners": [],
                "corner_grades": [],
                "patterns": [],
            }
        )
        report = _parse_coaching_response(response)
        assert report.drills == []


class TestCoachingReportDrillsField:
    """Test CoachingReport dataclass drills field."""

    def test_default_drills_empty(self) -> None:
        report = CoachingReport(
            summary="test",
            priority_corners=[],
            corner_grades=[],
            patterns=[],
        )
        assert report.drills == []

    def test_drills_can_be_set(self) -> None:
        report = CoachingReport(
            summary="test",
            priority_corners=[],
            corner_grades=[],
            patterns=[],
            drills=["drill 1", "drill 2"],
        )
        assert len(report.drills) == 2


# ---------------------------------------------------------------------------
# Landmark integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_landmarks_coaching() -> list[Landmark]:
    return [
        Landmark("T1 200m board", 90.0, LandmarkType.brake_board),
        Landmark("T1 100m board", 140.0, LandmarkType.brake_board),
        Landmark("T2 Armco", 380.0, LandmarkType.barrier),
    ]


class TestFormatLandmarkContext:
    def test_empty_landmarks(
        self,
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        text = _format_landmark_context(sample_all_lap_corners, [])
        assert text == ""

    def test_empty_corners(self, sample_landmarks_coaching: list[Landmark]) -> None:
        text = _format_landmark_context({}, sample_landmarks_coaching)
        assert text == ""

    def test_includes_header(
        self,
        sample_all_lap_corners: dict[int, list[Corner]],
        sample_landmarks_coaching: list[Landmark],
    ) -> None:
        text = _format_landmark_context(
            sample_all_lap_corners,
            sample_landmarks_coaching,
        )
        assert "Visual Landmarks" in text

    def test_includes_corner_references(
        self,
        sample_all_lap_corners: dict[int, list[Corner]],
        sample_landmarks_coaching: list[Landmark],
    ) -> None:
        text = _format_landmark_context(
            sample_all_lap_corners,
            sample_landmarks_coaching,
        )
        # At least one corner should have a reference resolved
        assert "T1:" in text or "T2:" in text


class TestBuildCoachingPromptWithLandmarks:
    def test_landmarks_in_prompt(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
        sample_landmarks_coaching: list[Landmark],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Barber",
            landmarks=sample_landmarks_coaching,
        )
        assert "Visual Landmarks" in prompt
        assert "visual landmarks instead of raw meter distances" in prompt.lower()

    def test_no_landmarks_backward_compatible(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test",
        )
        assert "Visual Landmarks" not in prompt
        assert "visual landmarks instead of raw meter distances" not in prompt.lower()

    def test_none_landmarks_backward_compatible(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test",
            landmarks=None,
        )
        assert "Visual Landmarks" not in prompt


class TestGenerateCoachingReportWithLandmarks:
    def test_passes_landmarks_to_prompt(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
        sample_landmarks_coaching: list[Landmark],
    ) -> None:
        mock_anthropic = _make_mock_anthropic(
            json.dumps(
                {
                    "summary": "Good with landmarks",
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
                "Barber",
                landmarks=sample_landmarks_coaching,
            )

        assert report.summary == "Good with landmarks"
        # call_args_list[0] is the coaching call; later calls may be the validator.
        call_list = mock_anthropic.Anthropic.return_value.messages.create.call_args_list
        coaching_call = call_list[0]
        prompt_text = coaching_call.kwargs["messages"][0]["content"]
        assert "Visual Landmarks" in prompt_text


# ---------------------------------------------------------------------------
# Pre-computed corner analysis integration tests
# ---------------------------------------------------------------------------


def _make_corner_analysis() -> SessionCornerAnalysis:
    """Build a sample SessionCornerAnalysis for testing."""
    from cataclysm.landmarks import Landmark, LandmarkReference, LandmarkType

    brake_landmark = LandmarkReference(
        landmark=Landmark("T5 3 board", 490.0, LandmarkType.brake_board),
        offset_m=-10.0,
    )
    ca = CornerAnalysis(
        corner_number=5,
        n_laps=8,
        stats_min_speed=CornerStats(
            best=38.2, mean=36.1, std=1.8, value_range=5.0, best_lap=3, n_laps=8
        ),
        stats_brake_point=CornerStats(
            best=924.0, mean=935.0, std=8.2, value_range=20.0, best_lap=3, n_laps=8
        ),
        stats_peak_brake_g=CornerStats(
            best=0.92, mean=0.85, std=0.05, value_range=0.12, best_lap=3, n_laps=8
        ),
        stats_throttle_commit=CornerStats(
            best=1120.0, mean=1118.0, std=5.1, value_range=15.0, best_lap=3, n_laps=8
        ),
        apex_distribution={"late": 6, "mid": 2},
        recommendation=CornerRecommendation(
            target_brake_m=924.0,
            target_brake_landmark=brake_landmark,
            target_min_speed_mph=38.2,
            gain_s=0.42,
            corner_type="slow",
        ),
        time_value=TimeValue(
            approach_speed_mph=72.0,
            time_per_meter_ms=31.1,
            brake_variance_time_cost_s=0.255,
        ),
        correlations=[
            CornerCorrelation(
                kpi_x="brake_point",
                kpi_y="min_speed",
                r=-0.87,
                strength="strong",
                n_points=8,
            )
        ],
    )
    return SessionCornerAnalysis(
        corners=[ca],
        best_lap=3,
        total_consistency_gain_s=1.24,
        n_laps_analyzed=8,
    )


class TestFormatCornerAnalysis:
    """Test the _format_corner_analysis() function."""

    def test_includes_header(self) -> None:
        analysis = _make_corner_analysis()
        text = _format_corner_analysis(analysis)
        assert "Pre-Computed Corner Analysis" in text

    def test_includes_best_lap(self) -> None:
        analysis = _make_corner_analysis()
        text = _format_corner_analysis(analysis)
        assert "Best lap: L3" in text

    def test_includes_total_gain(self) -> None:
        analysis = _make_corner_analysis()
        text = _format_corner_analysis(analysis)
        assert "1.24s" in text

    def test_includes_corner_stats(self) -> None:
        analysis = _make_corner_analysis()
        text = _format_corner_analysis(analysis)
        assert "T5" in text
        assert "38.2" in text  # best min speed
        assert "36.1" in text  # mean min speed

    def test_includes_brake_stats(self) -> None:
        analysis = _make_corner_analysis()
        text = _format_corner_analysis(analysis)
        assert "Brake pt:" in text
        assert "924" in text

    def test_includes_landmark(self) -> None:
        analysis = _make_corner_analysis()
        text = _format_corner_analysis(analysis)
        assert "3 board" in text

    def test_includes_correlation(self) -> None:
        analysis = _make_corner_analysis()
        text = _format_corner_analysis(analysis)
        assert "r=-0.87" in text
        assert "strong" in text

    def test_includes_time_value(self) -> None:
        analysis = _make_corner_analysis()
        text = _format_corner_analysis(analysis)
        assert "72 mph" in text
        assert "0.255s" in text

    def test_includes_apex_distribution(self) -> None:
        analysis = _make_corner_analysis()
        text = _format_corner_analysis(analysis)
        assert "6/8 late" in text
        assert "2/8 mid" in text


class TestBuildCoachingPromptWithCornerAnalysis:
    """Test corner_analysis parameter in _build_coaching_prompt."""

    def test_includes_analysis_section(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        analysis = _make_corner_analysis()
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Barber",
            corner_analysis=analysis,
        )
        assert "Pre-Computed Corner Analysis" in prompt
        assert "DO NOT re-derive" in prompt

    def test_includes_instructions(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        analysis = _make_corner_analysis()
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Barber",
            corner_analysis=analysis,
        )
        assert "pre-computed corner analysis" in prompt.lower()
        assert "primary data source" in prompt.lower()

    def test_no_analysis_backward_compatible(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test",
        )
        assert "Pre-Computed Corner Analysis" not in prompt
        assert "DO NOT re-derive" not in prompt

    def test_empty_analysis_backward_compatible(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        empty = SessionCornerAnalysis(
            corners=[], best_lap=1, total_consistency_gain_s=0.0, n_laps_analyzed=0
        )
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test",
            corner_analysis=empty,
        )
        assert "Pre-Computed Corner Analysis" not in prompt


class TestGenerateCoachingReportWithCornerAnalysis:
    """Test that corner_analysis is passed through to the API prompt."""

    def test_passes_analysis_to_prompt(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        mock_anthropic = _make_mock_anthropic(
            json.dumps(
                {
                    "summary": "Good with analysis",
                    "priority_corners": [],
                    "corner_grades": [],
                    "patterns": [],
                }
            )
        )

        analysis = _make_corner_analysis()

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_anthropic}),
        ):
            report = generate_coaching_report(
                sample_summaries,
                sample_all_lap_corners,
                "Barber",
                corner_analysis=analysis,
            )

        assert report.summary == "Good with analysis"
        # Use call_args_list[0] to get the coaching call, not the validator's call
        call_kwargs = mock_anthropic.Anthropic.return_value.messages.create.call_args_list[0]
        prompt_text = call_kwargs.kwargs["messages"][0]["content"]
        assert "Pre-Computed Corner Analysis" in prompt_text
        assert "DO NOT re-derive" in prompt_text


# ---------------------------------------------------------------------------
# Equipment context integration tests
# ---------------------------------------------------------------------------


class TestFormatEquipmentContext:
    """Test the _format_equipment_context() function."""

    def test_format_equipment_context_full(self) -> None:
        """Equipment and conditions format correctly for the coaching prompt."""
        from cataclysm.equipment import (
            BrakeSpec,
            EquipmentProfile,
            MuSource,
            SessionConditions,
            TireCompoundCategory,
            TireSpec,
            TrackCondition,
        )

        tire = TireSpec(
            model="Bridgestone RE-71RS",
            compound_category=TireCompoundCategory.SUPER_200TW,
            size="255/40R17",
            treadwear_rating=200,
            estimated_mu=1.10,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="Track test aggregate",
            pressure_psi=32.0,
        )
        brakes = BrakeSpec(compound="Hawk DTC-60")
        profile = EquipmentProfile(id="p1", name="Track Setup", tires=tire, brakes=brakes)
        conditions = SessionConditions(
            track_condition=TrackCondition.DRY,
            ambient_temp_c=28.0,
            humidity_pct=55.0,
        )

        text = _format_equipment_context(profile, conditions)
        assert "RE-71RS" in text
        assert "super_200tw" in text
        assert "1.10" in text
        assert "curated_table" in text
        assert "32.0 psi" in text
        assert "Hawk DTC-60" in text
        assert "dry" in text
        assert "28" in text
        assert "55" in text

    def test_format_equipment_context_none(self) -> None:
        """None inputs produce empty string."""
        assert _format_equipment_context(None, None) == ""

    def test_format_equipment_context_profile_only(self) -> None:
        """Profile without conditions still formats tire info."""
        from cataclysm.equipment import (
            EquipmentProfile,
            MuSource,
            TireCompoundCategory,
            TireSpec,
        )

        tire = TireSpec(
            model="Hoosier R7",
            compound_category=TireCompoundCategory.R_COMPOUND,
            size="275/35R18",
            treadwear_rating=40,
            estimated_mu=1.35,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="test",
        )
        profile = EquipmentProfile(id="p2", name="Race", tires=tire)
        text = _format_equipment_context(profile, None)
        assert "Hoosier R7" in text
        assert "r_comp" in text
        assert "1.35" in text
        # No pressure set, so "psi" should not appear
        assert "psi" not in text

    def test_format_equipment_context_conditions_only(self) -> None:
        """Conditions without profile still formats weather info."""
        from cataclysm.equipment import SessionConditions, TrackCondition

        conditions = SessionConditions(
            track_condition=TrackCondition.WET,
            ambient_temp_c=15.0,
        )
        text = _format_equipment_context(None, conditions)
        assert "wet" in text
        assert "15" in text
        assert "Tires" not in text

    def test_format_equipment_context_no_brakes(self) -> None:
        """Profile without brakes omits brake line."""
        from cataclysm.equipment import (
            EquipmentProfile,
            MuSource,
            TireCompoundCategory,
            TireSpec,
        )

        tire = TireSpec(
            model="Test Tire",
            compound_category=TireCompoundCategory.STREET,
            size="225/45R17",
            treadwear_rating=400,
            estimated_mu=0.85,
            mu_source=MuSource.FORMULA_ESTIMATE,
            mu_confidence="formula",
        )
        profile = EquipmentProfile(id="p3", name="Street", tires=tire)
        text = _format_equipment_context(profile, None)
        assert "Brakes" not in text


class TestBuildCoachingPromptWithEquipment:
    """Test equipment_profile and conditions in _build_coaching_prompt."""

    def test_includes_equipment_section(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        from cataclysm.equipment import (
            EquipmentProfile,
            MuSource,
            SessionConditions,
            TireCompoundCategory,
            TireSpec,
            TrackCondition,
        )

        tire = TireSpec(
            model="RE-71RS",
            compound_category=TireCompoundCategory.SUPER_200TW,
            size="255/40R17",
            treadwear_rating=200,
            estimated_mu=1.10,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="test",
        )
        profile = EquipmentProfile(id="p1", name="Track", tires=tire)
        conditions = SessionConditions(
            track_condition=TrackCondition.DRY,
            ambient_temp_c=30.0,
        )

        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Barber",
            equipment_profile=profile,
            conditions=conditions,
        )
        assert "Vehicle Equipment & Conditions" in prompt
        assert "RE-71RS" in prompt
        assert "dry" in prompt

    def test_no_equipment_backward_compatible(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test",
        )
        assert "Vehicle Equipment & Conditions" not in prompt


class TestGenerateCoachingReportWithEquipment:
    """Test that equipment is passed through to the API prompt."""

    def test_passes_equipment_to_prompt(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        from cataclysm.equipment import (
            EquipmentProfile,
            MuSource,
            SessionConditions,
            TireCompoundCategory,
            TireSpec,
            TrackCondition,
        )

        mock_anthropic = _make_mock_anthropic(
            json.dumps(
                {
                    "summary": "Good with equipment",
                    "priority_corners": [],
                    "corner_grades": [],
                    "patterns": [],
                }
            )
        )

        tire = TireSpec(
            model="NT01",
            compound_category=TireCompoundCategory.SUPER_200TW,
            size="245/40R17",
            treadwear_rating=200,
            estimated_mu=1.05,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="test",
        )
        profile = EquipmentProfile(id="p1", name="Track", tires=tire)
        conditions = SessionConditions(
            track_condition=TrackCondition.DAMP,
            ambient_temp_c=20.0,
            humidity_pct=80.0,
        )

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_anthropic}),
        ):
            report = generate_coaching_report(
                sample_summaries,
                sample_all_lap_corners,
                "Barber",
                equipment_profile=profile,
                conditions=conditions,
            )

        assert report.summary == "Good with equipment"
        # Use call_args_list[0] to get the coaching call, not the validator's call
        call_kwargs = mock_anthropic.Anthropic.return_value.messages.create.call_args_list[0]
        prompt_text = call_kwargs.kwargs["messages"][0]["content"]
        assert "NT01" in prompt_text
        assert "damp" in prompt_text
        assert "80" in prompt_text
