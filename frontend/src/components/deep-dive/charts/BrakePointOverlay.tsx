'use client';

import { useMemo } from 'react';
import { Marker, Source, Layer } from 'react-map-gl/mapbox';
import { useAllLapCorners, useOptimalComparison } from '@/hooks/useAnalysis';
import { useSession, useSessionLaps } from '@/hooks/useSession';
import { useSessionStore } from '@/stores';
import { colors } from '@/lib/design-tokens';
import type { Corner, LapData } from '@/lib/types';
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

/** Resolve brake GPS position: prefer lat/lon, fall back to distance interpolation */
function getBrakePos(
  corner: Corner,
  lapData: LapData,
  interpolate: (d: number, ld: LapData) => [number, number] | null,
): [number, number] | null {
  if (corner.brake_point_lat != null && corner.brake_point_lon != null) {
    return [corner.brake_point_lon, corner.brake_point_lat];
  }
  if (corner.brake_point_m != null) {
    return interpolate(corner.brake_point_m, lapData);
  }
  return null;
}

/** Compute [lon, lat] at a given distance along the track (duplicated from TrackMapSatellite to avoid export churn) */
function interpolateLatLon(
  distance: number,
  lapData: LapData,
): [number, number] | null {
  const idx = lapData.distance_m.findIndex((d) => d >= distance);
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
  const { data: session } = useSession(activeSessionId);
  const { data: laps } = useSessionLaps(activeSessionId);

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
    }> = [];

    for (const [lapStr, corners] of Object.entries(allLapCorners)) {
      const lapNum = Number(lapStr);
      const corner = corners.find((c) => c.number === cornerNumber);
      if (!corner) continue;

      const pos = getBrakePos(corner, lapData, interpolateLatLon);
      if (!pos) continue;

      dots.push({
        lon: pos[0],
        lat: pos[1],
        lapNumber: lapNum,
        isBest: lapNum === bestLapNumber,
        radius: dotRadius(corner.peak_brake_g),
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

  // Optimal brake line (dashed amber) — offset from best by brake_gap_m
  const optimalBrakeLine = useMemo((): GeoJSON.FeatureCollection | null => {
    const opp = optimalComparison?.corner_opportunities?.find(
      (o) => o.corner_number === cornerNumber,
    );
    if (!opp?.brake_gap_m) return null;

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

    return { distToApex, spreadM, brakeGapM: opp?.brake_gap_m ?? null };
  }, [brakeDots, allLapCorners, bestLapNumber, cornerNumber, optimalComparison]);

  if (brakeDots.length === 0) return null;

  return (
    <>
      {/* Per-lap brake scatter dots */}
      {brakeDots.map((dot) => (
        <Marker
          key={`brake-${dot.lapNumber}`}
          longitude={dot.lon}
          latitude={dot.lat}
          anchor="center"
        >
          <div
            style={{
              width: dot.radius * 2,
              height: dot.radius * 2,
              borderRadius: '50%',
              backgroundColor: dot.isBest
                ? colors.motorsport.throttle
                : `${colors.motorsport.brake}88`,
              border: dot.isBest ? '2px solid #fff' : 'none',
              boxShadow: dot.isBest
                ? `0 0 8px ${colors.motorsport.throttle}88`
                : 'none',
            }}
            title={`Lap ${dot.lapNumber}${dot.isBest ? ' (best)' : ''}`}
          />
        </Marker>
      ))}

      {/* Best-lap brake line (solid green) */}
      {bestBrakeLine && (
        <Source id="best-brake-line" type="geojson" data={bestBrakeLine}>
          <Layer
            id="best-brake-line-layer"
            type="line"
            paint={{
              'line-color': colors.motorsport.throttle,
              'line-width': 3,
              'line-opacity': 0.9,
            }}
            layout={{
              'line-cap': 'round',
            }}
          />
        </Source>
      )}

      {/* Optimal brake line (dashed amber) */}
      {optimalBrakeLine && (
        <Source id="optimal-brake-line" type="geojson" data={optimalBrakeLine}>
          <Layer
            id="optimal-brake-line-layer"
            type="line"
            paint={{
              'line-color': colors.motorsport.neutral,
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

      {/* Apex marker (diamond) */}
      {(() => {
        const bestCorners = allLapCorners?.[String(bestLapNumber)];
        const bestCorner = bestCorners?.find((c) => c.number === cornerNumber);
        if (!bestCorner) return null;
        const apexPos =
          bestCorner.apex_lat != null && bestCorner.apex_lon != null
            ? [bestCorner.apex_lon, bestCorner.apex_lat] as [number, number]
            : interpolateLatLon(bestCorner.apex_distance_m, lapData);
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
              <span className="text-[var(--text-secondary)]">vs optimal: </span>
              <span
                className="font-semibold tabular-nums"
                style={{
                  color: stats.brakeGapM > 0 ? colors.motorsport.neutral : colors.motorsport.throttle,
                }}
              >
                {stats.brakeGapM > 0 ? `${stats.brakeGapM.toFixed(1)}m later` : `${Math.abs(stats.brakeGapM).toFixed(1)}m earlier`}
              </span>
            </p>
          )}
          <div className="mt-1.5 flex items-center gap-3 text-[10px] text-[var(--text-secondary)]">
            <span className="flex items-center gap-1">
              <span
                style={{
                  display: 'inline-block',
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  backgroundColor: `${colors.motorsport.brake}88`,
                }}
              />
              Brake points
            </span>
            <span className="flex items-center gap-1">
              <span
                style={{
                  display: 'inline-block',
                  width: 8,
                  height: 2,
                  backgroundColor: colors.motorsport.throttle,
                  borderRadius: 1,
                }}
              />
              Best lap
            </span>
            {optimalBrakeLine && (
              <span className="flex items-center gap-1">
                <span
                  style={{
                    display: 'inline-block',
                    width: 8,
                    height: 2,
                    backgroundColor: colors.motorsport.neutral,
                    borderRadius: 1,
                    borderTop: `1px dashed ${colors.motorsport.neutral}`,
                  }}
                />
                Optimal
              </span>
            )}
          </div>
        </div>
      )}
    </>
  );
}
