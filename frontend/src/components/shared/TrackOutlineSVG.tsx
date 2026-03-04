'use client';

import { useId, useMemo } from 'react';

interface TrackOutlineSVGProps {
  coords: { lat: number[]; lon: number[] };
  className?: string;
  width?: number;
  height?: number;
}

export function TrackOutlineSVG({ coords, className, width = 400, height = 300 }: TrackOutlineSVGProps) {
  const filterId = useId();
  const pathD = useMemo(() => {
    const { lat, lon } = coords;
    if (lat.length < 10) return '';

    const minLat = Math.min(...lat), maxLat = Math.max(...lat);
    const minLon = Math.min(...lon), maxLon = Math.max(...lon);
    const rangeX = maxLon - minLon || 1e-6;
    const rangeY = maxLat - minLat || 1e-6;
    const padding = 30;
    const drawW = width - 2 * padding;
    const drawH = height - 2 * padding;
    const scale = Math.min(drawW / rangeX, drawH / rangeY);
    const cx = width / 2;
    const cy = height / 2;

    return lat
      .map((latVal, i) => {
        const x = cx + (lon[i] - (minLon + maxLon) / 2) * scale;
        const y = cy - (latVal - (minLat + maxLat) / 2) * scale;
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ') + ' Z';
  }, [coords, width, height]);

  if (!pathD) return null;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={className}>
      <defs>
        <filter id={`track-glow-${filterId}`}>
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      <path
        d={pathD}
        fill="none"
        stroke="#6366f1"
        strokeWidth={2.5}
        strokeOpacity={0.6}
        filter={`url(#track-glow-${filterId})`}
      />
    </svg>
  );
}
