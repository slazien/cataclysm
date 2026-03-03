'use client';

import { useEffect, useMemo, useState } from 'react';
import { motion as m } from 'motion/react';
import { useSessionStore } from '@/stores';
import { useSession } from '@/hooks/useSession';
import { useTrends, useMilestones } from '@/hooks/useTrends';
import { formatTimeShort, parseSessionDate } from '@/lib/formatters';
import { useSkillLevel } from '@/hooks/useSkillLevel';
import { ChevronDown, TrendingUp, Award, Sparkles } from 'lucide-react';
import { MetricCard } from '@/components/shared/MetricCard';
import { AiInsight } from '@/components/shared/AiInsight';
import { EmptyState } from '@/components/shared/EmptyState';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { ChartErrorBoundary } from '@/components/shared/ChartErrorBoundary';
import { TrackWatermark } from '@/components/shared/TrackWatermark';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { motion as motionTokens } from '@/lib/design-tokens';
import { useRecentAchievements } from '@/hooks/useAchievements';
import { BadgeGrid } from '@/components/achievements/BadgeGrid';
import { SeasonWrapped } from '@/components/wrapped/SeasonWrapped';
import { MilestoneTimeline } from './MilestoneTimeline';
import { LapTimeTrend } from './LapTimeTrend';
import { ConsistencyTrend } from './ConsistencyTrend';
import { CornerHeatmap } from './CornerHeatmap';
import { SessionBoxPlot } from './SessionBoxPlot';

interface TrackOption {
  name: string;
  sessionCount: number;
}

