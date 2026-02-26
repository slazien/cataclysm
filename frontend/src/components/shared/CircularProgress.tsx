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
 * - **Indeterminate**: omit `progress` for a smooth repeating fill-up animation.
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

  // Indeterminate: auto-advance from 0 → ~92% over 2s, then reset
  const [indeterminate, setIndeterminate] = useState(0);
  const isIndeterminate = progress === undefined;

  useEffect(() => {
    if (!isIndeterminate) return;

    let raf: number;
    let start: number | null = null;
    const duration = 2200; // ms for one fill cycle

    function tick(ts: number) {
      if (start === null) start = ts;
      const elapsed = ts - start;
      const t = (elapsed % duration) / duration;
      // Ease-in-out: starts slow, peaks, then slows into reset
      const eased = t < 0.5
        ? 2 * t * t
        : 1 - (-2 * t + 2) ** 2 / 2;
      setIndeterminate(eased * 92);
      raf = requestAnimationFrame(tick);
    }

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
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
