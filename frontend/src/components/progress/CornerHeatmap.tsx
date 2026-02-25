'use client';

import { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useUiStore, useAnalysisStore } from '@/stores';
import { colors, fonts } from '@/lib/design-tokens';
import { parseSessionDate } from '@/lib/formatters';
import type { TrendSessionSummary } from '@/lib/types';

type HeatmapMetric = 'min_speed' | 'brake_consistency' | 'grade';

interface CornerHeatmapProps {
  sessions: TrendSessionSummary[];
  cornerMinSpeedTrends: Record<string, (number | null)[]>;
  cornerBrakeStdTrends: Record<string, (number | null)[]>;
  cornerConsistencyTrends: Record<string, (number | null)[]>;
  className?: string;
}

const MARGINS = { top: 20, right: 20, bottom: 44, left: 64 };

function interpolateColor(t: number, metric: HeatmapMetric): string {
  // t is 0..1 where 0 = worst, 1 = best
  const clamped = Math.max(0, Math.min(1, t));
  if (metric === 'brake_consistency') {
    // Tight (good) = green, loose (bad) = orange/red
    const r = Math.round(239 - clamped * (239 - 34));
    const g = Math.round(68 + clamped * (197 - 68));
    const b = Math.round(68 - clamped * (68 - 94));
    return `rgb(${r},${g},${b})`;
  }
  // min_speed and grade: dark to bright green
  const r = Math.round(10 + clamped * 24);
  const g = Math.round(40 + clamped * 157);
  const b = Math.round(20 + clamped * 74);
  return `rgb(${r},${g},${b})`;
}

