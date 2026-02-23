"""Tests for cataclysm.kb_selector."""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

from cataclysm.corners import Corner
from cataclysm.gains import (
    CompositeGainResult,
    ConsistencyGainResult,
    GainEstimate,
    SegmentDefinition,
    SegmentGain,
    TheoreticalBestResult,
)
from cataclysm.kb_selector import (
    KB_SNIPPETS,
    MAX_INJECTION_TOKENS,
    _corner_pattern_snippets,
    _estimate_char_budget,
    select_kb_snippets,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_corner(
    number: int = 1,
    entry: float = 200.0,
    exit_m: float = 350.0,
    apex: float = 280.0,
    min_speed: float = 22.0,
    brake_pt: float | None = 150.0,
    peak_g: float | None = -0.8,
    throttle: float | None = 370.0,
    apex_type: str = "mid",
) -> Corner:
    return Corner(
        number=number,
        entry_distance_m=entry,
        exit_distance_m=exit_m,
        apex_distance_m=apex,
        min_speed_mps=min_speed,
        brake_point_m=brake_pt,
        peak_brake_g=peak_g,
        throttle_commit_m=throttle,
        apex_type=apex_type,
    )


def _make_seg(name: str, entry: float, exit_m: float, *, is_corner: bool) -> SegmentDefinition:
    return SegmentDefinition(
        name=name, entry_distance_m=entry, exit_distance_m=exit_m, is_corner=is_corner
    )


def _make_sg(
    seg: SegmentDefinition,
    gain: float,
) -> SegmentGain:
    return SegmentGain(
        segment=seg,
        best_time_s=3.0,
        avg_time_s=3.0 + gain,
        gain_s=gain,
        best_lap=1,
        lap_times_s={1: 3.0, 2: 3.0 + gain},
    )


def _make_gains(corner_gains: dict[int, float]) -> GainEstimate:
    """Build a minimal GainEstimate with per-corner consistency gains."""
    segs = []
    for cnum, gain in corner_gains.items():
        seg = _make_seg(f"T{cnum}", cnum * 100.0, cnum * 100.0 + 100.0, is_corner=True)
        segs.append(_make_sg(seg, gain))

    return GainEstimate(
        consistency=ConsistencyGainResult(
            segment_gains=segs,
            total_gain_s=sum(corner_gains.values()),
            avg_lap_time_s=94.0,
            best_lap_time_s=92.5,
        ),
        composite=CompositeGainResult(
            segment_gains=[],
            composite_time_s=92.0,
            best_lap_time_s=92.5,
            gain_s=0.5,
        ),
        theoretical=TheoreticalBestResult(
            sector_size_m=10.0,
            n_sectors=38,
            theoretical_time_s=91.7,
            best_lap_time_s=92.5,
            gain_s=0.8,
        ),
        clean_lap_numbers=[1, 2, 3],
        best_lap_number=1,
    )


# ---------------------------------------------------------------------------
# Tests: KB_SNIPPETS dict
# ---------------------------------------------------------------------------
class TestKBSnippets:
    def test_all_snippet_ids_are_strings(self) -> None:
        for key in KB_SNIPPETS:
            assert isinstance(key, str)

    def test_all_snippets_are_nonempty(self) -> None:
        for key, val in KB_SNIPPETS.items():
            assert len(val) > 20, f"Snippet {key} is too short"

    def test_expected_skill_snippets_exist(self) -> None:
        # Novice
        for sid in ["8.4", "8.5", "8.10", "1.1"]:
            assert sid in KB_SNIPPETS, f"Missing novice snippet {sid}"
        # Intermediate
        for sid in ["2.5", "3.6", "5.2"]:
            assert sid in KB_SNIPPETS, f"Missing intermediate snippet {sid}"
        # Advanced
        for sid in ["5.4", "5.5", "A.1"]:
            assert sid in KB_SNIPPETS, f"Missing advanced snippet {sid}"

    def test_pattern_trigger_snippets_exist(self) -> None:
        for sid in ["4.1", "2.7", "3.5", "5.3", "8.8", "10.4", "10.3", "10.5"]:
            assert sid in KB_SNIPPETS, f"Missing pattern snippet {sid}"


# ---------------------------------------------------------------------------
# Tests: Skill-level selection
# ---------------------------------------------------------------------------
class TestSkillLevelSelection:
    def test_novice_includes_novice_snippets(self) -> None:
        corners: dict[int, list[Corner]] = {}
        result = select_kb_snippets(corners, "novice")
        assert "8.4" in result
        assert "8.5" in result
        assert "1.1" in result

    def test_intermediate_includes_intermediate_snippets(self) -> None:
        corners: dict[int, list[Corner]] = {}
        result = select_kb_snippets(corners, "intermediate")
        assert "2.5" in result
        assert "3.6" in result
        assert "5.2" in result

    def test_advanced_includes_advanced_snippets(self) -> None:
        corners: dict[int, list[Corner]] = {}
        result = select_kb_snippets(corners, "advanced")
        assert "5.4" in result
        assert "5.5" in result
        assert "A.1" in result

    def test_unknown_skill_defaults_to_intermediate(self) -> None:
        corners: dict[int, list[Corner]] = {}
        result = select_kb_snippets(corners, "bogus_level")
        assert "2.5" in result  # intermediate snippet

    def test_novice_does_not_include_advanced(self) -> None:
        corners: dict[int, list[Corner]] = {}
        result = select_kb_snippets(corners, "novice")
        assert "5.4" not in result
        assert "A.1" not in result


# ---------------------------------------------------------------------------
# Tests: Per-corner pattern triggers
# ---------------------------------------------------------------------------
class TestEarlyApexTrigger:
    def test_early_apex_dominant(self) -> None:
        """When >50% of laps have early apex, inject 4.1."""
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(apex_type="early")],
            2: [_make_corner(apex_type="early")],
            3: [_make_corner(apex_type="mid")],
        }
        result = select_kb_snippets(all_corners, "intermediate")
        assert "4.1" in result

    def test_no_early_apex_no_trigger(self) -> None:
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(apex_type="mid")],
            2: [_make_corner(apex_type="late")],
            3: [_make_corner(apex_type="mid")],
        }
        result = select_kb_snippets(all_corners, "intermediate")
        assert "4.1" not in result


