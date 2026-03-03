'use client';

import { useMemo } from 'react';
import { motion } from 'motion/react';

interface RadarDataset {
  label: string;
  values: number[];
  color: string;
  /** Override fill opacity (default 0.15). */
  fillOpacity?: number;
  /** Override stroke opacity (default 1). */
  strokeOpacity?: number;
  /** Whether to render data-point circles (default true). */
  showDots?: boolean;
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
        const coords = ds.values.map((v, i) => {
          const r = (Math.min(v, maxValue) / maxValue) * radius;
          const angle = startAngle + i * angleStep;
          return { x: center + r * Math.cos(angle), y: center + r * Math.sin(angle) };
        });
        // SVG path d string (M start, L to each point, Z close) — needed for pathLength animation
        const pathD = coords
          .map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x},${c.y}`)
          .join(' ') + ' Z';
        // polygon points string for the fill area
        const polygon = coords.map((c) => `${c.x},${c.y}`).join(' ');
        return { ...ds, pathD, polygon, coords };
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

      {/* Data polygons — animated stroke draw + fill fade */}
      {dataPolygons.map((dp, i) => {
        const fillOp = dp.fillOpacity ?? 0.15;
        const strokeOp = dp.strokeOpacity ?? 1;
        const dots = dp.showDots !== false;
        return (
          <g key={i}>
            {/* Fill area — fades in after stroke draws */}
            <motion.polygon
              points={dp.polygon}
              fill={dp.color}
              fillOpacity={fillOp}
              stroke="none"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3, delay: 0.35 + i * 0.15, ease: 'easeOut' }}
            />
            {/* Stroke — draws itself via pathLength */}
            <motion.path
              d={dp.pathD}
              fill="none"
              stroke={dp.color}
              strokeWidth={dots ? 1.5 : 1}
              strokeOpacity={strokeOp}
              pathLength={1}
              strokeDasharray="1"
              strokeDashoffset="0"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: strokeOp }}
              transition={{ duration: 0.5, delay: i * 0.15, ease: 'easeOut' }}
            />
            {/* Data points — pop in after stroke completes (skip for ghost layers) */}
            {dots &&
              dp.coords.map((c, j) => (
                <motion.circle
                  key={j}
                  cx={c.x}
                  cy={c.y}
                  r={3}
                  fill={dp.color}
                  initial={{ opacity: 0, scale: 0 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{
                    duration: 0.25,
                    delay: 0.4 + i * 0.15 + j * 0.04,
                    ease: 'easeOut',
                  }}
                />
              ))}
          </g>
        );
      })}

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
