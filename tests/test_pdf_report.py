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
