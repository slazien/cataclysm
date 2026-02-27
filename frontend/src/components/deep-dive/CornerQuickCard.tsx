'use client';

import { useCorners, useAllLapCorners } from '@/hooks/useAnalysis';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useAnalysisStore } from '@/stores';
import { GlossaryTerm } from '@/components/shared/GlossaryTerm';
import { GradeChip } from '@/components/shared/GradeChip';
import { colors } from '@/lib/design-tokens';
import { worstGrade } from '@/lib/gradeUtils';
import { parseCornerNumber } from '@/lib/cornerUtils';
import { useUnits } from '@/hooks/useUnits';
import type { Corner, CornerGrade, PriorityCorner } from '@/lib/types';

interface CornerQuickCardProps {
  sessionId: string;
}

function findBestCorner(
  cornerNumber: number,
  allLapCorners: Record<string, Corner[]> | undefined,
): Corner | null {
  if (!allLapCorners) return null;
  let best: Corner | null = null;
  for (const lapCorners of Object.values(allLapCorners)) {
    const c = lapCorners.find((c) => c.number === cornerNumber);
    if (c && (best === null || c.min_speed_mph > best.min_speed_mph)) {
      best = c;
    }
  }
  return best;
}

interface KpiRowProps {
  label: React.ReactNode;
  value: string;
  delta?: number | null;
  unit?: string;
}

function KpiRow({ label, value, delta, unit = '' }: KpiRowProps) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs text-[var(--text-muted)]">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium tabular-nums text-[var(--text-primary)]">
          {value}
          {unit ? ` ${unit}` : ''}
        </span>
        {delta !== null && delta !== undefined && (
          <span
            className="text-xs font-medium tabular-nums"
            style={{
              color: delta > 0 ? colors.motorsport.throttle : delta < 0 ? colors.motorsport.brake : colors.text.muted,
            }}
          >
            {delta > 0 ? '+' : ''}
            {delta.toFixed(1)}
          </span>
        )}
      </div>
    </div>
  );
}

