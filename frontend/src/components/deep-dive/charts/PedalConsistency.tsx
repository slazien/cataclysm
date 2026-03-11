'use client';

import { useCallback, useEffect, useMemo } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useAllLapCorners } from '@/hooks/useAnalysis';
import { useUnits } from '@/hooks/useUnits';
import { useAnalysisStore } from '@/stores';
import { colors, fonts } from '@/lib/design-tokens';
import { parseCornerNumber } from '@/lib/cornerUtils';
import { InfoTooltip } from '@/components/shared/InfoTooltip';
import { getChartMargins } from './chartHelpers';

interface PedalConsistencyProps {
  sessionId: string;
}

interface BrakePoint {
  lapNumber: number;
  brakePointM: number;
}

interface ThrottlePoint {
  lapNumber: number;
  throttleCommitM: number;
}

export function PedalConsistency({ sessionId }: PedalConsistencyProps) {
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const hoveredPedalPoint = useAnalysisStore((s) => s.hoveredPedalPoint);
  const setHoveredPedalPoint = useAnalysisStore((s) => s.setHoveredPedalPoint);
  const { data: allLapCorners } = useAllLapCorners(sessionId);
  const { convertDistance, distanceUnit } = useUnits();

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx, makeTouchProps } =
    useCanvasChart(getChartMargins);

  const cornerNumber = selectedCorner ? parseCornerNumber(selectedCorner) : null;

  // Extract brake points for the selected corner across all laps
  const brakePoints: BrakePoint[] = useMemo(() => {
    if (cornerNumber === null || !allLapCorners) return [];
    const points: BrakePoint[] = [];
    for (const [lapNum, lapCorners] of Object.entries(allLapCorners)) {
      const c = lapCorners.find((lc) => lc.number === cornerNumber);
      if (c && c.brake_point_m !== null) {
        points.push({
          lapNumber: parseInt(lapNum, 10),
          brakePointM: c.brake_point_m,
        });
      }
    }
    points.sort((a, b) => a.lapNumber - b.lapNumber);
    return points;
  }, [allLapCorners, cornerNumber]);

  // Extract throttle commit points for the selected corner across all laps
  const throttlePoints: ThrottlePoint[] = useMemo(() => {
    if (cornerNumber === null || !allLapCorners) return [];
    const points: ThrottlePoint[] = [];
    for (const [lapNum, lapCorners] of Object.entries(allLapCorners)) {
      const c = lapCorners.find((lc) => lc.number === cornerNumber);
      if (c && c.throttle_commit_m !== null) {
        points.push({
          lapNumber: parseInt(lapNum, 10),
          throttleCommitM: c.throttle_commit_m,
        });
      }
    }
    points.sort((a, b) => a.lapNumber - b.lapNumber);
    return points;
  }, [allLapCorners, cornerNumber]);

  // Brake stats
  const brakeStats = useMemo(() => {
    if (brakePoints.length === 0) return { mean: 0, stdDev: 0 };
    const values = brakePoints.map((p) => p.brakePointM);
    const m = d3.mean(values) ?? 0;
    const sd = d3.deviation(values) ?? 0;
    return { mean: m, stdDev: sd };
  }, [brakePoints]);

  // Throttle stats
  const throttleStats = useMemo(() => {
    if (throttlePoints.length === 0) return { mean: 0, stdDev: 0 };
    const values = throttlePoints.map((p) => p.throttleCommitM);
    const m = d3.mean(values) ?? 0;
    const sd = d3.deviation(values) ?? 0;
    return { mean: m, stdDev: sd };
  }, [throttlePoints]);

  // Build split dual scales
  const { xScale, brakeYScale, throttleYScale, splitY } = useMemo(() => {
    const hasData = brakePoints.length > 0 || throttlePoints.length > 0;
    if (!hasData || dimensions.innerWidth <= 0) {
      const dummy = d3.scaleLinear().domain([0, 1]).range([0, 1]);
      return { xScale: dummy, brakeYScale: dummy, throttleYScale: dummy, splitY: 0 };
    }

    // Shared X axis
    const allLaps = [
      ...brakePoints.map((p) => p.lapNumber),
      ...throttlePoints.map((p) => p.lapNumber),
    ];
    const minLap = d3.min(allLaps) ?? 0;
    const maxLap = d3.max(allLaps) ?? 1;
    const xs = d3
      .scaleLinear()
      .domain([minLap - 0.5, maxLap + 0.5])
      .range([dimensions.margins.left, dimensions.margins.left + dimensions.innerWidth]);

    // If only one type has data, give it full height
    const hasBrake = brakePoints.length > 0;
    const hasThrottle = throttlePoints.length > 0;
    const topFraction = hasBrake && hasThrottle ? 0.46 : hasBrake ? 1.0 : 0.0;
    const gapFraction = hasBrake && hasThrottle ? 0.08 : 0.0;
    const bottomFraction = 1.0 - topFraction - gapFraction;

    const topHeight = dimensions.innerHeight * topFraction;
    const gapHeight = dimensions.innerHeight * gapFraction;
    const bottomHeight = dimensions.innerHeight * bottomFraction;
    const splitLine = dimensions.margins.top + topHeight + gapHeight / 2;

    // Brake Y (top)
    let bys = d3.scaleLinear().domain([0, 1]).range([0, 1]);
    if (hasBrake) {
      const bpValues = brakePoints.map((p) => p.brakePointM);
      const bpMin = d3.min(bpValues) ?? 0;
      const bpMax = d3.max(bpValues) ?? 1;
      const bpPad = (bpMax - bpMin) * 0.15 || 5;
      bys = d3
        .scaleLinear()
        .domain([bpMin - bpPad, bpMax + bpPad])
        .range([dimensions.margins.top + topHeight, dimensions.margins.top]);
    }

    // Throttle Y (bottom)
    let tys = d3.scaleLinear().domain([0, 1]).range([0, 1]);
    if (hasThrottle) {
      const tpValues = throttlePoints.map((p) => p.throttleCommitM);
      const tpMin = d3.min(tpValues) ?? 0;
      const tpMax = d3.max(tpValues) ?? 1;
      const tpPad = (tpMax - tpMin) * 0.15 || 5;
      tys = d3
        .scaleLinear()
        .domain([tpMin - tpPad, tpMax + tpPad])
        .range([
          dimensions.margins.top + topHeight + gapHeight + bottomHeight,
          dimensions.margins.top + topHeight + gapHeight,
        ]);
    }

    return { xScale: xs, brakeYScale: bys, throttleYScale: tys, splitY: splitLine };
  }, [brakePoints, throttlePoints, dimensions]);

  // Draw
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || dimensions.innerWidth <= 0) return;
    if (brakePoints.length === 0 && throttlePoints.length === 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    const hasBrake = brakePoints.length > 0;
    const hasThrottle = throttlePoints.length > 0;

    // --- BRAKE SECTION (top) ---
    if (hasBrake) {
      // Section label
      ctx.fillStyle = colors.motorsport.brake;
      ctx.font = `9px ${fonts.sans}`;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText('BRAKE', dimensions.margins.left + 4, dimensions.margins.top + 4);

      // Grid lines
      const brakeYTicks = brakeYScale.ticks(4);
      ctx.strokeStyle = colors.grid;
      ctx.lineWidth = 1;
      for (const tick of brakeYTicks) {
        const y = brakeYScale(tick);
        ctx.beginPath();
        ctx.moveTo(dimensions.margins.left, y);
        ctx.lineTo(dimensions.margins.left + dimensions.innerWidth, y);
        ctx.stroke();
      }

      // Y-axis tick labels
      ctx.font = `10px ${fonts.mono}`;
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      for (const tick of brakeYTicks) {
        ctx.fillStyle = colors.axis;
        ctx.fillText(`${convertDistance(tick).toFixed(0)}`, dimensions.margins.left - 6, brakeYScale(tick));
      }

      // Std dev band
      if (brakeStats.stdDev > 0) {
        const bandTop = brakeYScale(brakeStats.mean + brakeStats.stdDev);
        const bandBottom = brakeYScale(brakeStats.mean - brakeStats.stdDev);
        ctx.fillStyle = 'rgba(239, 68, 68, 0.08)';
        ctx.fillRect(dimensions.margins.left, bandTop, dimensions.innerWidth, bandBottom - bandTop);
      }

      // Mean reference line (dashed)
      const meanY = brakeYScale(brakeStats.mean);
      ctx.strokeStyle = colors.motorsport.brake;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(dimensions.margins.left, meanY);
      ctx.lineTo(dimensions.margins.left + dimensions.innerWidth, meanY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Mean label
      ctx.fillStyle = colors.motorsport.brake;
      ctx.font = `10px ${fonts.mono}`;
      ctx.textAlign = 'right';
      ctx.textBaseline = 'bottom';
      ctx.fillText(
        `avg: ${convertDistance(brakeStats.mean).toFixed(0)}${distanceUnit}`,
        dimensions.margins.left + dimensions.innerWidth - 4,
        meanY - 3,
      );

      // Dots
      for (let i = 0; i < brakePoints.length; i++) {
        const bp = brakePoints[i];
        const x = xScale(bp.lapNumber);
        const y = brakeYScale(bp.brakePointM);
        const color = colors.lap[i % colors.lap.length];

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, 2 * Math.PI);
        ctx.fill();

        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Lap number label below dot
        ctx.fillStyle = colors.text.muted;
        ctx.font = `9px ${fonts.mono}`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(`L${bp.lapNumber}`, x, y + 7);
      }

      // Std dev annotation (top-right of brake section)
      if (brakeStats.stdDev > 0) {
        ctx.fillStyle = colors.text.muted;
        ctx.font = `9px ${fonts.sans}`;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'top';
        ctx.fillText(
          `\u03c3 ${convertDistance(brakeStats.stdDev).toFixed(1)}${distanceUnit}`,
          dimensions.margins.left + dimensions.innerWidth - 4,
          dimensions.margins.top + 4,
        );
      }
    }

    // --- SEPARATOR ---
    if (hasBrake && hasThrottle) {
      ctx.strokeStyle = 'rgba(255,255,255,0.1)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(dimensions.margins.left, splitY);
      ctx.lineTo(dimensions.margins.left + dimensions.innerWidth, splitY);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // --- THROTTLE SECTION (bottom) ---
    if (hasThrottle) {
      // Compute top of throttle region for label placement
      const throttleRegionTop = hasThrottle && hasBrake
        ? splitY + (dimensions.innerHeight * 0.08) / 2
        : dimensions.margins.top;

      // Section label
      ctx.fillStyle = colors.motorsport.throttle;
      ctx.font = `9px ${fonts.sans}`;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText('THROTTLE', dimensions.margins.left + 4, throttleRegionTop + 4);

      // Grid lines
      const throttleYTicks = throttleYScale.ticks(4);
      ctx.strokeStyle = colors.grid;
      ctx.lineWidth = 1;
      for (const tick of throttleYTicks) {
        const y = throttleYScale(tick);
        ctx.beginPath();
        ctx.moveTo(dimensions.margins.left, y);
        ctx.lineTo(dimensions.margins.left + dimensions.innerWidth, y);
        ctx.stroke();
      }

      // Y-axis tick labels
      ctx.font = `10px ${fonts.mono}`;
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      for (const tick of throttleYTicks) {
        ctx.fillStyle = colors.axis;
        ctx.fillText(`${convertDistance(tick).toFixed(0)}`, dimensions.margins.left - 6, throttleYScale(tick));
      }

      // Std dev band
      if (throttleStats.stdDev > 0) {
        const bandTop = throttleYScale(throttleStats.mean + throttleStats.stdDev);
        const bandBottom = throttleYScale(throttleStats.mean - throttleStats.stdDev);
        ctx.fillStyle = 'rgba(34, 197, 94, 0.08)';
        ctx.fillRect(dimensions.margins.left, bandTop, dimensions.innerWidth, bandBottom - bandTop);
      }

      // Mean reference line (dashed)
      const meanY = throttleYScale(throttleStats.mean);
      ctx.strokeStyle = colors.motorsport.throttle;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(dimensions.margins.left, meanY);
      ctx.lineTo(dimensions.margins.left + dimensions.innerWidth, meanY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Mean label
      ctx.fillStyle = colors.motorsport.throttle;
      ctx.font = `10px ${fonts.mono}`;
      ctx.textAlign = 'right';
      ctx.textBaseline = 'bottom';
      ctx.fillText(
        `avg: ${convertDistance(throttleStats.mean).toFixed(0)}${distanceUnit}`,
        dimensions.margins.left + dimensions.innerWidth - 4,
        meanY - 3,
      );

      // Dots
      for (let i = 0; i < throttlePoints.length; i++) {
        const tp = throttlePoints[i];
        const x = xScale(tp.lapNumber);
        const y = throttleYScale(tp.throttleCommitM);
        const color = colors.lap[i % colors.lap.length];

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, 2 * Math.PI);
        ctx.fill();

        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Lap number label below dot
        ctx.fillStyle = colors.text.muted;
        ctx.font = `9px ${fonts.mono}`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(`L${tp.lapNumber}`, x, y + 7);
      }

      // Std dev annotation (top-right of throttle section)
      if (throttleStats.stdDev > 0) {
        ctx.fillStyle = colors.text.muted;
        ctx.font = `9px ${fonts.sans}`;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'top';
        ctx.fillText(
          `\u03c3 ${convertDistance(throttleStats.stdDev).toFixed(1)}${distanceUnit}`,
          dimensions.margins.left + dimensions.innerWidth - 4,
          throttleRegionTop + 4,
        );
      }
    }

    // --- SHARED X-AXIS ---
    const xTicks = xScale.ticks(Math.min(10, (xScale.domain()[1] ?? 1) - (xScale.domain()[0] ?? 0)));
    ctx.font = `10px ${fonts.mono}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (const tick of xTicks) {
      ctx.fillStyle = colors.axis;
      ctx.fillText(`${Math.round(tick)}`, xScale(tick), dimensions.margins.top + dimensions.innerHeight + 6);
    }

    // X-axis title
    ctx.fillStyle = colors.text.secondary;
    ctx.font = `11px ${fonts.sans}`;
    ctx.textAlign = 'center';
    ctx.fillText(
      'Lap Number',
      dimensions.margins.left + dimensions.innerWidth / 2,
      dimensions.margins.top + dimensions.innerHeight + 24,
    );
  }, [
    brakePoints,
    throttlePoints,
    brakeStats,
    throttleStats,
    xScale,
    brakeYScale,
    throttleYScale,
    splitY,
    dimensions,
    getDataCtx,
    convertDistance,
    distanceUnit,
  ]);

  // --- Hover handler: find nearest dot across both sections ---
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = overlayCanvasRef.current;
      if (!canvas || (brakePoints.length === 0 && throttlePoints.length === 0)) return;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      // Find nearest brake point
      let nearestBrake: BrakePoint | null = null;
      let nearestBrakeDist = Infinity;
      for (const bp of brakePoints) {
        const d = Math.hypot(mx - xScale(bp.lapNumber), my - brakeYScale(bp.brakePointM));
        if (d < nearestBrakeDist) {
          nearestBrakeDist = d;
          nearestBrake = bp;
        }
      }

      // Find nearest throttle point
      let nearestThrottle: ThrottlePoint | null = null;
      let nearestThrottleDist = Infinity;
      for (const tp of throttlePoints) {
        const d = Math.hypot(mx - xScale(tp.lapNumber), my - throttleYScale(tp.throttleCommitM));
        if (d < nearestThrottleDist) {
          nearestThrottleDist = d;
          nearestThrottle = tp;
        }
      }

      const ctx = getOverlayCtx();
      if (!ctx) return;
      ctx.clearRect(0, 0, dimensions.width, dimensions.height);

      // Pick closest overall
      const brakeWins = nearestBrakeDist <= nearestThrottleDist;
      const winner = brakeWins ? nearestBrake : nearestThrottle;
      const winnerDist = brakeWins ? nearestBrakeDist : nearestThrottleDist;
      const winnerType: 'brake' | 'throttle' = brakeWins ? 'brake' : 'throttle';

      if (winner && winnerDist < 15) {
        const hx = xScale(winner.lapNumber);
        const hy =
          winnerType === 'brake'
            ? brakeYScale((winner as BrakePoint).brakePointM)
            : throttleYScale((winner as ThrottlePoint).throttleCommitM);
        const distM =
          winnerType === 'brake'
            ? (winner as BrakePoint).brakePointM
            : (winner as ThrottlePoint).throttleCommitM;

        // Highlight ring
        ctx.strokeStyle = colors.text.primary;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(hx, hy, 7, 0, 2 * Math.PI);
        ctx.stroke();

        // Tooltip
        ctx.fillStyle = 'rgba(0,0,0,0.85)';
        const label = `L${winner.lapNumber}: ${convertDistance(distM).toFixed(0)}${distanceUnit}`;
        ctx.font = `11px ${fonts.mono}`;
        const tw = ctx.measureText(label).width;
        const tx = Math.min(hx + 12, dimensions.width - tw - 8);
        const ty = Math.max(hy - 24, dimensions.margins.top);
        ctx.fillRect(tx - 4, ty - 2, tw + 8, 18);
        ctx.fillStyle = colors.text.primary;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillText(label, tx, ty);

        setHoveredPedalPoint({ lapNumber: winner.lapNumber, distanceM: distM, type: winnerType });
      } else {
        setHoveredPedalPoint(null);
      }
    },
    [
      brakePoints,
      throttlePoints,
      xScale,
      brakeYScale,
      throttleYScale,
      dimensions,
      getOverlayCtx,
      setHoveredPedalPoint,
      convertDistance,
      distanceUnit,
      overlayCanvasRef,
    ],
  );

  const handleMouseLeave = useCallback(() => {
    const ctx = getOverlayCtx();
    if (ctx) ctx.clearRect(0, 0, dimensions.width, dimensions.height);
    setHoveredPedalPoint(null);
  }, [getOverlayCtx, dimensions, setHoveredPedalPoint]);

  // External hover sync: highlight dot when hoveredPedalPoint is set from another chart
  useEffect(() => {
    const ctx = getOverlayCtx();
    if (!ctx || dimensions.innerWidth <= 0 || !hoveredPedalPoint) return;

    let hx: number;
    let hy: number;
    let distM: number;

    if (hoveredPedalPoint.type === 'brake') {
      const bp = brakePoints.find((p) => p.lapNumber === hoveredPedalPoint.lapNumber);
      if (!bp) return;
      hx = xScale(bp.lapNumber);
      hy = brakeYScale(bp.brakePointM);
      distM = bp.brakePointM;
    } else {
      const tp = throttlePoints.find((p) => p.lapNumber === hoveredPedalPoint.lapNumber);
      if (!tp) return;
      hx = xScale(tp.lapNumber);
      hy = throttleYScale(tp.throttleCommitM);
      distM = tp.throttleCommitM;
    }

    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

    // Highlight ring
    ctx.strokeStyle = colors.text.primary;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(hx, hy, 7, 0, 2 * Math.PI);
    ctx.stroke();

    // Tooltip
    ctx.fillStyle = 'rgba(0,0,0,0.85)';
    const label = `L${hoveredPedalPoint.lapNumber}: ${convertDistance(distM).toFixed(0)}${distanceUnit}`;
    ctx.font = `11px ${fonts.mono}`;
    const tw = ctx.measureText(label).width;
    const tx = Math.min(hx + 12, dimensions.width - tw - 8);
    const ty = Math.max(hy - 24, dimensions.margins.top);
    ctx.fillRect(tx - 4, ty - 2, tw + 8, 18);
    ctx.fillStyle = colors.text.primary;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(label, tx, ty);
  }, [
    hoveredPedalPoint,
    brakePoints,
    throttlePoints,
    xScale,
    brakeYScale,
    throttleYScale,
    dimensions,
    getOverlayCtx,
    convertDistance,
    distanceUnit,
  ]);

  if (!selectedCorner || cornerNumber === null) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <p className="text-sm text-[var(--text-secondary)]">
          Select a corner to view pedal consistency
        </p>
      </div>
    );
  }

  if (brakePoints.length === 0 && throttlePoints.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <p className="text-sm text-[var(--text-secondary)]">
          No pedal data for Turn {cornerNumber}
        </p>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
      <div className="pointer-events-none absolute left-3 top-1 z-10 flex items-center gap-1.5">
        <h3 className="rounded bg-[var(--bg-surface)]/80 px-1 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Turn {cornerNumber} Pedal Points
        </h3>
        <InfoTooltip helpKey="chart.brake-consistency" className="pointer-events-auto" />
      </div>
      <div ref={containerRef} className="h-full w-full">
        <canvas
          ref={dataCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%', zIndex: 1 }}
        />
        <canvas
          ref={overlayCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%', cursor: 'crosshair', zIndex: 2, pointerEvents: 'auto' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          {...makeTouchProps(handleMouseMove, handleMouseLeave)}
        />
      </div>
    </div>
  );
}
