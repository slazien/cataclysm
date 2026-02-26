"""PDF report generation for coaching sessions."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from io import BytesIO

import plotly.graph_objects as go
from fpdf import FPDF

from cataclysm.coaching import CoachingReport, CornerGrade
from cataclysm.engine import LapSummary

MPS_TO_MPH = 2.23694


def _sanitize_text(text: str) -> str:
    """Replace Unicode characters unsupported by Helvetica with ASCII equivalents.

    fpdf2's built-in fonts only support Latin-1. AI-generated text commonly
    contains em-dashes, curly quotes, ellipses, etc. that must be transliterated.
    """
    replacements: dict[str, str] = {
        "\u2014": "--",  # em-dash
        "\u2013": "-",  # en-dash
        "\u2018": "'",  # left single quote
        "\u2019": "'",  # right single quote
        "\u201c": '"',  # left double quote
        "\u201d": '"',  # right double quote
        "\u2026": "...",  # ellipsis
        "\u2022": "*",  # bullet
        "\u00b1": "+/-",  # plus-minus
        "\u2264": "<=",  # less-than-or-equal
        "\u2265": ">=",  # greater-than-or-equal
        "\u00d7": "x",  # multiplication sign
        "\u2192": "->",  # right arrow
        "\u2190": "<-",  # left arrow
        "\u2248": "~=",  # approximately equal
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    # Fallback: replace any remaining non-Latin-1 characters via NFKD decomposition
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("latin-1", errors="replace").decode("latin-1")


@dataclass
class ReportContent:
    """All data needed to build a PDF report."""

    track_name: str
    session_date: str
    best_lap_number: int
    best_lap_time_s: float
    n_laps: int
    summaries: list[LapSummary]
    report: CoachingReport
    # Chart figures (Plotly go.Figure objects) -- all optional
    lap_times_fig: go.Figure | None = None
    speed_trace_fig: go.Figure | None = None
    track_map_fig: go.Figure | None = None
    g_force_fig: go.Figure | None = None


def _fig_to_png_bytes(fig: go.Figure, width: int = 1000, height: int = 450) -> bytes:
    """Convert a Plotly figure to PNG bytes via kaleido."""
    result: bytes = fig.to_image(format="png", width=width, height=height)  # type: ignore[assignment]
    return result


def _fmt_time(t: float) -> str:
    """Format seconds as M:SS.ss."""
    m = int(t // 60)
    s = t % 60
    return f"{m}:{s:05.2f}"


class _ReportPDF(FPDF):
    """Custom FPDF with header/footer."""

    def __init__(self, track_name: str, session_date: str) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self._track_name = track_name
        self._session_date = session_date
        self.set_auto_page_break(auto=True, margin=20)

    def header(self) -> None:
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, f"Cataclysm | {self._track_name} | {self._session_date}", align="L")
        self.ln(8)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def generate_pdf(content: ReportContent) -> bytes:
    """Generate a complete coaching report as PDF bytes.

    Layout:
    1. Title + session summary metrics
    2. Coaching summary text
    3. Lap times chart (if provided)
    4. Corner grades table
    5. Priority corners with tips
    6. Patterns + drills
    7. Speed trace chart (if provided)
    8. Track map chart (if provided)
    9. G-force diagram (if provided)
    """
    pdf = _ReportPDF(content.track_name, content.session_date)
    pdf.alias_nb_pages()
    pdf.add_page()

    # --- Title ---
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 12, "Coaching Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(
        0,
        7,
        f"{content.track_name} - {content.session_date}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    # --- Session metrics ---
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 0, 0)
    best_time = _fmt_time(content.best_lap_time_s)
    pdf.cell(
        0,
        6,
        f"Best Lap: L{content.best_lap_number} ({best_time})  |  Laps: {content.n_laps}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    # --- AI Coaching Summary ---
    if content.report.summary:
        _add_section_header(pdf, "Session Summary")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(0, 5, _sanitize_text(content.report.summary), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # --- Lap Times Chart ---
    if content.lap_times_fig is not None:
        _add_chart(pdf, content.lap_times_fig, "Lap Times", width=1000, height=350)

    # --- Corner Grades Table ---
    if content.report.corner_grades:
        _add_section_header(pdf, "Corner Grades")
        _add_grades_table(pdf, content.report.corner_grades)
        pdf.ln(4)

    # --- Priority Corners ---
    if content.report.priority_corners:
        _add_section_header(pdf, "Priority Corners")
        for pc in content.report.priority_corners:
            cost = pc.get("time_cost_s", 0)
            cn = pc.get("corner", "?")
            issue = pc.get("issue", "")
            tip = pc.get("tip", "")
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"T{cn} ({cost:+.3f}s)", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(0, 4.5, _sanitize_text(f"{issue}"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(0, 100, 0)
            pdf.multi_cell(0, 4.5, _sanitize_text(f"Tip: {tip}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

    # --- Patterns ---
    if content.report.patterns:
        _add_section_header(pdf, "Session Patterns")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(40, 40, 40)
        for p in content.report.patterns:
            pdf.multi_cell(0, 5, _sanitize_text(f"  * {p}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # --- Practice Drills ---
    if content.report.drills:
        _add_section_header(pdf, "Practice Drills")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(40, 40, 40)
        for i, drill in enumerate(content.report.drills, 1):
            pdf.multi_cell(0, 5, _sanitize_text(f"  {i}. {drill}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # --- Charts ---
    if content.speed_trace_fig is not None:
        _add_chart(pdf, content.speed_trace_fig, "Speed Trace")

    if content.track_map_fig is not None:
        _add_chart(pdf, content.track_map_fig, "Track Map", width=800, height=600)

    if content.g_force_fig is not None:
        _add_chart(pdf, content.g_force_fig, "Traction Circle", width=700, height=600)

    # --- Footer note ---
    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(
        0,
        5,
        "Generated by Cataclysm - AI-powered motorsport telemetry analysis",
        align="C",
    )

    output = pdf.output()
    return bytes(output) if output is not None else b""


def _add_section_header(pdf: _ReportPDF, title: str) -> None:
    """Add a styled section header."""
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    # Thin line under header
    pdf.set_draw_color(200, 200, 200)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())
    pdf.ln(3)


def _add_grades_table(pdf: _ReportPDF, grades: list[CornerGrade]) -> None:
    """Render corner grades as a table."""
    # Table header
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(255, 255, 255)
    pdf.set_fill_color(50, 50, 50)
    col_widths = [20, 25, 25, 25, 25, 70]
    headers = ["Corner", "Brake", "Trail", "Speed", "Throttle", "Notes"]
    for w, h in zip(col_widths, headers, strict=True):
        pdf.cell(w, 6, h, border=1, fill=True, align="C")
    pdf.ln()

    # Grade colors for PDF (R, G, B)
    grade_colors: dict[str, tuple[int, int, int]] = {
        "A": (45, 106, 46),
        "B": (26, 107, 90),
        "C": (138, 122, 0),
        "D": (168, 94, 0),
        "F": (168, 50, 50),
    }

    pdf.set_font("Helvetica", "", 9)
    for g in grades:
        pdf.set_text_color(0, 0, 0)
        pdf.set_fill_color(245, 245, 245)
        pdf.cell(col_widths[0], 6, f"T{g.corner}", border=1, fill=True, align="C")

        for val, w in zip(
            [g.braking, g.trail_braking, g.min_speed, g.throttle],
            col_widths[1:5],
            strict=True,
        ):
            r, gc, b = grade_colors.get(val, (100, 100, 100))
            pdf.set_fill_color(r, gc, b)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(w, 6, val, border=1, fill=True, align="C")

        pdf.set_text_color(60, 60, 60)
        pdf.set_fill_color(255, 255, 255)
        # Truncate notes to fit
        notes = g.notes[:80] + "..." if len(g.notes) > 80 else g.notes
        pdf.cell(col_widths[5], 6, _sanitize_text(notes), border=1, align="L")
        pdf.ln()


def _add_chart(
    pdf: _ReportPDF,
    fig: go.Figure,
    title: str,
    width: int = 1000,
    height: int = 450,
) -> None:
    """Add a chart image to the PDF."""
    _add_section_header(pdf, title)

    try:
        png_bytes = _fig_to_png_bytes(fig, width=width, height=height)
    except Exception:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(150, 50, 50)
        pdf.cell(
            0,
            6,
            f"(Chart '{title}' could not be rendered)",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        return

    # fpdf2 can accept BytesIO directly
    img_name = f"chart_{title.lower().replace(' ', '_')}.png"
    buf = BytesIO(png_bytes)
    buf.name = img_name  # fpdf2 needs a name attribute

    # Calculate width to fit page (A4 = 210mm, margins = 10mm each side)
    page_width = 190  # mm available
    aspect = height / width
    img_height = page_width * aspect

    # Check if we need a new page
    if pdf.get_y() + img_height + 10 > pdf.h - 20:
        pdf.add_page()

    pdf.image(buf, x=10, w=page_width)
    pdf.ln(5)