export function CornerQuickCard({ sessionId }: CornerQuickCardProps) {
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const setMode = useAnalysisStore((s) => s.setMode);

  const { data: corners } = useCorners(sessionId);
  const { data: report } = useCoachingReport(sessionId);
  const { data: allLapCorners } = useAllLapCorners(sessionId);
  const { convertSpeed, speedUnit } = useUnits();

  if (!selectedCorner) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
        <p className="text-center text-sm text-[var(--text-secondary)]">
          Click a corner on the track map to see details
        </p>
      </div>
    );
  }

  const cornerNumber = parseCornerNumber(selectedCorner);
  if (cornerNumber === null) return null;

  const corner = corners?.find((c) => c.number === cornerNumber);
  if (!corner) return null;

  // Get grade info
  const cornerGrade: CornerGrade | undefined = report?.corner_grades?.find(
    (cg) => cg.corner === cornerNumber,
  );

  // Get priority corner tip
  const priorityCorner: PriorityCorner | undefined = report?.priority_corners?.find(
    (pc) => pc.corner === cornerNumber,
  );

  // Compute "vs best" deltas (epsilon check instead of object identity)
  const bestCorner = findBestCorner(cornerNumber, allLapCorners);
  const rawMinSpeedDelta =
    bestCorner && Math.abs(corner.min_speed_mph - bestCorner.min_speed_mph) > 0.05
      ? corner.min_speed_mph - bestCorner.min_speed_mph
      : null;
  const minSpeedDelta = rawMinSpeedDelta !== null ? convertSpeed(rawMinSpeedDelta) : null;

  // Determine overall grade letter (worst of the four sub-grades)
  let overallGrade: string | null = null;
  if (cornerGrade) {
    const gradeLetters = [
      cornerGrade.braking,
      cornerGrade.trail_braking,
      cornerGrade.min_speed,
      cornerGrade.throttle,
    ].filter(Boolean);
    if (gradeLetters.length > 0) {
      overallGrade = worstGrade(gradeLetters);
    }
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-[var(--text-primary)]">
            Turn {cornerNumber}
          </h3>
          {overallGrade && <GradeChip grade={overallGrade} />}
        </div>
        <span className="text-xs text-[var(--text-muted)]">{corner.apex_type} apex</span>
      </div>

      {/* KPIs */}
      <div className="divide-y divide-[var(--cata-border)]">
        <KpiRow
          label={<GlossaryTerm term="Min Speed">Min Speed</GlossaryTerm>}
          value={convertSpeed(corner.min_speed_mph).toFixed(1)}
          unit={speedUnit}
          delta={minSpeedDelta}
        />
        <KpiRow
          label={<GlossaryTerm term="Brake Point">Brake Point</GlossaryTerm>}
          value={corner.brake_point_m !== null ? corner.brake_point_m.toFixed(0) : '--'}
          unit={corner.brake_point_m !== null ? 'm' : ''}
        />
        <KpiRow
          label={<GlossaryTerm term="Peak Brake G">Peak Brake G</GlossaryTerm>}
          value={corner.peak_brake_g !== null ? corner.peak_brake_g.toFixed(2) : '--'}
          unit={corner.peak_brake_g !== null ? 'g' : ''}
        />
        <KpiRow
          label={<GlossaryTerm term="Throttle Commit">Throttle Commit</GlossaryTerm>}
          value={corner.throttle_commit_m !== null ? corner.throttle_commit_m.toFixed(0) : '--'}
          unit={corner.throttle_commit_m !== null ? 'm' : ''}
        />
        <KpiRow
          label="Entry"
          value={corner.entry_distance_m.toFixed(0)}
          unit="m"
        />
        <KpiRow
          label="Exit"
          value={corner.exit_distance_m.toFixed(0)}
          unit="m"
        />
      </div>

      {/* Grade breakdown */}
      {cornerGrade && (
        <div className="flex flex-wrap gap-2">
          {cornerGrade.braking && (
            <div className="flex items-center gap-1">
              <span className="text-xs text-[var(--text-muted)]">Braking</span>
              <GradeChip grade={cornerGrade.braking} />
            </div>
          )}
          {cornerGrade.trail_braking && (
            <div className="flex items-center gap-1">
              <span className="text-xs text-[var(--text-muted)]"><GlossaryTerm term="Trail Braking">Trail</GlossaryTerm></span>
              <GradeChip grade={cornerGrade.trail_braking} />
            </div>
          )}
          {cornerGrade.min_speed && (
            <div className="flex items-center gap-1">
              <span className="text-xs text-[var(--text-muted)]"><GlossaryTerm term="Min Speed">Min Spd</GlossaryTerm></span>
              <GradeChip grade={cornerGrade.min_speed} />
            </div>
          )}
          {cornerGrade.throttle && (
            <div className="flex items-center gap-1">
              <span className="text-xs text-[var(--text-muted)]">Throttle</span>
              <GradeChip grade={cornerGrade.throttle} />
            </div>
          )}
        </div>
      )}

      {/* AI coaching tip */}
      {(priorityCorner || cornerGrade?.notes) && (
        <div className="rounded-md border border-[var(--ai-border-from)]/20 bg-[var(--ai-bg)] px-3 py-2">
          <div className="flex items-start gap-2">
            <svg
              className="mt-0.5 h-3.5 w-3.5 shrink-0"
              style={{ color: colors.ai.icon }}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
              />
            </svg>
            <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
              {priorityCorner?.tip ?? cornerGrade?.notes}
            </p>
          </div>
        </div>
      )}

      {/* Open in Corner Analysis */}
      <button
        onClick={() => setMode('corner')}
        className="mt-1 flex items-center justify-center gap-1 rounded-md border border-[var(--cata-border)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[var(--cata-accent)] hover:text-[var(--text-primary)]"
      >
        Open in Corner Analysis
        <svg
          className="h-3 w-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  );
}
