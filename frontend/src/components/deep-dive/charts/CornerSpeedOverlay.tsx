'use client';

import { useEffect, useMemo } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useAllLapCorners, useMultiLapData, useCorners } from '@/hooks/useAnalysis';
import { useSessionLaps } from '@/hooks/useSession';
import { useAnalysisStore } from '@/stores';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { colors, fonts } from '@/lib/design-tokens';
import { parseCornerNumber } from '@/lib/cornerUtils';
import { CHART_MARGINS as MARGINS } from './chartHelpers';
import { useUnits } from '@/hooks/useUnits';
import { InfoTooltip } from '@/components/shared/InfoTooltip';
import type { Corner } from '@/lib/types';

interface CornerSpeedOverlayProps {
  sessionId: string;
}

/** Draw only grid lines (behind data). */
function drawGrid(
  ctx: CanvasRenderingContext2D,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  innerWidth: number,
  innerHeight: number,
  margins: typeof MARGINS,
) {
  const yTicks = yScale.ticks(5);
  ctx.strokeStyle = colors.grid;
  ctx.lineWidth = 1;
  for (const tick of yTicks) {
    const y = yScale(tick);
    ctx.beginPath();
    ctx.moveTo(margins.left, y);
    ctx.lineTo(margins.left + innerWidth, y);
    ctx.stroke();
  }
}

