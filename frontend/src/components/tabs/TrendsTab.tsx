"use client";

import { useState, useMemo } from "react";
import { useSessionStore } from "@/store";
import { useSessions } from "@/hooks/useSession";
import { useTrends } from "@/hooks/useTrends";
import MetricCard from "@/components/layout/MetricCard";
import LapTimeTrend from "@/components/charts/d3/LapTimeTrend";
import ConsistencyTrend from "@/components/charts/d3/ConsistencyTrend";
import SessionBoxPlot from "@/components/charts/d3/SessionBoxPlot";
import CornerHeatmap from "@/components/charts/d3/CornerHeatmap";
import CornerTrendGrid from "@/components/charts/d3/CornerTrendGrid";
import Spinner from "@/components/ui/Spinner";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { formatLapTime } from "@/lib/formatters";
import type { TrendAnalysisData } from "@/lib/types";

type HeatmapMetric = "min_speed" | "brake_std" | "consistency";

const METRIC_LABELS: Record<HeatmapMetric, string> = {
  min_speed: "Min Speed (mph)",
  brake_std: "Brake Point Variation (m)",
  consistency: "Consistency Score",
};

function getSessionDates(trend: TrendAnalysisData): string[] {
  return trend.sessions.map((s) => s.session_date);
}

function getCornerData(
  trend: TrendAnalysisData,
  metric: HeatmapMetric,
): {
  cornerNumbers: string[];
  values: (number | null)[][];
} {
  const dataDict =
    metric === "min_speed"
      ? trend.corner_min_speed_trends
      : metric === "brake_std"
        ? trend.corner_brake_std_trends
        : trend.corner_consistency_trends;

  const cornerNumbers = Object.keys(dataDict).sort(
    (a, b) => parseInt(a) - parseInt(b),
  );
  const values = cornerNumbers.map((cn) => dataDict[cn]);

  return { cornerNumbers: cornerNumbers.map((cn) => `T${cn}`), values };
}

