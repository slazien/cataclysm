"use client";

import { useMemo, useCallback, useRef, useEffect, useState } from "react";
import MapGL, {
  Source,
  Layer,
  Marker,
  NavigationControl,
} from "react-map-gl/mapbox";
import "mapbox-gl/dist/mapbox-gl.css";
import type { TrackGeometry, TrackCorner } from "@/lib/admin-api";
import type { MapRef, MarkerDragEvent } from "react-map-gl/mapbox";
import type { GeoJSON } from "geojson";

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

const COLOR_LEFT = "#2dd4bf";
const COLOR_RIGHT = "#fb923c";

// ─── Helpers ────────────────────────────────────────────────────────────────

/** Find the nearest geometry point index to a given lat/lon (haversine approx) */
function findNearestLatLonIndex(
  lat: number,
  lon: number,
  geometry: TrackGeometry,
): number {
  let minDist = Infinity;
  let bestIdx = 0;
  const cosLat = Math.cos((lat * Math.PI) / 180);

  for (let i = 0; i < geometry.lats.length; i++) {
    const dlat = geometry.lats[i] - lat;
    const dlon = (geometry.lons[i] - lon) * cosLat;
    const d = dlat * dlat + dlon * dlon;
    if (d < minDist) {
      minDist = d;
      bestIdx = i;
    }
  }
  return bestIdx;
}

/** Build GeoJSON line from geometry lats/lons, colored by curvature segments */
function buildTrackGeoJson(
  geometry: TrackGeometry,
): GeoJSON.FeatureCollection {
  const n = geometry.lats.length;
  if (n < 2) return { type: "FeatureCollection", features: [] };

  const features: GeoJSON.Feature[] = [];
  let currentColor = curvatureColor(geometry.curvature[0]);
  let coords: [number, number][] = [
    [geometry.lons[0], geometry.lats[0]],
  ];

  for (let i = 1; i < n; i++) {
    const c = curvatureColor(geometry.curvature[i]);
    coords.push([geometry.lons[i], geometry.lats[i]]);

    if (c !== currentColor || i === n - 1) {
      features.push({
        type: "Feature",
        properties: { color: currentColor },
        geometry: { type: "LineString", coordinates: coords },
      });
      currentColor = c;
      // Overlap by one point for continuity
      coords = [[geometry.lons[i], geometry.lats[i]]];
    }
  }

  return { type: "FeatureCollection", features };
}

function curvatureColor(curv: number): string {
  if (curv > 0.001) return COLOR_LEFT;
  if (curv < -0.001) return COLOR_RIGHT;
  return "#94a3b8"; // neutral / straight
}

// ─── Component ──────────────────────────────────────────────────────────────

interface TrackEditorSatelliteProps {
  geometry: TrackGeometry;
  corners: TrackCorner[];
  selectedCornerIdx: number | null;
  addMode: boolean;
  onSelectCorner: (idx: number) => void;
  onDragCorner: (idx: number, fraction: number) => void;
  onAddCorner: (fraction: number, curvature: number) => void;
}

