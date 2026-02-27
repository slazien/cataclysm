'use client';

import { useState, useMemo } from 'react';
import { ArrowUpDown, Download } from 'lucide-react';
import { useSessionStore } from '@/stores';
import { useSessionLaps } from '@/hooks/useSession';
import { useSkillLevel } from '@/hooks/useSkillLevel';
import { formatLapTime } from '@/lib/formatters';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const MPS_TO_MPH = 2.23694;

type SortKey = 'lap_number' | 'lap_time_s' | 'max_speed_mps' | 'lap_distance_m';
type SortDir = 'asc' | 'desc';

export function RawDataTable() {
  const { showFeature } = useSkillLevel();
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { data: laps } = useSessionLaps(activeSessionId);
  const [sortKey, setSortKey] = useState<SortKey>('lap_number');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const sortedLaps = useMemo(() => {
    if (!laps) return [];
    return [...laps].sort((a, b) => {
      const aVal = a[sortKey] ?? 0;
      const bVal = b[sortKey] ?? 0;
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
    });
  }, [laps, sortKey, sortDir]);

  if (!showFeature('raw_data_table') || !laps || laps.length === 0) return null;

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  function handleExport() {
    if (!laps) return;
    const headers = ['Lap', 'Time (s)', 'Clean', 'Distance (m)', 'Max Speed (mph)'];
    const rows = laps.map((l) => [
      l.lap_number,
      l.lap_time_s?.toFixed(3) ?? '',
      l.is_clean ? 'Yes' : 'No',
      l.lap_distance_m?.toFixed(1) ?? '',
      (l.max_speed_mps * MPS_TO_MPH).toFixed(1),
    ]);
    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `laps_${activeSessionId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const columns: { key: SortKey; label: string }[] = [
    { key: 'lap_number', label: 'Lap' },
    { key: 'lap_time_s', label: 'Time' },
    { key: 'max_speed_mps', label: 'Max Speed' },
    { key: 'lap_distance_m', label: 'Distance' },
  ];

  return (
    <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">Raw Lap Data</h3>
        <Button variant="ghost" size="sm" onClick={handleExport} className="gap-1.5 text-xs">
          <Download className="h-3.5 w-3.5" />
          Export CSV
        </Button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--cata-border)]">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="cursor-pointer px-3 py-2 text-left text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                  onClick={() => toggleSort(col.key)}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    <ArrowUpDown className={cn('h-3 w-3', sortKey === col.key ? 'text-[var(--cata-accent)]' : 'opacity-30')} />
                  </span>
                </th>
              ))}
              <th className="px-3 py-2 text-left text-xs font-medium text-[var(--text-muted)]">
                Clean
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedLaps.map((lap) => (
              <tr key={lap.lap_number} className="border-b border-[var(--cata-border)]/50 hover:bg-[var(--bg-elevated)]">
                <td className="px-3 py-1.5 text-[var(--text-primary)]">L{lap.lap_number}</td>
                <td className="px-3 py-1.5 font-mono text-[var(--text-primary)]">{formatLapTime(lap.lap_time_s)}</td>
                <td className="px-3 py-1.5 text-[var(--text-secondary)]">{(lap.max_speed_mps * MPS_TO_MPH).toFixed(1)} mph</td>
                <td className="px-3 py-1.5 text-[var(--text-secondary)]">{lap.lap_distance_m.toFixed(0)} m</td>
                <td className="px-3 py-1.5">
                  <span className={cn(
                    'inline-block rounded px-1.5 py-0.5 text-xs font-medium',
                    lap.is_clean
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'bg-amber-500/10 text-amber-400',
                  )}>
                    {lap.is_clean ? 'Yes' : 'No'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
