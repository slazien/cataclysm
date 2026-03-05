'use client';

import { useMemo, useCallback, useRef, useEffect, useState } from 'react';
import MapGL, { Source, Layer, Marker, NavigationControl } from 'react-map-gl/mapbox';
import * as d3 from 'd3';
import 'mapbox-gl/dist/mapbox-gl.css';
import { useMultiLapData, useCorners, useDelta } from '@/hooks/useAnalysis';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useCornerKings } from '@/hooks/useLeaderboard';
import { useSession } from '@/hooks/useSession';
import { useAnalysisStore, useSessionStore } from '@/stores';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { colors } from '@/lib/design-tokens';
import { worstGrade } from '@/lib/gradeUtils';
import type { LapData, DeltaData, Corner, CornerGrade } from '@/lib/types';
import type { MapRef } from 'react-map-gl/mapbox';
import type { GeoJSON } from 'geojson';

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? '';

interface TrackMapSatelliteProps {
  sessionId: string;
}

/** Build ~100 GeoJSON LineString segments with per-segment color */
function buildGeoJson(
  lapData: LapData,
  delta: DeltaData | null | undefined,
): GeoJSON.FeatureCollection {
  const n = lapData.lat.length;
  if (n < 2) return { type: 'FeatureCollection', features: [] };

  const chunkSize = Math.max(1, Math.floor(n / 100));
  const features: GeoJSON.Feature[] = [];

  // Close the loop: append the first point so the trace connects back to S/F
  const closedLon = [...lapData.lon, lapData.lon[0]];
  const closedLat = [...lapData.lat, lapData.lat[0]];
  const closedN = closedLon.length;

  if (delta && delta.distance_m.length > 0) {
    const deltaScale = d3
      .scaleLinear()
      .domain([d3.min(delta.delta_s) ?? -1, 0, d3.max(delta.delta_s) ?? 1])
      .range([0, 0.5, 1])
      .clamp(true);

    const colorScale = d3
      .scaleLinear<string>()
      .domain([0, 0.5, 1])
      .range([colors.motorsport.throttle, colors.text.muted, colors.motorsport.brake]);

    for (let i = 0; i < closedN - 1; i += chunkSize) {
      const end = Math.min(i + chunkSize + 1, closedN);
      const coords: [number, number][] = [];
      for (let j = i; j < end; j++) {
        coords.push([closedLon[j], closedLat[j]]);
      }
      const midDist = lapData.distance_m[Math.min(i + Math.floor(chunkSize / 2), n - 1)];
      const dIdx = Math.min(d3.bisectLeft(delta.distance_m, midDist), delta.delta_s.length - 1);
      const t = deltaScale(delta.delta_s[dIdx]) as number;

      features.push({
        type: 'Feature',
        properties: { color: colorScale(t) as string },
        geometry: { type: 'LineString', coordinates: coords },
      });
    }
  } else {
    const minSpeed = d3.min(lapData.speed_mph) ?? 0;
    const maxSpeed = d3.max(lapData.speed_mph) ?? 1;
    const speedScale = d3
      .scaleLinear<string>()
      .domain([minSpeed, (minSpeed + maxSpeed) / 2, maxSpeed])
      .range([colors.motorsport.brake, colors.motorsport.neutral, colors.motorsport.throttle]);

    for (let i = 0; i < closedN - 1; i += chunkSize) {
      const end = Math.min(i + chunkSize + 1, closedN);
      const coords: [number, number][] = [];
      for (let j = i; j < end; j++) {
        coords.push([closedLon[j], closedLat[j]]);
      }
      const midIdx = Math.min(i + Math.floor(chunkSize / 2), n - 1);

      features.push({
        type: 'Feature',
        properties: { color: speedScale(lapData.speed_mph[midIdx]) as string },
        geometry: { type: 'LineString', coordinates: coords },
      });
    }
  }

  return { type: 'FeatureCollection', features };
}

