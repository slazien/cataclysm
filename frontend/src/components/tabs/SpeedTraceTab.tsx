"use client";

import { useState, useMemo } from "react";
import { useSessionStore } from "@/store";
import { useSessionLaps } from "@/hooks/useSession";
import { useCorners, useMultiLapData } from "@/hooks/useAnalysis";
import LinkedSpeedMap from "@/components/charts/d3/LinkedSpeedMap";
import BrakeThrottle from "@/components/charts/d3/BrakeThrottle";
import Spinner from "@/components/ui/Spinner";
import { formatLapTime } from "@/lib/formatters";
import type { LapSummary, Corner } from "@/lib/types";

function computeDefaultLaps(
  allLaps: LapSummary[],
): number[] {
  if (allLaps.length === 0) return [];
  const cleanLaps = allLaps.filter((l) => l.is_clean);
  const firstLap = allLaps[0].lap_number;
  const bestLap =
    cleanLaps.length > 0
      ? cleanLaps.reduce((best, l) => (l.lap_time_s < best.lap_time_s ? l : best)).lap_number
      : firstLap;
  if (bestLap !== firstLap) return [firstLap, bestLap];
  return [firstLap];
}

/** Inner component that manages lap selection state. Re-mounts when lapsKey changes. */
function SpeedTraceContent({
  sessionId,
  allLaps,
  corners,
}: {
  sessionId: string;
  allLaps: LapSummary[];
  corners: Corner[];
}) {
  const [selectedLaps, setSelectedLaps] = useState<number[]>(() =>
    computeDefaultLaps(allLaps),
  );

  const bestLapNumber = useMemo(() => {
    const cleanLaps = allLaps.filter((l) => l.is_clean);
    if (cleanLaps.length === 0) return allLaps.length > 0 ? allLaps[0].lap_number : null;
    return cleanLaps.reduce((best, l) => (l.lap_time_s < best.lap_time_s ? l : best))
      .lap_number;
  }, [allLaps]);

  // Fetch lap data for selected laps to populate BrakeThrottle
  const { data: lapDataList } = useMultiLapData(sessionId, selectedLaps);

  // Corner zones for BrakeThrottle
  const cornerZones = useMemo(() => {
    return corners.map((c) => ({
      number: c.number,
      entry: c.entry_distance_m,
      exit: c.exit_distance_m,
    }));
  }, [corners]);

  // G-force traces for BrakeThrottle
  const gTraces = useMemo(() => {
    return lapDataList.map((ld) => ({
      lapNumber: ld.lap_number,
      distance: ld.distance_m,
      longitudinalG: ld.longitudinal_g,
    }));
  }, [lapDataList]);

  const toggleLap = (lapNum: number) => {
    setSelectedLaps((prev) => {
      if (prev.includes(lapNum)) {
        return prev.filter((n) => n !== lapNum);
      }
      return [...prev, lapNum].sort((a, b) => a - b);
    });
  };

  const cleanLapsList = allLaps.filter((l) => l.is_clean);

  return (
    <div className="space-y-4">
      {/* Lap Selector */}
      <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
        <div className="mb-2 text-sm font-semibold text-[var(--text-primary)]">
          Select laps to overlay
          <span className="ml-2 text-xs font-normal text-[var(--text-secondary)]">
            (select 2 for delta comparison)
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {cleanLapsList.map((lap) => {
            const isSelected = selectedLaps.includes(lap.lap_number);
            const isBest = lap.lap_number === bestLapNumber;
            return (
              <button
                key={lap.lap_number}
                onClick={() => toggleLap(lap.lap_number)}
                className={`
                  rounded-md px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer
                  border
                  ${
                    isSelected
                      ? "border-[var(--accent-blue)] bg-[var(--accent-blue)]/20 text-[var(--accent-blue)]"
                      : "border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)]"
                  }
                `}
              >
                L{lap.lap_number}
                <span className="ml-1 opacity-70">{formatLapTime(lap.lap_time_s)}</span>
                {isBest && (
                  <span className="ml-1 text-[var(--accent-green)]">*</span>
                )}
              </button>
            );
          })}
        </div>
        {selectedLaps.length > 0 && (
          <div className="mt-2 text-xs text-[var(--text-secondary)]">
            Selected: {selectedLaps.map((n) => `L${n}`).join(", ")}
            {selectedLaps.length === 2 && " (delta comparison active)"}
          </div>
        )}
      </div>

      {/* LinkedSpeedMap */}
      {selectedLaps.length > 0 && (
        <LinkedSpeedMap
          sessionId={sessionId}
          selectedLaps={selectedLaps}
          corners={corners.length > 0 ? corners : undefined}
        />
      )}

      {/* BrakeThrottle */}
      {gTraces.length > 0 && (
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-3">
          <BrakeThrottle laps={gTraces} corners={cornerZones} height={300} />
        </div>
      )}
    </div>
  );
}

/** Outer wrapper that handles loading and provides a key for re-mounting when laps change. */
export default function SpeedTraceTab() {
  const { activeSessionId } = useSessionStore();
  const { data: laps, isLoading: lapsLoading } = useSessionLaps(activeSessionId);
  const { data: corners } = useCorners(activeSessionId);

  if (!activeSessionId) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
        Select a session to view speed traces
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

  const allLaps = laps ?? [];
  if (allLaps.length === 0) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
        No laps available
      </div>
    );
  }

  // Key on session+lap numbers so state resets when data changes
  const lapsKey = `${activeSessionId}-${allLaps.map((l) => l.lap_number).join(",")}`;

  return (
    <SpeedTraceContent
      key={lapsKey}
      sessionId={activeSessionId}
      allLaps={allLaps}
      corners={corners ?? []}
    />
  );
}
