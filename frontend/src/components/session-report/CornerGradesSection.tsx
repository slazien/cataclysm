'use client';

import { useState, useCallback, Fragment } from 'react';
import { motion as m, AnimatePresence } from 'motion/react';
import { useUiStore, useAnalysisStore } from '@/stores';
import { GradeChip } from '@/components/shared/GradeChip';
import { AiInsight } from '@/components/shared/AiInsight';
import { MarkdownText } from '@/components/shared/MarkdownText';
import { motion as motionTokens } from '@/lib/design-tokens';
import { useUnits } from '@/hooks/useUnits';
import { formatCoachingText } from '@/lib/textUtils';
import { InfoTooltip } from '@/components/shared/InfoTooltip';
import type { CornerGrade } from '@/lib/types';

const rowVariants = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
};

interface CornerGradesSectionProps {
  grades: CornerGrade[];
}

export function CornerGradesSection({ grades }: CornerGradesSectionProps) {
  const setActiveView = useUiStore((s) => s.setActiveView);
  const setMode = useAnalysisStore((s) => s.setMode);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);
  const { resolveSpeed } = useUnits();
  const [expandedCorner, setExpandedCorner] = useState<number | null>(null);

  const handleCornerClick = useCallback(
    (cornerNum: number) => {
      selectCorner(`T${cornerNum}`);
      setMode('corner');
      setActiveView('deep-dive');
    },
    [selectCorner, setMode, setActiveView],
  );

  const handleToggleNotes = useCallback(
    (e: React.MouseEvent, cornerNum: number) => {
      e.stopPropagation();
      setExpandedCorner((prev) => (prev === cornerNum ? null : cornerNum));
    },
    [],
  );

  return (
    <div>
      <h3 className="mb-3 flex items-center gap-1.5 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">
        Corner Grades
        <InfoTooltip helpKey="section.corner-grades" />
      </h3>
      <div className="relative">
      <div className="overflow-x-auto rounded-lg border border-[var(--cata-border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--cata-border)] bg-[var(--bg-surface)]">
              <th className="px-2 py-1.5 text-left font-medium text-[var(--text-secondary)] lg:px-3 lg:py-2">Corner</th>
              <th className="px-2 py-1.5 text-center font-medium text-[var(--text-secondary)] lg:px-3 lg:py-2">
                <span className="inline-flex items-center gap-1">Braking <InfoTooltip helpKey="grade.braking" side="bottom" /></span>
              </th>
              <th className="px-2 py-1.5 text-center font-medium text-[var(--text-secondary)] lg:px-3 lg:py-2">
                <span className="inline-flex items-center gap-1">Trail Braking <InfoTooltip helpKey="grade.trail-braking" side="bottom" /></span>
              </th>
              <th className="px-2 py-1.5 text-center font-medium text-[var(--text-secondary)] lg:px-3 lg:py-2">
                <span className="inline-flex items-center gap-1">Min Speed <InfoTooltip helpKey="grade.min-speed" side="bottom" /></span>
              </th>
              <th className="px-2 py-1.5 text-center font-medium text-[var(--text-secondary)] lg:px-3 lg:py-2">
                <span className="inline-flex items-center gap-1">Throttle <InfoTooltip helpKey="grade.throttle" side="bottom" /></span>
              </th>
            </tr>
          </thead>
          <m.tbody
            initial="initial"
            animate="animate"
            variants={{ animate: { transition: motionTokens.gradeStagger } }}
          >
            {grades.map((g) => {
              const hasNotes = Boolean(g.notes);
              const isExpanded = expandedCorner === g.corner;
              return (
                <Fragment key={g.corner}>
                  <m.tr
                    variants={rowVariants}
                    transition={motionTokens.gradeChip}
                    tabIndex={0}
                    role="button"
                    onClick={() => handleCornerClick(g.corner)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleCornerClick(g.corner); } }}
                    className="cursor-pointer border-b border-[var(--cata-border)] transition-colors last:border-0 hover:bg-[var(--bg-elevated)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--cata-accent)]"
                  >
                    <td className="px-2 py-1.5 font-medium text-[var(--text-primary)] lg:px-3 lg:py-2">
                      <span className="flex items-center gap-1">
                        T{g.corner}
                        {hasNotes && (
                          <button
                            type="button"
                            onClick={(e) => handleToggleNotes(e, g.corner)}
                            className="inline-flex items-center"
                            title="Toggle coaching notes"
                          >
                            <svg
                              className={`h-3 w-3 text-[var(--ai-icon)] transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={2}
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                            </svg>
                          </button>
                        )}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-center lg:px-3 lg:py-2"><GradeChip grade={g.braking} reason={g.braking_reason} /></td>
                    <td className="px-2 py-1.5 text-center lg:px-3 lg:py-2"><GradeChip grade={g.trail_braking} reason={g.trail_braking_reason} /></td>
                    <td className="px-2 py-1.5 text-center lg:px-3 lg:py-2"><GradeChip grade={g.min_speed} reason={g.min_speed_reason} /></td>
                    <td className="px-2 py-1.5 text-center lg:px-3 lg:py-2"><GradeChip grade={g.throttle} reason={g.throttle_reason} /></td>
                  </m.tr>
                  <AnimatePresence>
                    {isExpanded && hasNotes && (
                      <m.tr
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.2 }}
                        className="border-b border-[var(--cata-border)] last:border-0"
                      >
                        <td colSpan={5} className="px-2 py-2 lg:px-3">
                          <AiInsight mode="inline">
                            <MarkdownText block>{formatCoachingText(resolveSpeed(g.notes))}</MarkdownText>
                          </AiInsight>
                        </td>
                      </m.tr>
                    )}
                  </AnimatePresence>
                </Fragment>
              );
            })}
          </m.tbody>
        </table>
      </div>
      {/* Right-edge fade indicator for horizontal scroll on mobile */}
      <div className="pointer-events-none absolute inset-y-0 right-0 w-8 rounded-r-lg bg-gradient-to-l from-[var(--bg-surface)] to-transparent" />
      </div>
      <p className="mt-2 text-xs text-[var(--text-secondary)]">
        Click any row to deep dive. Use the arrow icon to expand coaching notes.
      </p>
    </div>
  );
}