/** Compute [lon, lat] at a given distance along the track */
function interpolateLatLon(
  distance: number,
  lapData: LapData,
): [number, number] | null {
  const idx = d3.bisectLeft(lapData.distance_m, distance);
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

/** Build corner labels with grades */
function buildCornerLabels(
  corners: Corner[],
  lapData: LapData,
  cornerGrades: CornerGrade[] | null,
): Array<{ lon: number; lat: number; number: number; grade: string | null }> {
  const gradeMap = new Map<number, string>();
  if (cornerGrades) {
    for (const cg of cornerGrades) {
      const gradeLetters = [cg.braking, cg.trail_braking, cg.min_speed, cg.throttle].filter(
        Boolean,
      );
      if (gradeLetters.length > 0) {
        gradeMap.set(cg.corner, worstGrade(gradeLetters));
      }
    }
  }

  return corners.map((c) => {
    const pos = interpolateLatLon(c.apex_distance_m, lapData);
    return {
      lon: pos ? pos[0] : 0,
      lat: pos ? pos[1] : 0,
      number: c.number,
      grade: gradeMap.get(c.number) ?? null,
    };
  });
}

export function TrackMapSatellite({ sessionId }: TrackMapSatelliteProps) {
  const mapRef = useRef<MapRef>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const cursorDistance = useAnalysisStore((s) => s.cursorDistance);
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { data: sessionData } = useSession(activeSessionId);
  const trackName = sessionData?.track_name ?? undefined;
  const { data: kingsData } = useCornerKings(trackName);

  const kingCorners = useMemo(() => {
    const set = new Set<number>();
    if (kingsData?.kings) {
      for (const k of kingsData.kings) {
        set.add(k.corner_number);
      }
    }
    return set;
  }, [kingsData]);

  const refLap = selectedLaps.length >= 2 ? selectedLaps[0] : null;
  const compLap = selectedLaps.length >= 2 ? selectedLaps[1] : null;

  const { data: lapDataArr, isLoading: lapsLoading } = useMultiLapData(
    sessionId,
    selectedLaps.length > 0 ? [selectedLaps[0]] : [],
  );
  const { data: corners } = useCorners(sessionId);
  const { data: delta } = useDelta(sessionId, refLap, compLap);
  const { data: report } = useCoachingReport(sessionId);

  const lapData = lapDataArr[0] ?? null;

  // Build GeoJSON for the track trace
  const geoJson = useMemo(() => {
    if (!lapData) return null;
    return buildGeoJson(lapData, delta);
  }, [lapData, delta]);

  // Corner labels
  const cornerLabels = useMemo(() => {
    if (!lapData || !corners) return [];
    return buildCornerLabels(corners, lapData, report?.corner_grades ?? null);
  }, [lapData, corners, report]);

  // Cursor position
  const cursorPos = useMemo(() => {
    if (cursorDistance === null || !lapData) return null;
    return interpolateLatLon(cursorDistance, lapData);
  }, [cursorDistance, lapData]);

  // S/F position
  const sfPos = useMemo((): [number, number] | null => {
    if (!lapData || lapData.lat.length === 0) return null;
    return [lapData.lon[0], lapData.lat[0]];
  }, [lapData]);

  // Auto-fit bounds on data change
  const fitBounds = useCallback(() => {
    if (!lapData || !mapRef.current) return;
    const lons = lapData.lon;
    const lats = lapData.lat;
    const minLon = d3.min(lons) ?? 0;
    const maxLon = d3.max(lons) ?? 0;
    const minLat = d3.min(lats) ?? 0;
    const maxLat = d3.max(lats) ?? 0;

    mapRef.current.fitBounds(
      [[minLon, minLat], [maxLon, maxLat]],
      { padding: 40, duration: 500 },
    );
  }, [lapData]);

  useEffect(() => {
    if (mapLoaded) fitBounds();
  }, [mapLoaded, fitBounds]);

  const handleCornerClick = useCallback(
    (cornerNumber: number) => {
      const cornerId = `T${cornerNumber}`;
      selectCorner(selectedCorner === cornerId ? null : cornerId);
    },
    [selectCorner, selectedCorner],
  );

  if (!MAPBOX_TOKEN) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <p className="text-sm text-[var(--text-secondary)]">
          Set NEXT_PUBLIC_MAPBOX_TOKEN to enable satellite view
        </p>
      </div>
    );
  }

  if (lapsLoading) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <CircularProgress size={20} />
      </div>
    );
  }

  if (!lapData || lapData.lat.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <p className="text-sm text-[var(--text-secondary)]">
          {selectedLaps.length === 0 ? 'Select laps to view track map' : 'No GPS data available'}
        </p>
      </div>
    );
  }

  // Initial center from data
  const centerLon = ((d3.min(lapData.lon) ?? 0) + (d3.max(lapData.lon) ?? 0)) / 2;
  const centerLat = ((d3.min(lapData.lat) ?? 0) + (d3.max(lapData.lat) ?? 0)) / 2;

  return (
    <div className="h-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] overflow-hidden">
      <MapGL
        ref={mapRef}
        mapboxAccessToken={MAPBOX_TOKEN}
        initialViewState={{
          longitude: centerLon,
          latitude: centerLat,
          zoom: 15,
          pitch: 45,
          bearing: 0,
        }}
        style={{ width: '100%', height: '100%' }}
        mapStyle="mapbox://styles/mapbox/satellite-v9"
        onLoad={() => setMapLoaded(true)}
        attributionControl={false}
      >
        <NavigationControl position="bottom-right" showCompass showZoom />

        {/* Track trace as colored line segments */}
        {geoJson && (
          <Source key={delta ? 'delta' : 'speed'} id="track-trace" type="geojson" data={geoJson}>
            <Layer
              id="track-line"
              type="line"
              paint={{
                'line-color': ['get', 'color'],
                'line-width': 4,
                'line-opacity': 0.9,
              }}
              layout={{
                'line-cap': 'round',
                'line-join': 'round',
              }}
            />
          </Source>
        )}

        {/* S/F marker */}
        {sfPos && (
          <Marker longitude={sfPos[0]} latitude={sfPos[1]} anchor="center">
            <div
              style={{
                width: 24,
                height: 10,
                display: 'grid',
                gridTemplateColumns: 'repeat(6, 1fr)',
                gridTemplateRows: 'repeat(2, 1fr)',
                borderRadius: 2,
                overflow: 'hidden',
                boxShadow: '0 1px 4px rgba(0,0,0,0.5)',
              }}
            >
              {Array.from({ length: 12 }, (_, i) => {
                const col = i % 6;
                const row = Math.floor(i / 6);
                return (
                  <div
                    key={i}
                    style={{ backgroundColor: (row + col) % 2 === 0 ? '#ffffff' : '#1a1a1a' }}
                  />
                );
              })}
            </div>
          </Marker>
        )}

        {/* Corner labels */}
        {cornerLabels.map((label) => {
          const isSelected = selectedCorner === `T${label.number}`;
          const gradeColor = label.grade
            ? (colors.grade as Record<string, string>)[label.grade.toLowerCase()] ?? colors.text.muted
            : null;

          return (
            <Marker
              key={label.number}
              longitude={label.lon}
              latitude={label.lat}
              anchor="center"
              onClick={(e) => {
                e.originalEvent.stopPropagation();
                handleCornerClick(label.number);
              }}
            >
              <div className="flex cursor-pointer items-center gap-0.5">
                {kingCorners.has(label.number) && (
                  <span style={{ fontSize: 8, marginRight: -2 }}>{'\u{1F451}'}</span>
                )}
                <div
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: '50%',
                    backgroundColor: colors.bg.elevated,
                    border: `${isSelected ? 2 : 1}px solid ${isSelected ? colors.motorsport.optimal : colors.text.muted}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 9,
                    fontWeight: 'bold',
                    color: colors.text.primary,
                    fontFamily: 'Inter, system-ui, sans-serif',
                    boxShadow: isSelected ? `0 0 8px ${colors.motorsport.optimal}66` : '0 1px 3px rgba(0,0,0,0.5)',
                  }}
                >
                  {label.number}
                </div>
                {label.grade && gradeColor && (
                  <div
                    style={{
                      fontSize: 8,
                      fontWeight: 'bold',
                      padding: '1px 3px',
                      borderRadius: 3,
                      color: gradeColor,
                      backgroundColor: `${gradeColor}22`,
                      fontFamily: 'Inter, system-ui, sans-serif',
                    }}
                  >
                    {label.grade}
                  </div>
                )}
              </div>
            </Marker>
          );
        })}

        {/* Cursor dot with pulse animation */}
        {cursorPos && (
          <Marker longitude={cursorPos[0]} latitude={cursorPos[1]} anchor="center">
            <div
              className="sat-cursor-pulse"
              style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                backgroundColor: colors.motorsport.optimal,
                border: '2px solid #fff',
                boxShadow: `0 0 6px ${colors.motorsport.optimal}88`,
              }}
            />
            <style>{`
              @keyframes sat-pulse {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.4); }
              }
              .sat-cursor-pulse { animation: sat-pulse 1s ease-in-out infinite; }
            `}</style>
          </Marker>
        )}
      </MapGL>
    </div>
  );
}