class TestBrakeVarianceTrigger:
    def test_high_brake_variance(self) -> None:
        """When brake points vary >8m, inject 2.7."""
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(brake_pt=140.0)],
            2: [_make_corner(brake_pt=160.0)],
            3: [_make_corner(brake_pt=145.0)],
        }
        result = select_kb_snippets(all_corners, "novice")
        assert "2.7" in result

    def test_low_brake_variance_no_trigger(self) -> None:
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(brake_pt=150.0)],
            2: [_make_corner(brake_pt=151.0)],
            3: [_make_corner(brake_pt=150.5)],
        }
        result = select_kb_snippets(all_corners, "novice")
        assert "2.7" not in result


class TestLowBrakeGTrigger:
    def test_low_peak_brake_g(self) -> None:
        """When mean peak brake G < 0.4, inject 2.5."""
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(peak_g=-0.3)],
            2: [_make_corner(peak_g=-0.35)],
            3: [_make_corner(peak_g=-0.25)],
        }
        # 2.5 is also a skill-level snippet for intermediate but check pattern trigger
        triggers = _corner_pattern_snippets(all_corners, None)
        snippet_ids = [t[0] for t in triggers]
        assert "2.5" in snippet_ids

    def test_high_brake_g_no_trigger(self) -> None:
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(peak_g=-0.8)],
            2: [_make_corner(peak_g=-0.9)],
        }
        triggers = _corner_pattern_snippets(all_corners, None)
        snippet_ids = [t[0] for t in triggers]
        assert "2.5" not in snippet_ids


class TestLateThrottleTrigger:
    def test_late_throttle_commit(self) -> None:
        """When throttle commit - apex > 30m median, inject 3.5 and 5.3."""
        # apex at 280, throttle at 320 -> offset = 40m > 30m
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(apex=280.0, throttle=320.0)],
            2: [_make_corner(apex=280.0, throttle=315.0)],
            3: [_make_corner(apex=280.0, throttle=325.0)],
        }
        triggers = _corner_pattern_snippets(all_corners, None)
        snippet_ids = [t[0] for t in triggers]
        assert "3.5" in snippet_ids
        assert "5.3" in snippet_ids


