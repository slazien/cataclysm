"""Tests for PDF report generation."""

from __future__ import annotations

import plotly.graph_objects as go
import pytest

from cataclysm.coaching import CoachingReport, CornerGrade
from cataclysm.engine import LapSummary
from cataclysm.pdf_report import ReportContent, _fig_to_png_bytes, generate_pdf

pytestmark = pytest.mark.slow


@pytest.fixture
def sample_report() -> CoachingReport:
    return CoachingReport(
        summary="Good session with consistent braking. Focus on throttle timing in T3.",
        priority_corners=[
            {
                "corner": 3,
                "time_cost_s": 0.45,
                "issue": "Late throttle",
                "tip": "Commit earlier",
            },
            {
                "corner": 1,
                "time_cost_s": 0.22,
                "issue": "Inconsistent brake point",
                "tip": "Pick a marker",
            },
        ],
        corner_grades=[
            CornerGrade(
                corner=1,
                braking="B",
                trail_braking="C",
                min_speed="B",
                throttle="B",
                notes="Solid but some brake variance",
            ),
            CornerGrade(
                corner=2,
                braking="A",
                trail_braking="B",
                min_speed="A",
                throttle="A",
                notes="Best corner",
            ),
            CornerGrade(
                corner=3,
                braking="C",
                trail_braking="D",
                min_speed="C",
                throttle="D",
                notes="Needs work",
            ),
        ],
        patterns=[
            "Brake point consistency improved mid-session",
            "Slight fatigue in last 3 laps",
        ],
        drills=["Brake marker drill for T1", "Throttle commit drill for T3"],
    )


@pytest.fixture
def sample_summaries() -> list[LapSummary]:
    return [
        LapSummary(lap_number=1, lap_time_s=93.5, lap_distance_m=3500.0, max_speed_mps=55.0),
        LapSummary(lap_number=2, lap_time_s=92.1, lap_distance_m=3500.0, max_speed_mps=56.0),
        LapSummary(lap_number=3, lap_time_s=92.8, lap_distance_m=3500.0, max_speed_mps=55.5),
    ]


@pytest.fixture
def sample_content(
    sample_report: CoachingReport, sample_summaries: list[LapSummary]
) -> ReportContent:
    return ReportContent(
        track_name="Barber Motorsports Park",
        session_date="22/02/2026",
        best_lap_number=2,
        best_lap_time_s=92.1,
        n_laps=3,
        summaries=sample_summaries,
        report=sample_report,
    )


class TestGeneratePdf:
    def test_returns_bytes(self, sample_content: ReportContent) -> None:
        result = generate_pdf(sample_content)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_starts_with_pdf_header(self, sample_content: ReportContent) -> None:
        result = generate_pdf(sample_content)
        assert result[:5] == b"%PDF-"

    def test_with_none_charts(self, sample_content: ReportContent) -> None:
        """Charts are all None by default -- should still produce valid PDF."""
        result = generate_pdf(sample_content)
        assert result[:5] == b"%PDF-"
        assert len(result) > 500  # has actual content

    def test_with_simple_chart(self, sample_content: ReportContent) -> None:
        """Test with a minimal Plotly figure."""
        fig = go.Figure(data=[go.Bar(x=[1, 2, 3], y=[4, 5, 6])])
        fig.update_layout(
            template="plotly_dark",
            width=800,
            height=400,
        )
        sample_content.lap_times_fig = fig
        result = generate_pdf(sample_content)
        assert result[:5] == b"%PDF-"
        assert len(result) > 1000  # chart adds significant size

    def test_empty_report(self, sample_summaries: list[LapSummary]) -> None:
        """Test with empty coaching report."""
        content = ReportContent(
            track_name="Test Track",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=1,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="",
                priority_corners=[],
                corner_grades=[],
                patterns=[],
            ),
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_long_notes_truncated(self, sample_content: ReportContent) -> None:
        """Verify long notes don't break the table layout."""
        sample_content.report.corner_grades[0] = CornerGrade(
            corner=1,
            braking="B",
            trail_braking="C",
            min_speed="B",
            throttle="B",
            notes="A" * 200,  # very long notes
        )
        result = generate_pdf(sample_content)
        assert result[:5] == b"%PDF-"

    def test_many_corners(self, sample_summaries: list[LapSummary]) -> None:
        """Test with many corners (should span multiple pages)."""
        grades = [
            CornerGrade(
                corner=i,
                braking="B",
                trail_braking="C",
                min_speed="A",
                throttle="B",
                notes=f"Corner {i} notes",
            )
            for i in range(1, 20)
        ]
        content = ReportContent(
            track_name="Test Track",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=3,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="Many corners session.",
                priority_corners=[],
                corner_grades=grades,
                patterns=["Pattern 1"],
                drills=["Drill 1"],
            ),
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"


