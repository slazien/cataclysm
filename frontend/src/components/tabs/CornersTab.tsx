"use client";

import { useState, useMemo } from "react";
import { useSessionStore } from "@/store";
import { useSessionLaps, useLapData } from "@/hooks/useSession";
import { useCorners, useAllLapCorners, useDelta, useMultiLapData } from "@/hooks/useAnalysis";
import CornerKPITable from "@/components/charts/d3/CornerKPITable";
import CornerDetailChart from "@/components/charts/d3/CornerDetailChart";
import CornerMiniMap from "@/components/charts/d3/CornerMiniMap";
import BrakeConsistency from "@/components/charts/d3/BrakeConsistency";
import Expandable from "@/components/ui/Expandable";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import { MPS_TO_MPH } from "@/lib/constants";
import type { LapSummary, Corner } from "@/lib/types";

const CORNER_TYPE_TIPS: Record<string, string> = {
  slow: "Slow corner (<40 mph): Prioritize exit speed over mid-corner speed. Brake later, use a late apex, and get on throttle early for the following straight.",
  medium:
    "Medium corner (40-80 mph): Balance entry speed with exit speed. Trail brake to the apex, maintain smooth inputs to maximize grip through the turn.",
  fast: "Fast corner (>80 mph): Prioritize carrying speed -- stay close to the geometric line. Minimize steering input, use progressive brake release, and trust the car's grip.",
};

const CORNER_TYPE_COLORS: Record<string, string> = {
  slow: "#d29922",
  medium: "#58a6ff",
  fast: "#3fb950",
};

const SLOW_MPH = 40;
const MEDIUM_MPH = 80;

function classifyCornerType(corner: Corner): string {
  const mph = corner.min_speed_mps * MPS_TO_MPH;
  if (mph < SLOW_MPH) return "slow";
  if (mph < MEDIUM_MPH) return "medium";
  return "fast";
}

