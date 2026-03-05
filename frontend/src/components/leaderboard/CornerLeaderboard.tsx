'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { useCornerLeaderboard } from '@/hooks/useLeaderboard';
import { useUnits } from '@/hooks/useUnits';
import type { CornerRecordEntry } from '@/lib/types';
import { KingBadge } from './KingBadge';
import { LeaderboardCompareCard } from './LeaderboardCompareCard';
import { cn } from '@/lib/utils';

const CATEGORIES = [
  { key: 'sector_time', label: 'Corner King', icon: '\u{1F451}' },
  { key: 'min_speed', label: 'Apex Predator', icon: '\u{1F3AF}' },
  { key: 'brake_point', label: 'Late Braker', icon: '\u{1F6D1}' },
  { key: 'consistency', label: 'Smooth Operator', icon: '\u{1F3B6}' },
] as const;

type CategoryKey = (typeof CATEGORIES)[number]['key'];

interface CornerLeaderboardProps {
  trackName: string;
  cornerNumber: number;
  limit?: number;
}

function formatTime(seconds: number): string {
  return seconds.toFixed(3) + 's';
}

const MPS_TO_MPH = 2.23694;

function formatCV(cv: number): string {
  return (cv * 100).toFixed(2) + '%';
}

function MetricColumns({
  category,
  entry,
}: {
  category: CategoryKey;
  entry: CornerRecordEntry;
}) {
  const { formatSpeed, formatDistance } = useUnits();
  const fmtSpd = (mps: number) => formatSpeed(mps * MPS_TO_MPH);
  switch (category) {
    case 'sector_time':
      return (
        <>
          <td className="px-4 py-2 text-right font-mono text-zinc-300">
            {formatTime(entry.sector_time_s)}
          </td>
          <td className="px-4 py-2 text-right text-zinc-400">
            {fmtSpd(entry.min_speed_mps)}
          </td>
        </>
      );
    case 'min_speed':
      return (
        <>
          <td className="px-4 py-2 text-right font-mono text-zinc-300">
            {fmtSpd(entry.min_speed_mps)}
          </td>
          <td className="px-4 py-2 text-right text-zinc-400">
            {formatTime(entry.sector_time_s)}
          </td>
        </>
      );
    case 'brake_point':
      return (
        <>
          <td className="px-4 py-2 text-right font-mono text-zinc-300">
            {entry.brake_point_m != null ? formatDistance(entry.brake_point_m) : '--'}
          </td>
          <td className="px-4 py-2 text-right text-zinc-400">
            {formatTime(entry.sector_time_s)}
          </td>
        </>
      );
    case 'consistency':
      return (
        <>
          <td className="px-4 py-2 text-right font-mono text-zinc-300">
            {entry.consistency_cv != null ? formatCV(entry.consistency_cv) : '--'}
          </td>
          <td className="px-4 py-2 text-right text-zinc-400">
            {formatTime(entry.sector_time_s)}
          </td>
        </>
      );
  }
}

function getColumnHeaders(category: CategoryKey): [string, string] {
  switch (category) {
    case 'sector_time':
      return ['Time', 'Min Speed'];
    case 'min_speed':
      return ['Min Speed', 'Time'];
    case 'brake_point':
      return ['Brake Dist', 'Time'];
    case 'consistency':
      return ['CV', 'Time'];
  }
}

