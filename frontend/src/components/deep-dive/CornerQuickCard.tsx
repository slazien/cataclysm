'use client';

import { useCorners, useAllLapCorners, useLineAnalysis, useOptimalComparison } from '@/hooks/useAnalysis';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useAnalysisStore } from '@/stores';
import { GlossaryTerm } from '@/components/shared/GlossaryTerm';
import { GradeChip } from '@/components/shared/GradeChip';
import { MarkdownText } from '@/components/shared/MarkdownText';
import { colors } from '@/lib/design-tokens';
import { worstGrade } from '@/lib/gradeUtils';
import { parseCornerNumber } from '@/lib/cornerUtils';
import { useUnits } from '@/hooks/useUnits';
import type { Corner, CornerGrade, CornerLineProfile, PriorityCorner } from '@/lib/types';

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
      <span className="text-xs text-[var(--text-secondary)]">{label}</span>
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
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const setMode = useAnalysisStore((s) => s.setMode);

  const { data: corners } = useCorners(sessionId);
  const { data: report } = useCoachingReport(sessionId);
  const { data: allLapCorners } = useAllLapCorners(sessionId);
  const { data: lineData } = useLineAnalysis(sessionId);
  const { data: optimalComparison } = useOptimalComparison(sessionId);
  const { convertSpeed, convertDistance, speedUnit, distanceUnit, resolveSpeed } = useUnits();

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

  // Use the selected lap's corner data when exactly one lap is selected,
  // otherwise fall back to best-lap corners from useCorners.
  const bestLapCorner = corners?.find((c) => c.number === cornerNumber) ?? null;
  let corner: Corner | null = bestLapCorner;
  let displayLap: number | null = null;
  if (selectedLaps.length === 1 && allLapCorners) {
    const lapKey = String(selectedLaps[0]);
    const lapCorners = allLapCorners[lapKey];
    const lapCorner = lapCorners?.find((c) => c.number === cornerNumber);
    if (lapCorner) {
      corner = lapCorner;
      displayLap = selectedLaps[0];
    }
  }
  if (!corner) return null;

  // Get grade info
  const cornerGrade: CornerGrade | undefined = report?.corner_grades?.find(
    (cg) => cg.corner === cornerNumber,
  );

  // Get priority corner tip
  const priorityCorner: PriorityCorner | undefined = report?.priority_corners?.find(
    (pc) => pc.corner === cornerNumber,
  );

  // Optimal comparison for this corner
  const optimalOpp = optimalComparison?.is_valid
    ? optimalComparison.corner_opportunities?.find((o) => o.corner_number === cornerNumber) ?? null
    : null;

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
    <div className="flex flex-col gap-3 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-[var(--text-primary)]">
            Turn {cornerNumber}
          </h3>
          {overallGrade && <GradeChip grade={overallGrade} />}
          {optimalOpp && optimalOpp.time_cost_s !== 0 && (
            <span
              className="text-xs font-medium tabular-nums"
              style={{
                color: optimalOpp.time_cost_s > 0
                  ? colors.motorsport.brake
                  : colors.motorsport.throttle,
              }}
            >
              {optimalOpp.time_cost_s > 0
                ? `−${optimalOpp.time_cost_s.toFixed(2)}s`
                : `+${Math.abs(optimalOpp.time_cost_s).toFixed(2)}s`}
            </span>
          )}
        </div>
        <span className="text-xs text-[var(--text-secondary)]">
          {displayLap ? `L${displayLap}` : 'Best lap'} · {corner.apex_type} apex
        </span>
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
          value={corner.brake_point_m !== null ? convertDistance(corner.brake_point_m).toFixed(0) : '--'}
          unit={corner.brake_point_m !== null ? distanceUnit : ''}
        />
        <KpiRow
          label={<GlossaryTerm term="Peak Brake G">Peak Brake G</GlossaryTerm>}
          value={corner.peak_brake_g !== null ? corner.peak_brake_g.toFixed(2) : '--'}
          unit={corner.peak_brake_g !== null ? 'g' : ''}
        />
        <KpiRow
          label={<GlossaryTerm term="Throttle Commit">Throttle Commit</GlossaryTerm>}
          value={corner.throttle_commit_m !== null ? convertDistance(corner.throttle_commit_m).toFixed(0) : '--'}
          unit={corner.throttle_commit_m !== null ? distanceUnit : ''}
        />
        <KpiRow
          label="Entry"
          value={convertDistance(corner.entry_distance_m).toFixed(0)}
          unit={distanceUnit}
        />
        <KpiRow
          label="Exit"
          value={convertDistance(corner.exit_distance_m).toFixed(0)}
          unit={distanceUnit}
        />
        {optimalOpp && (
          <KpiRow
            label="Optimal Min Speed"
            value={convertSpeed(optimalOpp.optimal_min_speed_mph).toFixed(1)}
            unit={speedUnit}
          />
        )}
      </div>

      {/* Grade breakdown */}
      {cornerGrade && (
        <div className="flex flex-wrap gap-2">
          {cornerGrade.braking && (
            <div className="flex items-center gap-1">
              <span className="text-xs text-[var(--text-secondary)]">Braking</span>
              <GradeChip grade={cornerGrade.braking} />
            </div>
          )}
          {cornerGrade.trail_braking && (
            <div className="flex items-center gap-1">
              <span className="text-xs text-[var(--text-secondary)]"><GlossaryTerm term="Trail Braking">Trail</GlossaryTerm></span>
              <GradeChip grade={cornerGrade.trail_braking} />
            </div>
          )}
          {cornerGrade.min_speed && (
            <div className="flex items-center gap-1">
              <span className="text-xs text-[var(--text-secondary)]"><GlossaryTerm term="Min Speed">Min Spd</GlossaryTerm></span>
              <GradeChip grade={cornerGrade.min_speed} />
            </div>
          )}
          {cornerGrade.throttle && (
            <div className="flex items-center gap-1">
              <span className="text-xs text-[var(--text-secondary)]">Throttle</span>
              <GradeChip grade={cornerGrade.throttle} />
            </div>
          )}
        </div>
      )}

      {/* Line analysis (if available for this corner) */}
      {lineData?.available && (() => {
        const lp: CornerLineProfile | undefined = lineData.corner_profiles.find(
          (p) => p.corner_number === cornerNumber,
        );
        if (!lp) return null;
        const tierColor =
          lp.consistency_tier === 'expert' ? colors.grade.a
          : lp.consistency_tier === 'consistent' ? colors.grade.b
          : lp.consistency_tier === 'developing' ? colors.grade.c
          : colors.grade.f;
        const errorLabel = lp.line_error_type.replace(/_/g, ' ');
        return (
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-[var(--text-secondary)]">
                Driving Line
              </span>
              <span
                className="rounded-sm px-1.5 py-0.5 text-[10px] font-medium uppercase"
                style={{ backgroundColor: `${tierColor}20`, color: tierColor }}
              >
                {lp.consistency_tier}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-[10px] text-[var(--text-secondary)]">Entry</div>
                <div className="text-xs font-medium tabular-nums text-[var(--text-primary)]">
                  {lp.d_entry_median > 0 ? '+' : ''}{convertDistance(lp.d_entry_median).toFixed(1)}{distanceUnit}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--text-secondary)]">Apex</div>
                <div className="text-xs font-medium tabular-nums text-[var(--text-primary)]">
                  {lp.d_apex_median > 0 ? '+' : ''}{convertDistance(lp.d_apex_median).toFixed(1)}{distanceUnit}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--text-secondary)]">Exit</div>
                <div className="text-xs font-medium tabular-nums text-[var(--text-primary)]">
                  {lp.d_exit_median > 0 ? '+' : ''}{convertDistance(lp.d_exit_median).toFixed(1)}{distanceUnit}
                </div>
              </div>
            </div>
            {lp.line_error_type !== 'good_line' && (
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-[var(--text-secondary)]">Issue:</span>
                <span className="text-xs capitalize text-[var(--text-secondary)]">
                  {errorLabel}
                </span>
                <span className="text-[10px] text-[var(--text-secondary)]">
                  ({lp.severity})
                </span>
              </div>
            )}
          </div>
        );
      })()}

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
              <MarkdownText>{resolveSpeed(priorityCorner?.tip ?? cornerGrade?.notes ?? '')}</MarkdownText>
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
