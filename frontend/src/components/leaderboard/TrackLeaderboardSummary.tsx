'use client';

import { useMemo } from 'react';
import { Trophy, Target, TrendingUp, Crown } from 'lucide-react';
import { useCornerKings, useCornerLeaderboard } from '@/hooks/useLeaderboard';
import { cn } from '@/lib/utils';

interface TrackLeaderboardSummaryProps {
  trackName: string;
}

interface RankCardProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  subtitle: string;
  accent?: boolean;
}

function RankCard({ icon: Icon, label, value, subtitle, accent }: RankCardProps) {
  return (
    <div className="flex flex-col items-center gap-1.5 rounded-lg bg-[var(--bg-elevated)] p-3">
      <Icon
        className={cn(
          'h-4 w-4',
          accent ? 'text-yellow-400' : 'text-[var(--text-muted)]',
        )}
      />
      <span className="font-[family-name:var(--font-display)] text-lg font-bold tracking-tight text-[var(--text-primary)]">
        {value}
      </span>
      <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
        {label}
      </span>
      <span className="text-[10px] text-[var(--text-secondary)]">{subtitle}</span>
    </div>
  );
}

export function TrackLeaderboardSummary({ trackName }: TrackLeaderboardSummaryProps) {
  // Fetch sector_time leaderboard for corner 1 as a proxy for "best lap rank"
  const { data: sectorData } = useCornerLeaderboard(trackName, 1, 10, 'sector_time');
  const { data: consistencyData } = useCornerLeaderboard(trackName, 1, 10, 'consistency');
  const { data: kingsData } = useCornerKings(trackName);

  const summary = useMemo(() => {
    // Best Lap rank: find the first entry marked as the user or first entry
    const bestLapRank = sectorData?.entries?.[0]?.rank ?? null;
    const consistencyRank = consistencyData?.entries?.[0]?.rank ?? null;

    // Corner Kings count: how many corners the user is king of
    const cornerKingsCount = kingsData?.kings?.length ?? 0;

    return { bestLapRank, consistencyRank, cornerKingsCount };
  }, [sectorData, consistencyData, kingsData]);

  const hasAnyData =
    summary.bestLapRank !== null ||
    summary.consistencyRank !== null ||
    summary.cornerKingsCount > 0;

  return (
    <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">
        Track Leaderboard
      </h3>
      {hasAnyData ? (
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          <RankCard
            icon={Trophy}
            label="Best Lap"
            value={summary.bestLapRank !== null ? `#${summary.bestLapRank}` : '--'}
            subtitle="Sector time"
          />
          <RankCard
            icon={Target}
            label="Consistency"
            value={summary.consistencyRank !== null ? `#${summary.consistencyRank}` : '--'}
            subtitle="CV ranking"
          />
          <RankCard
            icon={TrendingUp}
            label="Progress"
            value="--"
            subtitle="Coming soon"
          />
          <RankCard
            icon={Crown}
            label="Corner Kings"
            value={String(summary.cornerKingsCount)}
            subtitle={summary.cornerKingsCount === 1 ? '1 crown' : `${summary.cornerKingsCount} crowns`}
            accent={summary.cornerKingsCount > 0}
          />
        </div>
      ) : (
        <p className="text-sm text-[var(--text-muted)]">
          No leaderboard data available yet.
        </p>
      )}
    </div>
  );
}
