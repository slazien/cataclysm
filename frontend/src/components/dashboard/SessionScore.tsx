'use client';

import { useState, useEffect, useRef } from 'react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

export interface ScoreBreakdown {
  consistency: number | null;
  optimal: number | null;
  grades: number | null;
}

interface SessionScoreProps {
  score: number | null;
  breakdown: ScoreBreakdown | null;
  isLoading: boolean;
}

const SIZE = 120;
const STROKE_WIDTH = 10;
const RADIUS = (SIZE - STROKE_WIDTH) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function getScoreColor(score: number): string {
  if (score >= 80) return 'var(--color-throttle)'; // green
  if (score >= 60) return 'var(--color-neutral)';  // amber
  return 'var(--color-brake)';                      // red
}

function getSubtitle(score: number): string {
  if (score >= 80) return 'Strong session';
  if (score >= 60) return 'Room to improve';
  return 'Focus on fundamentals';
}

const BREAKDOWN_ROWS: { key: keyof ScoreBreakdown; label: string; weight: string }[] = [
  { key: 'consistency', label: 'Consistency', weight: '40%' },
  { key: 'optimal', label: 'Pace', weight: '30%' },
  { key: 'grades', label: 'Corner Grades', weight: '30%' },
];

function ScoreRow({ label, weight, value }: { label: string; weight: string; value: number }) {
  const color = getScoreColor(value);
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-[var(--text-secondary)]">
        {label} <span className="text-[var(--text-muted)]">({weight})</span>
      </span>
      <span className="font-semibold tabular-nums" style={{ color }}>
        {Math.round(value)}
      </span>
    </div>
  );
}

export function SessionScore({ score, breakdown, isLoading }: SessionScoreProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const animatedRef = useRef(false);

  useEffect(() => {
    if (score === null || isLoading) {
      setDisplayValue(0);
      animatedRef.current = false;
      return;
    }

    const target = Math.round(score);
    if (animatedRef.current) {
      setDisplayValue(target);
      return;
    }
    animatedRef.current = true;

    let start: number | null = null;
    const duration = 800; // ms
    let rafId: number;

    function animate(ts: number) {
      if (start === null) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(Math.round(eased * target));
      if (progress < 1) {
        rafId = requestAnimationFrame(animate);
      }
    }

    rafId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(rafId);
    };
  }, [score, isLoading]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-3">
        <div className="h-[120px] w-[120px] animate-pulse rounded-full bg-[var(--bg-elevated)]" />
      </div>
    );
  }

  const displayScore = score !== null ? displayValue : null;
  const fraction = displayScore !== null ? Math.min(Math.max(displayScore / 100, 0), 1) : 0;
  const dashOffset = CIRCUMFERENCE * (1 - fraction);
  const color = displayScore !== null ? getScoreColor(displayScore) : 'var(--text-muted)';

  const hasBreakdown = breakdown && Object.values(breakdown).some((v) => v !== null);

  const ring = (
    <div className="flex flex-col items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-3">
      <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
        Session Score
      </p>
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <svg
          width={SIZE}
          height={SIZE}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          className="-rotate-90"
        >
          {/* Background ring */}
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke="var(--bg-elevated)"
            strokeWidth={STROKE_WIDTH}
          />
          {/* Score arc */}
          {displayScore !== null && (
            <circle
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              stroke={color}
              strokeWidth={STROKE_WIDTH}
              strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={dashOffset}
              style={{ transition: 'stroke-dashoffset 0.6s ease-out, stroke 0.3s ease' }}
            />
          )}
        </svg>
        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="text-2xl font-bold tabular-nums"
            style={{ color }}
          >
            {displayScore !== null ? displayScore : '--'}
          </span>
          <span className="text-[10px] font-medium text-[var(--text-muted)]">/ 100</span>
        </div>
      </div>
      {displayScore !== null && (
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          {getSubtitle(displayScore)}
        </p>
      )}
    </div>
  );

  if (!hasBreakdown) return ring;

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="cursor-help">{ring}</div>
        </TooltipTrigger>
        <TooltipContent
          side="bottom"
          sideOffset={8}
          className="w-56 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-3 py-2.5 text-xs shadow-xl"
        >
          <p className="mb-1.5 font-semibold text-[var(--text-primary)]">Score Breakdown</p>
          <div className="flex flex-col gap-1">
            {BREAKDOWN_ROWS.map(({ key, label, weight }) => {
              const value = breakdown[key];
              if (value === null) return null;
              return <ScoreRow key={key} label={label} weight={weight} value={value} />;
            })}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
