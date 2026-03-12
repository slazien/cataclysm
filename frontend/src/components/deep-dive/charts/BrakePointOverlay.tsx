'use client';

import { useCallback, useMemo } from 'react';
import { Marker, Source, Layer } from 'react-map-gl/mapbox';
import { bisectLeft } from 'd3-array';
import { useAllLapCorners, useOptimalComparison } from '@/hooks/useAnalysis';
import { useSessionLaps } from '@/hooks/useSession';
import { useSessionStore } from '@/stores';
import { useAnalysisStore } from '@/stores';
import { colors } from '@/lib/design-tokens';
import type { LapData } from '@/lib/types';
import type { GeoJSON } from 'geojson';

interface BrakePointOverlayProps {
  sessionId: string;
  cornerNumber: number;
  lapData: LapData;
}

/** Size brake dot by peak_brake_g (harder brake = bigger) */
function dotRadius(peakG: number | null): number {
  if (!peakG || peakG <= 0) return 4;
  // Clamp to 0.3–1.5g → 3–8px radius
  const clamped = Math.max(0.3, Math.min(peakG, 1.5));
  return 3 + ((clamped - 0.3) / 1.2) * 5;
}

/** Compute [lon, lat] at a given distance along the track outline.
 *  Uses d3.bisectLeft for robust binary search (never returns -1). */
function interpolateLatLon(
  distance: number,
  lapData: LapData,
): [number, number] | null {
  if (lapData.distance_m.length === 0) return null;
  const idx = bisectLeft(lapData.distance_m, distance);
  if (idx <= 0) return [lapData.lon[0], lapData.lat[0]];
  if (idx >= lapData.distance_m.length) {
    return [lapData.lon[lapData.lon.length - 1], lapData.lat[lapData.lat.length - 1]];
  }

  const d0 = lapData.distance_m[idx - 1];
  const d1 = lapData.distance_m[idx];
  const t = d1 !== d0 ? (distance - d0) / (d1 - d0) : 0;

  return [
    lapData.lon[idx - 1] + t * (lapData.lon[idx] - lapData.lon[idx - 1]),
    lapData.lat[idx - 1] + t * (lapData.lat[idx] - lapData.lat[idx - 1]),
  ];
}

/** Build a short perpendicular line across the track at a point */
function buildPerpendicularLine(
  center: [number, number],
  lapData: LapData,
  distance: number,
  widthM: number = 10,
): GeoJSON.Feature | null {
  // Get two nearby points to determine track heading
  const before = interpolateLatLon(Math.max(0, distance - 5), lapData);
  const after = interpolateLatLon(distance + 5, lapData);
  if (!before || !after) return null;

  const dx = after[0] - before[0];
  const dy = after[1] - before[1];
  const len = Math.sqrt(dx * dx + dy * dy);
  if (len === 0) return null;

  // Perpendicular direction (normal to track heading)
  const nx = -dy / len;
  const ny = dx / len;

  // Convert widthM to approximate degrees (~111,000 m per degree latitude)
  const mPerDegLat = 111000;
  const mPerDegLon = 111000 * Math.cos((center[1] * Math.PI) / 180);
  const halfW = widthM / 2;

  const p1: [number, number] = [
    center[0] + (nx * halfW) / mPerDegLon,
    center[1] + (ny * halfW) / mPerDegLat,
  ];
  const p2: [number, number] = [
    center[0] - (nx * halfW) / mPerDegLon,
    center[1] - (ny * halfW) / mPerDegLat,
  ];

  return {
    type: 'Feature',
    properties: {},
    geometry: { type: 'LineString', coordinates: [p1, p2] },
  };
}