export function CornerLeaderboard({
  trackName,
  cornerNumber,
  limit = 10,
}: CornerLeaderboardProps) {
  const [category, setCategory] = useState<CategoryKey>('sector_time');
  const [selectedEntry, setSelectedEntry] = useState<CornerRecordEntry | null>(null);

  const { data, isLoading, error } = useCornerLeaderboard(
    trackName,
    cornerNumber,
    limit,
    category,
  );

  // Find the user's own entry — use king entry or fall back to first entry
  const userEntry = useMemo(() => {
    if (!data || data.entries.length === 0) return null;
    return data.entries.find((e) => e.is_king) ?? data.entries[0];
  }, [data]);

  const handleSharePosition = useCallback(async () => {
    const categoryLabel =
      CATEGORIES.find((c) => c.key === category)?.label ?? 'Corner King';
    const text = `Check out the ${categoryLabel} leaderboard for Turn ${cornerNumber} at ${trackName}!`;

    if (typeof navigator === 'undefined') return;
    if ('share' in navigator) {
      try {
        await (navigator as Navigator).share({ text, url: window.location.href });
      } catch {
        /* user cancelled */
      }
    } else {
      await (navigator as Navigator).clipboard.writeText(text);
    }
  }, [category, cornerNumber, trackName]);

  const [primaryHeader, secondaryHeader] = getColumnHeaders(category);

  if (isLoading) {
    return (
      <div className="animate-pulse text-sm text-zinc-400">
        Loading leaderboard...
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-sm text-red-400">
        Failed to load leaderboard
      </div>
    );
  }

  const isEmpty = !data || data.entries.length === 0;

  return (
    <div className="relative rounded-lg border border-zinc-700 bg-zinc-800/50 overflow-hidden">
      {/* Compare overlay */}
      {selectedEntry && userEntry && selectedEntry.rank !== userEntry.rank && (
        <LeaderboardCompareCard
          yourEntry={userEntry}
          theirEntry={selectedEntry}
          cornerNumber={cornerNumber}
          onClose={() => setSelectedEntry(null)}
        />
      )}

      {/* Category tabs — always visible so user can switch categories */}
      <div className="flex gap-1 overflow-x-auto px-4 py-2">
        {CATEGORIES.map((c) => (
          <button
            key={c.key}
            type="button"
            onClick={() => setCategory(c.key)}
            className={cn(
              'whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium transition-colors',
              category === c.key
                ? 'bg-[var(--cata-accent)] text-white'
                : 'bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
            )}
          >
            {c.icon} {c.label}
          </button>
        ))}
      </div>

      <div className="px-4 py-3 border-b border-zinc-700">
        <h3 className="text-sm font-semibold text-zinc-200">
          Corner {cornerNumber} Leaderboard
        </h3>
      </div>

      {isEmpty ? (
        <div className="px-4 py-6 text-center text-sm text-zinc-500">
          No leaderboard data for this category yet.
        </div>
      ) : (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-zinc-400 border-b border-zinc-700/50">
                <th className="px-4 py-2 text-left w-12">#</th>
                <th className="px-4 py-2 text-left">Driver</th>
                <th className="px-4 py-2 text-right">{primaryHeader}</th>
                <th className="px-4 py-2 text-right">{secondaryHeader}</th>
              </tr>
            </thead>
            <tbody>
              {data.entries.map((entry: CornerRecordEntry) => (
                <tr
                  key={entry.rank}
                  onClick={() => setSelectedEntry(entry)}
                  className={cn(
                    'border-b border-zinc-700/30 cursor-pointer transition-colors',
                    entry.is_king
                      ? 'bg-yellow-500/10'
                      : 'hover:bg-zinc-700/30',
                    selectedEntry?.rank === entry.rank && 'ring-1 ring-inset ring-[var(--cata-accent)]',
                  )}
                >
                  <td className="px-4 py-2 text-zinc-400 font-mono">
                    {entry.rank}
                  </td>
                  <td className="px-4 py-2 text-zinc-200 flex items-center gap-2">
                    {entry.user_name}
                    {entry.is_king && <KingBadge />}
                  </td>
                  <MetricColumns category={category} entry={entry} />
                </tr>
              ))}
            </tbody>
          </table>

          {/* Share footer */}
          <div className="flex items-center justify-between px-4 py-2 border-t border-[var(--cata-border)]">
            <span className="text-xs text-[var(--text-muted)]">
              {CATEGORIES.find((c) => c.key === category)?.label}
            </span>
            <button
              type="button"
              onClick={handleSharePosition}
              className="flex items-center gap-1 text-xs font-medium text-[var(--cata-accent)] hover:underline"
            >
              Share My Position
            </button>
          </div>
        </>
      )}
    </div>
  );
}
