import type * as d3 from 'd3';
import type { Corner } from '@/lib/types';

export const CHART_MARGINS = { top: 28, right: 16, bottom: 40, left: 56 };

/** Draw semi-transparent corner zone rectangles on a canvas context. */
export function drawCornerZones(
  ctx: CanvasRenderingContext2D,
  corners: Corner[],
  xScale: d3.ScaleLinear<number, number>,
  yTop: number,
  yHeight: number,
) {
  ctx.fillStyle = 'rgba(255, 255, 255, 0.03)';
  for (const c of corners) {
    const x0 = xScale(c.entry_distance_m);
    const x1 = xScale(c.exit_distance_m);
    ctx.fillRect(x0, yTop, x1 - x0, yHeight);
  }
}
