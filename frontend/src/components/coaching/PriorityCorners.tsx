"use client";

import type { PriorityCorner } from "@/lib/types";

interface PriorityCornersProps {
  corners: PriorityCorner[];
}

export default function PriorityCorners({ corners }: PriorityCornersProps) {
  if (corners.length === 0) return null;

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {corners.slice(0, 3).map((pc, i) => (
        <div
          key={pc.corner}
          className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4"
        >
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--accent-red)] text-xs font-bold text-white">
                {i + 1}
              </span>
              <span className="text-base font-bold text-[var(--text-primary)]">
                T{pc.corner}
              </span>
            </div>
            <span className="text-sm font-semibold text-[var(--accent-red)]">
              {pc.time_cost_s >= 0 ? "+" : ""}
              {pc.time_cost_s.toFixed(2)}s
            </span>
          </div>

          <p className="mb-2 text-sm text-[var(--text-secondary)]">
            {pc.issue}
          </p>

          <div className="rounded border border-[var(--accent-blue)] border-opacity-30 bg-[var(--accent-blue)] bg-opacity-5 p-2">
            <p className="text-xs font-medium text-[var(--accent-blue)]">
              Tip: {pc.tip}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
