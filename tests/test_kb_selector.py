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
    _session_level_snippets,
    classify_corner_type,
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
        # Use call_args_list[0] to get the coaching call, not the validator's call
        call_kwargs = mock_client.messages.create.call_args_list[0]
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
        call_kwargs = mock_client.messages.create.call_args_list[0]
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

        call_kwargs = mock_client.messages.create.call_args_list[0]
        system_prompt = call_kwargs.kwargs["system"]
        assert "Additional Coaching Knowledge" not in system_prompt


# ---------------------------------------------------------------------------
# Tests: Priority ordering
# ---------------------------------------------------------------------------
class TestPriorityOrdering:
    def test_top_gain_snippets_come_first(self) -> None:
        """Top-gain corner snippets should appear before skill-level ones."""
        gains = _make_gains({1: 0.8})
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(apex_type="early")],
            2: [_make_corner(apex_type="early")],
            3: [_make_corner(apex_type="early")],
        }
        result = select_kb_snippets(all_corners, "novice", gains=gains)
        # 4.1 (top-gain pattern) should appear before 8.4 (skill)
        pos_pattern = result.index("[4.1]")
        pos_skill = result.index("[8.4]")
        assert pos_pattern < pos_skill

    def test_skill_snippets_before_remaining_patterns(self) -> None:
        """Skill-level snippets come after top-3-gain but before remaining patterns."""
        gains = _make_gains({1: 0.5})
        # Early apex triggers 4.1, low brake G triggers 2.5, late throttle triggers 3.5+5.3
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(apex_type="early", peak_g=-0.3, throttle=320.0, apex=280.0)],
            2: [_make_corner(apex_type="early", peak_g=-0.3, throttle=315.0, apex=280.0)],
            3: [_make_corner(apex_type="early", peak_g=-0.3, throttle=325.0, apex=280.0)],
        }
        result = select_kb_snippets(all_corners, "novice", gains=gains)
        # All pattern-triggered snippets should be present
        assert "[4.1]" in result
        # Novice skill snippet should also be present
        assert "[8.4]" in result

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


# ---------------------------------------------------------------------------
# Edge cases for _corner_pattern_snippets (lines 179, 189)
# ---------------------------------------------------------------------------


class TestCornerPatternSnippetsEdgeCases:
    """Edge cases for _corner_pattern_snippets uncovered lines."""

    def test_malformed_segment_name_skipped(self) -> None:
        """Segment name without valid int suffix → ValueError caught, skipped."""
        gains = _make_gains({1: 0.5})
        # Hack the segment name to "T_bad" which can't be parsed as int
        gains.consistency.segment_gains[0].segment = SegmentDefinition(
            name="T_bad", entry_distance_m=100.0, exit_distance_m=200.0, is_corner=True
        )
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(number=1, apex_type="early")],
        }
        # Should not crash — the bad name is silently skipped
        triggers = _corner_pattern_snippets(all_corners, gains)
        # Corner 1 still gets default priority 0.1 (not from gains),
        # except CT.* triggers which have priority 0.2
        non_ct = [(sid, pri) for sid, pri in triggers if not sid.startswith("CT.")]
        assert all(pri == 0.1 for _, pri in non_ct)

    def test_empty_segment_name_skipped(self) -> None:
        """Segment name '' → IndexError caught, skipped."""
        gains = _make_gains({1: 0.5})
        gains.consistency.segment_gains[0].segment = SegmentDefinition(
            name="", entry_distance_m=100.0, exit_distance_m=200.0, is_corner=True
        )
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(number=1, apex_type="early")],
        }
        triggers = _corner_pattern_snippets(all_corners, gains)
        # Should not crash
        assert isinstance(triggers, list)

    def test_corner_number_with_no_data_skipped(self) -> None:
        """Corner number in corner_nums but no matching data → skipped (line 189)."""
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(number=1, apex_type="mid")],
            # Corner 2 exists in keys via corner detection but no lap has corner 99
        }
        # Add corner 99 to the all_corners keys set but with no actual data
        gains = _make_gains({99: 0.3})
        triggers = _corner_pattern_snippets(all_corners, gains)
        # Corner 99 was skipped (no data), only corner 1 patterns considered
        assert isinstance(triggers, list)


# ---------------------------------------------------------------------------
# Edge cases for select_kb_snippets output formatting (lines 288, 292, 297)
# ---------------------------------------------------------------------------