export function TrackEditorSatellite({
  geometry,
  corners,
  selectedCornerIdx,
  addMode,
  onSelectCorner,
  onDragCorner,
  onAddCorner,
}: TrackEditorSatelliteProps) {
  const mapRef = useRef<MapRef>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  // Build track trace GeoJSON
  const geoJson = useMemo(() => buildTrackGeoJson(geometry), [geometry]);

  // Compute center and bounds
  const { centerLon, centerLat, bounds } = useMemo(() => {
    let minLon = Infinity,
      maxLon = -Infinity,
      minLat = Infinity,
      maxLat = -Infinity;

    for (let i = 0; i < geometry.lats.length; i++) {
      const lat = geometry.lats[i];
      const lon = geometry.lons[i];
      if (lon < minLon) minLon = lon;
      if (lon > maxLon) maxLon = lon;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
    }

    return {
      centerLon: (minLon + maxLon) / 2,
      centerLat: (minLat + maxLat) / 2,
      bounds: [
        [minLon, minLat],
        [maxLon, maxLat],
      ] as [[number, number], [number, number]],
    };
  }, [geometry]);

  // Fit bounds on load
  useEffect(() => {
    if (mapLoaded && mapRef.current) {
      mapRef.current.fitBounds(bounds, {
        padding: 60,
        duration: 500,
      });
    }
  }, [mapLoaded, bounds]);

  // Corner drag handler
  const handleDragEnd = useCallback(
    (idx: number, e: MarkerDragEvent) => {
      const { lat, lng } = e.lngLat;
      const nearestIdx = findNearestLatLonIndex(lat, lng, geometry);
      const fraction = nearestIdx / (geometry.lats.length - 1);
      onDragCorner(idx, fraction);
    },
    [geometry, onDragCorner],
  );

  // Map click for add mode
  const handleMapClick = useCallback(
    (e: mapboxgl.MapLayerMouseEvent) => {
      if (!addMode) return;
      const { lat, lng } = e.lngLat;
      const nearestIdx = findNearestLatLonIndex(lat, lng, geometry);
      const fraction = nearestIdx / (geometry.lats.length - 1);
      const curv = geometry.curvature[nearestIdx];
      onAddCorner(fraction, curv);
    },
    [addMode, geometry, onAddCorner],
  );

  if (!MAPBOX_TOKEN) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Set NEXT_PUBLIC_MAPBOX_TOKEN to enable satellite view
      </div>
    );
  }

  return (
    <div
      className="h-full w-full"
      style={{ cursor: addMode ? "crosshair" : "default" }}
    >
      <MapGL
        ref={mapRef}
        mapboxAccessToken={MAPBOX_TOKEN}
        initialViewState={{
          longitude: centerLon,
          latitude: centerLat,
          zoom: 15,
          pitch: 0,
          bearing: 0,
        }}
        style={{ width: "100%", height: "100%" }}
        mapStyle="mapbox://styles/mapbox/satellite-v9"
        onLoad={() => setMapLoaded(true)}
        onClick={handleMapClick}
        attributionControl={false}
        cursor={addMode ? "crosshair" : undefined}
      >
        <NavigationControl position="bottom-right" showCompass showZoom />

        {/* Track trace colored by curvature */}
        <Source id="editor-track-trace" type="geojson" data={geoJson}>
          <Layer
            id="editor-track-line-bg"
            type="line"
            paint={{
              "line-color": "#1e293b",
              "line-width": 6,
              "line-opacity": 0.5,
            }}
          />
          <Layer
            id="editor-track-line"
            type="line"
            paint={{
              "line-color": ["get", "color"],
              "line-width": 3,
              "line-opacity": 0.85,
            }}
          />
        </Source>

        {/* S/F marker */}
        {geometry.lats.length > 0 && (
          <Marker
            longitude={geometry.lons[0]}
            latitude={geometry.lats[0]}
            anchor="center"
          >
            <div
              className="flex items-center justify-center rounded-sm bg-white px-1 py-0.5 text-[10px] font-bold text-black shadow"
              style={{ lineHeight: 1 }}
            >
              S/F
            </div>
          </Marker>
        )}

        {/* Corner markers */}
        {corners.map((corner, idx) => {
          const ptIdx = Math.round(
            corner.fraction * (geometry.lats.length - 1),
          );
          const lat = geometry.lats[ptIdx];
          const lon = geometry.lons[ptIdx];
          if (lat == null || lon == null) return null;

          const isSelected = selectedCornerIdx === idx;
          const color =
            corner.direction === "left" ? COLOR_LEFT : COLOR_RIGHT;

          return (
            <Marker
              key={`corner-${corner.number}-${idx}`}
              longitude={lon}
              latitude={lat}
              anchor="center"
              draggable={!addMode}
              onDragEnd={(e) => handleDragEnd(idx, e)}
              onClick={(e) => {
                e.originalEvent.stopPropagation();
                onSelectCorner(idx);
              }}
            >
              <div
                className="flex flex-col items-center"
                style={{ cursor: addMode ? "crosshair" : "grab" }}
              >
                {/* Marker dot */}
                <div
                  style={{
                    width: isSelected ? 20 : 14,
                    height: isSelected ? 20 : 14,
                    borderRadius: "50%",
                    backgroundColor: color,
                    border: isSelected
                      ? "3px solid white"
                      : "2px solid rgba(255,255,255,0.6)",
                    boxShadow: isSelected
                      ? "0 0 10px rgba(255,255,255,0.5)"
                      : "0 1px 3px rgba(0,0,0,0.5)",
                    transition: "all 150ms ease",
                  }}
                />
                {/* Label */}
                <span
                  className="mt-0.5 select-none whitespace-nowrap text-[11px] font-semibold"
                  style={{
                    color: "white",
                    textShadow:
                      "0 1px 3px rgba(0,0,0,0.8), 0 0 6px rgba(0,0,0,0.5)",
                    fontWeight: isSelected ? 700 : 600,
                  }}
                >
                  T{corner.number}
                </span>
              </div>
            </Marker>
          );
        })}
      </MapGL>
    </div>
  );
}
