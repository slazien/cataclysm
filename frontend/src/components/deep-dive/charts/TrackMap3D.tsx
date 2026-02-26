'use client';

import { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Line, OrbitControls, Html } from '@react-three/drei';
import * as d3 from 'd3';
import * as THREE from 'three';
import { useMultiLapData, useCorners, useDelta } from '@/hooks/useAnalysis';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useAnalysisStore } from '@/stores';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { colors } from '@/lib/design-tokens';
import { worstGrade } from '@/lib/gradeUtils';
import type { Corner, LapData, DeltaData, CornerGrade } from '@/lib/types';

interface TrackMap3DProps {
  sessionId: string;
}

const ELEVATION_EXAGGERATION = 3.0;
const WORLD_SCALE = 10; // normalise track to ~10 world units

interface Projected3D {
  positions: [number, number, number][];
  cornerPositions: Map<number, [number, number, number]>;
  sfPosition: [number, number, number];
}

function projectTo3D(
  lat: number[],
  lon: number[],
  altitudeM: number[] | null | undefined,
): Projected3D {
  const n = lat.length;
  if (n === 0) {
    return { positions: [], cornerPositions: new Map(), sfPosition: [0, 0, 0] };
  }

  const minLat = d3.min(lat) ?? 0;
  const maxLat = d3.max(lat) ?? 0;
  const minLon = d3.min(lon) ?? 0;
  const maxLon = d3.max(lon) ?? 0;

  const midLat = (minLat + maxLat) / 2;
  const lonScale = Math.cos((midLat * Math.PI) / 180);

  const latRange = maxLat - minLat || 1e-6;
  const lonRange = (maxLon - minLon) * lonScale || 1e-6;
  const maxRange = Math.max(latRange, lonRange);
  const scale = WORLD_SCALE / maxRange;

  const centerLat = (minLat + maxLat) / 2;
  const centerLon = (minLon + maxLon) / 2;

  // Altitude handling
  const hasAltitude = altitudeM && altitudeM.length === n;
  const minAlt = hasAltitude ? (d3.min(altitudeM) ?? 0) : 0;
  // Scale altitude relative to horizontal extent
  const altScale = hasAltitude ? (scale * ELEVATION_EXAGGERATION) / 111320 : 0;

  const positions: [number, number, number][] = new Array(n);
  for (let i = 0; i < n; i++) {
    const x = (lon[i] - centerLon) * lonScale * scale;
    const z = -(lat[i] - centerLat) * scale; // negate so north = -z (camera faces track)
    const y = hasAltitude ? (altitudeM![i] - minAlt) * altScale : 0;
    positions[i] = [x, y, z];
  }

  return {
    positions,
    cornerPositions: new Map(),
    sfPosition: positions[0],
  };
}

function getCornerPosition(
  cornerApexDist: number,
  distanceM: number[],
  positions: [number, number, number][],
): [number, number, number] {
  const idx = d3.bisectLeft(distanceM, cornerApexDist);
  if (idx <= 0) return positions[0];
  if (idx >= positions.length) return positions[positions.length - 1];

  const d0 = distanceM[idx - 1];
  const d1 = distanceM[idx];
  const t = d1 !== d0 ? (cornerApexDist - d0) / (d1 - d0) : 0;

  return [
    positions[idx - 1][0] + t * (positions[idx][0] - positions[idx - 1][0]),
    positions[idx - 1][1] + t * (positions[idx][1] - positions[idx - 1][1]),
    positions[idx - 1][2] + t * (positions[idx][2] - positions[idx - 1][2]),
  ];
}

function getCursorPosition(
  cursorDistance: number,
  distanceM: number[],
  positions: [number, number, number][],
): [number, number, number] {
  return getCornerPosition(cursorDistance, distanceM, positions);
}

