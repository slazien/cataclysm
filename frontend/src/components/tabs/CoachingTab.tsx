"use client";

import { useSessionStore, useUiStore } from "@/store";
import { useSessions, useSessionLaps, useLapData } from "@/hooks/useSession";
import { useCoachingReport, useGenerateReport, useIdealLap } from "@/hooks/useCoaching";
import { useCorners, useGains } from "@/hooks/useAnalysis";
import Spinner from "@/components/ui/Spinner";
import CoachingReportView from "@/components/coaching/CoachingReportView";
import CornerGrades from "@/components/coaching/CornerGrades";
import PriorityCorners from "@/components/coaching/PriorityCorners";
import ChatInterface from "@/components/coaching/ChatInterface";
import GainPerCorner from "@/components/charts/d3/GainPerCorner";
import IdealLapOverlay from "@/components/charts/d3/IdealLapOverlay";
import IdealLapDelta from "@/components/charts/d3/IdealLapDelta";
import MetricCard from "@/components/layout/MetricCard";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { MPS_TO_MPH } from "@/lib/constants";

export default function CoachingTab() {
  const { activeSessionId } = useSessionStore();
  const { skillLevel, setSkillLevel } = useUiStore();
  const { data: sessionsData } = useSessions();
  const { data: laps } = useSessionLaps(activeSessionId);
  const { data: corners } = useCorners(activeSessionId);
  const { data: gains } = useGains(activeSessionId);
  const { data: idealLap } = useIdealLap(activeSessionId);

  const {
    data: report,
    isLoading: reportLoading,
    isError: reportNotFound,
  } = useCoachingReport(activeSessionId);

  const generateMutation = useGenerateReport();

  // Best lap for ideal overlay
  const bestLapNumber =
    laps && laps.length > 0
      ? laps.reduce((best, l) => (l.lap_time_s < best.lap_time_s ? l : best))
          .lap_number
      : null;
  const bestLapTime =
    laps && laps.length > 0
      ? Math.min(...laps.map((l) => l.lap_time_s))
      : 0;

  const { data: bestLapData } = useLapData(activeSessionId, bestLapNumber);

  const sessions = sessionsData?.items ?? [];
  const activeSession = sessions.find(
    (s) => s.session_id === activeSessionId,
  );

  if (!activeSessionId || !activeSession) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
        Select a session to view coaching analysis
      </div>
    );
  }

  const hasReport = report && report.status === "ready" && !reportNotFound;
  const isGenerating = generateMutation.isPending;

  // Parse gains data for charts
  const gainsData = gains as Record<string, unknown> | undefined;
  const consistencyGains = extractSegmentGains(gainsData, "consistency");
  const compositeGains = extractSegmentGains(gainsData, "composite");

  // Gain metrics — gainsData is already unwrapped by api.ts (no .data wrapper)
  const consistencyTotal = getNestedNumber(gainsData, "consistency", "total_gain_s");
  const compositeGain = getNestedNumber(gainsData, "composite", "gain_s");
  const theoreticalGain = getNestedNumber(gainsData, "theoretical", "gain_s");

  // Corner zones for charts
  const cornerZones = (corners ?? []).map((c) => ({
    number: c.number,
    entry: c.entry_distance_m,
    exit: c.exit_distance_m,
  }));

  // Ideal lap delta computation
  const idealDelta =
    bestLapData && idealLap
      ? computeIdealDelta(bestLapData.distance_m, bestLapData.speed_mph, idealLap)
      : null;

  return (
    <div className="space-y-6">
      {/* Generate Report Section */}
      {!hasReport && !reportLoading && (
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-6 text-center">
          <h3 className="mb-2 text-lg font-semibold text-[var(--text-primary)]">
            AI Coaching Report
          </h3>
          <p className="mb-4 text-sm text-[var(--text-secondary)]">
            Generate an AI-powered analysis of your driving with corner-by-corner grades,
            priority improvements, and practice drills.
          </p>

          <div className="mb-4 flex items-center justify-center gap-3">
            <label className="text-sm text-[var(--text-secondary)]">Skill Level:</label>
            <select
              value={skillLevel}
              onChange={(e) => setSkillLevel(e.target.value)}
              className="rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-1.5 text-sm text-[var(--text-primary)]"
            >
              <option value="novice">Novice (HPDE 1-2)</option>
              <option value="intermediate">Intermediate (HPDE 3)</option>
              <option value="advanced">Advanced (HPDE 4+)</option>
            </select>
          </div>

          <button
            onClick={() => {
              if (activeSessionId) {
                generateMutation.mutate({
                  sessionId: activeSessionId,
                  skillLevel,
                });
              }
            }}
            disabled={isGenerating}
            className="rounded-md bg-[var(--accent-blue)] px-6 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {isGenerating ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" />
                Analyzing your session...
              </span>
            ) : (
              "Generate Coaching Report"
            )}
          </button>

          {generateMutation.isError && (
            <p className="mt-3 text-sm text-[var(--accent-red)]">
              Failed to generate report. Make sure ANTHROPIC_API_KEY is configured.
            </p>
          )}
        </div>
      )}

      {/* Loading State */}
      {(reportLoading || isGenerating) && !hasReport && (
        <div className="flex flex-col items-center justify-center py-16">
          <Spinner size="lg" />
          <p className="mt-4 text-sm text-[var(--text-muted)]">
            AI coach is analyzing your session...
          </p>
        </div>
      )}

      {/* Report Content */}
      {hasReport && report && (
        <>
          {/* Regenerate button */}
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              Coaching Report
            </h2>
            <div className="flex items-center gap-3">
              <select
                value={skillLevel}
                onChange={(e) => setSkillLevel(e.target.value)}
                className="rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2 py-1 text-xs text-[var(--text-primary)]"
              >
                <option value="novice">Novice</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
              <button
                onClick={() => {
                  if (activeSessionId) {
                    generateMutation.mutate({
                      sessionId: activeSessionId,
                      skillLevel,
                    });
                  }
                }}
                disabled={isGenerating}
                className="rounded-md border border-[var(--border-color)] px-3 py-1 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-secondary)]"
              >
                {isGenerating ? "Regenerating..." : "Regenerate"}
              </button>
            </div>
          </div>

          {/* Report Summary */}
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
            <CoachingReportView report={report} />
          </div>

          {/* Priority Corners */}
          {report.priority_corners.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-base font-bold text-[var(--text-primary)]">
                Priority Corners
              </h2>
              <PriorityCorners corners={report.priority_corners} />
            </div>
          )}

          {/* Corner Grades */}
          {report.corner_grades.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-base font-bold text-[var(--text-primary)]">
                Corner Grades
              </h2>
              <CornerGrades grades={report.corner_grades} />
            </div>
          )}
        </>
      )}

      {/* Gain Analysis — always visible when data is available */}
      {gainsData && (
        <>
          <div className="border-t border-[var(--border-color)]" />
          <div className="space-y-4">
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              Gain Analysis
            </h2>

            {/* Gain Metrics */}
            <div className="grid grid-cols-3 gap-3">
              <MetricCard
                label="Consistency Gain"
                value={
                  consistencyTotal !== null
                    ? `${consistencyTotal.toFixed(2)}s`
                    : "--"
                }
                subtitle="Avg vs best per corner"
              />
              <MetricCard
                label="Composite Gain"
                value={
                  compositeGain !== null
                    ? `${compositeGain.toFixed(2)}s`
                    : "--"
                }
                subtitle="Best lap vs best sectors"
              />
              <MetricCard
                label="Theoretical Gain"
                value={
                  theoreticalGain !== null
                    ? `${theoreticalGain.toFixed(2)}s`
                    : "--"
                }
                subtitle="Micro-sector limit"
              />
            </div>

            {/* Gain Per Corner Chart */}
            {consistencyGains.length > 0 && (
              <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
                <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
                  Time Gain Per Corner
                </h3>
                <ErrorBoundary>
                  <GainPerCorner
                    consistencyGains={consistencyGains}
                    compositeGains={compositeGains}
                  />
                </ErrorBoundary>
              </div>
            )}

            {/* Ideal Lap Overlay */}
            {bestLapData && idealLap && bestLapNumber && (
              <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
                <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
                  Ideal Lap (Composite Best Segments)
                </h3>
                <ErrorBoundary>
                  <IdealLapOverlay
                    bestLap={{
                      distance: bestLapData.distance_m,
                      speed: bestLapData.speed_mph,
                    }}
                    idealLap={{
                      distance: idealLap.distance_m,
                      speed: idealLap.speed_mph,
                    }}
                    corners={cornerZones}
                    bestLapNumber={bestLapNumber}
                    idealTime={computeIdealTime(idealLap)}
                    bestTime={bestLapTime}
                  />
                </ErrorBoundary>
              </div>
            )}

            {/* Ideal Lap Delta */}
            {idealDelta && bestLapNumber && (
              <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
                <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
                  Delta: Ideal vs Best Lap
                </h3>
                <ErrorBoundary>
                  <IdealLapDelta
                    distance={idealDelta.distance}
                    delta={idealDelta.delta}
                    bestLapNumber={bestLapNumber}
                    corners={cornerZones}
                  />
                </ErrorBoundary>
              </div>
            )}
          </div>
        </>
      )}

      {/* Follow-up Chat — always available */}
      {hasReport && report && (
        <>
          <div className="border-t border-[var(--border-color)]" />
          <div className="space-y-3">
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              Ask the Coach
            </h2>
            <ChatInterface sessionId={activeSessionId} />
          </div>
        </>
      )}
    </div>
  );
}

