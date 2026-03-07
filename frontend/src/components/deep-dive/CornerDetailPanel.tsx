'use client';

import { useCorners, useAllLapCorners, useOptimalComparison, useLineAnalysis } from '@/hooks/useAnalysis';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useAnalysisStore, useSessionStore } from '@/stores';
import { useSession } from '@/hooks/useSession';
import { GlossaryTerm } from '@/components/shared/GlossaryTerm';
import { CornerLeaderboard } from '@/components/leaderboard/CornerLeaderboard';
import { GradeChip } from '@/components/shared/GradeChip';
import { AiInsight } from '@/components/shared/AiInsight';
import { MarkdownText } from '@/components/shared/MarkdownText';
import { colors } from '@/lib/design-tokens';
import { worstGrade } from '@/lib/gradeUtils';
import { parseCornerNumber } from '@/lib/cornerUtils';
import { useUnits } from '@/hooks/useUnits';
import { useSkillLevel } from '@/hooks/useSkillLevel';
import { gradeExplanation } from '@/lib/skill-content';
import { InfoTooltip } from '@/components/shared/InfoTooltip';
import { CornerLineMap } from '@/components/deep-dive/charts/CornerLineMap';
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
  reason?: string;
  explanation?: string | null;
}

function GradeRow({ label, grade, reason, explanation }: GradeRowProps) {
  return (
    <div className="py-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-[var(--text-secondary)]">{label}</span>
        <GradeChip grade={grade} reason={reason} />
      </div>
      {explanation && (
        <p className="mt-0.5 text-[11px] leading-snug text-[var(--text-secondary)]">
          {explanation}
        </p>
      )}
    </div>
  );
}

export function CornerDetailPanel({ sessionId }: CornerDetailPanelProps) {
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { data: session } = useSession(activeSessionId);
  const { data: corners } = useCorners(sessionId);
  const { data: allLapCorners } = useAllLapCorners(sessionId);
  const { data: report } = useCoachingReport(sessionId);
  const { data: optimalComparison } = useOptimalComparison(sessionId);
  const { data: lineData } = useLineAnalysis(sessionId);
  const { convertSpeed, convertDistance, speedUnit, distanceUnit, resolveSpeed } = useUnits();
  const { skillLevel, showFeature } = useSkillLevel();
  const showExplanations = showFeature('grade_explanations');

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

  // Use selected lap's corner data when exactly one lap is selected,
  // otherwise fall back to best-lap corners.
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

  // Grade info
  const cornerGrade: CornerGrade | undefined = report?.corner_grades?.find(
    (cg) => cg.corner === cornerNumber,
  );

  // Priority corner tip
  const priorityCorner: PriorityCorner | undefined = report?.priority_corners?.find(
    (pc) => pc.corner === cornerNumber,
  );

  // Optimal comparison for this corner
  const optimalOpp = optimalComparison?.is_valid
    ? optimalComparison.corner_opportunities?.find((o) => o.corner_number === cornerNumber) ?? null
    : null;

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
          {optimalOpp && optimalOpp.time_cost_s !== 0 && (
            <span
              className="text-sm font-medium tabular-nums"
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
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-[var(--text-secondary)]">
            {displayLap ? `L${displayLap}` : 'Best lap'}{apexLabel ? ` · ${apexLabel}` : ''}
          </span>
          <kbd className="rounded border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-1 py-0.5 font-mono text-[10px] text-[var(--text-secondary)]">←→</kbd>
        </div>
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
            value={convertDistance(corner.brake_point_m).toFixed(0)}
            unit={distanceUnit}
            delta={brakePointDelta !== null ? convertDistance(brakePointDelta) : null}
            deltaUnit={distanceUnit}
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
            value={convertDistance(corner.throttle_commit_m).toFixed(0)}
            unit={distanceUnit}
            delta={throttleDelta !== null ? convertDistance(throttleDelta) : null}
            deltaUnit={distanceUnit}
            invertDelta
          />
        )}
        {optimalOpp && (
          <KpiRow
            label="Optimal Min Speed"
            value={convertSpeed(optimalOpp.optimal_min_speed_mph).toFixed(1)}
            unit={speedUnit}
          />
        )}
      </div>

      {/* Per-category grades */}
      {cornerGrade && (
        <div className="space-y-0.5 pt-3 mt-1 border-t border-[var(--cata-border)]">
          <h4 className="mb-1 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
            Grades
            <InfoTooltip helpKey="section.corner-grades" />
          </h4>
          {cornerGrade.braking && (
            <GradeRow
              label="Braking"
              grade={cornerGrade.braking}
              reason={cornerGrade.braking_reason}
              explanation={showExplanations ? gradeExplanation(cornerGrade.braking, 'braking', skillLevel) : null}
            />
          )}
          {cornerGrade.trail_braking && (
            <GradeRow
              label={<GlossaryTerm term="Trail Braking">Trail Braking</GlossaryTerm>}
              grade={cornerGrade.trail_braking}
              reason={cornerGrade.trail_braking_reason}
              explanation={showExplanations ? gradeExplanation(cornerGrade.trail_braking, 'trail_braking', skillLevel) : null}
            />
          )}
          {cornerGrade.min_speed && (
            <GradeRow
              label={<GlossaryTerm term="Min Speed">Min Speed</GlossaryTerm>}
              grade={cornerGrade.min_speed}
              reason={cornerGrade.min_speed_reason}
              explanation={showExplanations ? gradeExplanation(cornerGrade.min_speed, 'min_speed', skillLevel) : null}
            />
          )}
          {cornerGrade.throttle && (
            <GradeRow
              label="Throttle"
              grade={cornerGrade.throttle}
              reason={cornerGrade.throttle_reason}
              explanation={showExplanations ? gradeExplanation(cornerGrade.throttle, 'throttle', skillLevel) : null}
            />
          )}
        </div>
      )}

      {/* AI coaching tip */}
      {(priorityCorner?.tip || cornerGrade?.notes) && (
        <div className="pt-3 mt-1 border-t border-[var(--cata-border)]">
          <AiInsight mode="card">
            <p className="text-xs leading-relaxed"><MarkdownText>{resolveSpeed(priorityCorner?.tip ?? cornerGrade?.notes ?? '')}</MarkdownText></p>
          </AiInsight>
        </div>
      )}

      {/* Bird's-eye corner line map */}
      {lineData?.available && lineData.lap_traces?.length > 0 && (
        <div className="pt-3 mt-1 border-t border-[var(--cata-border)]">
          <div className="mb-1.5 text-xs font-medium text-[var(--text-secondary)]">
            Racing Line Map
          </div>
          <div className="rounded-md border border-[var(--cata-border)] bg-[var(--bg-base)] overflow-hidden">
            <CornerLineMap sessionId={sessionId} cornerNumber={cornerNumber} />
          </div>
        </div>
      )}

      {/* Corner leaderboard */}
      {session?.track_name && (
        <div className="pt-3 mt-1 border-t border-[var(--cata-border)]">
        <CornerLeaderboard
          trackName={session.track_name}
          cornerNumber={cornerNumber}
          limit={5}
        />
        </div>
      )}
    </div>
  );
}
