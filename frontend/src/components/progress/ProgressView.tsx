'use client';

import { useMemo } from 'react';
import { useSessionStore } from '@/stores';
import { useSession } from '@/hooks/useSession';
import { useTrends, useMilestones } from '@/hooks/useTrends';
import { formatTimeShort } from '@/lib/formatters';
import { useSkillLevel } from '@/hooks/useSkillLevel';
import { MetricCard } from '@/components/shared/MetricCard';
import { AiInsight } from '@/components/shared/AiInsight';
import { EmptyState } from '@/components/shared/EmptyState';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { ChartErrorBoundary } from '@/components/shared/ChartErrorBoundary';
import { MilestoneTimeline } from './MilestoneTimeline';
import { LapTimeTrend } from './LapTimeTrend';
import { ConsistencyTrend } from './ConsistencyTrend';
import { CornerHeatmap } from './CornerHeatmap';
import { SessionBoxPlot } from './SessionBoxPlot';

export function ProgressView() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { data: session, isLoading: sessionLoading } = useSession(activeSessionId);
  const { showFeature } = useSkillLevel();

  const trackName = session?.track_name ?? null;

  const { data: trendResponse, isLoading: trendsLoading } = useTrends(trackName);
  const { data: milestoneResponse } = useMilestones(trackName);

  const trendData = trendResponse?.data ?? null;
  const milestones = milestoneResponse?.milestones ?? [];

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
        message="Upload multiple sessions for the same track to see progress trends"
      />
    );
  }

  return (
    <div className="flex flex-col gap-6 overflow-y-auto p-6">
      {/* Section title */}
      <div>
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          Progress: {trendData.track_name}
        </h2>
        <p className="text-sm text-[var(--text-secondary)]">
          {trendData.n_sessions} session{trendData.n_sessions !== 1 ? 's' : ''} tracked
        </p>
      </div>

      {/* 1. Hero metrics row */}
      {heroMetrics && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
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
        </div>
      )}

      {/* 2. AI Progress Summary */}
      {aiSummary && (
        <AiInsight>
          <p>{aiSummary}</p>
        </AiInsight>
      )}

      {/* 3. Milestone Timeline */}
      <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
        <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">Milestone Timeline</h3>
        <ChartErrorBoundary name="Milestone Timeline">
          <MilestoneTimeline sessions={trendData.sessions} milestones={milestones} />
        </ChartErrorBoundary>
      </div>

      {/* 4. Two-column trend charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">Lap Time Trend</h3>
          <div className="h-[280px]">
            <ChartErrorBoundary name="Lap Time Trend">
              <LapTimeTrend
                sessions={trendData.sessions}
                bestLapTrend={trendData.best_lap_trend}
                top3AvgTrend={trendData.top3_avg_trend}
                theoreticalTrend={trendData.theoretical_trend}
              />
            </ChartErrorBoundary>
          </div>
        </div>
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">
            Consistency Trend
          </h3>
          <div className="h-[280px]">
            <ChartErrorBoundary name="Consistency Trend">
              <ConsistencyTrend
                sessions={trendData.sessions}
                consistencyTrend={trendData.consistency_trend}
              />
            </ChartErrorBoundary>
          </div>
        </div>
      </div>

      {/* 5. Corner Heatmap (hidden for novice) */}
      {showFeature('heatmap') && (
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">Corner Heatmap</h3>
          <div className="h-[320px]">
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

      {/* 6. Session Box Plot (hidden for novice) */}
      {showFeature('boxplot') && (
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">
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
  );
}
