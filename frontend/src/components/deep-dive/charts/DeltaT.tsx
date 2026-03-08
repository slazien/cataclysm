'use client';

import { useCallback, useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';
import { motion } from 'motion/react';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useAnimationFrame } from '@/hooks/useAnimationFrame';
import { useDelta } from '@/hooks/useAnalysis';
import { useAnalysisStore } from '@/stores';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { colors, fonts } from '@/lib/design-tokens';
import { getChartMargins } from './chartHelpers';
import { useUnits } from '@/hooks/useUnits';

interface DeltaTProps {
  sessionId: string;
}

export function DeltaT({ sessionId }: DeltaTProps) {
  const { convertDistance, distanceUnit } = useUnits();
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);

  const refLap = selectedLaps.length >= 2 ? selectedLaps[0] : null;
  const compLap = selectedLaps.length >= 2 ? selectedLaps[1] : null;

  // isPending (not isLoading) covers paused queries too — mobile browsers pause
  // fetches on background/network blip; isLoading = isPending && isFetching misses those.
  const { data: delta, isPending: isLoading } = useDelta(sessionId, refLap, compLap);

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx, makeTouchProps } =
    useCanvasChart(getChartMargins);

  const { xScale, yScale } = useMemo(() => {
    const m = dimensions.margins;
    if (!delta || delta.distance_m.length === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([m.left, m.left + 1]),
        yScale: d3.scaleLinear().domain([-1, 1]).range([m.top + 1, m.top]),
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
        .range([m.left, m.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([-bound, bound])
        .range([m.top + dimensions.innerHeight, m.top]),
    };
  }, [delta, dimensions.innerWidth, dimensions.innerHeight, dimensions.margins]);

  const xScaleRef = useRef(xScale);
  xScaleRef.current = xScale;
  const dimsRef = useRef(dimensions);
  dimsRef.current = dimensions;

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
    ctx.moveTo(dimensions.margins.left, zeroY);
    ctx.lineTo(dimensions.margins.left + dimensions.innerWidth, zeroY);
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
      ctx.moveTo(dimensions.margins.left, y);
      ctx.lineTo(dimensions.margins.left + dimensions.innerWidth, y);
      ctx.stroke();
      ctx.fillStyle = colors.axis;
      ctx.fillText(tick.toFixed(2), dimensions.margins.left - 6, y);
    }

    // X-axis ticks
    const xTicks = xScale.ticks(8);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (const tick of xTicks) {
      ctx.fillStyle = colors.axis;
      ctx.fillText(`${Math.round(convertDistance(tick))}`, xScale(tick), dimensions.margins.top + dimensions.innerHeight + 6);
    }

    // Axis labels
    ctx.fillStyle = colors.text.secondary;
    ctx.font = `11px ${fonts.sans}`;
    ctx.textAlign = 'center';
    ctx.fillText(
      `Distance (${distanceUnit})`,
      dimensions.margins.left + dimensions.innerWidth / 2,
      dimensions.margins.top + dimensions.innerHeight + 24,
    );

    ctx.save();
    ctx.translate(14, dimensions.margins.top + dimensions.innerHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillText('Delta (s) \u2014 ref vs compare', 0, 0);
    ctx.restore();

    // Total delta in top-right
    if (delta.total_delta_s !== undefined) {
      const totalStr = `${delta.total_delta_s >= 0 ? '+' : ''}${delta.total_delta_s.toFixed(3)}s`;
      ctx.font = `bold 12px ${fonts.mono}`;
      ctx.textAlign = 'right';
      ctx.textBaseline = 'top';
      ctx.fillStyle =
        delta.total_delta_s > 0 ? colors.motorsport.brake : colors.motorsport.throttle;
      ctx.fillText(totalStr, dimensions.margins.left + dimensions.innerWidth - 4, dimensions.margins.top + 4);
    }
  }, [delta, xScale, yScale, dimensions, convertDistance, distanceUnit]);

  // Mouse handlers as React event props — avoids stale listener bug when
  // canvas unmounts/remounts during loading transitions.
  const handleOverlayMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const scale = xScaleRef.current;
    const [xMin, xMax] = scale.range();
    if (x >= xMin && x <= xMax) {
      useAnalysisStore.getState().setCursorDistance(scale.invert(x));
    }
  }, []);

  const handleOverlayMouseLeave = useCallback(() => {
    useAnalysisStore.getState().setCursorDistance(null);
  }, []);

  // Cursor overlay — always-active RAF reads store directly
  useAnimationFrame(() => {
    const ctx = getOverlayCtx();
    if (!ctx) return;
    const dims = dimsRef.current;
    ctx.clearRect(0, 0, dims.width, dims.height);

    const cursorDist = useAnalysisStore.getState().cursorDistance;
    if (cursorDist === null || !delta) return;

    const x = xScaleRef.current(cursorDist);
    const dm = dims.margins;
    if (x < dm.left || x > dm.left + dims.innerWidth) return;

    // Vertical cursor line
    ctx.strokeStyle = colors.cursor;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x, dm.top);
    ctx.lineTo(x, dm.top + dims.innerHeight);
    ctx.stroke();

    // Tooltip with delta value
    const idx = d3.bisectLeft(delta.distance_m, cursorDist);
    const clampedIdx = Math.min(idx, delta.delta_s.length - 1);
    const dVal = delta.delta_s[clampedIdx];
    const label = `${dVal >= 0 ? '+' : ''}${dVal.toFixed(3)}s`;

    ctx.font = `11px ${fonts.mono}`;
    const tooltipY = dm.top + 8;
    const textWidth = ctx.measureText(label).width;
    const rightEdge = dm.left + dims.innerWidth;
    const tooltipX = x + textWidth + 20 > rightEdge ? x - textWidth - 16 : x + 10;
    ctx.fillStyle = 'rgba(10, 12, 16, 0.85)';
    ctx.fillRect(tooltipX - 2, tooltipY - 2, textWidth + 8, 16);
    ctx.fillStyle = dVal > 0 ? colors.motorsport.brake : colors.motorsport.throttle;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(label, tooltipX + 2, tooltipY);
  });

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
      <motion.div
        initial={{ clipPath: 'inset(0 100% 0 0)' }}
        animate={{ clipPath: 'inset(0 0% 0 0)' }}
        transition={{ duration: 0.5, ease: 'easeOut', delay: 0.2 }}
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
          {...makeTouchProps(handleOverlayMouseMove, handleOverlayMouseLeave)}
          style={{ width: '100%', height: '100%', cursor: 'crosshair', zIndex: 2, pointerEvents: 'auto' }}
        />
      </motion.div>
    </div>
  );
}
