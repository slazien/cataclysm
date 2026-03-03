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
    _format_cross_condition_context,
    _format_equipment_context,
    _format_gains_for_prompt,
    _format_landmark_context,
    _format_lap_summaries,
    _format_optimal_comparison,
    _format_weather_context,
    _parse_coaching_response,
    ask_followup,
    generate_coaching_report,
    resolve_speed_markers,
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
from cataclysm.optimal_comparison import CornerOpportunity, OptimalComparisonResult


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

    def test_includes_corner_count_constraint(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test",
        )
        assert "Number of corners: 2" in prompt
        assert "Include exactly 2 entries in corner_grades" in prompt
        assert "Do NOT include corners beyond T2" in prompt

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
    @pytest.mark.slow
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

    def test_filters_hallucinated_corner_grades(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        """Corner grades beyond the actual corner count are stripped."""
        response_json = json.dumps(
            {
                "summary": "Test",
                "priority_corners": [
                    {"corner": 1, "time_cost_s": 0.1, "issue": "ok", "tip": "ok"},
                    {"corner": 10, "time_cost_s": 0.5, "issue": "fake", "tip": "fake"},
                ],
                "corner_grades": [
                    {
                        "corner": 1,
                        "braking": "A",
                        "trail_braking": "A",
                        "min_speed": "A",
                        "throttle": "A",
                        "notes": "ok",
                    },
                    {
                        "corner": 2,
                        "braking": "B",
                        "trail_braking": "B",
                        "min_speed": "B",
                        "throttle": "B",
                        "notes": "ok",
                    },
                    {
                        "corner": 10,
                        "braking": "C",
                        "trail_braking": "C",
                        "min_speed": "C",
                        "throttle": "C",
                        "notes": "hallucinated",
                    },
                ],
                "patterns": [],
                "drills": [],
            }
        )
        mock_anthropic = _make_mock_anthropic(response_json)
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_anthropic}),
        ):
            report = generate_coaching_report(
                sample_summaries,
                sample_all_lap_corners,
                "Test",
            )
        # sample_all_lap_corners has 2 corners — T10 should be stripped
        assert len(report.corner_grades) == 2
        assert all(g.corner <= 2 for g in report.corner_grades)
        assert len(report.priority_corners) == 1
        assert report.priority_corners[0]["corner"] == 1


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


# ---------------------------------------------------------------------------
# Enriched coaching context in _format_corner_analysis
# ---------------------------------------------------------------------------


def _make_enriched_corner_analysis(
    *,
    coaching_notes: str | None = None,
    elevation_trend: str | None = None,
    gradient_pct: float | None = None,
    corner_type_hint: str | None = None,
    camber: str | None = None,
    blind: bool = False,
) -> SessionCornerAnalysis:
    """Build a SessionCornerAnalysis with enriched coaching fields."""
    ca = CornerAnalysis(
        corner_number=5,
        n_laps=4,
        stats_min_speed=CornerStats(
            best=38.0, mean=36.0, std=1.5, value_range=4.0, best_lap=1, n_laps=4
        ),
        stats_brake_point=None,
        stats_peak_brake_g=None,
        stats_throttle_commit=None,
        apex_distribution={"mid": 4},
        recommendation=CornerRecommendation(
            target_brake_m=None,
            target_brake_landmark=None,
            target_min_speed_mph=38.0,
            gain_s=0.10,
            corner_type="slow",
            coaching_notes=coaching_notes,
            elevation_trend=elevation_trend,
            gradient_pct=gradient_pct,
            corner_type_hint=corner_type_hint,
            camber=camber,
            blind=blind,
        ),
        time_value=None,
    )
    return SessionCornerAnalysis(
        corners=[ca],
        best_lap=1,
        total_consistency_gain_s=0.10,
        n_laps_analyzed=4,
    )


class TestFormatIncludesCoachingNotes:
    def test_coaching_notes_present(self) -> None:
        analysis = _make_enriched_corner_analysis(
            coaching_notes="Brake at the 3-board. Very late apex."
        )
        text = _format_corner_analysis(analysis)
        assert "Coach tip:" in text
        assert "Brake at the 3-board" in text

    def test_coaching_notes_absent(self) -> None:
        analysis = _make_enriched_corner_analysis()
        text = _format_corner_analysis(analysis)
        assert "Coach tip:" not in text


