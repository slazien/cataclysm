'use client';

interface SessionScoreProps {
  score: number | null;
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

export function SessionScore({ score, isLoading }: SessionScoreProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-3">
        <div className="h-[120px] w-[120px] animate-pulse rounded-full bg-[var(--bg-elevated)]" />
      </div>
    );
  }

  const displayScore = score !== null ? Math.round(score) : null;
  const fraction = displayScore !== null ? Math.min(Math.max(displayScore / 100, 0), 1) : 0;
  const dashOffset = CIRCUMFERENCE * (1 - fraction);
  const color = displayScore !== null ? getScoreColor(displayScore) : 'var(--text-muted)';

  return (
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
}