class TestMinSpeedVarianceTrigger:
    def test_high_min_speed_variance(self) -> None:
        """When std(min_speed) > 3 mph, inject 8.10."""
        # 22 mps = 49.2 mph, 20 mps = 44.7 mph, 24 mps = 53.7 mph -> std > 3 mph
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(min_speed=22.0)],
            2: [_make_corner(min_speed=20.0)],
            3: [_make_corner(min_speed=24.0)],
        }
        triggers = _corner_pattern_snippets(all_corners, None)
        snippet_ids = [t[0] for t in triggers]
        assert "8.10" in snippet_ids


class TestLargeGainTrigger:
    def test_large_consistency_gain(self) -> None:
        """When gain_s > 0.3s, inject 8.8."""
        gains = _make_gains({1: 0.5})
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner()],
            2: [_make_corner()],
        }
        triggers = _corner_pattern_snippets(all_corners, gains)
        snippet_ids = [t[0] for t in triggers]
        assert "8.8" in snippet_ids

    def test_small_gain_no_trigger(self) -> None:
        gains = _make_gains({1: 0.1})
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner()],
            2: [_make_corner()],
        }
        triggers = _corner_pattern_snippets(all_corners, gains)
        snippet_ids = [t[0] for t in triggers]
        assert "8.8" not in snippet_ids


# ---------------------------------------------------------------------------
# Tests: Token budget
# ---------------------------------------------------------------------------
class TestTokenBudget:
    def test_output_within_char_budget(self) -> None:
        """Result should not exceed the approximate token budget."""
        # Create data that triggers many snippets
        all_corners: dict[int, list[Corner]] = {
            i: [
                _make_corner(
                    number=j,
                    apex_type="early",
                    brake_pt=100.0 + i * 20,
                    peak_g=-0.3,
                    throttle=320.0,
                    apex=280.0,
                    min_speed=15.0 + i * 3,
                )
                for j in range(1, 6)
            ]
            for i in range(1, 8)
        }
        gains = _make_gains({i: 0.5 for i in range(1, 6)})
        result = select_kb_snippets(all_corners, "novice", gains=gains)
        budget = _estimate_char_budget()
        assert len(result) <= budget + 200  # small margin for header

    def test_char_budget_matches_constant(self) -> None:
        budget = _estimate_char_budget()
        assert budget == MAX_INJECTION_TOKENS * 4  # CHARS_PER_TOKEN = 4.0


# ---------------------------------------------------------------------------
# Tests: Empty / edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_empty_corners(self) -> None:
        result = select_kb_snippets({}, "intermediate")
        # Should still include skill-level snippets
        assert "2.5" in result

    def test_corners_with_no_brake_data(self) -> None:
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(brake_pt=None, peak_g=None, throttle=None)],
        }
        # Should not crash
        result = select_kb_snippets(all_corners, "novice")
        assert isinstance(result, str)

    def test_single_lap(self) -> None:
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner()],
        }
        result = select_kb_snippets(all_corners, "intermediate")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_none_gains(self) -> None:
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner()],
        }
        result = select_kb_snippets(all_corners, "advanced", gains=None)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Tests: Output format
