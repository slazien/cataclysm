'use client';

import { useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useAnimationFrame } from '@/hooks/useAnimationFrame';
import { useMultiLapData, useCorners } from '@/hooks/useAnalysis';
import { useAnalysisStore } from '@/stores';
import { colors, fonts } from '@/lib/design-tokens';
import { CHART_MARGINS as MARGINS, drawCornerZones } from './chartHelpers';

interface SpeedTraceProps {
  sessionId: string;
}

function drawAxes(
  ctx: CanvasRenderingContext2D,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  innerWidth: number,
  innerHeight: number,
  margins: typeof MARGINS,
) {
  ctx.strokeStyle = colors.axis;
  ctx.lineWidth = 1;
  ctx.fillStyle = colors.axis;
  ctx.font = `10px ${fonts.mono}`;

  // Y-axis ticks
  const yTicks = yScale.ticks(6);
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (const tick of yTicks) {
    const y = yScale(tick);
    // Grid line
    ctx.strokeStyle = colors.grid;
    ctx.beginPath();
    ctx.moveTo(margins.left, y);
    ctx.lineTo(margins.left + innerWidth, y);
    ctx.stroke();
    // Label
    ctx.fillStyle = colors.axis;
    ctx.fillText(`${tick}`, margins.left - 6, y);
  }

  // X-axis ticks
  const xTicks = xScale.ticks(8);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (const tick of xTicks) {
    const x = xScale(tick);
    ctx.fillStyle = colors.axis;
    ctx.fillText(`${tick}`, x, margins.top + innerHeight + 6);
  }

  // Axis labels
  ctx.fillStyle = colors.text.secondary;
  ctx.font = `11px ${fonts.sans}`;
  ctx.textAlign = 'center';
  ctx.fillText('Distance (m)', margins.left + innerWidth / 2, margins.top + innerHeight + 24);

  ctx.save();
  ctx.translate(14, margins.top + innerHeight / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = 'center';
  ctx.fillText('Speed (mph)', 0, 0);
  ctx.restore();
}

export function SpeedTrace({ sessionId }: SpeedTraceProps) {
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const cursorDistance = useAnalysisStore((s) => s.cursorDistance);

  const { data: lapDataArr, isLoading } = useMultiLapData(sessionId, selectedLaps);
  const { data: corners } = useCorners(sessionId);

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx } =
    useCanvasChart(MARGINS);

  // Build scales
  const { xScale, yScale } = useMemo(() => {
    if (lapDataArr.length === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.left, MARGINS.left + 1]),
        yScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.top + 1, MARGINS.top]),
      };
    }

    let maxDist = 0;
    let maxSpeed = 0;
    for (const lap of lapDataArr) {
      const ld = d3.max(lap.distance_m);
      const ls = d3.max(lap.speed_mph);
      if (ld !== undefined && ld > maxDist) maxDist = ld;
      if (ls !== undefined && ls > maxSpeed) maxSpeed = ls;
    }

    return {
      xScale: d3
        .scaleLinear()
        .domain([0, maxDist])
        .range([MARGINS.left, MARGINS.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([0, maxSpeed * 1.05])
        .range([MARGINS.top + dimensions.innerHeight, MARGINS.top]),
    };
  }, [lapDataArr, dimensions.innerWidth, dimensions.innerHeight]);

  // Stable ref for xScale to use in mouse events
  const xScaleRef = useRef(xScale);
  xScaleRef.current = xScale;

  // Draw data layer
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || dimensions.innerWidth <= 0 || lapDataArr.length === 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    // Corner zones
    if (corners) {
      drawCornerZones(ctx, corners, xScale, MARGINS.top, dimensions.innerHeight);
    }

    // Speed lines per lap
    for (let li = 0; li < lapDataArr.length; li++) {
      const lap = lapDataArr[li];
      const color = colors.lap[li % colors.lap.length];
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let i = 0; i < lap.distance_m.length; i++) {
        const x = xScale(lap.distance_m[i]);
        const y = yScale(lap.speed_mph[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Axes
    drawAxes(ctx, xScale, yScale, dimensions.innerWidth, dimensions.innerHeight, MARGINS);
  }, [lapDataArr, corners, xScale, yScale, dimensions]);

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
  }, [dimensions.innerWidth]);

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

    // Tooltip: show speed values at cursor
    if (lapDataArr.length > 0) {
      const tooltipY = MARGINS.top + 8;
      ctx.font = `11px ${fonts.mono}`;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';

      for (let li = 0; li < lapDataArr.length; li++) {
        const lap = lapDataArr[li];
        const idx = d3.bisectLeft(lap.distance_m, cursorDistance);
        const clampedIdx = Math.min(idx, lap.speed_mph.length - 1);
        const speed = lap.speed_mph[clampedIdx];
        const color = colors.lap[li % colors.lap.length];
        const label = `L${lap.lap_number}: ${speed.toFixed(1)} mph`;

        const textWidth = ctx.measureText(label).width;
        const rightEdge = MARGINS.left + dimensions.innerWidth;
        const tooltipX = x + textWidth + 20 > rightEdge ? x - textWidth - 16 : x + 10;

        ctx.fillStyle = 'rgba(10, 12, 16, 0.85)';
        ctx.fillRect(tooltipX - 2, tooltipY + li * 18 - 2, textWidth + 8, 16);

        ctx.fillStyle = color;
        ctx.fillText(label, tooltipX + 2, tooltipY + li * 18);
      }
    }
  }, cursorDistance !== null);

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
        <p className="text-sm text-[var(--text-secondary)]">Select laps to view speed trace</p>
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