/** Build per-vertex colors based on speed or delta */
function buildVertexColors(
  lapData: LapData,
  delta: DeltaData | null | undefined,
  n: number,
): string[] {
  const vertexColors: string[] = new Array(n);

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

    for (let i = 0; i < n; i++) {
      const dist = lapData.distance_m[i];
      const dIdx = Math.min(d3.bisectLeft(delta.distance_m, dist), delta.delta_s.length - 1);
      const t = deltaScale(delta.delta_s[dIdx]) as number;
      vertexColors[i] = colorScale(t) as string;
    }
  } else {
    const minSpeed = d3.min(lapData.speed_mph) ?? 0;
    const maxSpeed = d3.max(lapData.speed_mph) ?? 1;
    const speedScale = d3
      .scaleLinear<string>()
      .domain([minSpeed, (minSpeed + maxSpeed) / 2, maxSpeed])
      .range([colors.motorsport.brake, colors.motorsport.neutral, colors.motorsport.throttle]);

    for (let i = 0; i < n; i++) {
      vertexColors[i] = speedScale(lapData.speed_mph[i]) as string;
    }
  }

  return vertexColors;
}

/** Pulsing cursor sphere */
function CursorSphere({ position }: { position: [number, number, number] }) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    if (meshRef.current) {
      const s = 0.08 + 0.03 * Math.sin(clock.getElapsedTime() * 4);
      meshRef.current.scale.setScalar(s / 0.08);
    }
  });

  return (
    <mesh ref={meshRef} position={position}>
      <sphereGeometry args={[0.08, 16, 16]} />
      <meshBasicMaterial color={colors.motorsport.optimal} />
    </mesh>
  );
}

/** Corner label in 3D space */
function CornerLabel3D({
  position,
  number,
  grade,
  isSelected,
  onClick,
}: {
  position: [number, number, number];
  number: number;
  grade: string | null;
  isSelected: boolean;
  onClick: () => void;
}) {
  const gradeColor = grade
    ? (colors.grade as Record<string, string>)[grade.toLowerCase()] ?? colors.text.muted
    : null;

  return (
    <Html position={position} center style={{ pointerEvents: 'auto' }}>
      <div
        onClick={onClick}
        className="flex cursor-pointer items-center gap-0.5"
        style={{ transform: 'translate(0, -12px)' }}
      >
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
            boxShadow: isSelected ? `0 0 8px ${colors.motorsport.optimal}66` : 'none',
          }}
        >
          {number}
        </div>
        {grade && gradeColor && (
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
            {grade}
          </div>
        )}
      </div>
    </Html>
  );
}

/** S/F checkered marker in 3D space */
function SFMarker3D({ position }: { position: [number, number, number] }) {
  return (
    <Html position={position} center>
      <div
        style={{
          width: 24,
          height: 10,
          display: 'grid',
          gridTemplateColumns: 'repeat(6, 1fr)',
          gridTemplateRows: 'repeat(2, 1fr)',
          borderRadius: 2,
          overflow: 'hidden',
          opacity: 0.95,
          transform: 'translate(0, -16px)',
          boxShadow: '0 1px 4px rgba(0,0,0,0.5)',
        }}
      >
        {Array.from({ length: 12 }, (_, i) => {
          const col = i % 6;
          const row = Math.floor(i / 6);
          return (
            <div
              key={i}
              style={{
                backgroundColor: (row + col) % 2 === 0 ? '#ffffff' : '#1a1a1a',
              }}
            />
          );
        })}
      </div>
    </Html>
  );
}

