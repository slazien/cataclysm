'use client';

import { useMemo } from 'react';
import { motion as m } from 'motion/react';
import { useSessionStore, useAnalysisStore } from '@/stores';
import { useCorners, useAllLapCorners } from '@/hooks/useAnalysis';
import { useCoachingReport } from '@/hooks/useCoaching';
import { GradeChip } from '@/components/shared/GradeChip';
import { cn } from '@/lib/utils';
import { worstGrade, isNAGrade } from '@/lib/gradeUtils';
import { useUnits } from '@/hooks/useUnits';
import { motion as motionTokens } from '@/lib/design-tokens';
import type { Corner, CornerGrade, PriorityCorner } from '@/lib/types';

interface CornerReportCardGridProps {
  onSelectCorner?: () => void;
}

interface CornerCardData {
  cornerNumber: number;
  corner: Corner;
  overallGrade: string;
  cornerGrade: CornerGrade | undefined;
  priorityCorner: PriorityCorner | undefined;
}

const GRADE_SORT_ORDER: Record<string, number> = { F: 0, D: 1, C: 2, B: 3, A: 4 };

const gridItemVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
};

function buildCardData(
  corners: Corner[],
  report: { corner_grades?: CornerGrade[]; priority_corners?: PriorityCorner[] } | undefined,
): CornerCardData[] {
  const cards: CornerCardData[] = corners.map((corner) => {
    const cornerGrade = report?.corner_grades?.find((cg) => cg.corner === corner.number);
    const priorityCorner = report?.priority_corners?.find((pc) => pc.corner === corner.number);

    let overallGrade = 'C';
    if (cornerGrade) {
      const gradeLetters = [
        cornerGrade.braking,
        cornerGrade.trail_braking,
        cornerGrade.min_speed,
        cornerGrade.throttle,
      ].filter((g) => Boolean(g) && !isNAGrade(g));
      if (gradeLetters.length > 0) {
        overallGrade = worstGrade(gradeLetters);
      }
    }

    return {
      cornerNumber: corner.number,
      corner,
      overallGrade,
      cornerGrade,
      priorityCorner,
    };
  });

  // Sort by worst grade first (highest improvement opportunity)
  cards.sort(
    (a, b) => (GRADE_SORT_ORDER[a.overallGrade] ?? 2) - (GRADE_SORT_ORDER[b.overallGrade] ?? 2),
  );

  return cards;
}

function CornerCard({
  card,
  isSelected,
  onClick,
}: {
  card: CornerCardData;
  isSelected: boolean;
  onClick: () => void;
}) {
  const { cornerNumber, corner, overallGrade, cornerGrade, priorityCorner } = card;
  const { convertSpeed, speedUnit, resolveSpeed } = useUnits();

  return (
    <button
      onClick={onClick}
      className={cn(
        'flex flex-col gap-2 rounded-lg border p-3 text-left transition-colors',
        'bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)]',
        isSelected
          ? 'border-[var(--cata-accent)]'
          : 'border-[var(--cata-border)] hover:border-[var(--text-muted)]',
      )}
    >
      {/* Header: Corner name + overall grade */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-[var(--text-primary)]">
          Turn {cornerNumber}
        </span>
        <GradeChip grade={overallGrade} />
      </div>

      {/* Sub-grade chips */}
      {cornerGrade && (
        <m.div
          className="flex flex-wrap gap-1.5"
          initial="initial"
          animate="animate"
          variants={{ animate: { transition: motionTokens.gradeStagger } }}
        >
          {cornerGrade.braking && (
            <div className="flex items-center gap-1">
              <span className="text-[11px] text-[var(--text-secondary)]">Brk</span>
              <GradeChip grade={cornerGrade.braking} reason={cornerGrade.braking_reason} className="px-1.5 py-0 text-[11px]" />
            </div>
          )}
          {cornerGrade.trail_braking && (
            <div className="flex items-center gap-1">
              <span className="text-[11px] text-[var(--text-secondary)]">Trail</span>
              <GradeChip grade={cornerGrade.trail_braking} reason={cornerGrade.trail_braking_reason} className="px-1.5 py-0 text-[11px]" />
            </div>
          )}
          {cornerGrade.min_speed && (
            <div className="flex items-center gap-1">
              <span className="text-[11px] text-[var(--text-secondary)]">Spd</span>
              <GradeChip grade={cornerGrade.min_speed} reason={cornerGrade.min_speed_reason} className="px-1.5 py-0 text-[11px]" />
            </div>
          )}
          {cornerGrade.throttle && (
            <div className="flex items-center gap-1">
              <span className="text-[11px] text-[var(--text-secondary)]">Thr</span>
              <GradeChip grade={cornerGrade.throttle} reason={cornerGrade.throttle_reason} className="px-1.5 py-0 text-[11px]" />
            </div>
          )}
        </m.div>
      )}

      {/* Min speed KPI */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-[var(--text-secondary)]">Min Speed</span>
        <span className="text-xs font-medium tabular-nums text-[var(--text-primary)]">
          {convertSpeed(corner.min_speed_mph).toFixed(1)} {speedUnit}
        </span>
      </div>

      {/* AI tip for priority corners */}
      {priorityCorner?.tip && (
        <div className="rounded-md bg-[var(--ai-bg)] px-2 py-1.5">
          <div className="flex items-start gap-1.5">
            <span
              className="mt-0.5 shrink-0 text-[11px] text-[var(--ai-icon)]"
              role="img"
              aria-label="AI"
            >
              &#x1F916;
            </span>
            <p className="line-clamp-2 text-[11px] leading-relaxed text-[var(--text-secondary)]">
              {resolveSpeed(priorityCorner.tip)}
            </p>
          </div>
        </div>
      )}
    </button>
  );
}

export function CornerReportCardGrid({ onSelectCorner }: CornerReportCardGridProps) {
  const sessionId = useSessionStore((s) => s.activeSessionId);
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);

  const { data: corners } = useCorners(sessionId);
  const { data: allLapCorners } = useAllLapCorners(sessionId);
  const { data: report } = useCoachingReport(sessionId);

  // Use selected lap's corners when exactly one lap is selected
  const effectiveCorners = useMemo(() => {
    if (selectedLaps.length === 1 && allLapCorners) {
      const lapCorners = allLapCorners[String(selectedLaps[0])];
      if (lapCorners && lapCorners.length > 0) return lapCorners;
    }
    return corners ?? [];
  }, [corners, allLapCorners, selectedLaps]);

  const cards = useMemo(() => {
    if (effectiveCorners.length === 0) return [];
    return buildCardData(effectiveCorners, report ?? undefined);
  }, [effectiveCorners, report]);

  if (!sessionId) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">No session loaded</p>
      </div>
    );
  }

  if (cards.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">No corner data available</p>
      </div>
    );
  }

  return (
    <m.div
      className="grid grid-cols-2 gap-3 overflow-y-auto p-1 lg:grid-cols-3 xl:grid-cols-4"
      initial="initial"
      animate="animate"
      variants={{ animate: { transition: motionTokens.stagger } }}
    >
      {cards.map((card) => (
        <m.div
          key={card.cornerNumber}
          variants={gridItemVariants}
          transition={motionTokens.cardEntrance}
        >
          <CornerCard
            card={card}
            isSelected={selectedCorner === `T${card.cornerNumber}`}
            onClick={() => {
              selectCorner(`T${card.cornerNumber}`);
              onSelectCorner?.();
            }}
          />
        </m.div>
      ))}
    </m.div>
  );
}