class TestFigToPngBytes:
    def test_produces_png(self) -> None:
        fig = go.Figure(data=[go.Scatter(x=[1, 2], y=[3, 4])])
        result = _fig_to_png_bytes(fig)
        assert isinstance(result, bytes)
        # PNG magic bytes
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_custom_dimensions(self) -> None:
        fig = go.Figure(data=[go.Scatter(x=[1, 2], y=[3, 4])])
        result = _fig_to_png_bytes(fig, width=400, height=200)
        assert result[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# TestGeneratePdfChartBranches (lines 207, 210, 213)
# ---------------------------------------------------------------------------


class TestGeneratePdfChartBranches:
    """Tests for lines 207, 210, 213: speed_trace, track_map, g_force chart branches."""

    def test_with_speed_trace_fig(self, sample_summaries: list[LapSummary]) -> None:
        """PDF generation with speed_trace_fig should use the chart branch (line 207)."""
        fig = go.Figure(data=[go.Scatter(x=[0, 100, 200], y=[30, 25, 35])])
        content = ReportContent(
            track_name="Test Track",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=2,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="Speed trace test.",
                priority_corners=[],
                corner_grades=[],
                patterns=[],
            ),
            speed_trace_fig=fig,
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"
        assert len(result) > 500

    def test_with_track_map_fig(self, sample_summaries: list[LapSummary]) -> None:
        """PDF generation with track_map_fig should use the chart branch (line 210)."""
        fig = go.Figure(data=[go.Scatter(x=[0.0, 0.1, 0.2], y=[0.0, 0.05, 0.1])])
        content = ReportContent(
            track_name="Test Track",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=2,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="Track map test.",
                priority_corners=[],
                corner_grades=[],
                patterns=[],
            ),
            track_map_fig=fig,
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_with_g_force_fig(self, sample_summaries: list[LapSummary]) -> None:
        """PDF generation with g_force_fig should use the chart branch (line 213)."""
        fig = go.Figure(data=[go.Scatter(x=[0, 0.5, -0.5], y=[0.8, 0.3, 0.3])])
        content = ReportContent(
            track_name="Test Track",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=2,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="G-force test.",
                priority_corners=[],
                corner_grades=[],
                patterns=[],
            ),
            g_force_fig=fig,
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_with_all_charts(self, sample_content: ReportContent) -> None:
        """PDF with all chart types should produce valid output."""
        fig = go.Figure(data=[go.Scatter(x=[1, 2], y=[3, 4])])
        sample_content.speed_trace_fig = fig
        sample_content.track_map_fig = fig
        sample_content.g_force_fig = fig
        result = generate_pdf(sample_content)
        assert result[:5] == b"%PDF-"
        assert len(result) > 2000


# ---------------------------------------------------------------------------
# TestAddChartErrorPath (lines 298-308: error fallback in _add_chart)
# ---------------------------------------------------------------------------


class TestAddChartErrorPath:
    """Tests for lines 298-308: _add_chart error fallback when rendering fails."""

    def test_failing_chart_produces_valid_pdf_not_crash(
        self, sample_summaries: list[LapSummary]
    ) -> None:
        """If chart rendering fails, PDF still generates with an error note (lines 298-308)."""
        from unittest.mock import patch

        fig = go.Figure()
        content = ReportContent(
            track_name="Error Test",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=1,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="Error test.",
                priority_corners=[],
                corner_grades=[],
                patterns=[],
            ),
            speed_trace_fig=fig,
        )
        with patch(
            "cataclysm.pdf_report._fig_to_png_bytes",
            side_effect=RuntimeError("kaleido failure"),
        ):
            result = generate_pdf(content)
        # Should still produce a valid PDF even when chart rendering fails
        assert result[:5] == b"%PDF-"
        assert len(result) > 0


# ---------------------------------------------------------------------------
# TestAddChartPageBreak (line 322: page break when image doesn't fit)
# ---------------------------------------------------------------------------


class TestAddChartPageBreak:
    """Tests for line 322: page break when image doesn't fit on current page."""

    def test_multiple_charts_trigger_page_breaks(
        self, sample_summaries: list[LapSummary]
    ) -> None:
        """Multiple tall charts that overflow the page should trigger page breaks (line 322)."""
        # Use a very tall aspect-ratio figure to force overflow
        fig = go.Figure(data=[go.Scatter(x=list(range(10)), y=list(range(10)))])
        content = ReportContent(
            track_name="Page Break Test",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=1,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="Testing page overflow with multiple charts.",
                priority_corners=[],
                corner_grades=[],
                patterns=["Pattern A", "Pattern B"],
                drills=["Drill 1", "Drill 2"],
            ),
            speed_trace_fig=fig,
            track_map_fig=fig,
            g_force_fig=fig,
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"
        # Multi-chart PDF should have more content than a chartless one
        chartless = ReportContent(
            track_name="Page Break Test",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=1,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="Testing page overflow with multiple charts.",
                priority_corners=[],
                corner_grades=[],
                patterns=[],
                drills=[],
            ),
        )
        chartless_result = generate_pdf(chartless)
        assert len(result) > len(chartless_result)
