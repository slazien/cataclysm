'use client';

import { useCorners, useAllLapCorners } from '@/hooks/useAnalysis';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useAnalysisStore } from '@/stores';
import { GlossaryTerm } from '@/components/shared/GlossaryTerm';
import { GradeChip } from '@/components/shared/GradeChip';
import { AiInsight } from '@/components/shared/AiInsight';
import { colors } from '@/lib/design-tokens';
import { worstGrade } from '@/lib/gradeUtils';
import { parseCornerNumber } from '@/lib/cornerUtils';
import { useUnits } from '@/hooks/useUnits';
import type { Corner, CornerGrade, PriorityCorner } from '@/lib/types';

interface CornerDetailPanelProps {
  sessionId: string;
}

function findBestCorner(
  cornerNumber: number,
  allLapCorners: Record<string, Corner[]> | undefined,
): Corner | null {
  if (!allLapCorners) return null;
  let best: Corner | null = null;
  for (const lapCorners of Object.values(allLapCorners)) {
    const c = lapCorners.find((lc) => lc.number === cornerNumber);
    if (c && (best === null || c.min_speed_mph > best.min_speed_mph)) {
      best = c;
    }
  }
  return best;
}

interface KpiRowProps {
  label: React.ReactNode;
  value: string;
  unit?: string;
  delta?: number | null;
  deltaUnit?: string;
  invertDelta?: boolean; // true = negative is good (e.g., brake point closer is better)
}

function KpiRow({ label, value, unit = '', delta, deltaUnit, invertDelta }: KpiRowProps) {
  const isGood = delta !== null && delta !== undefined && (invertDelta ? delta < 0 : delta > 0);
  const isBad = delta !== null && delta !== undefined && (invertDelta ? delta > 0 : delta < 0);

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
              color: isGood
                ? colors.motorsport.throttle
                : isBad
                  ? colors.motorsport.brake
                  : colors.text.muted,
            }}
          >
            {delta > 0 ? '+' : ''}
            {delta.toFixed(1)}
            {deltaUnit ?? ''}
          </span>
        )}
      </div>
    </div>
  );
}

interface GradeRowProps {
  label: React.ReactNode;
  grade: string;
}

function GradeRow({ label, grade }: GradeRowProps) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-[var(--text-muted)]">{label}</span>
      <GradeChip grade={grade} />
    </div>
  );
}