export function ProgressView() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const sessions = useSessionStore((s) => s.sessions);
  const { data: session, isLoading: sessionLoading } = useSession(activeSessionId);
  const { showFeature } = useSkillLevel();
  const { data: recentAchievementsData } = useRecentAchievements(!!activeSessionId);
  const [badgesOpen, setBadgesOpen] = useState(false);
  const [wrappedOpen, setWrappedOpen] = useState(false);

  const isWrapSeason = new Date().getMonth() >= 9; // Oct, Nov, Dec

  const recentBadges = useMemo(() => {
    const unlocked = recentAchievementsData?.newly_unlocked ?? [];
    return unlocked.slice(0, 4);
  }, [recentAchievementsData]);

  const sessionTrackName = session?.track_name ?? null;
  const [selectedTrack, setSelectedTrack] = useState<string | null>(null);

  // Reset override when active session changes so we default to the new session's track
  useEffect(() => {
    setSelectedTrack(null);
  }, [activeSessionId]);

  // Derive available tracks from all sessions, sorted by session count descending
  const availableTracks: TrackOption[] = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of sessions) {
      const name = s.track_name;
      if (!name) continue;
      counts.set(name, (counts.get(name) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([name, sessionCount]) => ({ name, sessionCount }))
      .sort((a, b) => b.sessionCount - a.sessionCount || a.name.localeCompare(b.name));
  }, [sessions]);

  const effectiveTrack = selectedTrack ?? sessionTrackName;

  const { data: trendResponse, isLoading: trendsLoading } = useTrends(effectiveTrack);
  const { data: milestoneResponse } = useMilestones(effectiveTrack);

  const trendData = trendResponse?.data ?? null;
  const milestones = milestoneResponse?.milestones ?? [];

  // Compute PB session indices (sessions where best_lap_time_s was the best so far)
  const pbSessionIndices = useMemo(() => {
    if (!trendData) return new Set<number>();
    const indices = new Set<number>();
    let bestSoFar = Infinity;
    trendData.sessions.forEach((s, i) => {
      if (s.best_lap_time_s < bestSoFar) {
        bestSoFar = s.best_lap_time_s;
        indices.add(i);
      }
    });
    return indices;
  }, [trendData]);

  // Hero metrics
  const heroMetrics = useMemo(() => {
    if (!trendData || trendData.sessions.length === 0) return null;

    const sessions = trendData.sessions;
    const n = sessions.length;

    // Best lap across all sessions
    const validBestLaps = trendData.best_lap_trend.filter((v) => v > 0);
    const bestLap = validBestLaps.length > 0 ? Math.min(...validBestLaps) : sessions[n - 1].best_lap_time_s;

    // Top 3 average from latest session
    const latestTop3 = sessions[n - 1].top3_avg_time_s;

    // Consistency trend direction
    const consistencyValues = trendData.consistency_trend;
    let consistencyDelta: number | undefined;
    if (consistencyValues.length >= 2) {
      consistencyDelta =
        consistencyValues[consistencyValues.length - 1] -
        consistencyValues[consistencyValues.length - 2];
    }
    const latestConsistency = consistencyValues[consistencyValues.length - 1] ?? 0;

    return {
      bestLap,
      latestTop3,
      sessionCount: n,
      latestConsistency,
      consistencyDelta,
    };
  }, [trendData]);

  // AI summary text
  const aiSummary = useMemo(() => {
    if (!trendData || trendData.sessions.length === 0) return null;
    const n = trendData.sessions.length;
    const latestBest = trendData.best_lap_trend[n - 1];
    const firstBest = trendData.best_lap_trend[0];
    const improvement = firstBest - latestBest;

    const parts: string[] = [];
    if (improvement > 0) {
      parts.push(
        `You've improved by ${improvement.toFixed(2)}s over ${n} session${n > 1 ? 's' : ''} at ${trendData.track_name}.`,
      );
    } else if (n === 1) {
      parts.push(`First session at ${trendData.track_name} recorded.`);
    } else {
      parts.push(
        `${n} sessions at ${trendData.track_name}. Keep pushing for consistency gains.`,
      );
    }

    if (milestones.length > 0) {
      const recent = milestones[milestones.length - 1];
      parts.push(`Latest milestone: ${recent.description}.`);
    }

    return parts.join(' ');
  }, [trendData, milestones]);

  // Journey card metrics
  const journeyMetrics = useMemo(() => {
    if (!trendData || trendData.sessions.length < 2) return null;
    const sessions = trendData.sessions;
    const first = sessions[0];
    const latest = sessions[sessions.length - 1];
    const firstBestLap = first.best_lap_time_s;
    const latestBestLap = latest.best_lap_time_s;
    const improvement = firstBestLap - latestBestLap;

    const firstDate = parseSessionDate(first.session_date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
    const latestDate = parseSessionDate(latest.session_date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });

    return { firstBestLap, latestBestLap, improvement, firstDate, latestDate };
  }, [trendData]);

  // Loading session or trends
  if (sessionLoading || trendsLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <CircularProgress size={20} />
      </div>
    );
  }

  // No session selected
  if (!activeSessionId) {
    return (
      <EmptyState
        title="No session selected"
        message="Select a session to view your progress trends"
      />
    );
  }

  // No trend data
  if (!trendData || trendData.sessions.length === 0) {
    return (
      <EmptyState
        title="No trend data"
        message="Upload multiple sessions for the same track to track your improvement journey"
        icon={TrendingUp}
      />
    );
  }

  const showHeatmap = showFeature('heatmap');
  const showBoxplot = showFeature('boxplot');
  const showBothSkillCharts = showHeatmap && showBoxplot;

  return (
    <ScrollArea className="h-full">
      <div className="relative mx-auto flex max-w-5xl flex-col gap-6 p-4 lg:p-6">
        <TrackWatermark />

        {/* Season Wrapped banner */}
        {isWrapSeason && trendData && trendData.sessions.length >= 3 && (
          <div className="rounded-xl border border-[var(--cata-accent)]/30 bg-[var(--cata-accent)]/5 p-4">
            <div className="flex items-start gap-3">
              <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-[var(--cata-accent)]" />
              <div className="min-w-0 flex-1">
                <h3 className="font-[family-name:var(--font-display)] text-sm font-semibold text-[var(--text-primary)]">
                  Your {new Date().getFullYear()} Season Wrapped is ready!
                </h3>
                <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
                  See your year in review with stats, highlights, and your driving personality.
                </p>
                <button
                  type="button"
                  onClick={() => setWrappedOpen(true)}
                  className="mt-2 rounded-lg bg-[var(--cata-accent)] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90"
                >
                  View Wrapped
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 1. Header with track selector */}
        <div>
          <div className="flex items-center gap-2">
            <span className="font-[family-name:var(--font-display)] text-lg font-semibold tracking-tight text-[var(--text-primary)]">
              Progress:
            </span>
            {availableTracks.length <= 1 ? (
              <h2 className="font-[family-name:var(--font-display)] text-lg font-semibold tracking-tight text-[var(--text-primary)]">
                {trendData.track_name}
              </h2>
            ) : (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    aria-label={`Select track, currently ${effectiveTrack}`}
                    className="flex items-center gap-1 rounded-md px-2 py-0.5 font-[family-name:var(--font-display)] text-lg font-semibold tracking-tight text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-surface)]"
                  >
                    {effectiveTrack}
                    <ChevronDown className="size-4 text-[var(--text-muted)]" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="min-w-[200px]">
                  <DropdownMenuRadioGroup
                    value={effectiveTrack ?? ''}
                    onValueChange={setSelectedTrack}
                  >
                    {availableTracks.map((t) => (
                      <DropdownMenuRadioItem
                        key={t.name}
                        value={t.name}
                        disabled={t.sessionCount < 2}
                      >
                        <span className="flex w-full items-center justify-between gap-3">
                          <span>{t.name}</span>
                          <span className="text-xs text-[var(--text-muted)]">
                            {t.sessionCount < 2
                              ? `${t.sessionCount} session`
                              : `${t.sessionCount} sessions`}
                          </span>
                        </span>
                      </DropdownMenuRadioItem>
                    ))}
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
          <p className="text-sm text-[var(--text-secondary)]">
            {trendData.n_sessions} session{trendData.n_sessions !== 1 ? 's' : ''} tracked
          </p>
        </div>

        {/* 2. AI Progress Summary (promoted) */}
        {aiSummary && (
          <AiInsight>
            <p>{aiSummary}</p>
          </AiInsight>
        )}

        {/* 3. Journey Card */}
        {heroMetrics && journeyMetrics && trendData.sessions.length >= 2 && (
          <div className="rounded-lg border-l-[3px] border-l-[var(--cata-accent)] bg-gradient-to-r from-[var(--bg-surface)] to-[color-mix(in_srgb,var(--bg-surface)_92%,white)] p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--text-muted)]">
              Your journey at {trendData.track_name}
            </p>
            <div className="flex items-baseline gap-4 lg:gap-6">
              <div className="min-w-0">
                <p className="text-xs text-[var(--text-muted)]">Started</p>
                <p className="font-[family-name:var(--font-display)] text-xl font-bold tracking-tight text-[var(--text-secondary)] lg:text-2xl">
                  {formatTimeShort(journeyMetrics.firstBestLap)}
                </p>
                <p className="text-xs text-[var(--text-muted)]">{journeyMetrics.firstDate}</p>
              </div>
              <span className="text-lg text-[var(--text-muted)]">&rarr;</span>
              <div className="min-w-0">
                <p className="text-xs text-[var(--text-muted)]">Now</p>
                <p className="font-[family-name:var(--font-display)] text-xl font-bold tracking-tight text-[var(--text-primary)] lg:text-2xl">
                  {formatTimeShort(journeyMetrics.latestBestLap)}
                </p>
                <p className="text-xs text-[var(--text-muted)]">{journeyMetrics.latestDate}</p>
              </div>
              <div className="ml-auto min-w-0 text-right">
                <p className="text-xs text-[var(--text-muted)]">Improvement</p>
                <p className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-[var(--color-throttle)]">
                  -{journeyMetrics.improvement.toFixed(1)}s
                </p>
                <p className="text-xs text-[var(--text-muted)]">{trendData.sessions.length} sessions</p>
              </div>
            </div>
          </div>
        )}

        {/* 4. Hero metrics row */}
        {heroMetrics && (
          <m.div
            className="grid grid-cols-2 gap-3 lg:grid-cols-4"
            initial="initial"
            animate="animate"
            variants={{ animate: { transition: motionTokens.stagger } }}
          >
            <MetricCard
              label="Best Lap"
              value={formatTimeShort(heroMetrics.bestLap)}
              highlight="pb"
            />
            <MetricCard
              label="Top 3 Average"
              value={formatTimeShort(heroMetrics.latestTop3)}
              subtitle="Latest session"
            />
            <MetricCard
              label="Sessions"
              value={heroMetrics.sessionCount}
              subtitle={trendData.track_name}
            />
            <MetricCard
              label="Consistency"
              value={heroMetrics.latestConsistency.toFixed(0)}
              subtitle={
                heroMetrics.consistencyDelta !== undefined
                  ? `${heroMetrics.consistencyDelta > 0 ? '+' : ''}${heroMetrics.consistencyDelta.toFixed(1)} vs prev`
                  : 'Latest session'
              }
              highlight={
                heroMetrics.consistencyDelta !== undefined && heroMetrics.consistencyDelta < 0
                  ? 'bad'
                  : heroMetrics.consistencyDelta !== undefined && heroMetrics.consistencyDelta > 2
                    ? 'good'
                    : 'none'
              }
            />
          </m.div>
        )}

        {/* 4b. Recent Achievements */}
        {recentBadges.length > 0 && (
          <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Award className="h-4 w-4 text-yellow-400" />
                <h3 className="font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">
                  Recent Achievements
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setBadgesOpen(true)}
                className="text-xs font-medium text-[var(--cata-accent)] hover:underline"
              >
                View All
              </button>
            </div>
            <div className="flex gap-3 overflow-x-auto">
              {recentBadges.map((badge) => (
                <div
                  key={badge.id}
                  className="flex min-w-[100px] flex-col items-center gap-1.5 rounded-lg bg-[var(--bg-elevated)] p-3"
                >
                  <div
                    className="flex h-8 w-8 items-center justify-center rounded-full border"
                    style={{
                      borderColor:
                        badge.tier === 'gold'
                          ? '#ffd700'
                          : badge.tier === 'silver'
                            ? '#c0c0c0'
                            : '#cd7f32',
                    }}
                  >
                    <span className="text-sm">
                      {badge.tier === 'gold' ? '🥇' : badge.tier === 'silver' ? '🥈' : '🥉'}
                    </span>
                  </div>
                  <span className="text-center text-[10px] font-medium text-[var(--text-primary)]">
                    {badge.name}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 5. Milestone Timeline */}
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h3 className="mb-2 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">Milestone Timeline</h3>
          <ChartErrorBoundary name="Milestone Timeline">
            <MilestoneTimeline sessions={trendData.sessions} milestones={milestones} />
          </ChartErrorBoundary>
        </div>

        {/* 6. Two-column trend charts */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
            <h3 className="mb-2 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">Lap Time Trend</h3>
            <div className="h-[260px]">
              <ChartErrorBoundary name="Lap Time Trend">
                <LapTimeTrend
                  sessions={trendData.sessions}
                  bestLapTrend={trendData.best_lap_trend}
                  top3AvgTrend={trendData.top3_avg_trend}
                  theoreticalTrend={trendData.theoretical_trend}
                  pbIndices={pbSessionIndices}
                />
              </ChartErrorBoundary>
            </div>
          </div>
          <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
            <h3 className="mb-2 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">
              Consistency Trend
            </h3>
            <div className="h-[260px]">
              <ChartErrorBoundary name="Consistency Trend">
                <ConsistencyTrend
                  sessions={trendData.sessions}
                  consistencyTrend={trendData.consistency_trend}
                  pbIndices={pbSessionIndices}
                />
              </ChartErrorBoundary>
            </div>
          </div>
        </div>

        {/* 7. Heatmap + BoxPlot (2-col grid, skill-gated) */}
        {(showHeatmap || showBoxplot) && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {showHeatmap && (
              <div className={cn(
                'rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4',
                !showBothSkillCharts && 'lg:col-span-2',
              )}>
                <h3 className="mb-2 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">Corner Heatmap</h3>
                <div className="h-[280px]">
                  <ChartErrorBoundary name="Corner Heatmap">
                    <CornerHeatmap
                      sessions={trendData.sessions}
                      cornerMinSpeedTrends={trendData.corner_min_speed_trends}
                      cornerBrakeStdTrends={trendData.corner_brake_std_trends}
                      cornerConsistencyTrends={trendData.corner_consistency_trends}
                    />
                  </ChartErrorBoundary>
                </div>
              </div>
            )}
            {showBoxplot && (
              <div className={cn(
                'rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4',
                !showBothSkillCharts && 'lg:col-span-2',
              )}>
                <h3 className="mb-2 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">
                  Session Lap Time Distribution
                </h3>
                <div className="h-[280px]">
                  <ChartErrorBoundary name="Session Box Plot">
                    <SessionBoxPlot sessions={trendData.sessions} />
                  </ChartErrorBoundary>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      <BadgeGrid open={badgesOpen} onClose={() => setBadgesOpen(false)} />
      <SeasonWrapped open={wrappedOpen} onClose={() => setWrappedOpen(false)} />
    </ScrollArea>
  );
}