export function CornerHeatmap({
  sessions,
  cornerMinSpeedTrends,
  cornerBrakeStdTrends,
  cornerConsistencyTrends,
  className,
}: CornerHeatmapProps) {
  const setActiveView = useUiStore((s) => s.setActiveView);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);
  const setDeepDiveMode = useAnalysisStore((s) => s.setMode);

  const [metric, setMetric] = useState<HeatmapMetric>('min_speed');
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null);

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx } =
    useCanvasChart(MARGINS);

  // Select the data based on metric
  const data = useMemo(() => {
    switch (metric) {
      case 'min_speed':
        return cornerMinSpeedTrends;
      case 'brake_consistency':
        return cornerBrakeStdTrends;
      case 'grade':
        return cornerConsistencyTrends;
    }
  }, [metric, cornerMinSpeedTrends, cornerBrakeStdTrends, cornerConsistencyTrends]);

  // Corner keys sorted numerically
  const cornerKeys = useMemo(() => {
    return Object.keys(data).sort((a, b) => parseInt(a) - parseInt(b));
  }, [data]);

  const nCorners = cornerKeys.length;
  const nSessions = sessions.length;

  // Min/max for normalization
  const { minVal, maxVal } = useMemo(() => {
    let min = Infinity;
    let max = -Infinity;
    for (const key of cornerKeys) {
      for (const v of data[key]) {
        if (v != null) {
          if (v < min) min = v;
          if (v > max) max = v;
        }
      }
    }
    if (!isFinite(min)) return { minVal: 0, maxVal: 1 };
    return { minVal: min, maxVal: max };
  }, [data, cornerKeys]);

  // Cell geometry
  const cellWidth = useMemo(
    () => (nSessions > 0 ? dimensions.innerWidth / nSessions : 0),
    [nSessions, dimensions.innerWidth],
  );
  const cellHeight = useMemo(
    () => (nCorners > 0 ? dimensions.innerHeight / nCorners : 0),
    [nCorners, dimensions.innerHeight],
  );

  // Store refs for mouse handler
  const cellGeomRef = useRef({ cellWidth, cellHeight, nCorners, nSessions });
  cellGeomRef.current = { cellWidth, cellHeight, nCorners, nSessions };

  // Draw heatmap
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || dimensions.innerWidth <= 0 || nCorners === 0 || nSessions === 0) return;

    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

    const range = maxVal - minVal || 1;

    // Draw cells
    for (let row = 0; row < nCorners; row++) {
      const key = cornerKeys[row];
      const values = data[key];

      for (let col = 0; col < nSessions; col++) {
        const val = col < values.length ? values[col] : null;
        const x = MARGINS.left + col * cellWidth;
        const y = MARGINS.top + row * cellHeight;

        if (val == null) {
          ctx.fillStyle = colors.bg.surface;
        } else {
          let t: number;
          if (metric === 'brake_consistency') {
            // Lower std = better = higher t
            t = 1 - (val - minVal) / range;
          } else {
            // Higher value = better
            t = (val - minVal) / range;
          }
          ctx.fillStyle = interpolateColor(t, metric);
        }

        ctx.fillRect(x, y, cellWidth - 1, cellHeight - 1);
      }
    }

    // Row labels (corner numbers)
    ctx.fillStyle = colors.axis;
    ctx.font = `10px ${fonts.mono}`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let row = 0; row < nCorners; row++) {
      const y = MARGINS.top + row * cellHeight + cellHeight / 2;
      ctx.fillText(`T${cornerKeys[row]}`, MARGINS.left - 6, y);
    }

    // Column labels (session dates)
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    // Show a subset of labels if too many sessions
    const maxLabels = Math.floor(dimensions.innerWidth / 50);
    const step = Math.max(1, Math.ceil(nSessions / maxLabels));
    for (let col = 0; col < nSessions; col += step) {
      const x = MARGINS.left + col * cellWidth + cellWidth / 2;
      ctx.fillStyle = colors.axis;
      const dateLabel = parseSessionDate(sessions[col].session_date).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
      ctx.fillText(dateLabel, x, MARGINS.top + dimensions.innerHeight + 4);
    }

    // Axis labels
    ctx.fillStyle = colors.text.secondary;
    ctx.font = `11px ${fonts.sans}`;
    ctx.textAlign = 'center';
    ctx.fillText('Session', MARGINS.left + dimensions.innerWidth / 2, MARGINS.top + dimensions.innerHeight + 22);

    ctx.save();
    ctx.translate(14, MARGINS.top + dimensions.innerHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillText('Corner', 0, 0);
    ctx.restore();
  }, [data, cornerKeys, sessions, nCorners, nSessions, cellWidth, cellHeight, minVal, maxVal, metric, dimensions, getDataCtx]);

  // Mouse events for tooltip
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = overlayCanvasRef.current;
      if (!canvas || nCorners === 0 || nSessions === 0) return;
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const col = Math.floor((mouseX - MARGINS.left) / cellGeomRef.current.cellWidth);
      const row = Math.floor((mouseY - MARGINS.top) / cellGeomRef.current.cellHeight);

      if (col < 0 || col >= nSessions || row < 0 || row >= nCorners) {
        setTooltip(null);
        return;
      }

      const key = cornerKeys[row];
      const values = data[key];
      const val = col < values.length ? values[col] : null;

      let unit = '';
      let label = '';
      if (metric === 'min_speed') {
        unit = ' mph';
        label = 'Min Speed';
      } else if (metric === 'brake_consistency') {
        unit = ' m (std)';
        label = 'Brake Std';
      } else {
        unit = '';
        label = 'Consistency';
      }

      const valStr = val != null ? val.toFixed(1) : 'N/A';
      const dateStr = sessions[col]?.session_date ?? '';

      setTooltip({
        x: mouseX,
        y: mouseY - 16,
        text: `T${key} | ${dateStr} | ${label}: ${valStr}${unit}`,
      });
    },
    [cornerKeys, data, metric, nCorners, nSessions, sessions],
  );

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = overlayCanvasRef.current;
      if (!canvas || nCorners === 0) return;
      const rect = canvas.getBoundingClientRect();
      const mouseY = e.clientY - rect.top;
      const row = Math.floor((mouseY - MARGINS.top) / cellGeomRef.current.cellHeight);
      if (row < 0 || row >= nCorners) return;

      const cornerNumber = cornerKeys[row];
      selectCorner(`T${cornerNumber}`);
      setDeepDiveMode('corner');
      setActiveView('deep-dive');
    },
    [cornerKeys, nCorners, selectCorner, setDeepDiveMode, setActiveView],
  );

  const handleMouseLeave = useCallback(() => setTooltip(null), []);

  if (nCorners === 0 || nSessions === 0) {
    return (
      <div className={`flex h-full items-center justify-center ${className ?? ''}`}>
        <p className="text-sm text-[var(--text-muted)]">No corner trend data available</p>
      </div>
    );
  }

  const metricButtons: { key: HeatmapMetric; label: string }[] = [
    { key: 'min_speed', label: 'Min Speed' },
    { key: 'brake_consistency', label: 'Brake Consistency' },
    { key: 'grade', label: 'Grade' },
  ];

  return (
    <div className={`flex h-full flex-col ${className ?? ''}`}>
      {/* Metric selector */}
      <div className="flex gap-1 px-2 pb-2">
        {metricButtons.map((btn) => (
          <button
            key={btn.key}
            onClick={() => setMetric(btn.key)}
            className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
              metric === btn.key
                ? 'bg-[var(--cata-accent)] text-white'
                : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--bg-overlay)]'
            }`}
          >
            {btn.label}
          </button>
        ))}
      </div>
      {/* Chart area */}
      <div ref={containerRef} className="relative min-h-0 flex-1">
        <canvas
          ref={dataCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%' }}
        />
        <canvas
          ref={overlayCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%', cursor: 'pointer' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          onClick={handleClick}
        />
        {tooltip && (
          <div
            className="pointer-events-none absolute z-10 max-w-[300px] whitespace-nowrap rounded bg-[var(--bg-overlay)] px-2 py-1 text-xs text-[var(--text-primary)] shadow-lg"
            style={{ left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, -100%)' }}
          >
            {tooltip.text}
          </div>
        )}
      </div>
    </div>
  );
}
