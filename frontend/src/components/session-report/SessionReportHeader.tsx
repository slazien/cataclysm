'use client';

import type { SessionSummary, GPSQualityReport } from '@/lib/types';
import { ShareButton } from '@/components/dashboard/ShareButton';
import { ShareSessionDialog } from '@/components/comparison/ShareSessionDialog';
import { AssignEquipmentButton } from '@/components/equipment/AssignEquipmentButton';
import { useUnits } from '@/hooks/useUnits';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface SessionReportHeaderProps {
  session: SessionSummary | null;
  gpsQuality: GPSQualityReport | null;
  sessionId?: string;
}

/** Map score 0-100 to a hex color. */
function scoreHex(score: number): string {
  if (score >= 80) return '#22c55e'; // green-500
  if (score >= 60) return '#f59e0b'; // amber-500
  return '#ef4444'; // red-500
}

function scoreTw(score: number): string {
  if (score >= 80) return 'text-green-400';
  if (score >= 60) return 'text-yellow-400';
  return 'text-red-400';
}

/** SVG circular progress ring — fills clockwise from 12 o'clock. */
function ScoreRing({ score }: { score: number | null }) {
  const SIZE = 80;
  const STROKE = 4;
  const R = (SIZE - STROKE) / 2;
  const C = 2 * Math.PI * R;

  const pct = score != null ? Math.min(100, Math.max(0, score)) / 100 : 0;
  const offset = C * (1 - pct);
  const color = score != null ? scoreHex(score) : 'var(--cata-border)';

  return (
    <svg
      width={SIZE}
      height={SIZE}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="absolute inset-0"
    >
      {/* Background track */}
      <circle
        cx={SIZE / 2}
        cy={SIZE / 2}
        r={R}
        fill="none"
        stroke="var(--cata-border)"
        strokeWidth={STROKE}
        opacity={0.3}
      />
      {/* Clockwise progress arc starting at 12 o'clock */}
      {score != null && (
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={R}
          fill="none"
          stroke={color}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={C}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
          className="transition-all duration-700 ease-out"
        />
      )}
    </svg>
  );
}

function BreakdownRow({ label, value }: { label: string; value: number | null | undefined }) {
  if (value == null) return null;
  const rounded = Math.round(value);
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-xs text-[var(--text-muted)]">{label}</span>
      <span className={`text-xs font-semibold tabular-nums ${scoreTw(rounded)}`}>
        {rounded}
      </span>
    </div>
  );
}

export function SessionReportHeader({ session, gpsQuality, sessionId }: SessionReportHeaderProps) {
  const { formatTemp } = useUnits();
  const score = session?.session_score;
  const hasBreakdown =
    session?.score_consistency != null ||
    session?.score_pace != null ||
    session?.score_technique != null;

  const scoreCircle = (
    <div className="relative flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)]">
      <ScoreRing score={score ?? null} />
      <span className={`relative font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight ${score != null ? scoreTw(score) : 'text-[var(--text-muted)]'}`}>
        {score != null ? Math.round(score) : '\u2014'}
      </span>
      <span className="absolute -bottom-1 rounded-full bg-[var(--bg-surface)] px-1.5 text-[10px] font-medium text-[var(--text-muted)]">
        SCORE
      </span>
    </div>
  );

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-5">
      {/* Score circle with breakdown tooltip */}
      {hasBreakdown ? (
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger asChild>
              <button type="button" className="cursor-default">
                {scoreCircle}
              </button>
            </TooltipTrigger>
            <TooltipContent
              side="bottom"
              sideOffset={8}
              className="w-44 space-y-1.5 p-3"
            >
              <p className="mb-1 text-xs font-medium text-[var(--text-primary)]">Score Breakdown</p>
              <BreakdownRow label="Consistency" value={session?.score_consistency} />
              <BreakdownRow label="Pace" value={session?.score_pace} />
              <BreakdownRow label="Technique" value={session?.score_technique} />
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ) : (
        scoreCircle
      )}

      {/* Track info */}
      <div className="min-w-0 flex-1">
        <h1 className="truncate font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight text-[var(--text-primary)]">
          {session?.track_name ?? 'Loading...'}
        </h1>
        <p className="text-sm text-[var(--text-muted)]">{session?.session_date ?? ''}</p>
      </div>

      {/* Badges + Share actions */}
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        {gpsQuality && (
          <span className="rounded-full bg-[var(--bg-elevated)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
            GPS {gpsQuality.grade}
          </span>
        )}
        {session?.weather_condition && (
          <span className="rounded-full bg-[var(--bg-elevated)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
            {session.weather_temp_c != null ? formatTemp(session.weather_temp_c) : ''} {session.weather_condition}
          </span>
        )}
        {sessionId && (
          <>
            <AssignEquipmentButton sessionId={sessionId} />
            <ShareButton sessionId={sessionId} />
            <ShareSessionDialog sessionId={sessionId} />
          </>
        )}
      </div>
    </div>
  );
}