/** Inner 3D scene (must be inside Canvas) */
function TrackScene({
  lapData,
  positions,
  vertexColors,
  corners,
  cornerGrades,
  delta,
  cursorDistance,
  selectedCorner,
  onCornerClick,
}: {
  lapData: LapData;
  positions: [number, number, number][];
  vertexColors: string[];
  corners: Corner[];
  cornerGrades: CornerGrade[] | null;
  delta: DeltaData | null | undefined;
  cursorDistance: number | null;
  selectedCorner: string | null;
  onCornerClick: (cornerNumber: number) => void;
}) {
  // Corner grade map
  const gradeMap = useMemo(() => {
    const map = new Map<number, string>();
    if (cornerGrades) {
      for (const cg of cornerGrades) {
        const gradeLetters = [cg.braking, cg.trail_braking, cg.min_speed, cg.throttle].filter(
          Boolean,
        );
        if (gradeLetters.length > 0) {
          map.set(cg.corner, worstGrade(gradeLetters));
        }
      }
    }
    return map;
  }, [cornerGrades]);

  // Corner 3D positions
  const cornerPositions = useMemo(() => {
    return corners.map((c) => ({
      corner: c,
      pos: getCornerPosition(c.apex_distance_m, lapData.distance_m, positions),
    }));
  }, [corners, lapData.distance_m, positions]);

  // Cursor position
  const cursorPos = useMemo(() => {
    if (cursorDistance === null) return null;
    return getCursorPosition(cursorDistance, lapData.distance_m, positions);
  }, [cursorDistance, lapData.distance_m, positions]);

  // Convert hex colors to THREE.Color array for Line
  const threeColors = useMemo(() => {
    return vertexColors.map((c) => new THREE.Color(c));
  }, [vertexColors]);

  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 10, 5]} intensity={0.4} />

      {/* Track line with per-vertex colors */}
      <Line
        points={positions}
        vertexColors={threeColors}
        lineWidth={3}
      />

      {/* S/F marker */}
      {positions.length > 0 && <SFMarker3D position={positions[0]} />}

      {/* Corner labels */}
      {cornerPositions.map(({ corner: c, pos }) => (
        <CornerLabel3D
          key={c.number}
          position={pos}
          number={c.number}
          grade={gradeMap.get(c.number) ?? null}
          isSelected={selectedCorner === `T${c.number}`}
          onClick={() => onCornerClick(c.number)}
        />
      ))}

      {/* Cursor sphere */}
      {cursorPos && <CursorSphere position={cursorPos} />}

      <OrbitControls
        enableDamping
        dampingFactor={0.1}
        minDistance={2}
        maxDistance={30}
        maxPolarAngle={Math.PI / 2}
      />
    </>
  );
}

export function TrackMap3D({ sessionId }: TrackMap3DProps) {
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const cursorDistance = useAnalysisStore((s) => s.cursorDistance);
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);

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

  const { positions, vertexColors } = useMemo(() => {
    if (!lapData) return { positions: [] as [number, number, number][], vertexColors: [] as string[] };

    const proj = projectTo3D(lapData.lat, lapData.lon, lapData.altitude_m);
    const vc = buildVertexColors(lapData, delta, lapData.distance_m.length);

    return { positions: proj.positions, vertexColors: vc };
  }, [lapData, delta]);

  const handleCornerClick = (cornerNumber: number) => {
    const cornerId = `T${cornerNumber}`;
    selectCorner(selectedCorner === cornerId ? null : cornerId);
  };

  if (lapsLoading) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <CircularProgress size={20} />
      </div>
    );
  }

  if (!lapData || positions.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <p className="text-sm text-[var(--text-secondary)]">
          {selectedLaps.length === 0 ? 'Select laps to view track map' : 'No GPS data available'}
        </p>
      </div>
    );
  }

  return (
    <div className="h-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
      <Canvas
        camera={{ position: [0, 8, 8], fov: 50 }}
        style={{ background: colors.bg.base }}
      >
        <TrackScene
          lapData={lapData}
          positions={positions}
          vertexColors={vertexColors}
          corners={corners ?? []}
          cornerGrades={report?.corner_grades ?? null}
          delta={delta ?? null}
          cursorDistance={cursorDistance}
          selectedCorner={selectedCorner}
          onCornerClick={handleCornerClick}
        />
      </Canvas>
    </div>
  );
}