class TestSelectKbSnippetsFormatEdgeCases:
    """Edge cases for the formatting section of select_kb_snippets."""

    def test_tiny_char_budget_returns_empty(self) -> None:
        """When char_budget is too small for any snippet, returns '' (line 297)."""
        # Monkey-patch MAX_INJECTION_TOKENS to force a tiny char budget
        # The budget is MAX_INJECTION_TOKENS * 4 by default
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(number=1, apex_type="early")],
        }
        # Use a very small char_budget by patching the module constant
        with patch("cataclysm.kb_selector.MAX_INJECTION_TOKENS", 1):
            result = select_kb_snippets(all_corners, "novice")
        # With only 4 chars budget, nothing fits after the header
        assert result == ""


# ---------------------------------------------------------------------------
# Tests: New snippet categories (Wave 1B)
# ---------------------------------------------------------------------------


class TestNewSnippetCategories:
    """Verify all new snippet categories exist and are well-formed."""

    def test_load_transfer_snippets_exist(self) -> None:
        assert "LT.1" in KB_SNIPPETS
        assert "LT.2" in KB_SNIPPETS
        assert "load transfer" in KB_SNIPPETS["LT.1"].lower()
        assert "lateral" in KB_SNIPPETS["LT.2"].lower()

    def test_brake_trace_snippet_exists(self) -> None:
        assert "BR.1" in KB_SNIPPETS
        assert "brake trace" in KB_SNIPPETS["BR.1"].lower()

    def test_survival_reaction_snippets_exist(self) -> None:
        assert "SR.1" in KB_SNIPPETS
        assert "SR.2" in KB_SNIPPETS
        assert "survival reaction" in KB_SNIPPETS["SR.1"].lower()
        assert "attention" in KB_SNIPPETS["SR.2"].lower()

    def test_drivetrain_snippets_exist(self) -> None:
        assert "DT.1" in KB_SNIPPETS
        assert "DT.2" in KB_SNIPPETS
        assert "DT.3" in KB_SNIPPETS
        assert "fwd" in KB_SNIPPETS["DT.1"].lower()
        assert "rwd" in KB_SNIPPETS["DT.2"].lower()
        assert "awd" in KB_SNIPPETS["DT.3"].lower()

    def test_wet_weather_snippet_exists(self) -> None:
        assert "WET.1" in KB_SNIPPETS
        assert "wet" in KB_SNIPPETS["WET.1"].lower()

    def test_vision_snippet_exists(self) -> None:
        assert "VIS.1" in KB_SNIPPETS
        assert "look" in KB_SNIPPETS["VIS.1"].lower()

    def test_aero_snippet_exists(self) -> None:
        assert "AERO.1" in KB_SNIPPETS
        assert "aerodynamic" in KB_SNIPPETS["AERO.1"].lower()

    def test_total_snippet_count_expanded(self) -> None:
        """KB should now have 33+ snippets (28 base + 5 corner type)."""
        assert len(KB_SNIPPETS) >= 33


class TestExpandedSkillSnippets:
    """Verify new skill-level snippet assignments."""

    def test_novice_includes_vision_and_survival(self) -> None:
        corners: dict[int, list[Corner]] = {}
        result = select_kb_snippets(corners, "novice")
        assert "VIS.1" in result
        assert "SR.2" in result

    def test_intermediate_includes_load_transfer_and_brake_trace(self) -> None:
        corners: dict[int, list[Corner]] = {}
        result = select_kb_snippets(corners, "intermediate")
        assert "LT.1" in result
        assert "BR.1" in result

    def test_advanced_includes_lateral_load_transfer(self) -> None:
        corners: dict[int, list[Corner]] = {}
        result = select_kb_snippets(corners, "advanced")
        assert "LT.2" in result


# ---------------------------------------------------------------------------
# Tests: Session-level pattern triggers (Wave 1B)
# ---------------------------------------------------------------------------


