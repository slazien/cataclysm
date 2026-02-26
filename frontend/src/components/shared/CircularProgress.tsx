'use client';

import { useEffect, useState } from 'react';

interface CircularProgressProps {
  /** Size of the SVG in pixels. */
  size?: number;
  /** Stroke width of the progress arc. */
  strokeWidth?: number;
  /** 0-100 for determinate mode. Omit for indeterminate animation. */
  progress?: number;
  /** CSS color for the progress arc (default: cata-accent). */
  color?: string;
  /** CSS color for the background track. */
  trackColor?: string;
  /** Extra class names on the wrapper. */
  className?: string;
}

/**
 * Circular progress indicator that fills clockwise from 12 o'clock.
 *
 * - **Determinate**: pass `progress` (0-100) for a precise fill.
 * - **Indeterminate**: omit `progress` for a single fill-up that slows near completion.
 */
export function CircularProgress({
  size = 20,
  strokeWidth = 2.5,
  progress,
  color = 'var(--cata-accent)',
  trackColor = 'var(--text-muted)',
  className = '',
}: CircularProgressProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  // Indeterminate: fill once from 0 → ~90% over ~8s, then slow-creep toward 95%
  const [indeterminate, setIndeterminate] = useState(0);
  const isIndeterminate = progress === undefined;

  useEffect(() => {
    if (!isIndeterminate) return;

    let raf: number;
    let start: number | null = null;
    const fastPhase = 8000; // ms to reach ~90%

    function tick(ts: number) {
      if (start === null) start = ts;
      const elapsed = ts - start;

      let pct: number;
      if (elapsed < fastPhase) {
        // Fast phase: ease-out curve 0 → 90% over 8s
        const t = elapsed / fastPhase;
        pct = (1 - (1 - t) ** 3) * 90;
      } else {
        // Slow creep: 90 → 95% asymptotically (never reaches 100)
        const extra = elapsed - fastPhase;
        pct = 90 + 5 * (1 - Math.exp(-extra / 30000));
      }

      setIndeterminate(pct);
      raf = requestAnimationFrame(tick);
    }

    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      setIndeterminate(0);
    };
  }, [isIndeterminate]);

  const pct = isIndeterminate ? indeterminate : Math.min(100, Math.max(0, progress));
  const offset = circumference - (pct / 100) * circumference;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={className}
      style={{ transform: 'rotate(-90deg)' }}
    >
      {/* Background track */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={trackColor}
        strokeWidth={strokeWidth}
        opacity={0.25}
      />
      {/* Progress arc */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        style={{
          transition: isIndeterminate ? 'none' : 'stroke-dashoffset 0.4s ease',
        }}
      />
    </svg>
  );
}