// --- Helper functions ---

interface SegmentGainEntry {
  segment_name: string;
  gain_s: number;
  is_corner: boolean;
}

function extractSegmentGains(
  gainsData: Record<string, unknown> | undefined,
  tier: "consistency" | "composite",
): SegmentGainEntry[] {
  if (!gainsData) return [];
  // gainsData is already unwrapped by api.ts — access tier directly
  const tierData = gainsData[tier] as Record<string, unknown> | undefined;
  if (!tierData) return [];
  const segmentGains = tierData.segment_gains as
    | { segment: { name: string; is_corner: boolean }; gain_s: number }[]
    | undefined;
  if (!Array.isArray(segmentGains)) return [];

  return segmentGains.map((sg) => ({
    segment_name: sg.segment?.name ?? "?",
    gain_s: sg.gain_s ?? 0,
    is_corner: sg.segment?.is_corner ?? false,
  }));
}

function getNestedNumber(
  obj: Record<string, unknown> | undefined,
  ...keys: string[]
): number | null {
  let current: unknown = obj;
  for (const key of keys) {
    if (current == null || typeof current !== "object") return null;
    current = (current as Record<string, unknown>)[key];
  }
  return typeof current === "number" ? current : null;
}

function computeIdealTime(
  idealLap: { distance_m: number[]; speed_mph: number[] },
): number {
  // Estimate ideal lap time from speed data
  // Use trapezoidal integration: dt = dx / v
  const d = idealLap.distance_m;
  const v = idealLap.speed_mph;
  let time = 0;
  for (let i = 1; i < d.length; i++) {
    const dx = d[i] - d[i - 1];
    const avgSpeedMph = (v[i] + v[i - 1]) / 2;
    if (avgSpeedMph > 0) {
      // Convert mph to m/s: mph / 2.23694
      const avgSpeedMps = avgSpeedMph / MPS_TO_MPH;
      time += dx / avgSpeedMps;
    }
  }
  return time;
}