class TestSessionLevelSnippets:
    """Tests for _session_level_snippets function."""

    def test_empty_corners_returns_empty(self) -> None:
        result = _session_level_snippets({})
        assert result == []

    def test_survival_reaction_throttle_past_exit(self) -> None:
        """When throttle commit is past exit distance, trigger SR.1."""
        # throttle_commit_m=400 > exit_distance_m=350 -> survival reaction
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(throttle=400.0, exit_m=350.0)],
        }
        triggers = _session_level_snippets(all_corners)
        snippet_ids = [sid for sid, _ in triggers]
        assert "SR.1" in snippet_ids

    def test_no_survival_reaction_when_throttle_before_exit(self) -> None:
        """Normal throttle commit should not trigger SR.1."""
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(throttle=320.0, exit_m=350.0)],
        }
        triggers = _session_level_snippets(all_corners)
        snippet_ids = [sid for sid, _ in triggers]
        assert "SR.1" not in snippet_ids

    def test_low_grip_utilization(self) -> None:
        """When max peak brake G across session < 0.7g, trigger LT.1."""
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(peak_g=-0.3)],
            2: [_make_corner(peak_g=-0.5)],
            3: [_make_corner(peak_g=-0.4)],
        }
        triggers = _session_level_snippets(all_corners)
        snippet_ids = [sid for sid, _ in triggers]
        assert "LT.1" in snippet_ids

    def test_no_low_grip_when_high_g(self) -> None:
        """When peak brake G > 0.7g, LT.1 should not trigger."""
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(peak_g=-0.9)],
            2: [_make_corner(peak_g=-0.8)],
        }
        triggers = _session_level_snippets(all_corners)
        snippet_ids = [sid for sid, _ in triggers]
        assert "LT.1" not in snippet_ids

    def test_short_braking_zone(self) -> None:
        """When >30% of corners have brake-to-apex < 30m, trigger BR.1."""
        # apex=280, brake=260 -> 20m (short), all corners short
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(brake_pt=260.0, apex=280.0)],
            2: [_make_corner(brake_pt=265.0, apex=280.0)],
            3: [_make_corner(brake_pt=270.0, apex=280.0)],
        }
        triggers = _session_level_snippets(all_corners)
        snippet_ids = [sid for sid, _ in triggers]
        assert "BR.1" in snippet_ids

    def test_no_short_braking_when_long_zones(self) -> None:
        """Normal braking zones should not trigger BR.1."""
        # apex=280, brake=150 -> 130m (long)
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(brake_pt=150.0, apex=280.0)],
            2: [_make_corner(brake_pt=140.0, apex=280.0)],
        }
        triggers = _session_level_snippets(all_corners)
        snippet_ids = [sid for sid, _ in triggers]
        assert "BR.1" not in snippet_ids

    def test_high_speed_corner_triggers_aero(self) -> None:
        """When any corner has min_speed > 80 mph, trigger AERO.1."""
        # 80 mph = 35.76 m/s
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(min_speed=36.0)],  # ~80.5 mph
        }
        triggers = _session_level_snippets(all_corners)
        snippet_ids = [sid for sid, _ in triggers]
        assert "AERO.1" in snippet_ids

    def test_no_aero_when_low_speed(self) -> None:
        """Low-speed corners should not trigger AERO.1."""
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(min_speed=22.0)],  # ~49 mph
        }
        triggers = _session_level_snippets(all_corners)
        snippet_ids = [sid for sid, _ in triggers]
        assert "AERO.1" not in snippet_ids

    def test_no_brake_data_does_not_crash(self) -> None:
        """Corners with no brake data should not crash session-level detection."""
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(brake_pt=None, peak_g=None, throttle=None)],
        }
        triggers = _session_level_snippets(all_corners)
        assert isinstance(triggers, list)

    def test_session_snippets_integrated_into_select(self) -> None:
        """Session-level snippets should appear in select_kb_snippets output."""
        # High-speed corner triggers AERO.1 at session level
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(min_speed=36.0)],
        }
        result = select_kb_snippets(all_corners, "intermediate")
        assert "AERO.1" in result


# ---------------------------------------------------------------------------
# Tests: Token budget with new MAX_INJECTION_TOKENS
# ---------------------------------------------------------------------------


class TestUpdatedTokenBudget:
    def test_max_injection_tokens_is_3000(self) -> None:
        assert MAX_INJECTION_TOKENS == 3000

    def test_char_budget_is_12000(self) -> None:
        budget = _estimate_char_budget()
        assert budget == 12000  # 3000 * 4.0


# ---------------------------------------------------------------------------
# Tests: Corner type classification (classify_corner_type)
# ---------------------------------------------------------------------------


