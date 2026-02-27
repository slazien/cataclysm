'use client';

import { useMemo } from 'react';

interface RadarDataset {
  label: string;
  values: number[];
  color: string;
}

interface RadarChartProps {
  axes: readonly string[];
  datasets: RadarDataset[];
  size?: number;
  maxValue?: number;
}

const RINGS = [20, 40, 60, 80, 100];

export function RadarChart({ axes, datasets, size = 200, maxValue = 100 }: RadarChartProps) {
  const center = size / 2;
  const radius = size / 2 - 30; // padding for labels
  const n = axes.length;
  const angleStep = (2 * Math.PI) / n;
  const startAngle = -Math.PI / 2; // top

  const ringPaths = useMemo(
    () =>
      RINGS.map((ring) => {
        const r = (ring / maxValue) * radius;
        const points = Array.from({ length: n }, (_, i) => {
          const angle = startAngle + i * angleStep;
          return `${center + r * Math.cos(angle)},${center + r * Math.sin(angle)}`;
        });
        return points.join(' ');
      }),
    [center, radius, n, angleStep, startAngle, maxValue],
  );

  const axisLines = useMemo(
    () =>
      Array.from({ length: n }, (_, i) => {
        const angle = startAngle + i * angleStep;
        return {
          x: center + radius * Math.cos(angle),
          y: center + radius * Math.sin(angle),
          labelX: center + (radius + 16) * Math.cos(angle),
          labelY: center + (radius + 16) * Math.sin(angle),
        };
      }),
    [center, radius, n, angleStep, startAngle],
  );

  const dataPolygons = useMemo(
    () =>
      datasets.map((ds) => {
        const points = ds.values.map((v, i) => {
          const r = (Math.min(v, maxValue) / maxValue) * radius;
          const angle = startAngle + i * angleStep;
          return `${center + r * Math.cos(angle)},${center + r * Math.sin(angle)}`;
        });
        return { ...ds, polygon: points.join(' ') };
      }),
    [datasets, center, radius, angleStep, startAngle, maxValue],
  );

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="mx-auto">
      {/* Grid rings */}
      {ringPaths.map((points, i) => (
        <polygon
          key={i}
          points={points}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={1}
        />
      ))}

      {/* Axis lines */}
      {axisLines.map((axis, i) => (
        <line
          key={i}
          x1={center}
          y1={center}
          x2={axis.x}
          y2={axis.y}
          stroke="rgba(255,255,255,0.1)"
          strokeWidth={1}
        />
      ))}

      {/* Data polygons */}
      {dataPolygons.map((dp, i) => (
        <g key={i}>
          <polygon points={dp.polygon} fill={dp.color} fillOpacity={0.15} stroke={dp.color} strokeWidth={1.5} />
          {/* Data points */}
          {dp.values.map((v, j) => {
            const r = (Math.min(v, maxValue) / maxValue) * radius;
            const angle = startAngle + j * angleStep;
            return (
              <circle
                key={j}
                cx={center + r * Math.cos(angle)}
                cy={center + r * Math.sin(angle)}
                r={3}
                fill={dp.color}
              />
            );
          })}
        </g>
      ))}

      {/* Axis labels */}
      {axes.map((label, i) => (
        <text
          key={i}
          x={axisLines[i].labelX}
          y={axisLines[i].labelY}
          fill="rgba(200, 200, 210, 0.7)"
          fontSize={10}
          fontFamily="Inter, system-ui, sans-serif"
          textAnchor="middle"
          dominantBaseline="central"
        >
          {label}
        </text>
      ))}
    </svg>
  );
}
