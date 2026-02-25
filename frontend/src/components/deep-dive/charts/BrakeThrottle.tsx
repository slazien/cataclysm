'use client';

import { useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useAnimationFrame } from '@/hooks/useAnimationFrame';
import { useMultiLapData, useCorners } from '@/hooks/useAnalysis';
import { useAnalysisStore } from '@/stores';
import { colors, fonts } from '@/lib/design-tokens';
import type { Corner } from '@/lib/types';

interface BrakeThrottleProps {
  sessionId: string;
}

const MARGINS = { top: 16, right: 16, bottom: 36, left: 56 };

function drawCornerZones(
  ctx: CanvasRenderingContext2D,
  corners: Corner[],
  xScale: d3.ScaleLinear<number, number>,
  top: number,
  height: number,
) {
  ctx.fillStyle = 'rgba(255, 255, 255, 0.03)';
  for (const c of corners) {
    const x0 = xScale(c.entry_distance_m);
    const x1 = xScale(c.exit_distance_m);
    ctx.fillRect(x0, top, x1 - x0, height);
  }
}

export function BrakeThrottle({ sessionId }: BrakeThrottleProps) {
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const cursorDistance = useAnalysisStore((s) => s.cursorDistance);

  const { data: lapDataArr, isLoading } = useMultiLapData(sessionId, selectedLaps);
  const { data: corners } = useCorners(sessionId);

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx } =
    useCanvasChart(MARGINS);

  const { xScale, yScale } = useMemo(() => {
    if (lapDataArr.length === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.left, MARGINS.left + 1]),
        yScale: d3.scaleLinear().domain([-1, 1]).range([MARGINS.top + 1, MARGINS.top]),
      };
    }

    let maxDist = 0;
    let maxAbsG = 0;
    for (const lap of lapDataArr) {
      const ld = d3.max(lap.distance_m);
      if (ld !== undefined && ld > maxDist) maxDist = ld;
      for (const g of lap.longitudinal_g) {
        const absG = Math.abs(g);
        if (absG > maxAbsG) maxAbsG = absG;
      }
    }

    const bound = Math.max(maxAbsG * 1.1, 0.2);

    return {
      xScale: d3
        .scaleLinear()
        .domain([0, maxDist])
        .range([MARGINS.left, MARGINS.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([-bound, bound])
        .range([MARGINS.top + dimensions.innerHeight, MARGINS.top]),
    };
  }, [lapDataArr, dimensions.innerWidth, dimensions.innerHeight]);

  const xScaleRef = useRef(xScale);
  xScaleRef.current = xScale;

  // Data layer
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || lapDataArr.length === 0 || dimensions.innerWidth <= 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    // Corner zones
    if (corners) {
      drawCornerZones(ctx, corners, xScale, MARGINS.top, dimensions.innerHeight);
    }

    const zeroY = yScale(0);

    // Draw fills and lines for each lap
    for (let li = 0; li < lapDataArr.length; li++) {
      const lap = lapDataArr[li];
      const alpha = lapDataArr.length > 1 ? 0.25 : 0.35;

      // Filled areas
      for (let i = 1; i < lap.distance_m.length; i++) {
        const x0 = xScale(lap.distance_m[i - 1]);
        const x1 = xScale(lap.distance_m[i]);
        const y0 = yScale(lap.longitudinal_g[i - 1]);
        const y1 = yScale(lap.longitudinal_g[i]);
        const avgG = (lap.longitudinal_g[i - 1] + lap.longitudinal_g[i]) / 2;

        ctx.fillStyle =
          avgG < 0
            ? `rgba(239, 68, 68, ${alpha})` // braking — red
            : `rgba(34, 197, 94, ${alpha})`; // throttle — green

        ctx.beginPath();
        ctx.moveTo(x0, zeroY);
        ctx.lineTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.lineTo(x1, zeroY);
        ctx.closePath();
        ctx.fill();
      }

      // Line trace
      const lapColor = colors.lap[li % colors.lap.length];
      ctx.strokeStyle = lapColor;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i < lap.distance_m.length; i++) {
        const x = xScale(lap.distance_m[i]);
        const y = yScale(lap.longitudinal_g[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Zero line
    ctx.strokeStyle = colors.axis;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(MARGINS.left, zeroY);
    ctx.lineTo(MARGINS.left + dimensions.innerWidth, zeroY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Y-axis ticks
    const yTicks = yScale.ticks(5);
    ctx.font = `10px ${fonts.mono}`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (const tick of yTicks) {
      const y = yScale(tick);
      ctx.strokeStyle = colors.grid;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(MARGINS.left, y);
      ctx.lineTo(MARGINS.left + dimensions.innerWidth, y);
      ctx.stroke();
      ctx.fillStyle = colors.axis;
      ctx.fillText(tick.toFixed(1), MARGINS.left - 6, y);
    }

    // X-axis ticks
    const xTicks = xScale.ticks(8);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (const tick of xTicks) {
      ctx.fillStyle = colors.axis;
      ctx.fillText(`${tick}`, xScale(tick), MARGINS.top + dimensions.innerHeight + 6);
    }

    // Axis labels
    ctx.fillStyle = colors.text.secondary;
    ctx.font = `11px ${fonts.sans}`;
    ctx.textAlign = 'center';
    ctx.fillText(
      'Distance (m)',
      MARGINS.left + dimensions.innerWidth / 2,
      MARGINS.top + dimensions.innerHeight + 24,
    );

    ctx.save();
    ctx.translate(14, MARGINS.top + dimensions.innerHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillText('Long. G', 0, 0);
    ctx.restore();
  }, [lapDataArr, corners, xScale, yScale, dimensions, getDataCtx]);

  // Mouse events
  useEffect(() => {
    const overlay = overlayCanvasRef.current;
    if (!overlay) return;

    const setCursorDistance = useAnalysisStore.getState().setCursorDistance;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = overlay.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const scale = xScaleRef.current;
      if (x >= MARGINS.left && x <= MARGINS.left + dimensions.innerWidth) {
        setCursorDistance(scale.invert(x));
      }
    };

    const handleMouseLeave = () => setCursorDistance(null);

    overlay.addEventListener('mousemove', handleMouseMove);
    overlay.addEventListener('mouseleave', handleMouseLeave);
    return () => {
      overlay.removeEventListener('mousemove', handleMouseMove);
      overlay.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [overlayCanvasRef, dimensions.innerWidth]);

  // Cursor overlay
  useAnimationFrame(() => {
    const ctx = getOverlayCtx();
    if (!ctx) return;
    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    if (cursorDistance === null) return;

    const x = xScale(cursorDistance);
    if (x < MARGINS.left || x > MARGINS.left + dimensions.innerWidth) return;

    // Vertical cursor line
    ctx.strokeStyle = colors.cursor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, MARGINS.top);
    ctx.lineTo(x, MARGINS.top + dimensions.innerHeight);
    ctx.stroke();

    // Tooltip: g-values
    if (lapDataArr.length > 0) {
      ctx.font = `11px ${fonts.mono}`;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      const tooltipX = x + 10;
      const tooltipY = MARGINS.top + 8;

      for (let li = 0; li < lapDataArr.length; li++) {
        const lap = lapDataArr[li];
        const idx = d3.bisectLeft(lap.distance_m, cursorDistance);
        const clampedIdx = Math.min(idx, lap.longitudinal_g.length - 1);
        const gVal = lap.longitudinal_g[clampedIdx];
        const color = colors.lap[li % colors.lap.length];
        const label = `L${lap.lap_number}: ${gVal >= 0 ? '+' : ''}${gVal.toFixed(2)}g`;

        const textWidth = ctx.measureText(label).width;
        ctx.fillStyle = 'rgba(10, 12, 16, 0.85)';
        ctx.fillRect(tooltipX - 2, tooltipY + li * 18 - 2, textWidth + 8, 16);
        ctx.fillStyle = color;
        ctx.fillText(label, tooltipX + 2, tooltipY + li * 18);
      }
    }
  }, cursorDistance !== null || lapDataArr.length > 0);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--cata-accent)] border-t-transparent" />
      </div>
    );
  }

  if (selectedLaps.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">
          Select laps to view brake/throttle trace
        </p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative h-full w-full">
      <canvas
        ref={dataCanvasRef}
        className="absolute inset-0"
        style={{ width: '100%', height: '100%' }}
      />
      <canvas
        ref={overlayCanvasRef}
        className="absolute inset-0"
        style={{ width: '100%', height: '100%', cursor: 'crosshair' }}
      />
    </div>
  );
}
