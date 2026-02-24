"use client";

import { useState, useMemo } from "react";
import SpeedTrace from "./SpeedTrace";
import DeltaT from "./DeltaT";
import TrackMapInteractive from "./TrackMapInteractive";
import { useMultiLapData, useDelta, useCorners } from "@/hooks/useAnalysis";
import Spinner from "@/components/ui/Spinner";
import type { Corner } from "@/lib/types";

interface LinkedSpeedMapProps {
  sessionId: string;
  selectedLaps: number[];
  corners?: Corner[];
}

export default function LinkedSpeedMap({
  sessionId,
  selectedLaps,
  corners: propCorners,
}: LinkedSpeedMapProps) {
  const [hoverDistance, setHoverDistance] = useState<number | null>(null);
  const [xDomain, setXDomain] = useState<[number, number] | null>(null);

  // Fetch lap data for all selected laps
  const { data: lapDataList, isLoading: lapsLoading } = useMultiLapData(
    sessionId,
    selectedLaps,
  );

  // Fetch corners if not provided as prop
  const { data: fetchedCorners } = useCorners(
    propCorners ? null : sessionId,
  );
  const allCorners = useMemo(
    () => propCorners ?? fetchedCorners ?? [],
    [propCorners, fetchedCorners],
  );

  // When exactly 2 laps selected, fetch delta-T
  // Use first lap as ref (typically the best), second as comp
  const refLap = selectedLaps.length === 2 ? selectedLaps[0] : null;
  const compLap = selectedLaps.length === 2 ? selectedLaps[1] : null;
  const { data: deltaData, isLoading: deltaLoading } = useDelta(
    sessionId,
    refLap,
    compLap,
  );

  // Transform lap data for SpeedTrace
  const speedTraces = useMemo(() => {
    return lapDataList.map((ld) => ({
      lapNumber: ld.lap_number,
      distance: ld.distance_m,
      speed: ld.speed_mph,
    }));
  }, [lapDataList]);

  // Corner zones for line charts (entry/exit distance)
  const cornerZones = useMemo(() => {
    return allCorners.map((c) => ({
      number: c.number,
      entry: c.entry_distance_m,
      exit: c.exit_distance_m,
    }));
  }, [allCorners]);

  // Corner apexes for track map (need lat/lon from lap data)
  const cornerApexes = useMemo(() => {
    if (lapDataList.length === 0 || allCorners.length === 0) return [];

    // Use first selected lap's data for finding apex positions
    const primaryLap = lapDataList[0];
    const totalDist = primaryLap.distance_m;

    return allCorners.map((c) => {
      // Binary search for apex distance index
      let idx = 0;
      for (let i = 0; i < totalDist.length; i++) {
        if (totalDist[i] >= c.apex_distance_m) {
          idx = i;
          break;
        }
        idx = i;
      }

      return {
        number: c.number,
        apex_lat: primaryLap.lat[idx] ?? 0,
        apex_lon: primaryLap.lon[idx] ?? 0,
      };
    });
  }, [lapDataList, allCorners]);

  // Primary lap for track map (first selected)
  const primaryLapData = lapDataList.length > 0 ? lapDataList[0] : null;

  // Delta array aligned to primary lap's distance for track map coloring
  const trackMapDelta = useMemo(() => {
    if (!deltaData || !primaryLapData) return undefined;

    // If delta data distance array matches primary lap, use delta directly
    // Otherwise, interpolate delta onto primary lap distance points
    if (deltaData.distance_m.length === primaryLapData.distance_m.length) {
      return deltaData.delta_s;
    }

    // Simple linear interpolation of delta onto primary lap distances
    const result: number[] = [];
    let j = 0;
    for (let i = 0; i < primaryLapData.distance_m.length; i++) {
      const targetDist = primaryLapData.distance_m[i];
      while (
        j < deltaData.distance_m.length - 1 &&
        deltaData.distance_m[j + 1] < targetDist
      ) {
        j++;
      }
      if (j >= deltaData.distance_m.length - 1) {
        result.push(deltaData.delta_s[deltaData.delta_s.length - 1]);
      } else {
        const d0 = deltaData.distance_m[j];
        const d1 = deltaData.distance_m[j + 1];
        const t = d1 > d0 ? (targetDist - d0) / (d1 - d0) : 0;
        const v0 = deltaData.delta_s[j];
        const v1 = deltaData.delta_s[j + 1];
        result.push(v0 + t * (v1 - v0));
      }
    }
    return result;
  }, [deltaData, primaryLapData]);

  if (selectedLaps.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-[var(--text-muted)]">
        Select at least one lap to view speed trace
      </div>
    );
  }

  if (lapsLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (lapDataList.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-[var(--text-muted)]">
        No lap data available for selected laps
      </div>
    );
  }

  const showDelta = selectedLaps.length === 2 && deltaData && !deltaLoading;

  return (
    <div className="space-y-4">
      {/* Speed Trace */}
      <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-3">
        <SpeedTrace
          laps={speedTraces}
          corners={cornerZones}
          onHoverDistance={setHoverDistance}
          highlightDistance={hoverDistance}
          xDomain={xDomain}
          onXDomainChange={setXDomain}
          height={350}
        />
      </div>

      {/* Delta-T (only when 2 laps selected) */}
      {selectedLaps.length === 2 && (
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-3">
          {deltaLoading ? (
            <div className="flex items-center justify-center py-8">
              <Spinner />
            </div>
          ) : showDelta ? (
            <DeltaT
              distance={deltaData.distance_m}
              delta={deltaData.delta_s}
              refLap={refLap!}
              compLap={compLap!}
              corners={cornerZones}
              onHoverDistance={setHoverDistance}
              highlightDistance={hoverDistance}
              xDomain={xDomain}
              onXDomainChange={setXDomain}
              height={250}
            />
          ) : (
            <div className="flex items-center justify-center py-8 text-sm text-[var(--text-muted)]">
              Delta data not available
            </div>
          )}
        </div>
      )}

      {/* Track Map */}
      {primaryLapData && (
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-3">
          <TrackMapInteractive
            lat={primaryLapData.lat}
            lon={primaryLapData.lon}
            heading={primaryLapData.heading_deg}
            speed={primaryLapData.speed_mph}
            distance={primaryLapData.distance_m}
            delta={trackMapDelta}
            corners={cornerApexes}
            cursorDistance={hoverDistance}
            mapLap={primaryLapData.lap_number}
            height={400}
          />
        </div>
      )}
    </div>
  );
}