function CornersContent({
  sessionId,
  allLaps,
  corners,
}: {
  sessionId: string;
  allLaps: LapSummary[];
  corners: Corner[];
}) {
  const bestLapNumber = useMemo(() => {
    const cleanLaps = allLaps.filter((l) => l.is_clean);
    if (cleanLaps.length === 0) return allLaps.length > 0 ? allLaps[0].lap_number : null;
    return cleanLaps.reduce((best, l) => (l.lap_time_s < best.lap_time_s ? l : best)).lap_number;
  }, [allLaps]);

  const otherLaps = useMemo(
    () => allLaps.filter((l) => l.is_clean && l.lap_number !== bestLapNumber),
    [allLaps, bestLapNumber],
  );

  const [compLap, setCompLap] = useState<number | null>(
    otherLaps.length > 0 ? otherLaps[0].lap_number : null,
  );

  // Fetch all-lap corners for brake consistency
  const { data: allLapCorners } = useAllLapCorners(sessionId);

  // Delta between best and comparison lap
  const { data: deltaData } = useDelta(sessionId, bestLapNumber, compLap);

  // Comparison lap corners (we can get them from all-lap corners)
  const compCorners = useMemo(() => {
    if (!allLapCorners || compLap === null) return undefined;
    const key = String(compLap);
    return allLapCorners[key] ?? undefined;
  }, [allLapCorners, compLap]);

  // Fetch best lap data for track map
  const { data: bestLapData } = useLapData(sessionId, bestLapNumber);

  // Laps to overlay in corner detail charts
  const detailLapNumbers = useMemo(() => {
    const nums: number[] = [];
    if (bestLapNumber !== null) nums.push(bestLapNumber);
    if (compLap !== null && compLap !== bestLapNumber) nums.push(compLap);
    return nums;
  }, [bestLapNumber, compLap]);

  const { data: detailLapDataList } = useMultiLapData(sessionId, detailLapNumbers);

  // Prepare corner detail lap slices
  const detailLapSlices = useMemo(() => {
    return detailLapDataList.map((ld) => ({
      lapNumber: ld.lap_number,
      distance: ld.distance_m,
      speed: ld.speed_mph,
      longitudinalG: ld.longitudinal_g,
    }));
  }, [detailLapDataList]);

  const compLapOptions = useMemo(
    () => [
      { value: "", label: "None" },
      ...otherLaps.map((l) => ({
        value: String(l.lap_number),
        label: `Lap ${l.lap_number}`,
      })),
    ],
    [otherLaps],
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="text-sm text-[var(--text-primary)]">
            <span className="font-semibold">{corners.length} corners detected</span>
            {bestLapNumber !== null && (
              <span className="text-[var(--text-secondary)]">
                {" "}
                on best lap (L{bestLapNumber})
              </span>
            )}
          </div>
          <div className="w-48">
            <Select
              label="Compare with lap"
              options={compLapOptions}
              value={compLap !== null ? String(compLap) : ""}
              onChange={(e) => {
                const val = e.target.value;
                setCompLap(val ? Number(val) : null);
              }}
            />
          </div>
        </div>
      </div>

      {/* KPI Table */}
      <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
        <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
          Corner KPIs
        </h3>
        <CornerKPITable
          corners={corners}
          compCorners={compCorners}
          cornerDeltas={deltaData?.corner_deltas}
          bestLap={bestLapNumber ?? 0}
          compLap={compLap ?? undefined}
        />
      </div>

      {/* Divider */}
      <div className="border-t border-[var(--border-color)]" />

      {/* Per-corner detail sections */}
      <div className="space-y-3">
        <h2 className="text-base font-bold text-[var(--text-primary)]">
          Corner Details
        </h2>
        {corners.map((c) => {
          const cType = classifyCornerType(c);
          const speedMph = c.min_speed_mps * MPS_TO_MPH;
          const typeLabel = cType.charAt(0).toUpperCase() + cType.slice(1);
          const header = `T${c.number} -- ${speedMph.toFixed(0)} mph (${typeLabel}, ${c.apex_type} apex)`;
          const typeColor = CORNER_TYPE_COLORS[cType];

          // Brake consistency data from all-lap corners
          const brakeData = allLapCorners
            ? Object.entries(allLapCorners).map(([lapStr, lapCorners]) => {
                const match = lapCorners.find((lc) => lc.number === c.number);
                return {
                  lapNumber: Number(lapStr),
                  brakePointM: match?.brake_point_m ?? null,
                };
              })
            : [];

          return (
            <Expandable key={c.number} title={header} titleColor={typeColor}>
              {/* Mini map + detail chart side by side */}
              <div className="flex flex-col gap-4 lg:flex-row">
                {/* Mini map */}
                {bestLapData && (
                  <div className="flex-shrink-0">
                    <CornerMiniMap
                      lat={bestLapData.lat}
                      lon={bestLapData.lon}
                      distance={bestLapData.distance_m}
                      corner={c}
                      allCorners={corners}
                      size={220}
                    />
                  </div>
                )}

                {/* Detail chart */}
                <div className="flex-1 min-w-0">
                  <CornerDetailChart
                    cornerNumber={c.number}
                    laps={detailLapSlices}
                    corner={c}
                    height={380}
                  />
                </div>
              </div>

              {/* Corner type tip */}
              <div
                className="mt-3 rounded-md px-3 py-2 text-xs"
                style={{
                  backgroundColor: `${typeColor}15`,
                  color: typeColor,
                  borderLeft: `3px solid ${typeColor}`,
                }}
              >
                {CORNER_TYPE_TIPS[cType] ?? ""}
              </div>

              {/* Brake consistency */}
              {brakeData.length >= 2 && (
                <div className="mt-4">
                  <BrakeConsistency
                    cornerNumber={c.number}
                    laps={brakeData}
                    entryDistanceM={c.entry_distance_m}
                  />
                </div>
              )}
            </Expandable>
          );
        })}
      </div>
    </div>
  );
}

export default function CornersTab() {
  const { activeSessionId } = useSessionStore();
  const { data: laps, isLoading: lapsLoading } = useSessionLaps(activeSessionId);
  const { data: corners, isLoading: cornersLoading } = useCorners(activeSessionId);

  if (!activeSessionId) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
        Select a session to view corner analysis
      </div>
    );
  }

  if (lapsLoading || cornersLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  const allLaps = laps ?? [];
  const cornerList = corners ?? [];

  if (allLaps.length === 0) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
        No laps available
      </div>
    );
  }

  if (cornerList.length === 0) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
        No corners detected. This may happen with very short laps.
      </div>
    );
  }

  const lapsKey = `${activeSessionId}-${allLaps.map((l) => l.lap_number).join(",")}-corners`;

  return (
    <CornersContent
      key={lapsKey}
      sessionId={activeSessionId}
      allLaps={allLaps}
      corners={cornerList}
    />
  );
}
