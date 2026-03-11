'use client';

import { useMemo, useState } from 'react';
import { useUnits } from '@/hooks/useUnits';
import type { CornerConsistencyEntry } from '@/lib/types';

type SortKey = 'corner' | 'score' | 'brake' | 'speed';

interface CornerConsistencyTableProps {
  corners: CornerConsistencyEntry[];
  onCornerClick?: (corner: number) => void;
}

function scoreColor(score: number): string {
  if (score >= 80) return 'text-[var(--grade-a)]';
  if (score >= 60) return 'text-[var(--text-primary)]';
  return 'text-[var(--color-brake)]';
}

export function CornerConsistencyTable({ corners, onCornerClick }: CornerConsistencyTableProps) {
  const { formatSpeed, formatDistance } = useUnits();
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortAsc, setSortAsc] = useState(true);

  const sorted = useMemo(() => {
    const copy = [...corners];
    copy.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'corner':
          cmp = a.corner_number - b.corner_number;
          break;
        case 'score':
          cmp = a.consistency_score - b.consistency_score;
          break;
        case 'brake':
          cmp = (a.brake_point_std_m ?? 999) - (b.brake_point_std_m ?? 999);
          break;
        case 'speed':
          cmp = a.min_speed_std_mph - b.min_speed_std_mph;
          break;
      }
      return sortAsc ? cmp : -cmp;
    });
    return copy;
  }, [corners, sortKey, sortAsc]);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc((prev) => !prev);
    } else {
      setSortKey(key);
      setSortAsc(key === 'corner'); // corner sorts asc by default, others asc (lowest = worst → top)
    }
  }

  function sortIndicator(key: SortKey) {
    if (sortKey !== key) return '';
    return sortAsc ? ' ↑' : ' ↓';
  }

  return (
    <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5">
      <h3 className="mb-3 border-l-[3px] border-[var(--text-secondary)] pl-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-[var(--text-secondary)]">
        Corner Consistency
      </h3>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--cata-border)] text-xs uppercase tracking-wider text-[var(--text-secondary)]">
              <th className="cursor-pointer px-2 py-2" onClick={() => handleSort('corner')}>
                Corner{sortIndicator('corner')}
              </th>
              <th className="cursor-pointer px-2 py-2 text-right" onClick={() => handleSort('score')}>
                Score{sortIndicator('score')}
              </th>
              <th className="cursor-pointer px-2 py-2 text-right" onClick={() => handleSort('brake')}>
                Brake Std{sortIndicator('brake')}
              </th>
              <th className="cursor-pointer px-2 py-2 text-right" onClick={() => handleSort('speed')}>
                Speed Std{sortIndicator('speed')}
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((c) => (
              <tr
                key={c.corner_number}
                className={`border-b border-[var(--cata-border)]/50 transition-colors ${
                  onCornerClick ? 'cursor-pointer hover:bg-[var(--bg-elevated)]' : ''
                }`}
                onClick={onCornerClick ? () => onCornerClick(c.corner_number) : undefined}
              >
                <td className="px-2 py-2 font-medium text-[var(--text-primary)]">
                  T{c.corner_number}
                </td>
                <td className={`px-2 py-2 text-right font-mono ${scoreColor(c.consistency_score)}`}>
                  {Math.round(c.consistency_score)}
                </td>
                <td className="px-2 py-2 text-right font-mono text-[var(--text-secondary)]">
                  {c.brake_point_std_m != null ? `±${formatDistance(c.brake_point_std_m, 1)}` : '—'}
                </td>
                <td className="px-2 py-2 text-right font-mono text-[var(--text-secondary)]">
                  ±{formatSpeed(c.min_speed_std_mph, 1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-[11px] text-[var(--text-secondary)]">
        Click a corner to explore in Deep Dive. Sorted by consistency score (lowest first).
      </p>
    </div>
  );
}