export function CornerDetailPanel({ sessionId }: CornerDetailPanelProps) {
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const { data: corners } = useCorners(sessionId);
  const { data: allLapCorners } = useAllLapCorners(sessionId);
  const { data: report } = useCoachingReport(sessionId);
  const { convertSpeed, speedUnit } = useUnits();

  if (!selectedCorner) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
        <p className="text-center text-sm text-[var(--text-secondary)]">
          Click a corner on the map or use arrow keys
        </p>
      </div>
    );
  }

  const cornerNumber = parseCornerNumber(selectedCorner);
  if (cornerNumber === null) return null;

  const corner = corners?.find((c) => c.number === cornerNumber);
  if (!corner) return null;

  // Grade info
  const cornerGrade: CornerGrade | undefined = report?.corner_grades?.find(
    (cg) => cg.corner === cornerNumber,
  );

  // Priority corner tip
  const priorityCorner: PriorityCorner | undefined = report?.priority_corners?.find(
    (pc) => pc.corner === cornerNumber,
  );

  // Compute vs-best deltas (use epsilon check instead of object identity)
  const bestCorner = findBestCorner(cornerNumber, allLapCorners);
  const EPS = 0.05;

  const rawMinSpeedDelta =
    bestCorner && Math.abs(corner.min_speed_mph - bestCorner.min_speed_mph) > EPS
      ? corner.min_speed_mph - bestCorner.min_speed_mph
      : null;
  const minSpeedDelta = rawMinSpeedDelta !== null ? convertSpeed(rawMinSpeedDelta) : null;

  const brakePointDelta =
    bestCorner &&
    corner.brake_point_m !== null &&
    bestCorner.brake_point_m !== null &&
    Math.abs(corner.brake_point_m - bestCorner.brake_point_m) > EPS
      ? corner.brake_point_m - bestCorner.brake_point_m
      : null;

  const peakBrakeDelta =
    bestCorner &&
    corner.peak_brake_g !== null &&
    bestCorner.peak_brake_g !== null &&
    Math.abs(corner.peak_brake_g - bestCorner.peak_brake_g) > EPS
      ? corner.peak_brake_g - bestCorner.peak_brake_g
      : null;

  const throttleDelta =
    bestCorner &&
    corner.throttle_commit_m !== null &&
    bestCorner.throttle_commit_m !== null &&
    Math.abs(corner.throttle_commit_m - bestCorner.throttle_commit_m) > EPS
      ? corner.throttle_commit_m - bestCorner.throttle_commit_m
      : null;

  // Overall grade
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

  // Determine direction from apex type (best we can infer)
  const apexLabel = corner.apex_type
    ? `${corner.apex_type.charAt(0).toUpperCase() + corner.apex_type.slice(1)} Apex`
    : '';

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold text-[var(--text-primary)]">
            Turn {cornerNumber}
          </h3>
          {overallGrade && <GradeChip grade={overallGrade} />}
        </div>
        <span className="text-xs text-[var(--text-muted)]">{apexLabel}</span>
      </div>

      {/* KPIs with vs-best deltas */}
      <div className="divide-y divide-[var(--cata-border)]">
        <KpiRow
          label={<GlossaryTerm term="Min Speed">Min Speed</GlossaryTerm>}
          value={convertSpeed(corner.min_speed_mph).toFixed(1)}
          unit={speedUnit}
          delta={minSpeedDelta}
        />
        {corner.brake_point_m !== null && (
          <KpiRow
            label={<GlossaryTerm term="Brake Point">Brake Point</GlossaryTerm>}
            value={corner.brake_point_m.toFixed(0)}
            unit="m"
            delta={brakePointDelta}
            deltaUnit="m"
            invertDelta
          />
        )}
        {corner.peak_brake_g !== null && (
          <KpiRow
            label={<GlossaryTerm term="Peak Brake G">Peak Brake G</GlossaryTerm>}
            value={corner.peak_brake_g.toFixed(2)}
            unit="g"
            delta={peakBrakeDelta}
            deltaUnit="g"
          />
        )}
        {corner.throttle_commit_m !== null && (
          <KpiRow
            label={<GlossaryTerm term="Throttle Commit">Throttle Commit</GlossaryTerm>}
            value={corner.throttle_commit_m.toFixed(0)}
            unit="m"
            delta={throttleDelta}
            deltaUnit="m"
            invertDelta
          />
        )}
      </div>

      {/* Per-category grades */}
      {cornerGrade && (
        <div className="space-y-0.5">
          <h4 className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Grades
          </h4>
          {cornerGrade.braking && <GradeRow label="Braking" grade={cornerGrade.braking} />}
          {cornerGrade.trail_braking && (
            <GradeRow label={<GlossaryTerm term="Trail Braking">Trail Braking</GlossaryTerm>} grade={cornerGrade.trail_braking} />
          )}
          {cornerGrade.min_speed && <GradeRow label={<GlossaryTerm term="Min Speed">Min Speed</GlossaryTerm>} grade={cornerGrade.min_speed} />}
          {cornerGrade.throttle && <GradeRow label="Throttle" grade={cornerGrade.throttle} />}
        </div>
      )}

      {/* AI coaching tip */}
      {(priorityCorner?.tip || cornerGrade?.notes) && (
        <AiInsight mode="card">
          <p className="text-xs leading-relaxed">{priorityCorner?.tip ?? cornerGrade?.notes}</p>
        </AiInsight>
      )}
    </div>
  );
}