/** Draw axis tick labels, axis labels (on top of data). */
function drawLabels(
  ctx: CanvasRenderingContext2D,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  innerWidth: number,
  innerHeight: number,
  margins: typeof MARGINS,
  speedLabel: string,
  distLabel: string,
  convertDist: (m: number) => number,
) {
  ctx.font = `10px ${fonts.mono}`;

  // Y-axis tick labels
  const yTicks = yScale.ticks(5);
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (const tick of yTicks) {
    ctx.fillStyle = colors.axis;
    ctx.fillText(`${tick}`, margins.left - 6, yScale(tick));
  }

  // X-axis tick labels
  const xTicks = xScale.ticks(6);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (const tick of xTicks) {
    ctx.fillStyle = colors.axis;
    ctx.fillText(`${Math.round(convertDist(tick))}`, xScale(tick), margins.top + innerHeight + 6);
  }

  // Axis labels
  ctx.fillStyle = colors.text.secondary;
  ctx.font = `11px ${fonts.sans}`;
  ctx.textAlign = 'center';
  ctx.fillText(distLabel, margins.left + innerWidth / 2, margins.top + innerHeight + 24);

  ctx.save();
  ctx.translate(14, margins.top + innerHeight / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = 'center';
  ctx.fillText(speedLabel, 0, 0);
  ctx.restore();
}

/** Height fraction for the brake/throttle mini-trace strip. */
const G_STRIP_RATIO = 0.25;

export function CornerSpeedOverlay({ sessionId }: CornerSpeedOverlayProps) {
  const { convertSpeed, convertDistance, speedUnit, distanceUnit } = useUnits();
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const hoveredBrakeLap = useAnalysisStore((s) => s.hoveredBrakeLap);

  const { data: corners } = useCorners(sessionId);
  const { data: laps } = useSessionLaps(sessionId);
  const { data: allLapCorners } = useAllLapCorners(sessionId);

  // Get all clean lap numbers
  const cleanLapNumbers = useMemo(() => {
    if (!laps) return [];
    return laps.filter((l) => l.is_clean).map((l) => l.lap_number);
  }, [laps]);

  const { data: lapDataArr, isLoading } = useMultiLapData(sessionId, cleanLapNumbers);

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx } =
    useCanvasChart(MARGINS);

  // Resolve corner data
  const cornerNumber = selectedCorner ? parseCornerNumber(selectedCorner) : null;
  const corner: Corner | undefined = useMemo(() => {
    if (cornerNumber === null || !corners) return undefined;
    return corners.find((c) => c.number === cornerNumber);
  }, [corners, cornerNumber]);

  // Find the best lap (fastest min speed at this corner)
  const bestLapNumber = useMemo(() => {
    if (!allLapCorners || cornerNumber === null) return null;
    let bestSpeed = -Infinity;
    let bestLap: number | null = null;
    for (const [lapNum, lapCorners] of Object.entries(allLapCorners)) {
      const c = lapCorners.find((lc) => lc.number === cornerNumber);
      if (c && c.min_speed_mph > bestSpeed) {
        bestSpeed = c.min_speed_mph;
        bestLap = parseInt(lapNum, 10);
      }
    }
    return bestLap;
  }, [allLapCorners, cornerNumber]);

  // Ref lap: the first selected lap (if any)
  const refLap = selectedLaps.length >= 1 ? selectedLaps[0] : null;
  // Comparison lap: the second selected lap if any
  const compLap = selectedLaps.length >= 2 ? selectedLaps[1] : null;

  // Build scales scoped to the corner zone
  // Speed chart gets top ~75%, g-strip gets bottom ~25%
  const { xScale, yScale, gScale, speedAreaHeight, gStripTop, gStripHeight } = useMemo(() => {
    const totalHeight = dimensions.innerHeight;
    const gH = Math.round(totalHeight * G_STRIP_RATIO);
    const speedH = totalHeight - gH;
    const gTop = MARGINS.top + speedH;

    if (!corner || lapDataArr.length === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.left, MARGINS.left + 1]),
        yScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.top + 1, MARGINS.top]),
        gScale: d3.scaleLinear().domain([-1, 1]).range([gTop + gH, gTop]),
        speedAreaHeight: speedH,
        gStripTop: gTop,
        gStripHeight: gH,
      };
    }

    const entryDist = corner.entry_distance_m;
    const exitDist = corner.exit_distance_m;
    // Add a 10% margin outside the corner zone
    const span = exitDist - entryDist;
    const xMin = Math.max(0, entryDist - span * 0.1);
    const xMax = exitDist + span * 0.1;

    // Find min/max speed within this range across all laps
    let minSpeed = Infinity;
    let maxSpeed = -Infinity;
    let maxAbsG = 0;
    for (const lap of lapDataArr) {
      for (let i = 0; i < lap.distance_m.length; i++) {
        if (lap.distance_m[i] >= xMin && lap.distance_m[i] <= xMax) {
          const spd = convertSpeed(lap.speed_mph[i]);
          if (spd < minSpeed) minSpeed = spd;
          if (spd > maxSpeed) maxSpeed = spd;
          if (lap.longitudinal_g) {
            const absG = Math.abs(lap.longitudinal_g[i]);
            if (absG > maxAbsG) maxAbsG = absG;
          }
        }
      }
    }

    if (!isFinite(minSpeed)) minSpeed = 0;
    if (!isFinite(maxSpeed)) maxSpeed = 100;
    if (maxAbsG === 0) maxAbsG = 0.5;

    const speedPad = (maxSpeed - minSpeed) * 0.08;
    const gBound = maxAbsG * 1.15;

    return {
      xScale: d3
        .scaleLinear()
        .domain([xMin, xMax])
        .range([MARGINS.left, MARGINS.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([Math.max(0, minSpeed - speedPad), maxSpeed + speedPad])
        .range([MARGINS.top + speedH, MARGINS.top]),
      gScale: d3
        .scaleLinear()
        .domain([-gBound, gBound])
        .range([gTop + gH, gTop]),
      speedAreaHeight: speedH,
      gStripTop: gTop,
      gStripHeight: gH,
    };
  }, [corner, lapDataArr, dimensions.innerWidth, dimensions.innerHeight, convertSpeed]);

  // Draw
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || dimensions.innerWidth <= 0 || !corner || lapDataArr.length === 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    // --- 1. Grid lines (behind data) ---
    drawGrid(ctx, xScale, yScale, dimensions.innerWidth, speedAreaHeight, MARGINS);

    // Corner zone shading
    const entryX = xScale(corner.entry_distance_m);
    const apexX = xScale(corner.apex_distance_m);
    const exitX = xScale(corner.exit_distance_m);

    ctx.fillStyle = 'rgba(255, 255, 255, 0.03)';
    ctx.fillRect(entryX, MARGINS.top, exitX - entryX, dimensions.innerHeight);

    // Vertical markers: entry, apex, exit
    const markers = [
      { x: entryX, label: 'Entry', style: 'rgba(255,255,255,0.2)' },
      { x: apexX, label: 'Apex', style: colors.motorsport.optimal },
      { x: exitX, label: 'Exit', style: 'rgba(255,255,255,0.2)' },
    ];
    for (const m of markers) {
      ctx.strokeStyle = m.style;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(m.x, MARGINS.top);
      ctx.lineTo(m.x, MARGINS.top + dimensions.innerHeight);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // --- 2. Data: speed traces ---
    // All clean laps — thin, semi-transparent
    for (let li = 0; li < lapDataArr.length; li++) {
      const lap = lapDataArr[li];
      const isBest = lap.lap_number === bestLapNumber;
      const isComp = lap.lap_number === compLap;
      const isRef = lap.lap_number === refLap;

      // Skip best/comp/ref — draw them separately on top
      if (isBest || isComp || isRef) continue;

      ctx.strokeStyle = `${colors.lap[li % colors.lap.length]}40`; // ~25% opacity
      ctx.lineWidth = 1;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < lap.distance_m.length; i++) {
        const x = xScale(lap.distance_m[i]);
        const y = yScale(convertSpeed(lap.speed_mph[i]));
        if (!started) {
          ctx.moveTo(x, y);
          started = true;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }

    // Ref lap — solid, highlighted (when not also the best lap)
    if (refLap !== null && refLap !== bestLapNumber) {
      const refData = lapDataArr.find((l) => l.lap_number === refLap);
      if (refData) {
        ctx.strokeStyle = colors.lap[0];
        ctx.lineWidth = 2;
        ctx.beginPath();
        let started = false;
        for (let i = 0; i < refData.distance_m.length; i++) {
          const x = xScale(refData.distance_m[i]);
          const y = yScale(convertSpeed(refData.speed_mph[i]));
          if (!started) {
            ctx.moveTo(x, y);
            started = true;
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
      }
    }

    // Comparison lap — dashed
    if (compLap !== null) {
      const compData = lapDataArr.find((l) => l.lap_number === compLap);
      if (compData) {
        ctx.strokeStyle = colors.lap[1 % colors.lap.length];
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        let started = false;
        for (let i = 0; i < compData.distance_m.length; i++) {
          const x = xScale(compData.distance_m[i]);
          const y = yScale(convertSpeed(compData.speed_mph[i]));
          if (!started) {
            ctx.moveTo(x, y);
            started = true;
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }

    // Best lap — thick, solid, purple
    const bestData = bestLapNumber !== null
      ? lapDataArr.find((l) => l.lap_number === bestLapNumber)
      : undefined;

    if (bestData) {
      ctx.strokeStyle = colors.motorsport.pb;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < bestData.distance_m.length; i++) {
        const x = xScale(bestData.distance_m[i]);
        const y = yScale(convertSpeed(bestData.speed_mph[i]));
        if (!started) {
          ctx.moveTo(x, y);
          started = true;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }

    // --- 3. Brake/throttle mini-trace strip (best lap only) ---
    // Separator line between speed chart and g-strip
    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(MARGINS.left, gStripTop);
    ctx.lineTo(MARGINS.left + dimensions.innerWidth, gStripTop);
    ctx.stroke();

    // Draw brake/throttle fill for the best lap (or first available)
    const gLap = bestData ?? lapDataArr[0];
    if (gLap && gLap.longitudinal_g && gStripHeight > 0) {
      const gData = gLap.longitudinal_g;
      const zeroY = gScale(0);

      // Clip to the strip area
      ctx.save();
      ctx.beginPath();
      ctx.rect(MARGINS.left, gStripTop, dimensions.innerWidth, gStripHeight);
      ctx.clip();

      // Fill segments colored by sign of longitudinal_g
      for (let i = 1; i < gLap.distance_m.length; i++) {
        const x0 = xScale(gLap.distance_m[i - 1]);
        const x1 = xScale(gLap.distance_m[i]);
        const y0 = gScale(gData[i - 1]);
        const y1 = gScale(gData[i]);
        const avgG = (gData[i - 1] + gData[i]) / 2;

        ctx.fillStyle = avgG < 0
          ? 'rgba(239, 68, 68, 0.35)' // braking — red
          : 'rgba(34, 197, 94, 0.35)'; // throttle — green

        ctx.beginPath();
        ctx.moveTo(x0, zeroY);
        ctx.lineTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.lineTo(x1, zeroY);
        ctx.closePath();
        ctx.fill();
      }

      // Zero line in the g-strip
      ctx.strokeStyle = colors.axis;
      ctx.lineWidth = 0.5;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(MARGINS.left, zeroY);
      ctx.lineTo(MARGINS.left + dimensions.innerWidth, zeroY);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.restore();

      // Label for g-strip
      ctx.fillStyle = colors.text.muted;
      ctx.font = `9px ${fonts.sans}`;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText('Long. G', MARGINS.left + 4, gStripTop + 3);
    }

    // --- 4. Axis tick labels and axis labels (on top) ---
    drawLabels(ctx, xScale, yScale, dimensions.innerWidth, speedAreaHeight, MARGINS, `Speed (${speedUnit})`, `Distance (${distanceUnit})`, convertDistance);

    // Entry/apex/exit marker labels
    for (const m of markers) {
      ctx.fillStyle = m.style;
      ctx.font = `9px ${fonts.sans}`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      ctx.fillText(m.label, m.x, MARGINS.top - 2);
    }

    // --- 5. Legend ---
    const legendY = MARGINS.top + 8;
    const legendX = MARGINS.left + 8;
    let legendRow = 0;
    ctx.font = `10px ${fonts.sans}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';

    // Best lap label
    ctx.fillStyle = colors.motorsport.pb;
    ctx.fillRect(legendX, legendY + legendRow * 16, 14, 2);
    ctx.fillText(
      bestLapNumber !== null ? `Best (L${bestLapNumber})` : 'Best',
      legendX + 18,
      legendY + legendRow * 16 - 4,
    );
    legendRow++;

    // Ref lap label (when not the best lap)
    if (refLap !== null && refLap !== bestLapNumber) {
      ctx.strokeStyle = colors.lap[0];
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(legendX, legendY + legendRow * 16);
      ctx.lineTo(legendX + 14, legendY + legendRow * 16);
      ctx.stroke();
      ctx.fillStyle = colors.text.secondary;
      ctx.fillText(`Ref (L${refLap})`, legendX + 18, legendY + legendRow * 16 - 4);
      legendRow++;
    }

    // Comp lap label
    if (compLap !== null) {
      ctx.strokeStyle = colors.lap[1 % colors.lap.length];
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(legendX, legendY + legendRow * 16);
      ctx.lineTo(legendX + 14, legendY + legendRow * 16);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = colors.text.secondary;
      ctx.fillText(`Comp (L${compLap})`, legendX + 18, legendY + legendRow * 16 - 4);
    }
  }, [
    lapDataArr,
    corner,
    bestLapNumber,
    refLap,
    compLap,
    xScale,
    yScale,
    gScale,
    speedAreaHeight,
    gStripTop,
    gStripHeight,
    dimensions,
    getDataCtx,
    convertSpeed,
    convertDistance,
    speedUnit,
    distanceUnit,
  ]);

  // --- Cross-chart hover: highlight lap line + vertical brake marker ---
  useEffect(() => {
    const ctx = getOverlayCtx();
    if (!ctx) return;
    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

    if (!hoveredBrakeLap || !corner || lapDataArr.length === 0 || dimensions.innerWidth <= 0) return;

    const lapData = lapDataArr.find((l) => l.lap_number === hoveredBrakeLap.lapNumber);
    if (!lapData) return;

    // Draw highlighted speed line for this lap
    ctx.strokeStyle = colors.text.primary;
    ctx.lineWidth = 2.5;
    ctx.globalAlpha = 0.9;
    ctx.beginPath();
    let started = false;
    for (let i = 0; i < lapData.distance_m.length; i++) {
      const x = xScale(lapData.distance_m[i]);
      const y = yScale(convertSpeed(lapData.speed_mph[i]));
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Draw vertical marker at brake point distance
    // Brake points are often before the corner entry zone, so clamp to the
    // visible chart area but still draw the line at the edge with an arrow.
    const bpXRaw = xScale(hoveredBrakeLap.brakePointM);
    const chartLeft = MARGINS.left;
    const chartRight = MARGINS.left + dimensions.innerWidth;
    const bpX = Math.max(chartLeft, Math.min(chartRight, bpXRaw));
    const isOffChart = bpXRaw < chartLeft;

    ctx.save();
    ctx.beginPath();
    ctx.rect(chartLeft, MARGINS.top, dimensions.innerWidth, dimensions.innerHeight);
    ctx.clip();

    ctx.strokeStyle = colors.motorsport.brake;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 3]);
    ctx.beginPath();
    ctx.moveTo(bpX, MARGINS.top);
    ctx.lineTo(bpX, MARGINS.top + dimensions.innerHeight);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();

    // Label (above chart)
    ctx.fillStyle = colors.motorsport.brake;
    ctx.font = `10px ${fonts.mono}`;
    ctx.textAlign = isOffChart ? 'left' : 'center';
    ctx.textBaseline = 'bottom';
    const bpLabel = `${isOffChart ? '\u25C0 ' : ''}BP L${hoveredBrakeLap.lapNumber}`;
    ctx.fillText(bpLabel, bpX + (isOffChart ? 2 : 0), MARGINS.top - 2);
  }, [hoveredBrakeLap, lapDataArr, corner, xScale, yScale, dimensions, getOverlayCtx, convertSpeed]);

  if (!selectedCorner || cornerNumber === null) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <p className="text-sm text-[var(--text-secondary)]">Select a corner to view speed overlay</p>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
      <div className="pointer-events-none absolute left-3 top-1 z-10 flex items-center gap-1.5">
        <h3 className="rounded bg-[var(--bg-surface)]/80 px-1 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Turn {cornerNumber} Speed
        </h3>
        <InfoTooltip helpKey="chart.corner-speed-overlay" className="pointer-events-auto" />
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
        />
      </div>
      {isLoading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-[var(--bg-surface)]/80">
          <CircularProgress size={20} />
        </div>
      )}
    </div>
  );
}