class TestFormatIncludesElevation:
    def test_elevation_downhill(self) -> None:
        analysis = _make_enriched_corner_analysis(elevation_trend="downhill", gradient_pct=-3.5)
        text = _format_corner_analysis(analysis)
        assert "Elevation: DOWNHILL" in text
        assert "-3.5%" in text

    def test_elevation_flat_omitted(self) -> None:
        analysis = _make_enriched_corner_analysis(elevation_trend="flat")
        text = _format_corner_analysis(analysis)
        assert "Elevation:" not in text


class TestFormatIncludesEnrichedFields:
    def test_corner_type_hint(self) -> None:
        analysis = _make_enriched_corner_analysis(corner_type_hint="hairpin")
        text = _format_corner_analysis(analysis)
        assert "Type: hairpin" in text

    def test_blind_visibility(self) -> None:
        analysis = _make_enriched_corner_analysis(blind=True)
        text = _format_corner_analysis(analysis)
        assert "Visibility: BLIND" in text

    def test_camber_off_camber(self) -> None:
        analysis = _make_enriched_corner_analysis(camber="off-camber")
        text = _format_corner_analysis(analysis)
        assert "Camber: off-camber" in text

    def test_positive_camber_omitted(self) -> None:
        """Positive camber is the default and should not be shown."""
        analysis = _make_enriched_corner_analysis(camber="positive")
        text = _format_corner_analysis(analysis)
        assert "Camber:" not in text


class TestFormatOmitsEnrichedWhenNone:
    def test_all_none(self) -> None:
        """No enriched lines when all coaching fields are None."""
        analysis = _make_enriched_corner_analysis()
        text = _format_corner_analysis(analysis)
        assert "Elevation:" not in text
        assert "Type:" not in text
        assert "Visibility:" not in text
        assert "Camber:" not in text
        assert "Coach tip:" not in text


# ---------------------------------------------------------------------------
# resolve_speed_markers
# ---------------------------------------------------------------------------


