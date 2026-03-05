'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { motion } from 'motion/react';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useAnimationFrame } from '@/hooks/useAnimationFrame';
import { useGGDiagram } from '@/hooks/useAnalysis';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { colors, fonts } from '@/lib/design-tokens';
import type { GGPoint, CornerGGSummary } from '@/lib/types';

const MARGINS = { top: 36, right: 24, bottom: 36, left: 48 };
const POINT_RADIUS = 2;

interface GGDiagramChartProps {
  sessionId: string;
}

/** Return the color for a G-G point based on longitudinal G (braking vs acceleration). */
function pointColor(lonG: number, alpha = 0.6): string {
  if (lonG < -0.05) return `rgba(239, 68, 68, ${alpha})`; // brake red
  if (lonG > 0.05) return `rgba(34, 197, 94, ${alpha})`; // throttle green
  return `rgba(245, 158, 11, ${alpha})`; // neutral amber
}

/** Assign a consistent color per corner number from the lap palette. */
function cornerColor(cornerNum: number, alpha = 0.7): string {
  const idx = (cornerNum - 1) % colors.lap.length;
  const hex = colors.lap[idx];
  // Parse hex to rgba
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function GGDiagramChart({ sessionId }: GGDiagramChartProps) {
  const [cornerFilter, setCornerFilter] = useState<number | undefined>(undefined);
  const { data: ggData, isLoading } = useGGDiagram(sessionId, cornerFilter);

  const {
    containerRef,
    dataCanvasRef,
    overlayCanvasRef,
    dimensions,
    getDataCtx,
    getOverlayCtx,
  } = useCanvasChart(MARGINS);

  // Build symmetric scales centered at 0
  const { xScale, yScale, maxG } = useMemo(() => {
    if (!ggData || ggData.points.length === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([-1, 1]).range([MARGINS.left, MARGINS.left + 1]),
        yScale: d3.scaleLinear().domain([-1, 1]).range([MARGINS.top + 1, MARGINS.top]),
        maxG: 1,
      };
    }

    // Use observed_max_g padded a bit, and ensure symmetry
    const pad = ggData.observed_max_g * 1.15;
    const m = Math.max(pad, 0.5);

    // Force square aspect — use the smaller of inner width/height
    const plotSize = Math.min(dimensions.innerWidth, dimensions.innerHeight);
    const xCenter = MARGINS.left + dimensions.innerWidth / 2;
    const yCenter = MARGINS.top + dimensions.innerHeight / 2;

    return {
      xScale: d3
        .scaleLinear()
        .domain([-m, m])
        .range([xCenter - plotSize / 2, xCenter + plotSize / 2]),
      yScale: d3
        .scaleLinear()
        .domain([-m, m])
        .range([yCenter + plotSize / 2, yCenter - plotSize / 2]),
      maxG: m,
    };
  }, [ggData, dimensions.innerWidth, dimensions.innerHeight]);

  // Refs for RAF and mouse events
  const xScaleRef = useRef(xScale);
  xScaleRef.current = xScale;
  const yScaleRef = useRef(yScale);
  yScaleRef.current = yScale;
  const dimsRef = useRef(dimensions);
  dimsRef.current = dimensions;
  const ggDataRef = useRef(ggData);
  ggDataRef.current = ggData;
  const hoverIdxRef = useRef<number | null>(null);

  // Draw data layer
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || !ggData || ggData.points.length === 0 || dimensions.innerWidth <= 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    // Chart area background
    const [xMin, xMax] = xScale.range();
    const [yMax, yMin] = yScale.range(); // note: y range is inverted (bottom, top)
    ctx.fillStyle = 'rgba(10, 12, 16, 0.4)';
    ctx.fillRect(xMin, yMin, xMax - xMin, yMax - yMin);

    // Crosshair at 0,0
    const x0 = xScale(0);
    const y0 = yScale(0);
    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(xMin, y0);
    ctx.lineTo(xMax, y0);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x0, yMin);
    ctx.lineTo(x0, yMax);
    ctx.stroke();

    // Reference performance envelope — draw the actual observed boundary
    // by finding the max combined-G in each angular sector, then connecting
    // those points to show the car's real asymmetric capability.
    const N_ENV_SECTORS = 36;
    const sectorWidth = (2 * Math.PI) / N_ENV_SECTORS;
    const sectorMax = new Float64Array(N_ENV_SECTORS);
    for (const pt of ggData.points) {
      const cg = Math.sqrt(pt.lat_g * pt.lat_g + pt.lon_g * pt.lon_g);
      const angle = Math.atan2(pt.lon_g, pt.lat_g);
      const idx = Math.min(
        Math.floor((angle + Math.PI) / sectorWidth),
        N_ENV_SECTORS - 1,
      );
      if (cg > sectorMax[idx]) sectorMax[idx] = cg;
    }
    // Fill empty sectors with the average to avoid gaps
    let envSum = 0;
    let envCount = 0;
    for (let i = 0; i < N_ENV_SECTORS; i++) {
      if (sectorMax[i] > 0) { envSum += sectorMax[i]; envCount++; }
    }
    const envAvg = envCount > 0 ? envSum / envCount : ggData.observed_max_g;
    for (let i = 0; i < N_ENV_SECTORS; i++) {
      if (sectorMax[i] <= 0) sectorMax[i] = envAvg;
    }

    ctx.strokeStyle = colors.text.muted;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    for (let i = 0; i <= N_ENV_SECTORS; i++) {
      const si = i % N_ENV_SECTORS;
      const angle = -Math.PI + si * sectorWidth + sectorWidth / 2;
      const r = sectorMax[si];
      const px = xScale(r * Math.cos(angle));
      const py = yScale(r * Math.sin(angle));
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.stroke();
    ctx.setLineDash([]);

    // Quadrant labels
    ctx.font = `10px ${fonts.sans}`;
    ctx.fillStyle = colors.text.muted;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('Braking', x0, yScale(-maxG * 0.88));
    ctx.fillText('Accel', x0, yScale(maxG * 0.88));
    ctx.fillText('Left', xScale(-maxG * 0.88), y0);
    ctx.fillText('Right', xScale(maxG * 0.88), y0);

    // Scatter points
    const hasCornerFilter = cornerFilter !== undefined;
    for (const pt of ggData.points) {
      const px = xScale(pt.lat_g);
      const py = yScale(pt.lon_g);
      if (px < xMin || px > xMax || py < yMin || py > yMax) continue;

      const fill = hasCornerFilter && pt.corner_number !== null
        ? cornerColor(pt.corner_number)
        : pointColor(pt.lon_g);

      ctx.fillStyle = fill;
      ctx.beginPath();
      ctx.arc(px, py, POINT_RADIUS, 0, Math.PI * 2);
      ctx.fill();
    }

    // Axes tick labels
    ctx.font = `10px ${fonts.mono}`;
    ctx.fillStyle = colors.axis;

    // X-axis ticks
    const xTicks = xScale.ticks(6);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (const t of xTicks) {
      const x = xScale(t);
      if (x < xMin || x > xMax) continue;
      ctx.fillText(t.toFixed(1), x, yMax + 4);
    }

    // Y-axis ticks
    const yTicks = yScale.ticks(6);
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (const t of yTicks) {
      const y = yScale(t);
      if (y < yMin || y > yMax) continue;
      ctx.fillText(t.toFixed(1), xMin - 6, y);
    }

    // Axis labels
    ctx.fillStyle = colors.text.secondary;
    ctx.font = `11px ${fonts.sans}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText('Lateral G', (xMin + xMax) / 2, yMax + 18);

    ctx.save();
    ctx.translate(MARGINS.left - 36, (yMin + yMax) / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText('Longitudinal G', 0, 0);
    ctx.restore();
  }, [ggData, xScale, yScale, maxG, dimensions, cornerFilter, getDataCtx]);

  // Mouse hover for tooltip
  const handleOverlayMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const data = ggDataRef.current;
      if (!data || data.points.length === 0) return;

      const rect = e.currentTarget.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const xs = xScaleRef.current;
      const ys = yScaleRef.current;

      // Find nearest point within 10px
      let bestIdx = -1;
      let bestDist = 100; // px threshold squared
      for (let i = 0; i < data.points.length; i++) {
        const pt = data.points[i];
        const px = xs(pt.lat_g);
        const py = ys(pt.lon_g);
        const dx = mx - px;
        const dy = my - py;
        const d = dx * dx + dy * dy;
        if (d < bestDist) {
          bestDist = d;
          bestIdx = i;
        }
      }
      hoverIdxRef.current = bestIdx >= 0 ? bestIdx : null;
    },
    [],
  );

  const handleOverlayMouseLeave = useCallback(() => {
    hoverIdxRef.current = null;
  }, []);

  // Tooltip overlay via RAF
  useAnimationFrame(() => {
    const ctx = getOverlayCtx();
    if (!ctx) return;
    const dims = dimsRef.current;
    ctx.clearRect(0, 0, dims.width, dims.height);

    const idx = hoverIdxRef.current;
    const data = ggDataRef.current;
    if (idx === null || !data) return;

    const pt = data.points[idx];
    const xs = xScaleRef.current;
    const ys = yScaleRef.current;
    const px = xs(pt.lat_g);
    const py = ys(pt.lon_g);

    // Highlight circle
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(px, py, POINT_RADIUS + 3, 0, Math.PI * 2);
    ctx.stroke();

    // Tooltip text
    const lines: string[] = [];
    if (pt.corner_number !== null) lines.push(`T${pt.corner_number}`);
    lines.push(`Lat: ${pt.lat_g.toFixed(2)}G`);
    lines.push(`Lon: ${pt.lon_g.toFixed(2)}G`);

    ctx.font = `11px ${fonts.mono}`;
    const lineHeight = 16;
    const padding = 6;
    const maxTextWidth = Math.max(...lines.map((l) => ctx.measureText(l).width));
    const boxW = maxTextWidth + padding * 2;
    const boxH = lines.length * lineHeight + padding * 2 - 4;

    // Position tooltip to avoid edges
    const [xMin, xMax] = xs.range();
    let tx = px + 12;
    let ty = py - boxH - 6;
    if (tx + boxW > xMax) tx = px - boxW - 12;
    if (ty < MARGINS.top) ty = py + 12;

    ctx.fillStyle = 'rgba(10, 12, 16, 0.9)';
    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(tx, ty, boxW, boxH, 4);
    } else {
      ctx.rect(tx, ty, boxW, boxH);
    }
    ctx.fill();

    ctx.fillStyle = '#e2e4e9';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    for (let i = 0; i < lines.length; i++) {
      ctx.fillText(lines[i], tx + padding, ty + padding + i * lineHeight);
    }
  });

  // Corner selector options from per_corner data
  const cornerOptions = useMemo(() => {
    if (!ggData?.per_corner) return [];
    return [...ggData.per_corner].sort((a, b) => a.corner_number - b.corner_number);
  }, [ggData]);

  if (isLoading) {
    return (
      <div className="flex h-full min-h-[300px] items-center justify-center rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <CircularProgress size={20} />
      </div>
    );
  }

  if (!ggData || ggData.points.length === 0) {
    return (
      <div className="flex h-full min-h-[300px] items-center justify-center rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <p className="text-sm text-[var(--text-secondary)]">No G-force data available</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      {/* Header with utilization and corner selector */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold tabular-nums text-[var(--text-primary)]">
              {Math.round(ggData.overall_utilization_pct)}%
            </span>
            <span className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
              Grip Utilization
            </span>
          </div>
          <p className="mt-0.5 text-[10px] text-[var(--text-tertiary)]">
            How much of your performance envelope you use (max {ggData.observed_max_g.toFixed(2)}G)
          </p>
        </div>

        {/* Corner filter dropdown */}
        {cornerOptions.length > 0 && (
          <select
            value={cornerFilter ?? ''}
            onChange={(e) =>
              setCornerFilter(e.target.value ? Number(e.target.value) : undefined)
            }
            className="rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-2 py-1 text-xs text-[var(--text-secondary)] outline-none focus:ring-1 focus:ring-[var(--accent-primary)]"
          >
            <option value="">All Corners</option>
            {cornerOptions.map((c) => (
              <option key={c.corner_number} value={c.corner_number}>
                T{c.corner_number} ({Math.round(c.utilization_pct)}%)
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Chart area — square-ish */}
      <div
        ref={containerRef}
        className="relative aspect-square w-full"
        style={{ minHeight: 300, maxHeight: 500 }}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
          className="absolute inset-0"
        >
          <canvas
            ref={dataCanvasRef}
            className="absolute inset-0"
            style={{ width: '100%', height: '100%', zIndex: 1 }}
          />
          <canvas
            ref={overlayCanvasRef}
            className="absolute inset-0"
            onMouseMove={handleOverlayMouseMove}
            onMouseLeave={handleOverlayMouseLeave}
            style={{
              width: '100%',
              height: '100%',
              cursor: 'crosshair',
              zIndex: 2,
              pointerEvents: 'auto',
            }}
          />
        </motion.div>
      </div>

      {/* Per-corner utilization mini-bars */}
      {cornerFilter === undefined && cornerOptions.length > 0 && (
        <CornerUtilizationBars corners={cornerOptions} onSelect={setCornerFilter} />
      )}
    </div>
  );
}

/** Small horizontal bar chart summarizing per-corner grip utilization. */
function CornerUtilizationBars({
  corners,
  onSelect,
}: {
  corners: CornerGGSummary[];
  onSelect: (corner: number) => void;
}) {
  return (
    <div className="mt-1 space-y-1">
      <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
        Per-Corner Utilization
      </p>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 sm:grid-cols-3 md:grid-cols-4">
        {corners.map((c) => (
          <button
            key={c.corner_number}
            onClick={() => onSelect(c.corner_number)}
            className="group flex items-center gap-1.5 rounded-md px-1 py-0.5 text-left transition-colors hover:bg-[var(--bg-elevated)]"
          >
            <span className="min-w-[24px] text-[10px] font-semibold text-[var(--text-secondary)]">
              T{c.corner_number}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--bg-overlay)]">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${Math.min(c.utilization_pct, 100)}%`,
                  backgroundColor:
                    c.utilization_pct >= 80
                      ? colors.grade.a
                      : c.utilization_pct >= 60
                        ? colors.grade.c
                        : colors.grade.f,
                }}
              />
            </div>
            <span className="min-w-[30px] text-right text-[10px] tabular-nums text-[var(--text-muted)]">
              {Math.round(c.utilization_pct)}%
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