export default function TrendsTab() {
  const { activeSessionId } = useSessionStore();
  const { data: sessionsData } = useSessions();
  const [heatmapMetric, setHeatmapMetric] =
    useState<HeatmapMetric>("min_speed");

  const sessions = sessionsData?.items ?? [];
  const activeSession = sessions.find(
    (s) => s.session_id === activeSessionId,
  );
  const trackName = activeSession?.track_name ?? null;

  const { data: trendsResponse, isLoading, error } = useTrends(trackName);

  const trend = trendsResponse?.data ?? null;

  // Derived data
  const dates = useMemo(
    () => (trend ? getSessionDates(trend) : []),
    [trend],
  );

  const lapTimesPerSession = useMemo(
    () =>
      trend
        ? trend.sessions.map((s) => s.lap_times_s ?? [])
        : [],
    [trend],
  );

  const cornerData = useMemo(
    () =>
      trend
        ? getCornerData(trend, heatmapMetric)
        : { cornerNumbers: [], values: [] },
    [trend, heatmapMetric],
  );

  const hasCornerData = useMemo(
    () =>
      trend
        ? Object.keys(trend.corner_min_speed_trends).length > 0
        : false,
    [trend],
  );

  // --- Metric computations ---
  const allTimeBest = useMemo(
    () =>
      trend && trend.best_lap_trend.length > 0
        ? Math.min(...trend.best_lap_trend)
        : null,
    [trend],
  );

  const latestBest = useMemo(
    () =>
      trend && trend.best_lap_trend.length > 0
        ? trend.best_lap_trend[trend.best_lap_trend.length - 1]
        : null,
    [trend],
  );

  const latestBestDelta = useMemo(() => {
    if (!trend || trend.best_lap_trend.length < 2) return null;
    const prev = Math.min(
      ...trend.best_lap_trend.slice(0, -1),
    );
    return trend.best_lap_trend[trend.best_lap_trend.length - 1] - prev;
  }, [trend]);

  const latestConsistency = useMemo(
    () =>
      trend && trend.consistency_trend.length > 0
        ? trend.consistency_trend[trend.consistency_trend.length - 1]
        : null,
    [trend],
  );

  const consistencyDelta = useMemo(() => {
    if (!trend || trend.consistency_trend.length < 2) return null;
    return (
      trend.consistency_trend[trend.consistency_trend.length - 1] -
      trend.consistency_trend[trend.consistency_trend.length - 2]
    );
  }, [trend]);

  const milestones = useMemo(
    () => (trend ? trend.milestones.slice(-3) : []),
    [trend],
  );

  // --- Guard states ---

  if (!trackName) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
        Select a session to view trends
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !trend) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
        Need 2+ sessions at the same track to show trends
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Metric Cards Row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard
          label="Sessions"
          value={String(trend.n_sessions)}
          subtitle={trackName}
        />
        <MetricCard
          label="All-Time Best"
          value={allTimeBest !== null ? formatLapTime(allTimeBest) : "--"}
        />
        <MetricCard
          label="Latest Best"
          value={latestBest !== null ? formatLapTime(latestBest) : "--"}
          subtitle={
            latestBestDelta !== null
              ? `${latestBestDelta >= 0 ? "+" : ""}${latestBestDelta.toFixed(2)}s`
              : undefined
          }
        />
        <MetricCard
          label="Consistency"
          value={
            latestConsistency !== null
              ? `${latestConsistency.toFixed(0)}/100`
              : "--"
          }
          subtitle={
            consistencyDelta !== null
              ? `${consistencyDelta >= 0 ? "+" : ""}${consistencyDelta.toFixed(0)} from prev`
              : undefined
          }
        />
      </div>

      {/* Milestones */}
      {milestones.length > 0 && (
        <div className="space-y-2">
          {milestones.map((m, i) => (
            <div
              key={i}
              className="rounded-lg border border-[var(--accent-green)]/30 bg-[var(--accent-green)]/5 px-4 py-2.5"
            >
              <span className="text-sm font-medium text-[var(--accent-green)]">
                {m.description}
              </span>
              <span className="ml-2 text-xs text-[var(--text-muted)]">
                {m.session_date}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Lap Time Trend (full width) */}
      <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
        <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
          Lap Time Trend
        </h3>
        <ErrorBoundary>
          <LapTimeTrend
            dates={dates}
            bestLapTrend={trend.best_lap_trend}
            top3AvgTrend={trend.top3_avg_trend}
            theoreticalTrend={trend.theoretical_trend}
          />
        </ErrorBoundary>
      </div>

      {/* Two-column: Consistency + Box Plot */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
          <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
            Consistency Trend
          </h3>
          <ErrorBoundary>
            <ConsistencyTrend
              dates={dates}
              scores={trend.consistency_trend}
            />
          </ErrorBoundary>
        </div>
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
          <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
            Lap Time Distribution
          </h3>
          <ErrorBoundary>
            <SessionBoxPlot
              dates={dates}
              lapTimesPerSession={lapTimesPerSession}
              bestLapTrend={trend.best_lap_trend}
            />
          </ErrorBoundary>
        </div>
      </div>

      {/* Corner Progression */}
      {hasCornerData && (
        <>
          <div className="border-t border-[var(--border-color)]" />

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-[var(--text-primary)]">
                Corner Progression
              </h2>
              <select
                value={heatmapMetric}
                onChange={(e) =>
                  setHeatmapMetric(e.target.value as HeatmapMetric)
                }
                className="rounded border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-1.5 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
              >
                <option value="min_speed">Min Speed (mph)</option>
                <option value="brake_std">Brake Point Variation (m)</option>
                <option value="consistency">Consistency Score</option>
              </select>
            </div>

            {/* Corner Heatmap */}
            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
              <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
                Corner Heatmap &mdash; {METRIC_LABELS[heatmapMetric]}
              </h3>
              <ErrorBoundary>
                <CornerHeatmap
                  dates={dates}
                  cornerNumbers={cornerData.cornerNumbers}
                  values={cornerData.values}
                  metric={heatmapMetric}
                  metricLabel={METRIC_LABELS[heatmapMetric]}
                />
              </ErrorBoundary>
            </div>

            {/* Corner Trend Grid (small multiples) */}
            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
              <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
                Corner Min Speed Trends
              </h3>
              <ErrorBoundary>
                <CornerTrendGrid
                  dates={dates}
                  cornerMinSpeedTrends={trend.corner_min_speed_trends}
                />
              </ErrorBoundary>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
