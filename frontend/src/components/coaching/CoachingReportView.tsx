"use client";

import type { CoachingReport } from "@/lib/types";

const GRADE_COLORS: Record<string, string> = {
  A: "#3fb950",
  B: "#58a6ff",
  C: "#d29922",
  D: "#ffa657",
  F: "#f85149",
};

function GradeBadge({ grade, large = false }: { grade: string; large?: boolean }) {
  const color = GRADE_COLORS[grade] ?? "#8b949e";
  return (
    <span
      className={`inline-flex items-center justify-center rounded font-bold text-white ${
        large ? "h-12 w-12 text-2xl" : "h-6 w-6 text-xs"
      }`}
      style={{ backgroundColor: color }}
    >
      {grade}
    </span>
  );
}

interface CoachingReportViewProps {
  report: CoachingReport;
}

export default function CoachingReportView({ report }: CoachingReportViewProps) {
  // Compute overall grade from corner grades average
  const gradeScore: Record<string, number> = {
    A: 5,
    B: 4,
    C: 3,
    D: 2,
    F: 1,
  };
  const scoreToGrade = (score: number): string => {
    if (score >= 4.5) return "A";
    if (score >= 3.5) return "B";
    if (score >= 2.5) return "C";
    if (score >= 1.5) return "D";
    return "F";
  };

  const allGradeValues = report.corner_grades.flatMap((g) =>
    [g.braking, g.trail_braking, g.min_speed, g.throttle]
      .filter((v) => v !== "N/A" && v !== "?")
      .map((v) => gradeScore[v] ?? 3),
  );
  const avgScore =
    allGradeValues.length > 0
      ? allGradeValues.reduce((a, b) => a + b, 0) / allGradeValues.length
      : 3;
  const overallGrade = scoreToGrade(avgScore);

  return (
    <div className="space-y-6">
      {/* Overall Grade + Summary */}
      <div className="flex items-start gap-4">
        <GradeBadge grade={overallGrade} large />
        <div className="flex-1">
          <p className="text-sm text-[var(--text-primary)]">{report.summary}</p>
        </div>
      </div>

      {/* Strengths / Weaknesses / Patterns */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Patterns as Strengths */}
        {report.patterns.length > 0 && (
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
            <h4 className="mb-2 text-sm font-semibold text-[var(--accent-green)]">
              Session Patterns
            </h4>
            <ul className="space-y-1">
              {report.patterns.map((p, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-[var(--text-secondary)]">
                  <span className="mt-0.5 text-[var(--accent-green)]">&#9679;</span>
                  {p}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Drills */}
        {report.drills.length > 0 && (
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
            <h4 className="mb-2 text-sm font-semibold text-[var(--accent-yellow)]">
              Practice Drills
            </h4>
            <ol className="space-y-2">
              {report.drills.map((d, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-[var(--text-secondary)]">
                  <span className="mt-0.5 flex-shrink-0 font-bold text-[var(--accent-yellow)]">
                    {i + 1}.
                  </span>
                  {d}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  );
}

export { GradeBadge, GRADE_COLORS };
