'use client';

import { useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useAnimationFrame } from '@/hooks/useAnimationFrame';
import { useDelta } from '@/hooks/useAnalysis';
import { useAnalysisStore } from '@/stores';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { colors, fonts } from '@/lib/design-tokens';
import { CHART_MARGINS as MARGINS } from './chartHelpers';

interface DeltaTProps {
  sessionId: string;
}

export function DeltaT({ sessionId }: DeltaTProps) {
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const cursorDistance = useAnalysisStore((s) => s.cursorDistance);

  const refLap = selectedLaps.length >= 2 ? selectedLaps[0] : null;
  const compLap = selectedLaps.length >= 2 ? selectedLaps[1] : null;

  const { data: delta, isLoading } = useDelta(sessionId, refLap, compLap);

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx } =
    useCanvasChart(MARGINS);

  const { xScale, yScale } = useMemo(() => {
    if (!delta || delta.distance_m.length === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.left, MARGINS.left + 1]),
        yScale: d3.scaleLinear().domain([-1, 1]).range([MARGINS.top + 1, MARGINS.top]),
      };
    }

    const maxDist = d3.max(delta.distance_m) ?? 1;
    const maxAbs =
      d3.max(delta.delta_s.map((v) => Math.abs(v))) ?? 1;
    const bound = Math.max(maxAbs * 1.2, 0.1);

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
  }, [delta, dimensions.innerWidth, dimensions.innerHeight]);

  const xScaleRef = useRef(xScale);
  xScaleRef.current = xScale;

  // Data layer
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || !delta || delta.distance_m.length === 0 || dimensions.innerWidth <= 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    const zeroY = yScale(0);

    // Draw filled areas
    // Green (gaining) — above zero line (delta < 0 means comp is faster)
    // Red (losing) — below zero line (delta > 0 means comp is slower)
    // Convention: positive delta = ref is slower, so red above, green below
    // We draw positive delta (losing time) as red above zero, negative (gaining) as green below zero
    for (let i = 1; i < delta.distance_m.length; i++) {
      const x0 = xScale(delta.distance_m[i - 1]);
      const x1 = xScale(delta.distance_m[i]);
      const y0 = yScale(delta.delta_s[i - 1]);
      const y1 = yScale(delta.delta_s[i]);

      const deltaVal = (delta.delta_s[i - 1] + delta.delta_s[i]) / 2;

      ctx.fillStyle =
        deltaVal > 0
          ? 'rgba(239, 68, 68, 0.35)' // red — losing time
          : 'rgba(34, 197, 94, 0.35)'; // green — gaining time

      ctx.beginPath();
      ctx.moveTo(x0, zeroY);
      ctx.lineTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.lineTo(x1, zeroY);
      ctx.closePath();
      ctx.fill();
    }

    // Delta line
    ctx.strokeStyle = colors.text.primary;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < delta.distance_m.length; i++) {
      const x = xScale(delta.distance_m[i]);
      const y = yScale(delta.delta_s[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

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
      ctx.fillText(tick.toFixed(2), MARGINS.left - 6, y);
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
    ctx.fillText('Delta (s)', 0, 0);
    ctx.restore();

    // Total delta in top-right
    if (delta.total_delta_s !== undefined) {
      const totalStr = `${delta.total_delta_s >= 0 ? '+' : ''}${delta.total_delta_s.toFixed(3)}s`;
      ctx.font = `bold 12px ${fonts.mono}`;
      ctx.textAlign = 'right';
      ctx.textBaseline = 'top';
      ctx.fillStyle =
        delta.total_delta_s > 0 ? colors.motorsport.brake : colors.motorsport.throttle;
      ctx.fillText(totalStr, MARGINS.left + dimensions.innerWidth - 4, MARGINS.top + 4);
    }
  }, [delta, xScale, yScale, dimensions]);

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

    if (cursorDistance === null || !delta) return;

    const x = xScale(cursorDistance);
    if (x < MARGINS.left || x > MARGINS.left + dimensions.innerWidth) return;

    // Vertical cursor line
    ctx.strokeStyle = colors.cursor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, MARGINS.top);
    ctx.lineTo(x, MARGINS.top + dimensions.innerHeight);
    ctx.stroke();

    // Tooltip with delta value
    const idx = d3.bisectLeft(delta.distance_m, cursorDistance);
    const clampedIdx = Math.min(idx, delta.delta_s.length - 1);
    const dVal = delta.delta_s[clampedIdx];
    const label = `${dVal >= 0 ? '+' : ''}${dVal.toFixed(3)}s`;

    ctx.font = `11px ${fonts.mono}`;
    const tooltipY = MARGINS.top + 8;
    const textWidth = ctx.measureText(label).width;
    const rightEdge = MARGINS.left + dimensions.innerWidth;
    const tooltipX = x + textWidth + 20 > rightEdge ? x - textWidth - 16 : x + 10;
    ctx.fillStyle = 'rgba(10, 12, 16, 0.85)';
    ctx.fillRect(tooltipX - 2, tooltipY - 2, textWidth + 8, 16);
    ctx.fillStyle = dVal > 0 ? colors.motorsport.brake : colors.motorsport.throttle;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(label, tooltipX + 2, tooltipY);
  }, cursorDistance !== null);

  if (selectedLaps.length < 2) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">Select 2 laps to compare delta.</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <CircularProgress size={20} />
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative h-full w-full">
      <canvas
        ref={dataCanvasRef}
        className="absolute inset-0"
        style={{ width: '100%', height: '100%', zIndex: 1 }}
      />
      <canvas
        ref={overlayCanvasRef}
        className="absolute inset-0"
        style={{ width: '100%', height: '100%', cursor: 'crosshair', zIndex: 2, pointerEvents: 'auto' }}
      />
    </div>
  );
}
