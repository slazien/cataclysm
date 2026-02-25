import { colors, fonts } from '@/lib/design-tokens';
import type * as d3 from 'd3';
import type { TrendSessionSummary } from '@/lib/types';

interface DrawTrendAxesOptions {
  ctx: CanvasRenderingContext2D;
  xScale: d3.ScaleLinear<number, number>;
  yScale: d3.ScaleLinear<number, number>;
  sessions: TrendSessionSummary[];
  innerWidth: number;
  innerHeight: number;
  margins: { top: number; right: number; bottom: number; left: number };
  yLabel: string;
  formatYTick?: (value: number) => string;
  yTickCount?: number;
}

export function drawTrendAxes({
  ctx,
  xScale,
  yScale,
  sessions,
  innerWidth,
  innerHeight,
  margins,
  yLabel,
  formatYTick = (v) => `${v}`,
  yTickCount = 5,
}: DrawTrendAxesOptions): void {
  ctx.strokeStyle = colors.axis;
  ctx.fillStyle = colors.axis;
  ctx.font = `10px ${fonts.mono}`;

  // Y-axis ticks
  const yTicks = yScale.ticks(yTickCount);
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (const tick of yTicks) {
    const y = yScale(tick);
    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(margins.left, y);
    ctx.lineTo(margins.left + innerWidth, y);
    ctx.stroke();
    ctx.fillStyle = colors.axis;
    ctx.fillText(formatYTick(tick), margins.left - 6, y);
  }

  // X-axis labels
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (let i = 0; i < sessions.length; i++) {
    const x = xScale(i);
    ctx.fillStyle = colors.axis;
    const dateLabel = new Date(sessions[i].session_date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
    ctx.fillText(dateLabel, x, margins.top + innerHeight + 6);
  }

  // Axis labels
  ctx.fillStyle = colors.text.secondary;
  ctx.font = `11px ${fonts.sans}`;
  ctx.textAlign = 'center';
  ctx.fillText('Session', margins.left + innerWidth / 2, margins.top + innerHeight + 28);

  ctx.save();
  ctx.translate(14, margins.top + innerHeight / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = 'center';
  ctx.fillText(yLabel, 0, 0);
  ctx.restore();
}