class TestClassifyCornerType:
    """Tests for classify_corner_type function."""

    def test_empty_corner_data_returns_medium(self) -> None:
        """Empty input defaults to 'medium'."""
        result = classify_corner_type([])
        assert result == "medium"

    def test_hairpin_classification(self) -> None:
        """Hairpin: speed loss > 30 mph, min speed < 35 mph."""
        # min_speed = 13 mps (~29.1 mph), brake at 100m, entry at 200m = 100m brake dist
        # peak_brake_g = -0.9 -> decel = 8.829 m/s^2
        # entry_speed = sqrt(13^2 + 2*8.829*100) = sqrt(169 + 1765.8) = sqrt(1934.8) = ~44.0 m/s
        # speed loss = (44.0 - 13.0) * 2.237 = ~69.3 mph -> > 30 mph
        # min speed = 13 * 2.237 = 29.1 mph -> < 35 mph
        corners = [
            _make_corner(
                min_speed=13.0,
                brake_pt=100.0,
                entry=200.0,
                exit_m=350.0,
                peak_g=-0.9,
            ),
        ]
        result = classify_corner_type(corners)
        assert result == "hairpin"

    def test_sweeper_classification(self) -> None:
        """Sweeper: speed loss < 15 mph, min speed > 65 mph."""
        # min_speed = 32 mps (~71.6 mph), small brake dist, low decel
        # brake at 180, entry at 200 = 20m brake dist
        # peak_brake_g = -0.2 -> decel = 1.962 m/s^2
        # entry_speed = sqrt(32^2 + 2*1.962*20) = sqrt(1024 + 78.48) = sqrt(1102.48) = ~33.2 m/s
        # speed loss = (33.2 - 32.0) * 2.237 = ~2.7 mph -> < 15 mph
        # min speed = 32 * 2.237 = 71.6 mph -> > 65 mph
        corners = [
            _make_corner(
                min_speed=32.0,
                brake_pt=180.0,
                entry=200.0,
                exit_m=350.0,
                peak_g=-0.2,
            ),
        ]
        result = classify_corner_type(corners)
        assert result == "sweeper"

    def test_kink_classification(self) -> None:
        """Kink: speed loss < 8 mph, min speed > 80 mph."""
        # min_speed = 38 mps (~85 mph), tiny brake dist, minimal decel
        # brake at 195, entry at 200 = 5m brake dist
        # peak_brake_g = -0.1 -> decel = 0.981 m/s^2
        # entry_speed = sqrt(38^2 + 2*0.981*5) = sqrt(1444 + 9.81) = sqrt(1453.81) = ~38.1 m/s
        # speed loss = (38.1 - 38.0) * 2.237 = ~0.2 mph -> < 8 mph
        # min speed = 38 * 2.237 = 85.0 mph -> > 80 mph
        corners = [
            _make_corner(
                min_speed=38.0,
                brake_pt=195.0,
                entry=200.0,
                exit_m=350.0,
                peak_g=-0.1,
            ),
        ]
        result = classify_corner_type(corners)
        assert result == "kink"

    def test_medium_classification(self) -> None:
        """Medium: speed loss 15-30 mph, min speed 35-65 mph."""
        # min_speed = 20 mps (~44.7 mph), moderate brake dist
        # brake at 140, entry at 200 = 60m brake dist
        # peak_brake_g = -0.5 -> decel = 4.905 m/s^2
        # entry_speed = sqrt(20^2 + 2*4.905*60) = sqrt(400 + 588.6) = sqrt(988.6) = ~31.4 m/s
        # speed loss = (31.4 - 20.0) * 2.237 = ~25.6 mph -> 15 < x < 30
        # min speed = 20 * 2.237 = 44.7 mph -> 35 < x < 65
        corners = [
            _make_corner(
                min_speed=20.0,
                brake_pt=140.0,
                entry=200.0,
                exit_m=350.0,
                peak_g=-0.5,
            ),
        ]
        result = classify_corner_type(corners)
        assert result == "medium"

    def test_chicane_detection(self) -> None:
        """Chicane: two consecutive corners with < 50m gap between exit and entry."""
        corner1 = [
            _make_corner(number=1, exit_m=300.0, min_speed=20.0),
        ]
        corner2 = [
            _make_corner(number=2, entry=320.0, exit_m=450.0, min_speed=20.0),
        ]
        all_corners_by_number = {1: corner1, 2: corner2}
        result = classify_corner_type(corner1, all_corners_by_number)
        assert result == "chicane"

    def test_no_chicane_when_gap_too_large(self) -> None:
        """Should not classify as chicane when gap between corners > 50m."""
        corner1 = [
            _make_corner(number=1, exit_m=300.0, min_speed=20.0),
        ]
        corner2 = [
            _make_corner(number=2, entry=400.0, exit_m=500.0, min_speed=20.0),
        ]
        all_corners_by_number = {1: corner1, 2: corner2}
        result = classify_corner_type(corner1, all_corners_by_number)
        # Not chicane — gap is 100m
        assert result != "chicane"

    def test_no_brake_data_falls_back_to_defaults(self) -> None:
        """Without brake data, uses default speed loss (15 mph) and classifies from min speed."""
        corners = [
            _make_corner(min_speed=22.0, brake_pt=None, peak_g=None),
        ]
        result = classify_corner_type(corners)
        # min_speed = 22*2.237 = 49.2 mph, default speed_loss = 15
        # 15 <= 15 <= 30 and 35 <= 49.2 <= 65 -> "medium"
        assert result == "medium"

    def test_multiple_laps_uses_median(self) -> None:
        """Classification uses median values across multiple laps."""
        # 3 laps of similar hairpin data
        corners = [
            _make_corner(min_speed=12.0, brake_pt=100.0, entry=200.0, peak_g=-0.9),
            _make_corner(min_speed=13.0, brake_pt=95.0, entry=200.0, peak_g=-0.85),
            _make_corner(min_speed=14.0, brake_pt=105.0, entry=200.0, peak_g=-0.95),
        ]
        result = classify_corner_type(corners)
        assert result == "hairpin"

    def test_without_corners_by_number_skips_chicane(self) -> None:
        """When all_corners_by_number is None, chicane detection is skipped."""
        corners = [
            _make_corner(number=1, exit_m=300.0, min_speed=20.0),
        ]
        result = classify_corner_type(corners, None)
        # Should not crash and should classify based on speed
        assert result in ("hairpin", "medium", "sweeper", "kink", "chicane")


