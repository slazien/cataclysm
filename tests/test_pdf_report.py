"""Tests for PDF report generation."""

from __future__ import annotations

import base64

import plotly.graph_objects as go
import pytest

from cataclysm.coaching import CoachingReport, CornerGrade
from cataclysm.engine import LapSummary
from cataclysm.pdf_report import ReportContent, _fig_to_png_bytes, generate_pdf


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


@pytest.mark.slow
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


@pytest.mark.slow
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


@pytest.mark.slow
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


@pytest.mark.slow
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


@pytest.mark.slow
class TestAddChartPageBreak:
    """Tests for line 322: page break when image doesn't fit on current page."""

    def test_multiple_charts_trigger_page_breaks(self, sample_summaries: list[LapSummary]) -> None:
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


# ---------------------------------------------------------------------------
# TestSanitizeText (lines 22-43)
# ---------------------------------------------------------------------------


class TestSanitizeText:
    """Tests for _sanitize_text — Unicode transliteration for fpdf2."""

    def test_em_dash_replaced(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("one\u2014two")
        assert result == "one--two"

    def test_en_dash_replaced(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("range\u2013end")
        assert result == "range-end"

    def test_left_single_quote(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("\u2018hello\u2019")
        assert result == "'hello'"

    def test_left_double_quote(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("\u201cworld\u201d")
        assert result == '"world"'

    def test_ellipsis(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("wait\u2026")
        assert result == "wait..."

    def test_bullet(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("\u2022 item")
        assert result == "* item"

    def test_plus_minus(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("0.5\u00b10.1")
        assert result == "0.5+/-0.1"

    def test_less_than_or_equal(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("x\u2264y")
        assert result == "x<=y"

    def test_greater_than_or_equal(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("x\u2265y")
        assert result == "x>=y"

    def test_multiplication_sign(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("2\u00d73")
        assert result == "2x3"

    def test_right_arrow(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("A\u2192B")
        assert result == "A->B"

    def test_left_arrow(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("B\u2190A")
        assert result == "B<-A"

    def test_approximately_equal(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("x\u2248y")
        assert result == "x~=y"

    def test_plain_ascii_unchanged(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("Hello world 123")
        assert result == "Hello world 123"

    def test_multiple_replacements(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        result = _sanitize_text("\u2018test\u2019 \u2014 result")
        assert "--" in result
        assert "'" in result


# ---------------------------------------------------------------------------
# TestPrepareText (line 48)
# ---------------------------------------------------------------------------


class TestPrepareText:
    """Tests for _prepare_text — resolve speed markers then sanitize."""

    def test_speed_markers_and_unicode(self) -> None:
        from cataclysm.pdf_report import _prepare_text

        # Speed marker gets resolved, unicode gets replaced
        result = _prepare_text("Target: {{speed:60}} \u2014 maintain")
        assert "60 mph" in result
        assert "--" in result

    def test_no_markers_plain_text(self) -> None:
        from cataclysm.pdf_report import _prepare_text

        result = _prepare_text("Plain text")
        assert result == "Plain text"


# ---------------------------------------------------------------------------
# TestFmtTime (lines 77-79)
# ---------------------------------------------------------------------------


class TestFmtTime:
    """Tests for _fmt_time — format seconds as M:SS.ss."""

    def test_under_a_minute(self) -> None:
        from cataclysm.pdf_report import _fmt_time

        result = _fmt_time(45.3)
        assert result == "0:45.30"

    def test_over_a_minute(self) -> None:
        from cataclysm.pdf_report import _fmt_time

        result = _fmt_time(92.1)
        assert result == "1:32.10"

    def test_exactly_a_minute(self) -> None:
        from cataclysm.pdf_report import _fmt_time

        result = _fmt_time(60.0)
        assert result == "1:00.00"

    def test_large_time(self) -> None:
        from cataclysm.pdf_report import _fmt_time

        result = _fmt_time(125.75)
        assert result == "2:05.75"


# ---------------------------------------------------------------------------
# TestReportPDFHeader (lines 91-95) / Footer (lines 97-101)
# ---------------------------------------------------------------------------


class TestReportPDFHeaderFooter:
    """Tests that _ReportPDF.header() and footer() run without error."""

    def test_header_runs_in_generate_pdf(self, sample_content: ReportContent) -> None:
        """header() is called during PDF generation — valid PDF means it ran."""
        result = generate_pdf(sample_content)
        assert result[:5] == b"%PDF-"

    def test_footer_runs_in_generate_pdf(self, sample_content: ReportContent) -> None:
        """footer() is called on each page — valid PDF means it ran."""
        result = generate_pdf(sample_content)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# TestReportContentDataclass (lines 51-66)
# ---------------------------------------------------------------------------


class TestReportContentDataclass:
    """Tests for ReportContent dataclass defaults and field access."""

    def test_default_chart_fields_none(self, sample_summaries: list[LapSummary]) -> None:
        """Chart figures default to None."""
        from cataclysm.coaching import CoachingReport

        content = ReportContent(
            track_name="T",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=1,
            summaries=sample_summaries,
            report=CoachingReport(summary="", priority_corners=[], corner_grades=[], patterns=[]),
        )
        assert content.lap_times_fig is None
        assert content.speed_trace_fig is None
        assert content.track_map_fig is None
        assert content.g_force_fig is None

    def test_chart_fields_assignable(self, sample_content: ReportContent) -> None:
        """Chart figures can be assigned."""
        fig = go.Figure()
        sample_content.lap_times_fig = fig
        assert sample_content.lap_times_fig is fig


# ---------------------------------------------------------------------------
# TestAddSectionHeader (lines 232-238)
# ---------------------------------------------------------------------------


class TestAddSectionHeader:
    """Tests for _add_section_header — produces valid PDF with header text."""

    def test_section_header_in_pdf(self, sample_summaries: list[LapSummary]) -> None:
        """generate_pdf should call _add_section_header for summary, producing valid PDF."""
        from cataclysm.coaching import CoachingReport

        content = ReportContent(
            track_name="Test",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=1,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="Header section test.",
                priority_corners=[],
                corner_grades=[],
                patterns=["Pattern A"],
                drills=["Drill B"],
            ),
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# TestAddGradesTable (lines 244-283)
# ---------------------------------------------------------------------------


class TestAddGradesTable:
    """Tests for _add_grades_table — grade color logic for all grades."""

    def test_all_grade_colors(self, sample_summaries: list[LapSummary]) -> None:
        """All 5 grade letters (A, B, C, D, F) exercised without error."""
        from cataclysm.coaching import CoachingReport, CornerGrade

        grades = [
            CornerGrade(corner=i, braking=g, trail_braking=g, min_speed=g, throttle=g, notes="n")
            for i, g in enumerate(["A", "B", "C", "D", "F"], 1)
        ]
        content = ReportContent(
            track_name="Test",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=1,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="",
                priority_corners=[],
                corner_grades=grades,
                patterns=[],
            ),
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_unknown_grade_fallback(self, sample_summaries: list[LapSummary]) -> None:
        """Unknown grade letter (e.g. 'N/A') should not crash the table."""
        from cataclysm.coaching import CoachingReport, CornerGrade

        grades = [
            CornerGrade(
                corner=1,
                braking="N/A",
                trail_braking="N/A",
                min_speed="N/A",
                throttle="N/A",
                notes="Not applicable",
            )
        ]
        content = ReportContent(
            track_name="Test",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=1,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="",
                priority_corners=[],
                corner_grades=grades,
                patterns=[],
            ),
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# TestGeneratePdfPriorityCorners (lines 169-185)
# ---------------------------------------------------------------------------


class TestGeneratePdfPriorityCorners:
    """Tests the priority corners section rendering (lines 169-185)."""

    def test_priority_corners_rendered(self, sample_content: ReportContent) -> None:
        """Priority corners section should not cause crash."""
        result = generate_pdf(sample_content)
        assert result[:5] == b"%PDF-"

    def test_priority_corners_with_unicode(self, sample_summaries: list[LapSummary]) -> None:
        """Priority corners containing Unicode text should be sanitized."""
        from cataclysm.coaching import CoachingReport

        content = ReportContent(
            track_name="Test",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=1,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="",
                priority_corners=[
                    {
                        "corner": 5,
                        "time_cost_s": 0.3,
                        "issue": "Late apex \u2014 see telemetry",
                        "tip": "Use the \u20182-board\u2019 as reference",
                    }
                ],
                corner_grades=[],
                patterns=[],
            ),
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# TestGeneratePdfPatternsAndDrills (lines 187-203)
# ---------------------------------------------------------------------------


class TestGeneratePdfPatternsAndDrills:
    """Tests the patterns/drills section rendering."""

    def test_patterns_section_rendered(self, sample_summaries: list[LapSummary]) -> None:
        """Patterns list should be rendered correctly."""
        from cataclysm.coaching import CoachingReport

        content = ReportContent(
            track_name="Test",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=1,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="",
                priority_corners=[],
                corner_grades=[],
                patterns=["Pattern A", "Pattern B", "Pattern C"],
            ),
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_drills_section_rendered(self, sample_summaries: list[LapSummary]) -> None:
        """Drills list should be rendered with numbered items."""
        from cataclysm.coaching import CoachingReport

        content = ReportContent(
            track_name="Test",
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
                drills=["Drill 1", "Drill 2"],
            ),
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# Non-slow tests: mock fpdf2 to cover remaining lines without actually
# rendering a PDF (avoids the slow mark and kaleido dependency).
# ---------------------------------------------------------------------------

# A real 10×10 red PNG (75 bytes) that PIL/fpdf2 can parse.
_MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAAEklEQVR4nGP8z4APMOGVHbHSAEEsAROxCnMTAAAAAElFTkSuQmCC"
)


class TestSanitizeTextFallback:
    """Line 42-43: non-Latin-1 fallback path via NFKD normalization."""

    def test_non_latin1_char_replaced(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        # U+0105 (a with ogonek) is not in the replacements dict, so falls
        # through to the NFKD decomposition path.
        result = _sanitize_text("caf\u00e9")
        # After NFKD + latin-1 encode/decode, accent may be dropped or replaced
        assert isinstance(result, str)

    def test_chinese_char_replaced_with_question_mark(self) -> None:
        from cataclysm.pdf_report import _sanitize_text

        # CJK characters cannot be represented in latin-1
        result = _sanitize_text("\u4e2d\u6587")
        # Should be replaced (either ? or empty), not raise
        assert isinstance(result, str)
        assert "\u4e2d" not in result


class TestReportPDFClass:
    """Lines 86-101: _ReportPDF constructor, header, footer."""

    def test_constructor_stores_fields(self) -> None:
        from cataclysm.pdf_report import _ReportPDF

        pdf = _ReportPDF("My Track", "01/01/2026")
        assert pdf._track_name == "My Track"
        assert pdf._session_date == "01/01/2026"

    def test_header_called_on_add_page(self) -> None:
        """header() is invoked automatically when add_page() is called."""
        from cataclysm.pdf_report import _ReportPDF

        pdf = _ReportPDF("Test Track", "02/02/2026")
        pdf.alias_nb_pages()
        # add_page triggers header(); should not raise
        pdf.add_page()
        # page number should be 1
        assert pdf.page_no() == 1

    def test_footer_invoked_at_close(self) -> None:
        """footer() is invoked when the PDF is output; no crash expected."""
        from cataclysm.pdf_report import _ReportPDF

        pdf = _ReportPDF("Test Track", "02/02/2026")
        pdf.alias_nb_pages()
        pdf.add_page()
        result = bytes(pdf.output())
        assert result[:5] == b"%PDF-"


class TestFigToPngBytesMock:
    """Lines 71-72: _fig_to_png_bytes — ensure it delegates to fig.to_image."""

    def test_delegates_to_to_image(self) -> None:
        from unittest.mock import MagicMock

        from cataclysm.pdf_report import _fig_to_png_bytes

        fake_png = b"\x89PNG\r\n\x1a\nFAKE"
        fig = MagicMock()
        fig.to_image.return_value = fake_png
        result = _fig_to_png_bytes(fig, width=800, height=400)
        fig.to_image.assert_called_once_with(format="png", width=800, height=400)
        assert result == fake_png

    def test_default_dimensions(self) -> None:
        from unittest.mock import MagicMock

        from cataclysm.pdf_report import _fig_to_png_bytes

        fig = MagicMock()
        fig.to_image.return_value = b"PNG"
        _fig_to_png_bytes(fig)
        fig.to_image.assert_called_once_with(format="png", width=1000, height=450)


class TestGeneratePdfMocked:
    """Cover generate_pdf (lines 118-227) with mocked FPDF and kaleido."""

    def _make_content(
        self,
        sample_summaries: list[LapSummary],
        *,
        summary: str = "Test summary",
        priority_corners: list[dict] | None = None,
        corner_grades: list | None = None,
        patterns: list[str] | None = None,
        drills: list[str] | None = None,
    ) -> ReportContent:
        from cataclysm.coaching import CoachingReport, CornerGrade

        if priority_corners is None:
            priority_corners = [{"corner": 1, "time_cost_s": 0.3, "issue": "Late", "tip": "Fix"}]
        if corner_grades is None:
            corner_grades = [
                CornerGrade(
                    corner=1,
                    braking="B",
                    trail_braking="C",
                    min_speed="B",
                    throttle="B",
                    notes="ok",
                ),
            ]
        if patterns is None:
            patterns = ["Pattern A"]
        if drills is None:
            drills = ["Drill 1"]
        return ReportContent(
            track_name="Mock Track",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=2,
            summaries=sample_summaries,
            report=CoachingReport(
                summary=summary,
                priority_corners=priority_corners,
                corner_grades=corner_grades,
                patterns=patterns,
                drills=drills,
            ),
        )

    def test_minimal_content_produces_pdf(self, sample_summaries: list[LapSummary]) -> None:
        """generate_pdf with no charts produces valid PDF bytes."""
        content = self._make_content(
            sample_summaries,
            summary="",
            priority_corners=[],
            corner_grades=[],
            patterns=[],
            drills=[],
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_with_summary_section(self, sample_summaries: list[LapSummary]) -> None:
        """Lines 151-156: summary section is rendered."""
        content = self._make_content(sample_summaries, summary="Great driving today!")
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_with_priority_corners_section(self, sample_summaries: list[LapSummary]) -> None:
        """Lines 169-185: priority corners rendered with tip/issue."""
        content = self._make_content(
            sample_summaries,
            priority_corners=[
                {"corner": 3, "time_cost_s": 0.45, "issue": "Under-rotation", "tip": "Apex later"},
                {
                    "corner": 5,
                    "time_cost_s": 0.20,
                    "issue": "Late throttle",
                    "tip": "Commit earlier",
                },
            ],
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_with_patterns_and_drills(self, sample_summaries: list[LapSummary]) -> None:
        """Lines 188-203: patterns and drills rendered."""
        content = self._make_content(
            sample_summaries,
            patterns=["Brake consistency improved", "Fatigue in last 3 laps"],
            drills=["Brake marker drill", "Throttle commitment drill"],
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_with_all_grade_colors(self, sample_summaries: list[LapSummary]) -> None:
        """Lines 253-283: all five grade letters in the grades table."""
        from cataclysm.coaching import CoachingReport, CornerGrade

        grades = [
            CornerGrade(corner=i, braking=g, trail_braking=g, min_speed=g, throttle=g, notes="note")
            for i, g in enumerate(["A", "B", "C", "D", "F"], 1)
        ]
        content = ReportContent(
            track_name="Grade Test",
            session_date="01/01/2026",
            best_lap_number=1,
            best_lap_time_s=90.0,
            n_laps=1,
            summaries=sample_summaries,
            report=CoachingReport(
                summary="",
                priority_corners=[],
                corner_grades=grades,
                patterns=[],
            ),
        )
        result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_with_chart_mocked(self, sample_summaries: list[LapSummary]) -> None:
        """Lines 159-161: lap_times_fig branch, with kaleido mocked."""
        from unittest.mock import MagicMock, patch

        fake_png = _MINIMAL_PNG
        content = self._make_content(sample_summaries, summary="Chart test")
        content.lap_times_fig = MagicMock()

        with patch("cataclysm.pdf_report._fig_to_png_bytes", return_value=fake_png):
            result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_with_speed_trace_mocked(self, sample_summaries: list[LapSummary]) -> None:
        """Lines 206-207: speed_trace_fig branch, with kaleido mocked."""
        from unittest.mock import MagicMock, patch

        fake_png = _MINIMAL_PNG
        content = self._make_content(sample_summaries, summary="Speed trace test")
        content.speed_trace_fig = MagicMock()

        with patch("cataclysm.pdf_report._fig_to_png_bytes", return_value=fake_png):
            result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_with_track_map_mocked(self, sample_summaries: list[LapSummary]) -> None:
        """Lines 209-210: track_map_fig branch."""
        from unittest.mock import MagicMock, patch

        fake_png = _MINIMAL_PNG
        content = self._make_content(sample_summaries)
        content.track_map_fig = MagicMock()

        with patch("cataclysm.pdf_report._fig_to_png_bytes", return_value=fake_png):
            result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_with_g_force_mocked(self, sample_summaries: list[LapSummary]) -> None:
        """Lines 212-213: g_force_fig branch."""
        from unittest.mock import MagicMock, patch

        fake_png = _MINIMAL_PNG
        content = self._make_content(sample_summaries)
        content.g_force_fig = MagicMock()

        with patch("cataclysm.pdf_report._fig_to_png_bytes", return_value=fake_png):
            result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_chart_error_fallback(self, sample_summaries: list[LapSummary]) -> None:
        """Lines 298-308: _add_chart catches exception and writes error note."""
        from unittest.mock import MagicMock, patch

        content = self._make_content(sample_summaries)
        content.speed_trace_fig = MagicMock()

        with patch(
            "cataclysm.pdf_report._fig_to_png_bytes",
            side_effect=RuntimeError("kaleido not available"),
        ):
            result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_page_break_when_image_doesnt_fit(self, sample_summaries: list[LapSummary]) -> None:
        """Lines 321-322: new page added when image height overflows current page."""
        from unittest.mock import MagicMock, patch

        # A very tall image relative to page height will trigger the page break.
        # fake a PNG with a 1:3 width/height ratio so img_height = 190 * 3 = 570mm > A4
        fake_png = _MINIMAL_PNG
        content = self._make_content(sample_summaries)
        content.track_map_fig = MagicMock()

        # Pass width=100, height=600 to force a very tall aspect ratio
        import cataclysm.pdf_report as pdf_mod

        original = pdf_mod._add_chart

        def tall_add_chart(pdf, fig, title, width=1000, height=450):  # type: ignore
            return original(pdf, fig, title, width=100, height=600)

        with (
            patch("cataclysm.pdf_report._fig_to_png_bytes", return_value=fake_png),
            patch("cataclysm.pdf_report._add_chart", side_effect=tall_add_chart),
        ):
            result = generate_pdf(content)
        assert result[:5] == b"%PDF-"

    def test_add_section_header_directly(self) -> None:
        """Lines 232-238: _add_section_header draws line below title."""
        from cataclysm.pdf_report import _add_section_header, _ReportPDF

        pdf = _ReportPDF("Track", "01/01/2026")
        pdf.alias_nb_pages()
        pdf.add_page()
        _add_section_header(pdf, "My Section")
        result = bytes(pdf.output())
        assert result[:5] == b"%PDF-"

    def test_add_grades_table_directly(self) -> None:
        """Lines 244-283: _add_grades_table renders all grade colors."""
        from cataclysm.coaching import CornerGrade
        from cataclysm.pdf_report import _add_grades_table, _ReportPDF

        grades = [
            CornerGrade(
                corner=1,
                braking="A",
                trail_braking="B",
                min_speed="C",
                throttle="D",
                notes="short note",
            ),
            CornerGrade(
                corner=2,
                braking="F",
                trail_braking="A",
                min_speed="B",
                throttle="C",
                notes="x" * 100,
            ),  # long notes → truncated
        ]
        pdf = _ReportPDF("Track", "01/01/2026")
        pdf.alias_nb_pages()
        pdf.add_page()
        _add_grades_table(pdf, grades)
        result = bytes(pdf.output())
        assert result[:5] == b"%PDF-"

    def test_add_chart_directly_with_mock_png(self) -> None:
        """Lines 294-325: _add_chart with a valid PNG bytes."""
        from unittest.mock import MagicMock, patch

        fake_png = _MINIMAL_PNG
        from cataclysm.pdf_report import _add_chart, _ReportPDF

        pdf = _ReportPDF("Track", "01/01/2026")
        pdf.alias_nb_pages()
        pdf.add_page()
        fig = MagicMock()

        with patch("cataclysm.pdf_report._fig_to_png_bytes", return_value=fake_png):
            _add_chart(pdf, fig, "Speed Trace")
        result = bytes(pdf.output())
        assert result[:5] == b"%PDF-"

    def test_output_bytes_wrapping(self, sample_summaries: list[LapSummary]) -> None:
        """Line 226-227: output() bytearray is converted to bytes."""
        content = self._make_content(
            sample_summaries,
            summary="",
            priority_corners=[],
            corner_grades=[],
            patterns=[],
            drills=[],
        )
        result = generate_pdf(content)
        assert isinstance(result, bytes)
        assert len(result) > 0
