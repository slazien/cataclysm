'use client';

import { useMemo, useState } from 'react';
import { useMiniSectors } from '@/hooks/useAnalysis';
import { useSessionStore } from '@/stores';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { colors } from '@/lib/design-tokens';
import type { MiniSector, MiniSectorLapData } from '@/lib/types';

const SVG_WIDTH = 500;
const SVG_HEIGHT = 400;
const PADDING = 20;

const SECTOR_COLORS: Record<string, string> = {
  pb: colors.motorsport.pb,
  faster: colors.motorsport.throttle,
  slower: colors.motorsport.brake,
  neutral: colors.motorsport.neutral,
};

function projectGps(
  gpsPoints: [number, number][],
  allSectors: MiniSector[],
  width: number,
  height: number,
  padding: number,
): { x: number[]; y: number[] } {
  // Collect all GPS points from all sectors to compute bounds
  const allPts = allSectors.flatMap((s) => s.gps_points);
  if (allPts.length === 0) return { x: [], y: [] };

  const lats = allPts.map((p) => p[0]);
  const lons = allPts.map((p) => p[1]);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);

  const latRange = maxLat - minLat || 1e-6;
  const lonRange = maxLon - minLon || 1e-6;
  const midLat = (minLat + maxLat) / 2;
  const lonScale = Math.cos((midLat * Math.PI) / 180);

  const dataW = lonRange * lonScale;
  const dataH = latRange;
  const availW = width - 2 * padding;
  const availH = height - 2 * padding;
  const scale = Math.min(availW / dataW, availH / dataH);

  const scaledW = dataW * scale;
  const scaledH = dataH * scale;
  const offsetX = padding + (availW - scaledW) / 2;
  const offsetY = padding + (availH - scaledH) / 2;

  const x = gpsPoints.map((p) => offsetX + (p[1] - minLon) * lonScale * scale);
  const y = gpsPoints.map((p) => offsetY + scaledH - (p[0] - minLat) * scale);

  return { x, y };
}

interface SectorPath {
  d: string;
  color: string;
  sectorIndex: number;
}

function buildSectorPaths(
  sectors: MiniSector[],
  lapData: MiniSectorLapData | null,
): SectorPath[] {
  if (sectors.length === 0) return [];

  return sectors.map((sector) => {
    const { x, y } = projectGps(sector.gps_points, sectors, SVG_WIDTH, SVG_HEIGHT, PADDING);
    if (x.length < 2) return { d: '', color: colors.text.muted, sectorIndex: sector.index };

    const points = x.map((xi, i) => `${xi},${y[i]}`);
    const d = 'M' + points.join('L');

    let classification = 'neutral';
    if (lapData && lapData.classifications[sector.index]) {
      classification = lapData.classifications[sector.index];
    }

    return {
      d,
      color: SECTOR_COLORS[classification] ?? colors.text.muted,
      sectorIndex: sector.index,
    };
  });
}

interface TooltipData {
  sectorIndex: number;
  time: number;
  delta: number;
  classification: string;
  x: number;
  y: number;
}

export function MiniSectorMap() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { data, isLoading } = useMiniSectors(activeSessionId, 20);
  const [selectedLap, setSelectedLap] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);

  // Available laps
  const lapNumbers = useMemo(() => {
    if (!data?.lap_data) return [];
    return Object.keys(data.lap_data)
      .map(Number)
      .sort((a, b) => a - b);
  }, [data]);

  // Auto-select first lap
  const activeLap = selectedLap ?? (lapNumbers.length > 0 ? String(lapNumbers[0]) : null);
  const lapData = activeLap && data?.lap_data ? data.lap_data[activeLap] ?? null : null;

  const sectorPaths = useMemo(() => {
    if (!data?.sectors) return [];
    return buildSectorPaths(data.sectors, lapData);
  }, [data, lapData]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <CircularProgress size={20} />
      </div>
    );
  }

  if (!data || data.sectors.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">No mini-sector data available</p>
      </div>
    );
  }

  const handleSectorHover = (sectorIndex: number, event: React.MouseEvent) => {
    if (!lapData) return;
    const rect = (event.currentTarget as SVGElement).closest('svg')?.getBoundingClientRect();
    if (!rect) return;
    setTooltip({
      sectorIndex,
      time: lapData.sector_times_s[sectorIndex],
      delta: lapData.deltas_s[sectorIndex],
      classification: lapData.classifications[sectorIndex],
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    });
  };

  return (
    <div className="flex h-full flex-col gap-2 p-3">
      {/* Header with lap selector */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          Mini-Sector Map
        </h3>
        <select
          value={activeLap ?? ''}
          onChange={(e) => setSelectedLap(e.target.value)}
          className="rounded border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-2 py-1 text-xs text-[var(--text-primary)]"
        >
          {lapNumbers.map((ln) => (
            <option key={ln} value={ln}>
              Lap {ln}
            </option>
          ))}
        </select>
      </div>

      {/* SVG Track */}
      <div className="relative min-h-0 flex-1 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <svg
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          className="h-full w-full"
          preserveAspectRatio="xMidYMid meet"
          onMouseLeave={() => setTooltip(null)}
        >
          {sectorPaths.map((seg) =>
            seg.d ? (
              <path
                key={seg.sectorIndex}
                d={seg.d}
                fill="none"
                stroke={seg.color}
                strokeWidth={4}
                strokeLinecap="round"
                strokeLinejoin="round"
                onMouseEnter={(e) => handleSectorHover(seg.sectorIndex, e)}
                onMouseMove={(e) => handleSectorHover(seg.sectorIndex, e)}
                onMouseLeave={() => setTooltip(null)}
                className="cursor-pointer"
                style={{ opacity: tooltip && tooltip.sectorIndex !== seg.sectorIndex ? 0.4 : 1 }}
              />
            ) : null,
          )}
        </svg>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="pointer-events-none absolute z-10 rounded bg-[var(--bg-elevated)] px-2 py-1 text-xs shadow-lg"
            style={{ left: tooltip.x + 12, top: tooltip.y - 30 }}
          >
            <div className="font-semibold text-[var(--text-primary)]">
              Sector {tooltip.sectorIndex + 1}
            </div>
            <div className="text-[var(--text-secondary)]">{tooltip.time.toFixed(3)}s</div>
            <div
              style={{
                color:
                  tooltip.delta < -0.001
                    ? colors.motorsport.throttle
                    : tooltip.delta > 0.001
                      ? colors.motorsport.brake
                      : colors.motorsport.pb,
              }}
            >
              {tooltip.delta >= 0 ? '+' : ''}
              {tooltip.delta.toFixed(3)}s
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 text-[10px] text-[var(--text-secondary)]">
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-2 w-3 rounded-sm"
            style={{ backgroundColor: colors.motorsport.pb }}
          />
          PB
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-2 w-3 rounded-sm"
            style={{ backgroundColor: colors.motorsport.throttle }}
          />
          Faster
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-2 w-3 rounded-sm"
            style={{ backgroundColor: colors.motorsport.brake }}
          />
          Slower
        </span>
      </div>
    </div>
  );
}