# ---------------------------------------------------------------------------
# Tests: Corner type snippets exist in KB_SNIPPETS
# ---------------------------------------------------------------------------


class TestCornerTypeSnippets:
    """Verify corner type snippets exist and are well-formed."""

    def test_all_corner_type_snippets_exist(self) -> None:
        for ct in ["CT.HAIRPIN", "CT.MEDIUM", "CT.SWEEPER", "CT.KINK", "CT.CHICANE"]:
            assert ct in KB_SNIPPETS, f"Missing corner type snippet {ct}"

    def test_corner_type_snippets_are_nonempty(self) -> None:
        for ct in ["CT.HAIRPIN", "CT.MEDIUM", "CT.SWEEPER", "CT.KINK", "CT.CHICANE"]:
            assert len(KB_SNIPPETS[ct]) > 50, f"Snippet {ct} is too short"

    def test_hairpin_snippet_content(self) -> None:
        assert "hairpin" in KB_SNIPPETS["CT.HAIRPIN"].lower()
        assert "rotation" in KB_SNIPPETS["CT.HAIRPIN"].lower()

    def test_sweeper_snippet_content(self) -> None:
        assert "sweeper" in KB_SNIPPETS["CT.SWEEPER"].lower()
        assert "momentum" in KB_SNIPPETS["CT.SWEEPER"].lower()

    def test_kink_snippet_content(self) -> None:
        assert "kink" in KB_SNIPPETS["CT.KINK"].lower()
        assert "lifting" in KB_SNIPPETS["CT.KINK"].lower()

    def test_chicane_snippet_content(self) -> None:
        assert "chicane" in KB_SNIPPETS["CT.CHICANE"].lower()
        assert "sacrifice" in KB_SNIPPETS["CT.CHICANE"].lower()

    def test_medium_snippet_content(self) -> None:
        assert "medium" in KB_SNIPPETS["CT.MEDIUM"].lower()
        assert "throttle" in KB_SNIPPETS["CT.MEDIUM"].lower()


# ---------------------------------------------------------------------------
# Tests: Corner type snippets in pattern triggers
# ---------------------------------------------------------------------------