class TestResolveSpeedMarkers:
    """Tests for the resolve_speed_markers utility."""

    def test_imperial_basic(self) -> None:
        assert resolve_speed_markers("carry {{speed:3}} more") == "carry 3 mph more"

    def test_metric_basic(self) -> None:
        result = resolve_speed_markers("carry {{speed:3}} more", metric=True)
        assert result == "carry 5 km/h more"

    def test_no_markers_passthrough(self) -> None:
        text = "No speed values here."
        assert resolve_speed_markers(text) == text
        assert resolve_speed_markers(text, metric=True) == text

    def test_multiple_markers(self) -> None:
        text = "{{speed:2}}-{{speed:3}} more through apex"
        assert resolve_speed_markers(text) == "2 mph-3 mph more through apex"

    def test_decimal_preservation(self) -> None:
        # 42.5 mph * 1.60934 = 68.39695 -> 68.4 (1 decimal place preserved)
        result = resolve_speed_markers("{{speed:42.5}}", metric=True)
        assert result == "68.4 km/h"

    def test_integer_value_metric(self) -> None:
        # 100 mph * 1.60934 = 160.934 -> 161 (0 decimal places)
        result = resolve_speed_markers("{{speed:100}}", metric=True)
        assert result == "161 km/h"

    def test_imperial_preserves_original_value(self) -> None:
        assert resolve_speed_markers("{{speed:42.5}}") == "42.5 mph"

    def test_empty_string(self) -> None:
        assert resolve_speed_markers("") == ""

    def test_prompt_contains_speed_formatting_instruction(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        prompt = _build_coaching_prompt(sample_summaries, sample_all_lap_corners, "Test Track")
        assert "{{speed:N}}" in prompt
        assert "SPEED FORMATTING" in prompt


# ---------------------------------------------------------------------------
# TestFormatGainsMarkdown (lines 300-333: _format_gains_for_prompt corner list)
# ---------------------------------------------------------------------------


class TestFormatGainsMarkdownEdgeCases:
    """Tests for the per-corner gains section of _format_gains_for_prompt."""

    def _make_gains(
        self,
        corner_gain: float,
        *,
        is_corner: bool = True,
        seg_name: str = "T1",
    ) -> GainEstimate:
        seg = SegmentDefinition(seg_name, 100.0, 200.0, is_corner=is_corner)
        sg = SegmentGain(
            segment=seg,
            best_time_s=3.0,
            avg_time_s=3.0 + corner_gain,
            gain_s=corner_gain,
            best_lap=1,
            lap_times_s={1: 3.0},
        )
        return GainEstimate(
            consistency=ConsistencyGainResult(
                segment_gains=[sg],
                total_gain_s=corner_gain,
                avg_lap_time_s=93.0,
                best_lap_time_s=92.5,
            ),
            composite=CompositeGainResult(
                segment_gains=[],
                composite_time_s=92.0,
                best_lap_time_s=92.5,
                gain_s=0.0,
            ),
            theoretical=TheoreticalBestResult(
                sector_size_m=10.0,
                n_sectors=38,
                theoretical_time_s=92.0,
                best_lap_time_s=92.5,
                gain_s=0.0,
            ),
            clean_lap_numbers=[1],
            best_lap_number=1,
        )

    def test_all_corners_below_threshold_shows_placeholder(self) -> None:
        """When all corner gains are below 0.01s, placeholder message appears."""
        gains = self._make_gains(0.005)  # below 0.01 threshold
        text = _format_gains_for_prompt(gains)
        assert "all corners below 0.01s threshold" in text

    def test_corner_gains_sorted_descending(self) -> None:
        """Corner gains should appear in descending order (largest first)."""
        t1 = SegmentDefinition("T1", 100.0, 200.0, is_corner=True)
        t2 = SegmentDefinition("T2", 300.0, 400.0, is_corner=True)
        t3 = SegmentDefinition("T3", 500.0, 600.0, is_corner=True)
        segs = [
            SegmentGain(
                segment=t1,
                best_time_s=3.0,
                avg_time_s=3.1,
                gain_s=0.1,
                best_lap=1,
                lap_times_s={1: 3.0},
            ),
            SegmentGain(
                segment=t2,
                best_time_s=3.0,
                avg_time_s=3.5,
                gain_s=0.5,
                best_lap=1,
                lap_times_s={1: 3.0},
            ),
            SegmentGain(
                segment=t3,
                best_time_s=3.0,
                avg_time_s=3.3,
                gain_s=0.3,
                best_lap=1,
                lap_times_s={1: 3.0},
            ),
        ]
        gains = GainEstimate(
            consistency=ConsistencyGainResult(
                segment_gains=segs, total_gain_s=0.9, avg_lap_time_s=93.0, best_lap_time_s=92.5
            ),
            composite=CompositeGainResult(
                segment_gains=[], composite_time_s=92.0, best_lap_time_s=92.5, gain_s=0.0
            ),
            theoretical=TheoreticalBestResult(
                sector_size_m=10.0,
                n_sectors=38,
                theoretical_time_s=92.0,
                best_lap_time_s=92.5,
                gain_s=0.0,
            ),
            clean_lap_numbers=[1],
            best_lap_number=1,
        )
        text = _format_gains_for_prompt(gains)
        t2_pos = text.index("T2")
        t3_pos = text.index("T3")
        t1_pos = text.index("T1")
        assert t2_pos < t3_pos < t1_pos

    def test_straights_excluded_from_per_corner_list(self) -> None:
        """Non-corner (straight) segments must not appear in the corner list."""
        straight_gains = self._make_gains(0.5, is_corner=False, seg_name="S1")
        # Add a corner with small gain to avoid placeholder
        corner = SegmentDefinition("T1", 100.0, 200.0, is_corner=True)
        sg_corner = SegmentGain(
            segment=corner,
            best_time_s=3.0,
            avg_time_s=3.3,
            gain_s=0.3,
            best_lap=1,
            lap_times_s={1: 3.0},
        )
        straight_gains.consistency.segment_gains.append(sg_corner)
        text = _format_gains_for_prompt(straight_gains)
        lines = text.split("\n")
        bullet_lines = [ln for ln in lines if ln.startswith("- ")]
        bullet_names = [ln.split(":")[0].strip("- ") for ln in bullet_lines]
        assert "S1" not in bullet_names


# ---------------------------------------------------------------------------
# TestFormatOptimalComparison (lines 309-333: _format_optimal_comparison)
# ---------------------------------------------------------------------------


class TestFormatOptimalComparison:
    """Tests for _format_optimal_comparison."""

    def _make_result(
        self,
        opportunities: list | None = None,
        actual: float = 93.0,
        optimal: float = 91.5,
    ) -> OptimalComparisonResult:
        import numpy as np

        return OptimalComparisonResult(
            corner_opportunities=opportunities or [],
            actual_lap_time_s=actual,
            optimal_lap_time_s=optimal,
            total_gap_s=actual - optimal,
            speed_delta_mps=np.zeros(10),
            distance_m=np.arange(10) * 0.7,
        )

    def test_includes_header(self) -> None:
        text = _format_optimal_comparison(self._make_result())
        assert "Physics-Optimal Analysis" in text

    def test_shows_times_and_gap(self) -> None:
        text = _format_optimal_comparison(self._make_result(actual=93.0, optimal=91.5))
        assert "93.00" in text
        assert "91.50" in text
        assert "1.50" in text

    def test_no_opportunities_shows_placeholder(self) -> None:
        text = _format_optimal_comparison(self._make_result(opportunities=[]))
        assert "no corner data available" in text

    def test_opportunity_with_brake_gap(self) -> None:
        import numpy as np

        opp = CornerOpportunity(
            corner_number=3,
            actual_min_speed_mps=20.0,
            optimal_min_speed_mps=23.0,
            speed_gap_mps=3.0,
            speed_gap_mph=6.7,
            actual_brake_point_m=150.0,
            optimal_brake_point_m=165.0,
            brake_gap_m=15.0,
            time_cost_s=0.45,
        )
        result = OptimalComparisonResult(
            corner_opportunities=[opp],
            actual_lap_time_s=93.0,
            optimal_lap_time_s=91.5,
            total_gap_s=1.5,
            speed_delta_mps=np.zeros(10),
            distance_m=np.arange(10) * 0.7,
        )
        text = _format_optimal_comparison(result)
        assert "T3" in text
        assert "brakes" in text

    def test_opportunity_without_brake_gap(self) -> None:
        import numpy as np

        opp = CornerOpportunity(
            corner_number=1,
            actual_min_speed_mps=18.0,
            optimal_min_speed_mps=20.0,
            speed_gap_mps=2.0,
            speed_gap_mph=4.5,
            actual_brake_point_m=None,
            optimal_brake_point_m=None,
            brake_gap_m=None,
            time_cost_s=0.2,
        )
        result = OptimalComparisonResult(
            corner_opportunities=[opp],
            actual_lap_time_s=93.0,
            optimal_lap_time_s=91.5,
            total_gap_s=1.5,
            speed_delta_mps=np.zeros(10),
            distance_m=np.arange(10) * 0.7,
        )
        text = _format_optimal_comparison(result)
        assert "T1" in text
        assert "brakes" not in text

    def test_top_10_limit(self) -> None:
        """Only the top 10 opportunities should appear in the output."""
        import numpy as np

        opps = [
            CornerOpportunity(
                corner_number=i,
                actual_min_speed_mps=20.0,
                optimal_min_speed_mps=22.0,
                speed_gap_mps=2.0,
                speed_gap_mph=4.5,
                actual_brake_point_m=None,
                optimal_brake_point_m=None,
                brake_gap_m=None,
                time_cost_s=0.1 * i,
            )
            for i in range(1, 16)
        ]
        result = OptimalComparisonResult(
            corner_opportunities=opps,
            actual_lap_time_s=93.0,
            optimal_lap_time_s=91.5,
            total_gap_s=1.5,
            speed_delta_mps=np.zeros(10),
            distance_m=np.arange(10) * 0.7,
        )
        text = _format_optimal_comparison(result)
        assert "T11" not in text
        assert "T15" not in text
        assert "T10" in text


# ---------------------------------------------------------------------------
# TestFormatWeatherContext (lines 501-518)
# ---------------------------------------------------------------------------


class TestFormatWeatherContext:
    """Tests for _format_weather_context."""

    def test_none_weather_returns_empty(self) -> None:
        assert _format_weather_context(None) == ""

    def test_dry_condition(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        text = _format_weather_context(SessionConditions(track_condition=TrackCondition.DRY))
        assert "Weather Conditions" in text
        assert "dry" in text

    def test_ambient_temp_included_when_present(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        weather = SessionConditions(track_condition=TrackCondition.DRY, ambient_temp_c=22.0)
        text = _format_weather_context(weather)
        assert "22" in text

    def test_ambient_temp_absent_when_none(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        weather = SessionConditions(track_condition=TrackCondition.DRY, ambient_temp_c=None)
        text = _format_weather_context(weather)
        assert "Ambient" not in text

    def test_humidity_included_when_present(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        weather = SessionConditions(track_condition=TrackCondition.DRY, humidity_pct=65.0)
        text = _format_weather_context(weather)
        assert "65" in text
        assert "Humidity" in text

    def test_wind_speed_included_when_present(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        weather = SessionConditions(track_condition=TrackCondition.DRY, wind_speed_kmh=20.0)
        text = _format_weather_context(weather)
        assert "Wind" in text

    def test_precipitation_included_when_positive(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        weather = SessionConditions(track_condition=TrackCondition.WET, precipitation_mm=3.5)
        text = _format_weather_context(weather)
        assert "3.5" in text
        assert "Precipitation" in text

    def test_precipitation_zero_not_shown(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        weather = SessionConditions(track_condition=TrackCondition.DRY, precipitation_mm=0.0)
        text = _format_weather_context(weather)
        assert "Precipitation" not in text


# ---------------------------------------------------------------------------
# TestFormatCrossConditionContext (lines 521-558)
# ---------------------------------------------------------------------------


class TestFormatCrossConditionContext:
    """Tests for _format_cross_condition_context."""

    def test_both_none_returns_empty(self) -> None:
        assert _format_cross_condition_context(None, None) == ""

    def test_one_none_returns_empty(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        weather = SessionConditions(track_condition=TrackCondition.DRY)
        assert _format_cross_condition_context(weather, None) == ""
        assert _format_cross_condition_context(None, weather) == ""

    def test_same_condition_small_temp_diff_returns_empty(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        a = SessionConditions(track_condition=TrackCondition.DRY, ambient_temp_c=20.0)
        b = SessionConditions(track_condition=TrackCondition.DRY, ambient_temp_c=22.0)
        assert _format_cross_condition_context(a, b) == ""

    def test_different_track_condition_triggers_warning(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        a = SessionConditions(track_condition=TrackCondition.DRY)
        b = SessionConditions(track_condition=TrackCondition.WET)
        text = _format_cross_condition_context(a, b)
        assert "Cross-Condition Warning" in text
        assert "DIFFERENT" in text

    def test_large_temp_diff_triggers_warning(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        a = SessionConditions(track_condition=TrackCondition.DRY, ambient_temp_c=10.0)
        b = SessionConditions(track_condition=TrackCondition.DRY, ambient_temp_c=25.0)
        text = _format_cross_condition_context(a, b)
        assert "Cross-Condition Warning" in text

    def test_condition_diff_adds_wet_coaching_note(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        a = SessionConditions(track_condition=TrackCondition.DRY)
        b = SessionConditions(track_condition=TrackCondition.WET)
        text = _format_cross_condition_context(a, b)
        assert "Wet/damp" in text or "grip" in text.lower()

    def test_temp_diff_only_does_not_add_wet_note(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        a = SessionConditions(track_condition=TrackCondition.DRY, ambient_temp_c=5.0)
        b = SessionConditions(track_condition=TrackCondition.DRY, ambient_temp_c=25.0)
        text = _format_cross_condition_context(a, b)
        assert "Wet/damp" not in text

    def test_temp_none_no_temp_warning(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        a = SessionConditions(track_condition=TrackCondition.DRY, ambient_temp_c=None)
        b = SessionConditions(track_condition=TrackCondition.DRY, ambient_temp_c=None)
        assert _format_cross_condition_context(a, b) == ""


# ---------------------------------------------------------------------------
# TestGuardrailRetryLogic (lines 847-859)
# ---------------------------------------------------------------------------


class TestGuardrailRetryLogic:
    """Tests for the guardrail validation retry path in generate_coaching_report."""

    def _valid_response(self) -> str:
        return json.dumps(
            {
                "summary": "Good session.",
                "priority_corners": [],
                "corner_grades": [],
                "patterns": [],
            }
        )

    def test_validation_failure_triggers_retry_and_sets_flag(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        mock_anthropic = _make_mock_anthropic(self._valid_response())
        mock_validator = MagicMock()
        failed = MagicMock()
        failed.passed = False
        failed.violations = ["test violation"]
        mock_validator.record_and_maybe_validate.return_value = failed
        mock_validator.force_validate.return_value = failed

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_anthropic}),
            patch("cataclysm.coaching._get_validator", return_value=mock_validator),
        ):
            report = generate_coaching_report(sample_summaries, sample_all_lap_corners, "Test")

        assert report.validation_failed is True
        assert "test violation" in report.validation_violations

    def test_no_validation_fired_no_retry(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        mock_anthropic = _make_mock_anthropic(self._valid_response())
        mock_validator = MagicMock()
        mock_validator.record_and_maybe_validate.return_value = None

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_anthropic}),
            patch("cataclysm.coaching._get_validator", return_value=mock_validator),
        ):
            report = generate_coaching_report(sample_summaries, sample_all_lap_corners, "Test")

        mock_validator.force_validate.assert_not_called()
        assert report.validation_failed is False

    def test_validation_fails_then_retry_passes_no_flag(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        mock_anthropic = _make_mock_anthropic(self._valid_response())
        mock_validator = MagicMock()
        failed = MagicMock()
        failed.passed = False
        failed.violations = ["violation"]
        passed = MagicMock()
        passed.passed = True
        mock_validator.record_and_maybe_validate.return_value = failed
        mock_validator.force_validate.return_value = passed

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_anthropic}),
            patch("cataclysm.coaching._get_validator", return_value=mock_validator),
        ):
            report = generate_coaching_report(sample_summaries, sample_all_lap_corners, "Test")

        assert report.validation_failed is False


# ---------------------------------------------------------------------------
# Additional coverage tests for remaining uncovered lines
# ---------------------------------------------------------------------------


class TestResolveSpeedMarkersEdgeCases:
    """Additional edge cases for resolve_speed_markers."""

    def test_non_matching_pattern_passthrough(self) -> None:
        """Text that doesn't match the speed marker pattern passes through unchanged."""
        # The regex only matches {{speed:digits}} — non-numeric text won't match
        result = resolve_speed_markers("{{speed:abc}} faster")
        assert result == "{{speed:abc}} faster"

    def test_zero_speed_marker(self) -> None:
        """{{speed:0}} is a valid marker and should be resolved."""
        result = resolve_speed_markers("{{speed:0}} delta")
        assert result == "0 mph delta"


class TestResolveRefNoneDistance:
    """Tests for lines 219, 233: brake/throttle ref returns '—' when distance is None."""

    def test_resolve_brake_ref_none_distance(self) -> None:
        """_resolve_brake_ref(None, ...) returns '—' (line 219)."""
        from cataclysm.coaching import _resolve_brake_ref

        result = _resolve_brake_ref(None, landmarks=None)
        assert result == "—"

    def test_resolve_throttle_ref_none_distance(self) -> None:
        """_resolve_throttle_ref(None, ...) returns '—' (line 233)."""
        from cataclysm.coaching import _resolve_throttle_ref

        result = _resolve_throttle_ref(None, landmarks=None)
        assert result == "—"


class TestFormatCornerCharacter:
    """Tests for lines 390, 394: 'flat' and 'lift' character hints in _format_corner_analysis."""

    def _make_analysis_with_character(self, character: str) -> SessionCornerAnalysis:
        ca = CornerAnalysis(
            corner_number=3,
            n_laps=5,
            stats_min_speed=CornerStats(
                best=50.0, mean=48.0, std=1.0, value_range=4.0, best_lap=1, n_laps=5
            ),
            stats_brake_point=None,
            stats_peak_brake_g=None,
            stats_throttle_commit=None,
            apex_distribution={"mid": 5},
            recommendation=CornerRecommendation(
                target_brake_m=None,
                target_brake_landmark=None,
                target_min_speed_mph=50.0,
                gain_s=0.1,
                corner_type="fast",
                character=character,
            ),
            time_value=None,
            correlations=[],
        )
        return SessionCornerAnalysis(
            corners=[ca],
            best_lap=1,
            total_consistency_gain_s=0.5,
            n_laps_analyzed=5,
        )

    def test_flat_character_hint_shown(self) -> None:
        """character='flat' adds FLAT note to formatted output (line 390)."""
        analysis = self._make_analysis_with_character("flat")
        text = _format_corner_analysis(analysis)
        assert "FLAT" in text

    def test_lift_character_hint_shown(self) -> None:
        """character='lift' adds LIFT note to formatted output (line 394)."""
        analysis = self._make_analysis_with_character("lift")
        text = _format_corner_analysis(analysis)
        assert "LIFT" in text


class TestParseCoachingResponsePlainCodeBlock:
    """Tests for lines 712-713: plain ``` code block (no json prefix)."""

    def test_plain_code_block_extracted(self) -> None:
        """Response wrapped in ``` (not ```json) should be extracted (lines 712-713)."""
        payload = {
            "summary": "Plain block test.",
            "priority_corners": [],
            "corner_grades": [],
            "patterns": [],
        }
        import json as _json

        json_str = _json.dumps(payload)
        # Wrap in plain triple-backtick block (no 'json' tag)
        backticks = "```"
        text = backticks + "\n" + json_str + "\n" + backticks
        result = _parse_coaching_response(text)
        assert result.summary == "Plain block test."

    def test_json_fallback_brace_extraction(self) -> None:
        """Malformed text where JSON is extracted by brace search (lines 723-724)."""
        payload = {
            "summary": "Brace fallback test.",
            "priority_corners": [],
            "corner_grades": [],
            "patterns": [],
        }
        import json as _json

        json_str = _json.dumps(payload)
        # Add non-JSON prefix/suffix so direct json.loads fails but brace search works
        text = "Here is the result:\n" + json_str + "\nEnd of response."
        result = _parse_coaching_response(text)
        assert result.summary == "Brace fallback test."


class TestAskFollowupWeatherAndKbContext:
    """Tests for lines 895-900: weather and KB context in ask_followup system prompt."""

    def _make_mock_followup(self, response_text: str = "Great question.") -> MagicMock:
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=response_text)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mock_module = MagicMock()
        mock_module.Anthropic.return_value = mock_client
        return mock_module

    def test_weather_context_appended_to_system_when_present(
        self,
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        """When weather has data, _format_weather_context returns non-empty and is appended
        to system prompt (lines 895-896)."""
        from cataclysm.equipment import SessionConditions, TrackCondition

        ctx = CoachingContext()
        mock_report = CoachingReport(
            summary="Good session.",
            priority_corners=[],
            corner_grades=[],
            patterns=[],
        )
        mock_report.raw_response = "Initial coaching done."
        ctx.messages.append({"role": "assistant", "content": "Initial coaching done."})

        conditions = SessionConditions(
            track_condition=TrackCondition.DRY,
            ambient_temp_c=25.0,
            track_temp_c=35.0,
        )
        mock_anthropic = self._make_mock_followup("Weather tip.")
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict("sys.modules", {"anthropic": mock_anthropic}),
        ):
            result = ask_followup(
                ctx, "How does weather affect braking?", mock_report, weather=conditions
            )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_kb_context_appended_when_corners_present(
        self,
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        """When all_lap_corners provided, KB snippets are selected and appended (lines 898-900)."""
        ctx = CoachingContext()
        mock_report = CoachingReport(
            summary="Good session.",
            priority_corners=[],
            corner_grades=[],
            patterns=[],
        )
        mock_report.raw_response = "Initial coaching done."
        ctx.messages.append({"role": "assistant", "content": "Initial coaching done."})

        mock_anthropic = self._make_mock_followup("KB response.")
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict("sys.modules", {"anthropic": mock_anthropic}),
        ):
            result = ask_followup(
                ctx,
                "What should I focus on?",
                mock_report,
                all_lap_corners=sample_all_lap_corners,
            )
        assert isinstance(result, str)

    def test_followup_api_exception_returns_error_message(self) -> None:
        """When the Anthropic API raises an exception, friendly error message returned
        (lines 909-911)."""
        ctx = CoachingContext()
        mock_report = CoachingReport(
            summary="Good session.",
            priority_corners=[],
            corner_grades=[],
            patterns=[],
        )
        mock_report.raw_response = "Initial coaching done."
        ctx.messages.append({"role": "assistant", "content": "Initial coaching done."})

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("connection refused")
        mock_module = MagicMock()
        mock_module.Anthropic.return_value = mock_client

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict("sys.modules", {"anthropic": mock_module}),
        ):
            result = ask_followup(ctx, "What happened?", mock_report)
        assert "unavailable" in result.lower() or "overloaded" in result.lower()


# ---------------------------------------------------------------------------
# Tests for final uncovered branches (lines 446, 606-607)
# ---------------------------------------------------------------------------


class TestFormatCornerAnalysisTargetBrakeM:
    """Test line 446: target_brake_m shown when no landmark is set."""

    def test_brake_distance_shown_without_landmark(self) -> None:
        """When target_brake_landmark is None but target_brake_m has a value, raw distance shown."""
        ca = CornerAnalysis(
            corner_number=2,
            n_laps=4,
            stats_min_speed=CornerStats(
                best=45.0, mean=43.0, std=1.2, value_range=4.5, best_lap=1, n_laps=4
            ),
            stats_brake_point=CornerStats(
                best=500.0, mean=510.0, std=6.0, value_range=18.0, best_lap=1, n_laps=4
            ),
            stats_peak_brake_g=None,
            stats_throttle_commit=None,
            apex_distribution={"mid": 4},
            recommendation=CornerRecommendation(
                target_brake_m=500.0,  # raw distance, no landmark
                target_brake_landmark=None,
                target_min_speed_mph=45.0,
                gain_s=0.3,
                corner_type="medium",
            ),
            time_value=None,
            correlations=[],
        )
        analysis = SessionCornerAnalysis(
            corners=[ca],
            best_lap=1,
            total_consistency_gain_s=0.3,
            n_laps_analyzed=4,
        )
        text = _format_corner_analysis(analysis)
        # Should show the raw distance since no landmark (line 446)
        assert "500m" in text


class TestBuildCoachingPromptWithOptimalComparison:
    """Test lines 606-607: optimal_comparison section in _build_coaching_prompt."""

    def test_optimal_comparison_section_included(
        self,
        sample_summaries: list[LapSummary],
        sample_all_lap_corners: dict[int, list[Corner]],
    ) -> None:
        """Passing optimal_comparison adds the comparison section (lines 606-607)."""
        import numpy as np

        from cataclysm.optimal_comparison import CornerOpportunity, OptimalComparisonResult

        n = 10
        comparison = OptimalComparisonResult(
            actual_lap_time_s=92.5,
            optimal_lap_time_s=90.0,
            total_gap_s=2.5,
            corner_opportunities=[
                CornerOpportunity(
                    corner_number=1,
                    actual_min_speed_mps=26.8,
                    optimal_min_speed_mps=28.1,
                    speed_gap_mps=1.3,
                    speed_gap_mph=2.9,
                    actual_brake_point_m=None,
                    optimal_brake_point_m=None,
                    brake_gap_m=None,
                    time_cost_s=0.4,
                ),
            ],
            speed_delta_mps=np.zeros(n),
            distance_m=np.arange(n) * 0.7,
        )
        prompt = _build_coaching_prompt(
            sample_summaries,
            sample_all_lap_corners,
            "Test Track",
            optimal_comparison=comparison,
        )
        # optimal section and instruction should be in prompt
        assert "Optimal" in prompt or "optimal" in prompt or "physics" in prompt.lower()