export function BrakePointOverlay({
  sessionId,
  cornerNumber,
  lapData,
}: BrakePointOverlayProps) {
  const { data: allLapCorners } = useAllLapCorners(sessionId);
  const { data: optimalComparison } = useOptimalComparison(sessionId);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { data: laps } = useSessionLaps(activeSessionId);
  const hoveredPedalPoint = useAnalysisStore((s) => s.hoveredPedalPoint);
  const setHoveredPedalPoint = useAnalysisStore((s) => s.setHoveredPedalPoint);

  const bestLapNumber = useMemo(() => {
    if (!laps || laps.length === 0) return null;
    let best = laps[0];
    for (const lap of laps) {
      if (lap.lap_time_s < best.lap_time_s) best = lap;
    }
    return best.lap_number;
  }, [laps]);

  // Collect per-lap brake points for this corner
  const brakeDots = useMemo(() => {
    if (!allLapCorners) return [];
    const dots: Array<{
      lon: number;
      lat: number;
      lapNumber: number;
      isBest: boolean;
      radius: number;
      brakePointM: number;
    }> = [];

    for (const [lapStr, corners] of Object.entries(allLapCorners)) {
      const lapNum = Number(lapStr);
      const corner = corners.find((c) => c.number === cornerNumber);
      if (!corner?.brake_point_m) continue;

      const pos = interpolateLatLon(corner.brake_point_m, lapData);
      if (!pos) continue;

      dots.push({
        lon: pos[0],
        lat: pos[1],
        lapNumber: lapNum,
        isBest: lapNum === bestLapNumber,
        radius: dotRadius(corner.peak_brake_g),
        brakePointM: corner.brake_point_m,
      });
    }

    return dots;
  }, [allLapCorners, cornerNumber, lapData, bestLapNumber]);

  // Collect per-lap throttle commit points for this corner
  const throttleDots = useMemo(() => {
    if (!allLapCorners) return [];
    const dots: Array<{
      lon: number;
      lat: number;
      lapNumber: number;
      isBest: boolean;
      throttleCommitM: number;
    }> = [];

    for (const [lapStr, corners] of Object.entries(allLapCorners)) {
      const lapNum = Number(lapStr);
      const corner = corners.find((c) => c.number === cornerNumber);
      if (!corner?.throttle_commit_m) continue;

      const pos = interpolateLatLon(corner.throttle_commit_m, lapData);
      if (!pos) continue;

      dots.push({
        lon: pos[0],
        lat: pos[1],
        lapNumber: lapNum,
        isBest: lapNum === bestLapNumber,
        throttleCommitM: corner.throttle_commit_m,
      });
    }
    return dots;
  }, [allLapCorners, cornerNumber, lapData, bestLapNumber]);

  // Best-lap brake line (solid green)
  const bestBrakeLine = useMemo((): GeoJSON.FeatureCollection | null => {
    const bestDot = brakeDots.find((d) => d.isBest);
    if (!bestDot) return null;

    // Find the best lap's corner to get brake_point_m for heading
    const bestCorners = allLapCorners?.[String(bestLapNumber)];
    const bestCorner = bestCorners?.find((c) => c.number === cornerNumber);
    const brakeDist = bestCorner?.brake_point_m;
    if (brakeDist == null) return null;

    const line = buildPerpendicularLine([bestDot.lon, bestDot.lat], lapData, brakeDist, 14);
    if (!line) return null;

    return { type: 'FeatureCollection', features: [line] };
  }, [brakeDots, allLapCorners, bestLapNumber, cornerNumber, lapData]);

  // Optimal brake line (dashed) — offset from best by brake_gap_m
  // Only shown when brake_gap_m < 0 (driver brakes earlier than physics model).
  // When brake_gap_m > 0, the driver already outperforms the model — showing a
  // "brake earlier" line would contradict the coaching advice.
  const optimalBrakeLine = useMemo((): GeoJSON.FeatureCollection | null => {
    const opp = optimalComparison?.corner_opportunities?.find(
      (o) => o.corner_number === cornerNumber,
    );
    if (!opp?.brake_gap_m || opp.brake_gap_m > 0) return null;

    const bestCorners = allLapCorners?.[String(bestLapNumber)];
    const bestCorner = bestCorners?.find((c) => c.number === cornerNumber);
    if (!bestCorner?.brake_point_m) return null;

    // brake_gap_m positive = driver brakes later than optimal → optimal is earlier
    const optimalDist = bestCorner.brake_point_m - opp.brake_gap_m;
    const pos = interpolateLatLon(optimalDist, lapData);
    if (!pos) return null;

    const line = buildPerpendicularLine(pos, lapData, optimalDist, 14);
    if (!line) return null;

    return { type: 'FeatureCollection', features: [line] };
  }, [optimalComparison, allLapCorners, bestLapNumber, cornerNumber, lapData]);

  // Best-lap throttle line (solid blue)
  const bestThrottleLine = useMemo((): GeoJSON.FeatureCollection | null => {
    const bestDot = throttleDots.find((d) => d.isBest);
    if (!bestDot) return null;

    const bestCorners = allLapCorners?.[String(bestLapNumber)];
    const bestCorner = bestCorners?.find((c) => c.number === cornerNumber);
    const throttleDist = bestCorner?.throttle_commit_m;
    if (throttleDist == null) return null;

    const line = buildPerpendicularLine([bestDot.lon, bestDot.lat], lapData, throttleDist, 14);
    if (!line) return null;

    return { type: 'FeatureCollection', features: [line] };
  }, [throttleDots, allLapCorners, bestLapNumber, cornerNumber, lapData]);

  // Optimal throttle line (dashed green)
  const optimalThrottleLine = useMemo((): GeoJSON.FeatureCollection | null => {
    const opp = optimalComparison?.corner_opportunities?.find(
      (o) => o.corner_number === cornerNumber,
    );
    if (!opp?.throttle_gap_m) return null;

    const bestCorners = allLapCorners?.[String(bestLapNumber)];
    const bestCorner = bestCorners?.find((c) => c.number === cornerNumber);
    if (!bestCorner?.throttle_commit_m) return null;

    const optimalDist = bestCorner.throttle_commit_m - opp.throttle_gap_m;
    const pos = interpolateLatLon(optimalDist, lapData);
    if (!pos) return null;

    const line = buildPerpendicularLine(pos, lapData, optimalDist, 14);
    if (!line) return null;

    return { type: 'FeatureCollection', features: [line] };
  }, [optimalComparison, allLapCorners, bestLapNumber, cornerNumber, lapData]);

  // Stats for the info panel
  const stats = useMemo(() => {
    if (brakeDots.length === 0) return null;

    const bestCorners = allLapCorners?.[String(bestLapNumber)];
    const bestCorner = bestCorners?.find((c) => c.number === cornerNumber);
    const apexDist = bestCorner?.apex_distance_m ?? 0;
    const brakeDist = bestCorner?.brake_point_m ?? 0;
    const distToApex = brakeDist > 0 && apexDist > 0 ? Math.round(apexDist - brakeDist) : null;

    // Compute scatter spread (std dev of brake distances)
    const allBrakeDists: number[] = [];
    if (allLapCorners) {
      for (const corners of Object.values(allLapCorners)) {
        const c = corners.find((cc) => cc.number === cornerNumber);
        if (c?.brake_point_m != null) allBrakeDists.push(c.brake_point_m);
      }
    }
    let spreadM: number | null = null;
    if (allBrakeDists.length >= 2) {
      const mean = allBrakeDists.reduce((a, b) => a + b, 0) / allBrakeDists.length;
      const variance = allBrakeDists.reduce((a, b) => a + (b - mean) ** 2, 0) / allBrakeDists.length;
      spreadM = Math.sqrt(variance);
    }

    const opp = optimalComparison?.corner_opportunities?.find(
      (o) => o.corner_number === cornerNumber,
    );

    return { distToApex, spreadM, brakeGapM: opp?.brake_gap_m ?? null, throttleGapM: opp?.throttle_gap_m ?? null };
  }, [brakeDots, allLapCorners, bestLapNumber, cornerNumber, optimalComparison]);

  const handleDotEnter = useCallback(
    (lapNumber: number, brakePointM: number) => {
      setHoveredPedalPoint({ lapNumber, distanceM: brakePointM, type: 'brake' });
    },
    [setHoveredPedalPoint],
  );

  const handleThrottleDotEnter = useCallback(
    (lapNumber: number, throttleCommitM: number) => {
      setHoveredPedalPoint({ lapNumber, distanceM: throttleCommitM, type: 'throttle' });
    },
    [setHoveredPedalPoint],
  );

  const handleDotLeave = useCallback(() => {
    setHoveredPedalPoint(null);
  }, [setHoveredPedalPoint]);

  if (brakeDots.length === 0 && throttleDots.length === 0) return null;

  return (
    <>
      {/* Per-lap brake scatter dots */}
      {brakeDots.map((dot) => {
        const isHovered = hoveredPedalPoint?.lapNumber === dot.lapNumber && hoveredPedalPoint?.type === 'brake';
        const highlightRadius = isHovered ? dot.radius + 4 : dot.radius;

        return (
          <Marker
            key={`brake-${dot.lapNumber}`}
            longitude={dot.lon}
            latitude={dot.lat}
            anchor="center"
          >
            <div
              onMouseEnter={() => handleDotEnter(dot.lapNumber, dot.brakePointM)}
              onMouseLeave={handleDotLeave}
              style={{
                width: highlightRadius * 2,
                height: highlightRadius * 2,
                borderRadius: '50%',
                backgroundColor: `${colors.motorsport.brake}${dot.isBest ? '' : isHovered ? 'dd' : '88'}`,
                border: dot.isBest || isHovered ? '2px solid #fff' : 'none',
                boxShadow: isHovered
                  ? `0 0 12px ${colors.motorsport.brake}cc`
                  : dot.isBest
                    ? `0 0 8px ${colors.motorsport.brake}88`
                    : 'none',
                transition: 'all 150ms ease-out',
                cursor: 'pointer',
              }}
              title={`Lap ${dot.lapNumber}${dot.isBest ? ' (best)' : ''}`}
            />
          </Marker>
        );
      })}

      {/* Best-lap brake line (solid red) */}
      {bestBrakeLine && (
        <Source id="best-brake-line" type="geojson" data={bestBrakeLine}>
          <Layer
            id="best-brake-line-layer"
            type="line"
            paint={{
              'line-color': colors.motorsport.brake,
              'line-width': 3,
              'line-opacity': 0.9,
            }}
            layout={{
              'line-cap': 'round',
            }}
          />
        </Source>
      )}

      {/* Optimal brake line (dashed red) */}
      {optimalBrakeLine && (
        <Source id="optimal-brake-line" type="geojson" data={optimalBrakeLine}>
          <Layer
            id="optimal-brake-line-layer"
            type="line"
            paint={{
              'line-color': colors.motorsport.brake,
              'line-width': 2.5,
              'line-opacity': 0.8,
              'line-dasharray': [4, 3],
            }}
            layout={{
              'line-cap': 'round',
            }}
          />
        </Source>
      )}

      {/* Per-lap throttle commit dots (triangles) */}
      {throttleDots.map((dot) => {
        const isHovered = hoveredPedalPoint?.lapNumber === dot.lapNumber && hoveredPedalPoint?.type === 'throttle';
        const size = isHovered ? 14 : 10;

        return (
          <Marker
            key={`throttle-${dot.lapNumber}`}
            longitude={dot.lon}
            latitude={dot.lat}
            anchor="center"
          >
            <div
              onMouseEnter={() => handleThrottleDotEnter(dot.lapNumber, dot.throttleCommitM)}
              onMouseLeave={handleDotLeave}
              style={{
                width: 0,
                height: 0,
                borderLeft: `${size / 2}px solid transparent`,
                borderRight: `${size / 2}px solid transparent`,
                borderBottom: `${size}px solid ${
                  dot.isBest
                    ? colors.motorsport.throttle
                    : `${colors.motorsport.throttle}${isHovered ? 'dd' : '88'}`
                }`,
                filter: isHovered
                  ? `drop-shadow(0 0 6px ${colors.motorsport.throttle}cc)`
                  : dot.isBest
                    ? `drop-shadow(0 0 4px ${colors.motorsport.throttle}66)`
                    : 'none',
                transition: 'all 150ms ease-out',
                cursor: 'pointer',
              }}
              title={`Throttle L${dot.lapNumber}${dot.isBest ? ' (best)' : ''}`}
            />
          </Marker>
        );
      })}

      {/* Best-lap throttle line (solid green) */}
      {bestThrottleLine && (
        <Source id="best-throttle-line" type="geojson" data={bestThrottleLine}>
          <Layer
            id="best-throttle-line-layer"
            type="line"
            paint={{
              'line-color': colors.motorsport.throttle,
              'line-width': 3,
              'line-opacity': 0.9,
            }}
            layout={{ 'line-cap': 'round' }}
          />
        </Source>
      )}

      {/* Optimal throttle line (dashed green) */}
      {optimalThrottleLine && (
        <Source id="optimal-throttle-line" type="geojson" data={optimalThrottleLine}>
          <Layer
            id="optimal-throttle-line-layer"
            type="line"
            paint={{
              'line-color': colors.motorsport.throttle,
              'line-width': 2.5,
              'line-opacity': 0.8,
              'line-dasharray': [4, 3],
            }}
            layout={{ 'line-cap': 'round' }}
          />
        </Source>
      )}

      {/* Apex marker (diamond) */}
      {(() => {
        const bestCorners = allLapCorners?.[String(bestLapNumber)];
        const bestCorner = bestCorners?.find((c) => c.number === cornerNumber);
        if (!bestCorner) return null;
        const apexPos = interpolateLatLon(bestCorner.apex_distance_m, lapData);
        if (!apexPos) return null;

        return (
          <Marker longitude={apexPos[0]} latitude={apexPos[1]} anchor="center">
            <div
              style={{
                width: 10,
                height: 10,
                backgroundColor: colors.motorsport.optimal,
                transform: 'rotate(45deg)',
                border: '1px solid #fff',
                boxShadow: `0 0 4px ${colors.motorsport.optimal}66`,
              }}
              title="Apex"
            />
          </Marker>
        );
      })()}

      {/* Stats overlay */}
      {stats && (
        <div
          className="absolute bottom-2 left-2 z-10 rounded-lg px-3 py-2"
          style={{
            backgroundColor: 'rgba(10, 12, 16, 0.85)',
            backdropFilter: 'blur(8px)',
          }}
        >
          {stats.distToApex != null && (
            <p className="text-xs text-[var(--text-primary)]">
              <span className="text-[var(--text-secondary)]">Best brake: </span>
              <span className="font-semibold tabular-nums">{stats.distToApex}m</span>
              <span className="text-[var(--text-secondary)]"> before apex</span>
            </p>
          )}
          {stats.spreadM != null && (
            <p className="text-xs text-[var(--text-primary)]">
              <span className="text-[var(--text-secondary)]">Spread: </span>
              <span className="font-semibold tabular-nums">±{stats.spreadM.toFixed(1)}m</span>
            </p>
          )}
          {stats.brakeGapM != null && Math.abs(stats.brakeGapM) >= 0.5 && (
            <p className="text-xs text-[var(--text-primary)]">
              <span style={{ color: colors.motorsport.brake }} className="text-[var(--text-secondary)]">Brake gap: </span>
              <span className="font-semibold tabular-nums">
                {stats.brakeGapM > 0 ? `${stats.brakeGapM.toFixed(1)}m late` : `${Math.abs(stats.brakeGapM).toFixed(1)}m early`}
              </span>
            </p>
          )}
          {stats.throttleGapM != null && Math.abs(stats.throttleGapM) >= 0.5 && (
            <p className="text-xs text-[var(--text-primary)]">
              <span style={{ color: colors.motorsport.throttle }} className="text-[var(--text-secondary)]">Throttle gap: </span>
              <span className="font-semibold tabular-nums">
                {stats.throttleGapM > 0 ? `${stats.throttleGapM.toFixed(1)}m late` : `${Math.abs(stats.throttleGapM).toFixed(1)}m early`}
              </span>
            </p>
          )}
          <div className="mt-1.5 space-y-0.5 text-[10px] text-[var(--text-secondary)]">
            {/* Brake row */}
            <div className="flex items-center gap-2">
              <span style={{ color: colors.motorsport.brake }} className="font-semibold">Brake</span>
              <span className="flex items-center gap-1">
                <span style={{ display: 'inline-block', width: 5, height: 5, borderRadius: '50%', backgroundColor: `${colors.motorsport.brake}88` }} />
                per lap
              </span>
              <span className="flex items-center gap-1">
                <span style={{ display: 'inline-block', width: 8, height: 2, backgroundColor: colors.motorsport.brake, borderRadius: 1 }} />
                best
              </span>
              {optimalBrakeLine && (
                <span className="flex items-center gap-1">
                  <span style={{ display: 'inline-block', width: 8, height: 0, borderTop: `2px dashed ${colors.motorsport.brake}` }} />
                  optimal
                </span>
              )}
            </div>
            {/* Throttle row */}
            <div className="flex items-center gap-2">
              <span style={{ color: colors.motorsport.throttle }} className="font-semibold">Throttle</span>
              <span className="flex items-center gap-1">
                <span style={{ display: 'inline-block', width: 0, height: 0, borderLeft: '3px solid transparent', borderRight: '3px solid transparent', borderBottom: `5px solid ${colors.motorsport.throttle}88` }} />
                per lap
              </span>
              <span className="flex items-center gap-1">
                <span style={{ display: 'inline-block', width: 8, height: 2, backgroundColor: colors.motorsport.throttle, borderRadius: 1 }} />
                best
              </span>
              {optimalThrottleLine && (
                <span className="flex items-center gap-1">
                  <span style={{ display: 'inline-block', width: 8, height: 0, borderTop: `2px dashed ${colors.motorsport.throttle}` }} />
                  optimal
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
