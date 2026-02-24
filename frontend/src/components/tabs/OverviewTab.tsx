"use client";

import { useSessionStore } from "@/store";
import { useSessionLaps, useLapData, useSessions } from "@/hooks/useSession";
import { useConsistency, useCorners } from "@/hooks/useAnalysis";
import MetricCard from "@/components/layout/MetricCard";
import LapTimesBar from "@/components/charts/d3/LapTimesBar";
import LapConsistencyChart from "@/components/charts/d3/LapConsistency";
import TrackSpeedMap from "@/components/charts/d3/TrackSpeedMap";
import TrackConsistencyMap from "@/components/charts/d3/TrackConsistencyMap";
import TractionCircle from "@/components/charts/d3/TractionCircle";
import Spinner from "@/components/ui/Spinner";
import { formatLapTime } from "@/lib/formatters";
import { MPS_TO_MPH } from "@/lib/constants";

export default function OverviewTab() {
  const { activeSessionId } = useSessionStore();
  const { data: sessionsData } = useSessions();
  const { data: laps, isLoading: lapsLoading } = useSessionLaps(activeSessionId);
  const { data: consistency, isLoading: consistencyLoading } =
    useConsistency(activeSessionId);
  const { data: corners } = useCorners(activeSessionId);

  const sessions = sessionsData?.items ?? [];
  const activeSession = sessions.find(
    (s) => s.session_id === activeSessionId,
  );

  // Best lap for traction circle
  const bestLapNumber =
    laps && laps.length > 0
      ? laps.reduce((best, l) => (l.lap_time_s < best.lap_time_s ? l : best))
          .lap_number
      : null;

  const { data: bestLapData } = useLapData(activeSessionId, bestLapNumber);

  if (!activeSessionId || !activeSession) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
        Select a session to view analysis
      </div>
    );
  }

  if (lapsLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  const cleanLaps = laps?.filter((l) => l.is_clean) ?? [];
  const allLaps = laps ?? [];

  const bestTime =
    allLaps.length > 0
      ? Math.min(...allLaps.map((l) => l.lap_time_s))
      : 0;
  const worstTime =
    cleanLaps.length > 0
      ? Math.max(...cleanLaps.map((l) => l.lap_time_s))
      : 0;
  const avgTime =
    cleanLaps.length > 0
      ? cleanLaps.reduce((s, l) => s + l.lap_time_s, 0) / cleanLaps.length
      : 0;
  const topSpeed =
    allLaps.length > 0
      ? Math.max(...allLaps.map((l) => l.max_speed_mps)) * MPS_TO_MPH
      : 0;

  const lapConsistency = consistency?.lap_consistency ?? null;
  const trackPosition = consistency?.track_position ?? null;

  return (
    <div className="space-y-6">
      {/* Metric Cards Row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard
          label="Best Lap"
          value={bestTime > 0 ? formatLapTime(bestTime) : "--"}
          subtitle={bestLapNumber ? `Lap ${bestLapNumber}` : undefined}
        />
        <MetricCard
          label="Worst Clean Lap"
          value={worstTime > 0 ? formatLapTime(worstTime) : "--"}
        />
        <MetricCard
          label="Average"
          value={avgTime > 0 ? formatLapTime(avgTime) : "--"}
          subtitle={`${cleanLaps.length} clean laps`}
        />
        <MetricCard
          label="Top Speed"
          value={topSpeed > 0 ? `${topSpeed.toFixed(1)} mph` : "--"}
        />
      </div>

      {/* Lap Times Bar Chart */}
      <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
        <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
          Lap Times
        </h3>
        <LapTimesBar laps={allLaps} />
      </div>

      {/* Divider */}
      <div className="border-t border-[var(--border-color)]" />

      {/* Session Consistency Section */}
      <div className="space-y-4">
        <h2 className="text-base font-bold text-[var(--text-primary)]">
          Session Consistency
        </h2>

        {consistencyLoading ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : (
          <>
            {/* Consistency Metric Cards */}
            {lapConsistency && (
              <div className="grid grid-cols-3 gap-3">
                <MetricCard
                  label="Consistency Score"
                  value={`${(lapConsistency.consistency_score * 100).toFixed(0)}%`}
                  subtitle={
                    lapConsistency.consistency_score >= 0.8
                      ? "Excellent"
                      : lapConsistency.consistency_score >= 0.6
                        ? "Good"
                        : "Needs work"
                  }
                />
                <MetricCard
                  label="Avg Lap Delta"
                  value={`${lapConsistency.mean_abs_consecutive_delta_s.toFixed(2)}s`}
                  subtitle="Mean absolute consecutive"
                />
                <MetricCard
                  label="Spread"
                  value={`${lapConsistency.spread_s.toFixed(2)}s`}
                  subtitle="Best to worst"
                />
              </div>
            )}

            {/* Lap Consistency Chart */}
            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
              <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
                Consecutive Lap Deltas
              </h3>
              <LapConsistencyChart data={lapConsistency} />
            </div>

            {/* Track Maps Side-by-Side */}
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
                <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
                  Track Speed Map
                </h3>
                <TrackSpeedMap
                  trackData={trackPosition}
                  corners={corners ?? []}
                />
              </div>
              <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
                <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
                  Track Consistency Map
                </h3>
                <TrackConsistencyMap trackData={trackPosition} />
              </div>
            </div>

            {/* Traction Circle */}
            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
              <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
                Traction Circle (Best Lap)
              </h3>
              <TractionCircle lapData={bestLapData ?? null} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
