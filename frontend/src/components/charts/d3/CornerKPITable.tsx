"use client";

import { useState, useMemo } from "react";
import type { Corner, CornerDelta } from "@/lib/types";

interface CornerKPITableProps {
  corners: Corner[];
  compCorners?: Corner[];
  cornerDeltas?: CornerDelta[];
  bestLap: number;
  compLap?: number;
}

type SortKey =
  | "number"
  | "type"
  | "apex"
  | "minSpeed"
  | "brakePoint"
  | "peakBrakeG"
  | "throttleCommit"
  | "delta";

type SortDir = "asc" | "desc";

const CORNER_TYPE_COLORS: Record<string, string> = {
  slow: "#d29922",
  medium: "#58a6ff",
  fast: "#3fb950",
};

const SLOW_MPH = 40;
const MEDIUM_MPH = 80;

function classifyCornerType(corner: Corner): string {
  const mph = corner.min_speed_mph;
  if (mph < SLOW_MPH) return "slow";
  if (mph < MEDIUM_MPH) return "medium";
  return "fast";
}

function formatBrakePoint(m: number | null): string {
  if (m === null) return "\u2014";
  return `${m.toFixed(0)}m`;
}

function formatG(g: number | null): string {
  if (g === null) return "\u2014";
  return `${g.toFixed(2)}G`;
}

function formatThrottle(m: number | null): string {
  if (m === null) return "\u2014";
  return `${m.toFixed(0)}m`;
}

function SortHeader({
  label,
  sKey,
  sortKey,
  sortDir,
  onSort,
}: {
  label: string;
  sKey: SortKey;
  sortKey: SortKey;
  sortDir: SortDir;
  onSort: (key: SortKey) => void;
}) {
  return (
    <th
      className="cursor-pointer select-none px-3 py-2 text-left text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors whitespace-nowrap"
      onClick={() => onSort(sKey)}
    >
      {label}
      {sortKey === sKey && (
        <span className="ml-1">{sortDir === "asc" ? "\u25B2" : "\u25BC"}</span>
      )}
    </th>
  );
}

