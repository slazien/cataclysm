'use client';

import { useEffect, useMemo } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useUnits } from '@/hooks/useUnits';
import { colors, fonts } from '@/lib/design-tokens';

const MARGINS = { top: 16, right: 16, bottom: 36, left: 56 };
const MARGINS_MOBILE = { top: 12, right: 8, bottom: 28, left: 40 };
const getCompMargins = (isMobile: boolean) => (isMobile ? MARGINS_MOBILE : MARGINS);

interface ComparisonDeltaChartProps {
  cornerNumber: number;
  distanceM: number[];
  deltaTimeS: number[];
}

export function ComparisonDeltaChart({
  cornerNumber,
  distanceM,
  deltaTimeS,
}: ComparisonDeltaChartProps) {
  const { convertDistance, distanceUnit } = useUnits();
  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx } =
    useCanvasChart(getCompMargins);

  const { xScale, yScale } = useMemo(() => {
    if (distanceM.length === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([dimensions.margins.left, dimensions.margins.left + 1]),
        yScale: d3.scaleLinear().domain([-1, 1]).range([dimensions.margins.top + 1, dimensions.margins.top]),
      };
    }

    const minDist = d3.min(distanceM) ?? 0;
    const maxDist = d3.max(distanceM) ?? 1;
    const maxAbs = d3.max(deltaTimeS.map((v) => Math.abs(v))) ?? 0.1;
    const bound = Math.max(maxAbs * 1.2, 0.05);

    return {
      xScale: d3
        .scaleLinear()
        .domain([minDist, maxDist])
        .range([dimensions.margins.left, dimensions.margins.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([-bound, bound])
        .range([dimensions.margins.top + dimensions.innerHeight, dimensions.margins.top]),
    };
  }, [distanceM, deltaTimeS, dimensions.innerWidth, dimensions.innerHeight]);

  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || distanceM.length === 0 || dimensions.innerWidth <= 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    const zeroY = yScale(0);

    // Draw filled areas
    for (let i = 1; i < distanceM.length; i++) {
      const x0 = xScale(distanceM[i - 1]);
      const x1 = xScale(distanceM[i]);
      const y0 = yScale(deltaTimeS[i - 1]);
      const y1 = yScale(deltaTimeS[i]);

      const deltaVal = (deltaTimeS[i - 1] + deltaTimeS[i]) / 2;

      ctx.fillStyle =
        deltaVal > 0
          ? 'rgba(34, 197, 94, 0.35)' // green -- positive = A gaining
          : 'rgba(239, 68, 68, 0.35)'; // red -- negative = A losing

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
    for (let i = 0; i < distanceM.length; i++) {
      const x = xScale(distanceM[i]);
      const y = yScale(deltaTimeS[i]);
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
      ctx.fillText(tick.toFixed(3), dimensions.margins.left - 6, y);
    }

    // X-axis ticks
    const xTicks = xScale.ticks(6);
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
    ctx.fillText('Delta (s)', 0, 0);
    ctx.restore();

    // Corner label in top-left
    ctx.font = `bold 12px ${fonts.sans}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillStyle = colors.text.primary;
    ctx.fillText(`Turn ${cornerNumber}`, dimensions.margins.left + 4, dimensions.margins.top + 4);
  }, [cornerNumber, distanceM, deltaTimeS, xScale, yScale, dimensions, getDataCtx, convertDistance, distanceUnit]);

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
        style={{ width: '100%', height: '100%', zIndex: 2 }}
      />
    </div>
  );
}