function computeIdealDelta(
  bestDistance: number[],
  bestSpeedMph: number[],
  idealLap: { distance_m: number[]; speed_mph: number[] },
): { distance: number[]; delta: number[] } | null {
  if (bestDistance.length < 2 || idealLap.distance_m.length < 2) return null;

  // Compute cumulative time for both traces
  const cumTimeBest = cumulativeTime(bestDistance, bestSpeedMph);
  const cumTimeIdeal = cumulativeTime(idealLap.distance_m, idealLap.speed_mph);

  // Interpolate ideal cumulative time at best distance points
  const distance: number[] = [];
  const delta: number[] = [];

  let j = 0;
  for (let i = 0; i < bestDistance.length; i++) {
    const d = bestDistance[i];
    // Find interpolation bracket in ideal
    while (
      j < idealLap.distance_m.length - 1 &&
      idealLap.distance_m[j + 1] < d
    ) {
      j++;
    }
    if (j >= idealLap.distance_m.length - 1) break;

    const d0 = idealLap.distance_m[j];
    const d1 = idealLap.distance_m[j + 1];
    const t0 = cumTimeIdeal[j];
    const t1 = cumTimeIdeal[j + 1];
    const frac = d1 !== d0 ? (d - d0) / (d1 - d0) : 0;
    const idealTimeAtD = t0 + frac * (t1 - t0);

    distance.push(d);
    // Delta: positive = best is slower = time lost
    delta.push(cumTimeBest[i] - idealTimeAtD);
  }

  return { distance, delta };
}

function cumulativeTime(distance: number[], speedMph: number[]): number[] {
  const cumTime = [0];
  for (let i = 1; i < distance.length; i++) {
    const dx = distance[i] - distance[i - 1];
    const avgSpeedMps = ((speedMph[i] + speedMph[i - 1]) / 2) / MPS_TO_MPH;
    const dt = avgSpeedMps > 0 ? dx / avgSpeedMps : 0;
    cumTime.push(cumTime[i - 1] + dt);
  }
  return cumTime;
}
