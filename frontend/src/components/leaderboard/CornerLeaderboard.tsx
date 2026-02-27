'use client';

import React from 'react';
import { useCornerLeaderboard } from '@/hooks/useLeaderboard';
import type { CornerRecordEntry } from '@/lib/types';
import { KingBadge } from './KingBadge';

interface CornerLeaderboardProps {
  trackName: string;
  cornerNumber: number;
  limit?: number;
}

function formatTime(seconds: number): string {
  return seconds.toFixed(3) + 's';
}

function formatSpeed(mps: number): string {
  const mph = mps * 2.23694;
  return mph.toFixed(1) + ' mph';
}

export function CornerLeaderboard({
  trackName,
  cornerNumber,
  limit = 10,
}: CornerLeaderboardProps) {
  const { data, isLoading, error } = useCornerLeaderboard(
    trackName,
    cornerNumber,
    limit,
  );

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

  if (!data || data.entries.length === 0) {
    return (
      <div className="text-sm text-zinc-500">
        No leaderboard data yet. Opt in and upload sessions to compete!
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-700">
        <h3 className="text-sm font-semibold text-zinc-200">
          Corner {cornerNumber} Leaderboard
        </h3>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-zinc-400 border-b border-zinc-700/50">
            <th className="px-4 py-2 text-left w-12">#</th>
            <th className="px-4 py-2 text-left">Driver</th>
            <th className="px-4 py-2 text-right">Time</th>
            <th className="px-4 py-2 text-right">Min Speed</th>
          </tr>
        </thead>
        <tbody>
          {data.entries.map((entry: CornerRecordEntry) => (
            <tr
              key={entry.rank}
              className={`border-b border-zinc-700/30 ${
                entry.is_king
                  ? 'bg-yellow-500/10'
                  : 'hover:bg-zinc-700/30'
              }`}
            >
              <td className="px-4 py-2 text-zinc-400 font-mono">
                {entry.rank}
              </td>
              <td className="px-4 py-2 text-zinc-200 flex items-center gap-2">
                {entry.user_name}
                {entry.is_king && <KingBadge />}
              </td>
              <td className="px-4 py-2 text-right font-mono text-zinc-300">
                {formatTime(entry.sector_time_s)}
              </td>
              <td className="px-4 py-2 text-right text-zinc-400">
                {formatSpeed(entry.min_speed_mps)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