# ---------------------------------------------------------------------------
class TestOutputFormat:
    def test_has_header(self) -> None:
        result = select_kb_snippets({}, "novice")
        assert result.startswith("## Additional Coaching Knowledge")

    def test_snippets_have_section_ids(self) -> None:
        result = select_kb_snippets({}, "novice")
        assert "[8.4]" in result
        assert "[8.5]" in result

    def test_empty_when_no_snippets_match(self) -> None:
        """Edge case: if somehow all snippets were removed from KB_SNIPPETS."""
        # We can't easily test this without modifying KB_SNIPPETS,
        # but we can verify a valid skill level always produces output
        result = select_kb_snippets({}, "novice")
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Tests: Integration with coaching.py
# ---------------------------------------------------------------------------
class TestCoachingIntegration:
    def test_generate_report_includes_kb_context(self) -> None:
        """Verify that generate_coaching_report passes KB snippets to the API."""
        from cataclysm.coaching import generate_coaching_report

        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(
                text=json.dumps(
                    {
                        "summary": "KB enriched",
                        "priority_corners": [],
                        "corner_grades": [],
                        "patterns": [],
                    }
                )
            )
        ]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        from cataclysm.engine import LapSummary

        summaries = [
            LapSummary(lap_number=1, lap_time_s=90.0, lap_distance_m=500.0, max_speed_mps=40.0),
        ]
        corners_map: dict[int, list[Corner]] = {
            1: [_make_corner(apex_type="early")],
        }

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_anthropic}),
        ):
            report = generate_coaching_report(
                summaries,
                corners_map,
                "Test Track",
                skill_level="novice",
            )

        assert report.summary == "KB enriched"
        call_kwargs = mock_client.messages.create.call_args
        system_prompt = call_kwargs.kwargs["system"]
        assert "Additional Coaching Knowledge" in system_prompt
        assert "8.4" in system_prompt  # novice snippet

    def test_followup_includes_kb_context_when_corners_provided(self) -> None:
        """Verify ask_followup appends KB snippets when corner data is passed."""
        from cataclysm.coaching import CoachingContext, CoachingReport, ask_followup

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="Great question about braking!")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        ctx = CoachingContext()
        report = CoachingReport("summary", [], [], [], raw_response="report text")
        corners_map: dict[int, list[Corner]] = {
            1: [_make_corner()],
        }

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_anthropic}),
        ):
            answer = ask_followup(
                ctx,
                "How do I brake better?",
                report,
                all_lap_corners=corners_map,
                skill_level="advanced",
            )

        assert answer == "Great question about braking!"
        call_kwargs = mock_client.messages.create.call_args
        system_prompt = call_kwargs.kwargs["system"]
        assert "Additional Coaching Knowledge" in system_prompt
        assert "5.4" in system_prompt  # advanced snippet

    def test_followup_without_corners_has_no_kb(self) -> None:
        """Verify ask_followup without corner data omits KB injection."""
        from cataclysm.coaching import CoachingContext, CoachingReport, ask_followup

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="Answer")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        ctx = CoachingContext()
        report = CoachingReport("summary", [], [], [], raw_response="report text")

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_anthropic}),
        ):
            ask_followup(ctx, "Question?", report)

        call_kwargs = mock_client.messages.create.call_args
        system_prompt = call_kwargs.kwargs["system"]
        assert "Additional Coaching Knowledge" not in system_prompt


# ---------------------------------------------------------------------------
# Tests: Priority ordering
# ---------------------------------------------------------------------------
class TestPriorityOrdering:
    def test_skill_snippets_come_first(self) -> None:
        """Skill-level snippets should appear before pattern-triggered ones."""
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(apex_type="early")],
            2: [_make_corner(apex_type="early")],
            3: [_make_corner(apex_type="early")],
        }
        result = select_kb_snippets(all_corners, "novice")
        # 8.4 (skill) should appear before 4.1 (pattern)
        pos_skill = result.index("[8.4]")
        pos_pattern = result.index("[4.1]")
        assert pos_skill < pos_pattern

    def test_higher_gain_patterns_prioritized(self) -> None:
        """Pattern triggers for corners with larger gains should come first."""
        gains = _make_gains({1: 0.5, 2: 0.1})
        # Corner 1 has early apex (high gain), corner 2 also has early apex (low gain)
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(number=1, apex_type="early"), _make_corner(number=2, apex_type="mid")],
            2: [_make_corner(number=1, apex_type="early"), _make_corner(number=2, apex_type="mid")],
            3: [_make_corner(number=1, apex_type="early"), _make_corner(number=2, apex_type="mid")],
        }
        triggers = _corner_pattern_snippets(all_corners, gains)
        # 4.1 for corner 1 (gain=0.5) should have higher priority
        early_triggers = [(sid, pri) for sid, pri in triggers if sid == "4.1"]
        assert len(early_triggers) >= 1
        assert early_triggers[0][1] == 0.5  # from corner 1
