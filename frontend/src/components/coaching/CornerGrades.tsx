"use client";

import type { CornerGrade } from "@/lib/types";
import { GradeBadge, GRADE_COLORS } from "./CoachingReportView";

interface CornerGradesProps {
  grades: CornerGrade[];
}

function SubRating({ label, grade }: { label: string; grade: string }) {
  if (grade === "N/A" || grade === "?") {
    return (
      <div className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
        <span className="inline-block h-4 w-4 rounded bg-[#444] text-center text-[10px] font-bold leading-4 text-[var(--text-muted)]">
          -
        </span>
        {label}
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
      <GradeBadge grade={grade} />
      {label}
    </div>
  );
}

function gradeAverage(g: CornerGrade): number {
  const scoreMap: Record<string, number> = { A: 5, B: 4, C: 3, D: 2, F: 1 };
  const values = [g.braking, g.trail_braking, g.min_speed, g.throttle]
    .filter((v) => v !== "N/A" && v !== "?")
    .map((v) => scoreMap[v] ?? 3);
  return values.length > 0
    ? values.reduce((a, b) => a + b, 0) / values.length
    : 3;
}

export default function CornerGrades({ grades }: CornerGradesProps) {
  // Sort by worst-first
  const sorted = [...grades].sort(
    (a, b) => gradeAverage(a) - gradeAverage(b),
  );

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {sorted.map((g) => {
        const avg = gradeAverage(g);
        const overallGrade =
          avg >= 4.5
            ? "A"
            : avg >= 3.5
              ? "B"
              : avg >= 2.5
                ? "C"
                : avg >= 1.5
                  ? "D"
                  : "F";
        const borderColor = GRADE_COLORS[overallGrade] ?? "#30363d";

        return (
          <div
            key={g.corner}
            className="rounded-lg border bg-[var(--bg-card)] p-3"
            style={{ borderColor: `${borderColor}44` }}
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-bold text-[var(--text-primary)]">
                T{g.corner}
              </span>
              <GradeBadge grade={overallGrade} />
            </div>

            <div className="mb-2 grid grid-cols-2 gap-1">
              <SubRating label="Braking" grade={g.braking} />
              <SubRating label="Trail" grade={g.trail_braking} />
              <SubRating label="Speed" grade={g.min_speed} />
              <SubRating label="Throttle" grade={g.throttle} />
            </div>

            {g.notes && (
              <p className="text-xs leading-relaxed text-[var(--text-muted)]">
                {g.notes}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
