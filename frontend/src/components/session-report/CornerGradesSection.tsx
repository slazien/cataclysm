'use client';

import { useUiStore, useAnalysisStore } from '@/stores';
import { GradeChip } from '@/components/shared/GradeChip';
import type { CornerGrade } from '@/lib/types';

interface CornerGradesSectionProps {
  grades: CornerGrade[];
  isNovice: boolean;
}

export function CornerGradesSection({ grades, isNovice }: CornerGradesSectionProps) {
  const setActiveView = useUiStore((s) => s.setActiveView);
  const setMode = useAnalysisStore((s) => s.setMode);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);

  function handleCornerClick(cornerNum: number) {
    selectCorner(`T${cornerNum}`);
    setMode('corner');
    setActiveView('deep-dive');
  }

  return (
    <div>
      <h3 className="mb-3 text-sm font-medium text-[var(--text-secondary)]">Corner Grades</h3>
      <div className="overflow-x-auto rounded-lg border border-[var(--cata-border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--cata-border)] bg-[var(--bg-surface)]">
              <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">Corner</th>
              <th className="px-3 py-2 text-center font-medium text-[var(--text-muted)]">Braking</th>
              <th className="px-3 py-2 text-center font-medium text-[var(--text-muted)]">Trail Braking</th>
              <th className="px-3 py-2 text-center font-medium text-[var(--text-muted)]">Min Speed</th>
              <th className="px-3 py-2 text-center font-medium text-[var(--text-muted)]">Throttle</th>
              {!isNovice && (
                <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">Notes</th>
              )}
            </tr>
          </thead>
          <tbody>
            {grades.map((g) => (
              <tr
                key={g.corner}
                onClick={() => handleCornerClick(g.corner)}
                className="cursor-pointer border-b border-[var(--cata-border)] transition-colors last:border-0 hover:bg-[var(--bg-elevated)]"
              >
                <td className="px-3 py-2 font-medium text-[var(--text-primary)]">T{g.corner}</td>
                <td className="px-3 py-2 text-center"><GradeChip grade={g.braking} /></td>
                <td className="px-3 py-2 text-center"><GradeChip grade={g.trail_braking} /></td>
                <td className="px-3 py-2 text-center"><GradeChip grade={g.min_speed} /></td>
                <td className="px-3 py-2 text-center"><GradeChip grade={g.throttle} /></td>
                {!isNovice && (
                  <td className="px-3 py-2 text-xs text-[var(--text-muted)]">{g.notes}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {isNovice && grades.length > 0 && (
        <p className="mt-2 text-xs text-[var(--text-muted)]">
          Click any corner row to see detailed analysis in Deep Dive.
        </p>
      )}
    </div>
  );
}