export default function CornerKPITable({
  corners,
  compCorners,
  cornerDeltas,
  bestLap,
  compLap,
}: CornerKPITableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("number");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const compMap = useMemo(() => {
    if (!compCorners) return {};
    const m: Record<number, Corner> = {};
    for (const c of compCorners) m[c.number] = c;
    return m;
  }, [compCorners]);

  const deltaMap = useMemo(() => {
    if (!cornerDeltas) return {};
    const m: Record<number, number> = {};
    for (const cd of cornerDeltas) m[cd.corner_number] = cd.delta_s;
    return m;
  }, [cornerDeltas]);

  const hasComparison = !!compCorners && compCorners.length > 0;

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const sorted = useMemo(() => {
    const arr = [...corners];
    arr.sort((a, b) => {
      let va: number | string;
      let vb: number | string;
      switch (sortKey) {
        case "number":
          va = a.number;
          vb = b.number;
          break;
        case "type":
          va = classifyCornerType(a);
          vb = classifyCornerType(b);
          break;
        case "apex":
          va = a.apex_type;
          vb = b.apex_type;
          break;
        case "minSpeed":
          va = a.min_speed_mph;
          vb = b.min_speed_mph;
          break;
        case "brakePoint":
          va = a.brake_point_m ?? Infinity;
          vb = b.brake_point_m ?? Infinity;
          break;
        case "peakBrakeG":
          va = a.peak_brake_g ?? 0;
          vb = b.peak_brake_g ?? 0;
          break;
        case "throttleCommit":
          va = a.throttle_commit_m ?? Infinity;
          vb = b.throttle_commit_m ?? Infinity;
          break;
        case "delta":
          va = deltaMap[a.number] ?? 0;
          vb = deltaMap[b.number] ?? 0;
          break;
        default:
          va = a.number;
          vb = b.number;
      }
      if (va < vb) return sortDir === "asc" ? -1 : 1;
      if (va > vb) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return arr;
  }, [corners, sortKey, sortDir, deltaMap]);

  if (corners.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-[var(--text-muted)]">
        No corner data available
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border-color)]">
      <table className="w-full text-sm">
        <thead className="bg-[var(--bg-secondary)]">
          <tr>
            <SortHeader label="Corner" sKey="number" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="Type" sKey="type" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="Apex" sKey="apex" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader
              label={hasComparison ? `Min Speed (L${bestLap})` : "Min Speed"}
              sKey="minSpeed"
              sortKey={sortKey}
              sortDir={sortDir}
              onSort={handleSort}
            />
            {hasComparison && (
              <th className="px-3 py-2 text-left text-xs font-medium text-[var(--text-secondary)] whitespace-nowrap">
                Min Speed (L{compLap})
              </th>
            )}
            <SortHeader label="Brake Point" sKey="brakePoint" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            {hasComparison && (
              <th className="px-3 py-2 text-left text-xs font-medium text-[var(--text-secondary)] whitespace-nowrap">
                Brake Pt (L{compLap})
              </th>
            )}
            <SortHeader label="Peak Brake G" sKey="peakBrakeG" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            {hasComparison && (
              <th className="px-3 py-2 text-left text-xs font-medium text-[var(--text-secondary)] whitespace-nowrap">
                Peak G (L{compLap})
              </th>
            )}
            <SortHeader label="Throttle Commit" sKey="throttleCommit" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            {hasComparison && <SortHeader label="Delta" sKey="delta" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />}
          </tr>
        </thead>
        <tbody>
          {sorted.map((c) => {
            const cType = classifyCornerType(c);
            const typeColor = CORNER_TYPE_COLORS[cType] ?? "var(--text-primary)";
            const cc = compMap[c.number];
            const delta = deltaMap[c.number];
            const speedMph = c.min_speed_mph;
            const compSpeedMph = cc ? cc.min_speed_mph : null;

            return (
              <tr
                key={c.number}
                className="border-t border-[var(--border-color)] hover:bg-[var(--bg-secondary)] transition-colors"
              >
                <td className="px-3 py-2 font-medium text-[var(--text-primary)]">
                  T{c.number}
                </td>
                <td className="px-3 py-2" style={{ color: typeColor }}>
                  {cType.charAt(0).toUpperCase() + cType.slice(1)}
                </td>
                <td className="px-3 py-2 text-[var(--text-secondary)]">
                  {c.apex_type}
                </td>
                <td className="px-3 py-2 text-[var(--text-primary)] tabular-nums">
                  {speedMph.toFixed(1)} mph
                </td>
                {hasComparison && (
                  <td className="px-3 py-2 text-[var(--text-secondary)] tabular-nums">
                    {compSpeedMph !== null ? `${compSpeedMph.toFixed(1)} mph` : "\u2014"}
                  </td>
                )}
                <td className="px-3 py-2 text-[var(--text-secondary)] tabular-nums">
                  {formatBrakePoint(c.brake_point_m)}
                </td>
                {hasComparison && (
                  <td className="px-3 py-2 text-[var(--text-secondary)] tabular-nums">
                    {formatBrakePoint(cc?.brake_point_m ?? null)}
                  </td>
                )}
                <td className="px-3 py-2 text-[var(--text-secondary)] tabular-nums">
                  {formatG(c.peak_brake_g)}
                </td>
                {hasComparison && (
                  <td className="px-3 py-2 text-[var(--text-secondary)] tabular-nums">
                    {formatG(cc?.peak_brake_g ?? null)}
                  </td>
                )}
                <td className="px-3 py-2 text-[var(--text-secondary)] tabular-nums">
                  {formatThrottle(c.throttle_commit_m)}
                </td>
                {hasComparison && (
                  <td
                    className="px-3 py-2 font-medium tabular-nums"
                    style={{
                      color:
                        delta !== undefined
                          ? delta <= 0
                            ? "#3fb950"
                            : "#f85149"
                          : "var(--text-secondary)",
                    }}
                  >
                    {delta !== undefined ? `${delta >= 0 ? "+" : ""}${delta.toFixed(3)}s` : "\u2014"}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
