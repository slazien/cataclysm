'use client';

import { useMemo } from 'react';

interface SpeedGaugeProps {
  speed: number; // current speed in mph
  maxSpeed: number; // max speed of the lap
}

const SIZE = 200;
const STROKE = 16;
const RADIUS = (SIZE - STROKE) / 2;
const CX = SIZE / 2;
const CY = SIZE / 2;

// Arc spans 240 degrees (from 150 to 390)
const START_ANGLE = 150;
const END_ANGLE = 390;
const SWEEP = END_ANGLE - START_ANGLE; // 240

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function describeArc(cx: number, cy: number, r: number, startDeg: number, endDeg: number): string {
  const start = polarToCartesian(cx, cy, r, endDeg);
  const end = polarToCartesian(cx, cy, r, startDeg);
  const largeArc = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`;
}

/**
 * Circular SVG speed gauge.
 *
 * - Background arc in dark grey
 * - Filled arc with gradient colour from green (slow) to yellow to red (fast)
 * - Large speed number in the centre
 * - "mph" label below
 */
export function SpeedGauge({ speed, maxSpeed }: SpeedGaugeProps) {
  const clampedMax = Math.max(maxSpeed, 1);
  const fraction = Math.min(speed / clampedMax, 1);
  const currentAngle = START_ANGLE + fraction * SWEEP;

  // Colour transitions: green -> yellow -> red
  const gaugeColor = useMemo(() => {
    const t = fraction;
    if (t < 0.5) {
      // green to yellow
      const r = Math.round(34 + t * 2 * (245 - 34));
      const g = Math.round(197 + t * 2 * (158 - 197));
      const b = Math.round(94 + t * 2 * (11 - 94));
      return `rgb(${r}, ${g}, ${b})`;
    }
    // yellow to red
    const t2 = (t - 0.5) * 2;
    const r = Math.round(245 + t2 * (239 - 245));
    const g = Math.round(158 - t2 * 158);
    const b = Math.round(11 + t2 * (68 - 11));
    return `rgb(${r}, ${g}, ${b})`;
  }, [fraction]);

  const bgArcPath = describeArc(CX, CY, RADIUS, START_ANGLE, END_ANGLE);
  const fillArcPath =
    fraction > 0.001 ? describeArc(CX, CY, RADIUS, START_ANGLE, currentAngle) : '';

  return (
    <div className="flex flex-col items-center">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="h-auto w-full max-w-[200px]">
        {/* Background arc */}
        <path
          d={bgArcPath}
          fill="none"
          stroke="var(--bg-overlay, #252830)"
          strokeWidth={STROKE}
          strokeLinecap="round"
        />

        {/* Filled arc */}
        {fillArcPath && (
          <path
            d={fillArcPath}
            fill="none"
            stroke={gaugeColor}
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
        )}

        {/* Speed value */}
        <text
          x={CX}
          y={CY - 4}
          textAnchor="middle"
          dominantBaseline="central"
          fill="var(--text-primary, #e2e4e9)"
          fontSize={42}
          fontWeight="bold"
          fontFamily="'JetBrains Mono', 'SF Mono', monospace"
        >
          {Math.round(speed)}
        </text>

        {/* Unit label */}
        <text
          x={CX}
          y={CY + 28}
          textAnchor="middle"
          dominantBaseline="central"
          fill="var(--text-muted, #555b67)"
          fontSize={14}
          fontFamily="'Inter', system-ui, sans-serif"
        >
          mph
        </text>
      </svg>
    </div>
  );
}