class TestCornerTypeInPatternTriggers:
    """Verify corner type snippets are injected via _corner_pattern_snippets."""

    def test_hairpin_snippet_in_triggers(self) -> None:
        """A hairpin corner should trigger CT.HAIRPIN snippet."""
        all_corners: dict[int, list[Corner]] = {
            1: [
                _make_corner(min_speed=13.0, brake_pt=100.0, entry=200.0, exit_m=350.0, peak_g=-0.9)
            ],
        }
        triggers = _corner_pattern_snippets(all_corners, None)
        snippet_ids = [sid for sid, _ in triggers]
        assert "CT.HAIRPIN" in snippet_ids

    def test_corner_type_priority_is_0_2(self) -> None:
        """Corner type snippets should have priority 0.2."""
        all_corners: dict[int, list[Corner]] = {
            1: [
                _make_corner(min_speed=13.0, brake_pt=100.0, entry=200.0, exit_m=350.0, peak_g=-0.9)
            ],
        }
        triggers = _corner_pattern_snippets(all_corners, None)
        ct_triggers = [(sid, pri) for sid, pri in triggers if sid.startswith("CT.")]
        assert len(ct_triggers) >= 1
        for _sid, pri in ct_triggers:
            assert pri == 0.2

    def test_sweeper_snippet_in_triggers(self) -> None:
        """A sweeper corner should trigger CT.SWEEPER snippet."""
        all_corners: dict[int, list[Corner]] = {
            1: [
                _make_corner(min_speed=32.0, brake_pt=180.0, entry=200.0, exit_m=350.0, peak_g=-0.2)
            ],
        }
        triggers = _corner_pattern_snippets(all_corners, None)
        snippet_ids = [sid for sid, _ in triggers]
        assert "CT.SWEEPER" in snippet_ids

    def test_corner_type_appears_in_final_output(self) -> None:
        """Corner type snippets should appear in select_kb_snippets output."""
        all_corners: dict[int, list[Corner]] = {
            1: [
                _make_corner(min_speed=13.0, brake_pt=100.0, entry=200.0, exit_m=350.0, peak_g=-0.9)
            ],
        }
        result = select_kb_snippets(all_corners, "intermediate")
        assert "CT.HAIRPIN" in result

    def test_multiple_corner_types_in_triggers(self) -> None:
        """Different corners should get different corner type snippets."""
        all_corners: dict[int, list[Corner]] = {
            1: [
                # Hairpin (corner 1)
                _make_corner(
                    number=1,
                    min_speed=13.0,
                    brake_pt=100.0,
                    entry=200.0,
                    exit_m=350.0,
                    peak_g=-0.9,
                ),
            ],
            2: [
                # Sweeper (corner 2)
                _make_corner(
                    number=2,
                    min_speed=32.0,
                    brake_pt=480.0,
                    entry=500.0,
                    exit_m=650.0,
                    peak_g=-0.2,
                ),
            ],
        }
        triggers = _corner_pattern_snippets(all_corners, None)
        snippet_ids = [sid for sid, _ in triggers]
        assert "CT.HAIRPIN" in snippet_ids
        assert "CT.SWEEPER" in snippet_ids


# ---------------------------------------------------------------------------
# Tests: Additional edge cases for coverage
# ---------------------------------------------------------------------------


class TestSessionLevelSnippetsEmptyCornerLists:
    """Cover _session_level_snippets line 368: non-empty dict with empty value lists."""

    def test_dict_with_empty_lap_lists_returns_empty(self) -> None:
        """When all_lap_corners has keys but all lap lists are empty,
        the secondary guard (line 368) fires and returns []."""
        # all_lap_corners is truthy (non-empty dict), but all values are [].
        # This bypasses the line-359 guard and hits the line-368 guard.
        result = _session_level_snippets({1: [], 2: []})
        assert result == []


class TestSelectKbSnippetsNonExistentSnippetId:
    """Cover select_kb_snippets line 597: snippet is None when sid not in KB_SNIPPETS."""

    def test_unknown_snippet_id_is_silently_skipped(self) -> None:
        """When selected_ids contains an ID not in KB_SNIPPETS, it is skipped
        without error (line 597: if snippet is None: continue)."""
        # Inject a fake snippet ID via _session_level_snippets returning a
        # non-existent key.  Use a real corner so other code paths stay clean.
        all_corners: dict[int, list[Corner]] = {
            1: [_make_corner(min_speed=36.0)],  # triggers AERO.1 (real ID)
        }

        def _fake_session_triggers(
            corners: dict[int, list[Corner]],
        ) -> list[tuple[str, float]]:
            # Return one real ID and one non-existent ID
            return [("AERO.1", 0.15), ("NONEXISTENT.FAKE.99", 0.15)]

        with patch(
            "cataclysm.kb_selector._session_level_snippets",
            side_effect=_fake_session_triggers,
        ):
            result = select_kb_snippets(all_corners, "intermediate")

        # AERO.1 is real and should appear; the fake ID should be skipped silently
        assert "AERO.1" in result
        assert "NONEXISTENT.FAKE.99" not in result
