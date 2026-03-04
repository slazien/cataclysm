'use client';

import { cn } from '@/lib/utils';

interface CornerDeltaRow {
  corner_number: number;
  time_a?: number;
  time_b?: number;
  a_min_speed_mph: number;
  b_min_speed_mph: number;
  speed_diff_mph: number;
  entry_distance_m: number;
  exit_distance_m: number;
}

interface CornerScorecardProps {
  cornerDeltas: CornerDeltaRow[];
  onSelectCorner: (corner: number) => void;
  selectedCorner: number | null;
}

export function CornerScorecard({
  cornerDeltas,
  onSelectCorner,
  selectedCorner,
}: CornerScorecardProps) {
  if (cornerDeltas.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-6 text-center">
        <p className="text-sm text-[var(--text-muted)]">No corner data available</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      <h2 className="mb-3 text-sm font-medium text-[var(--text-primary)] font-[family-name:var(--font-display)]">
        Corner-by-Corner Scorecard
      </h2>
      <p className="mb-4 text-xs text-[var(--text-secondary)]">
        Click a corner to see the delta chart below
      </p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--cata-border)]">
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Corner
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                A Speed
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                B Speed
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Delta
              </th>
            </tr>
          </thead>
          <tbody>
            {cornerDeltas.map((cd) => {
              const isSelected = selectedCorner === cd.corner_number;
              const isPositive = cd.speed_diff_mph > 0;
              const isNegative = cd.speed_diff_mph < 0;

              // Determine which driver has better speed per corner
              const aFasterSpeed = cd.a_min_speed_mph > cd.b_min_speed_mph;
              const bFasterSpeed = cd.b_min_speed_mph > cd.a_min_speed_mph;

              return (
                <tr
                  key={cd.corner_number}
                  onClick={() => onSelectCorner(cd.corner_number)}
                  className={cn(
                    'cursor-pointer border-b border-[var(--cata-border)]/50 transition-colors',
                    isSelected
                      ? 'border-l-2 border-l-[var(--cata-accent)] bg-[var(--cata-accent)]/5'
                      : 'hover:bg-[var(--bg-elevated)]',
                  )}
                >
                  <td className="px-3 py-2 font-medium text-[var(--text-primary)]">
                    T{cd.corner_number}
                  </td>
                  <td
                    className={cn(
                      'px-3 py-2 text-right font-mono',
                      aFasterSpeed
                        ? 'font-medium text-[var(--color-throttle)]'
                        : 'text-[var(--text-secondary)]',
                    )}
                  >
                    {cd.a_min_speed_mph.toFixed(1)} mph
                  </td>
                  <td
                    className={cn(
                      'px-3 py-2 text-right font-mono',
                      bFasterSpeed
                        ? 'font-medium text-[var(--color-throttle)]'
                        : 'text-[var(--text-secondary)]',
                    )}
                  >
                    {cd.b_min_speed_mph.toFixed(1)} mph
                  </td>
                  <td
                    className={cn(
                      'px-3 py-2 text-right font-mono font-medium',
                      isPositive && 'text-[var(--color-throttle)]',
                      isNegative && 'text-[var(--color-brake)]',
                      !isPositive && !isNegative && 'text-[var(--text-muted)]',
                    )}
                  >
                    {isPositive ? '+' : ''}
                    {cd.speed_diff_mph.toFixed(1)} mph
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
