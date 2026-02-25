'use client';

import { useRef, useEffect, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { useSessionLaps } from '@/hooks/useSession';
import { formatLapTime } from '@/lib/formatters';
import { colors } from '@/lib/design-tokens';
import type { LapSummary } from '@/lib/types';

interface LapTimesBarProps {
  sessionId: string;
}

const MARGIN = { top: 16, right: 16, bottom: 36, left: 56 };
const BAR_HEIGHT = 220;

function getBarColor(lap: LapSummary, bestTime: number): string {
  if (lap.lap_time_s === bestTime) return colors.motorsport.pb;
  if (lap.is_clean) return colors.motorsport.optimal;
  return colors.text.muted;
}

export function LapTimesBar({ sessionId }: LapTimesBarProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(600);
  const { data: laps, isLoading } = useSessionLaps(sessionId);

  // ResizeObserver for responsive width
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setWidth(entry.contentRect.width);
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const renderChart = useCallback(() => {
    if (!svgRef.current || !laps || laps.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const chartWidth = width - MARGIN.left - MARGIN.right;
    const chartHeight = BAR_HEIGHT - MARGIN.top - MARGIN.bottom;

    const sortedLaps = [...laps].sort((a, b) => a.lap_number - b.lap_number);
    const lapTimes = sortedLaps.map((l) => l.lap_time_s);
    const bestTime = Math.min(...lapTimes);
    const avgTime = lapTimes.reduce((a, b) => a + b, 0) / lapTimes.length;

    // Y scale: start from a reasonable floor to show variation
    const yMin = Math.min(...lapTimes) - 2;
    const yMax = Math.max(...lapTimes) + 1;

    const xScale = d3
      .scaleBand<string>()
      .domain(sortedLaps.map((l) => String(l.lap_number)))
      .range([0, chartWidth])
      .padding(0.25);

    const yScale = d3.scaleLinear().domain([yMax, yMin]).range([0, chartHeight]);

    const g = svg
      .append('g')
      .attr('transform', `translate(${MARGIN.left},${MARGIN.top})`);

    // Grid lines
    const yTicks = yScale.ticks(5);
    g.selectAll('.grid-line')
      .data(yTicks)
      .enter()
      .append('line')
      .attr('x1', 0)
      .attr('x2', chartWidth)
      .attr('y1', (d) => yScale(d))
      .attr('y2', (d) => yScale(d))
      .attr('stroke', colors.grid)
      .attr('stroke-dasharray', '2,4');

    // Bars
    g.selectAll('.bar')
      .data(sortedLaps)
      .enter()
      .append('rect')
      .attr('x', (d) => xScale(String(d.lap_number))!)
      .attr('y', (d) => yScale(d.lap_time_s))
      .attr('width', xScale.bandwidth())
      .attr('height', (d) => chartHeight - yScale(d.lap_time_s))
      .attr('fill', (d) => getBarColor(d, bestTime))
      .attr('rx', 2)
      .attr('opacity', 0.85);

    // Best lap reference line
    g.append('line')
      .attr('x1', 0)
      .attr('x2', chartWidth)
      .attr('y1', yScale(bestTime))
      .attr('y2', yScale(bestTime))
      .attr('stroke', colors.motorsport.pb)
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '6,4');

    // Best lap label
    g.append('text')
      .attr('x', chartWidth - 4)
      .attr('y', yScale(bestTime) - 4)
      .attr('text-anchor', 'end')
      .attr('fill', colors.motorsport.pb)
      .attr('font-size', 10)
      .attr('font-family', 'Inter, system-ui, sans-serif')
      .text(`PB ${formatLapTime(bestTime)}`);

    // Average line
    g.append('line')
      .attr('x1', 0)
      .attr('x2', chartWidth)
      .attr('y1', yScale(avgTime))
      .attr('y2', yScale(avgTime))
      .attr('stroke', colors.text.muted)
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', '2,4');

    // Average label
    g.append('text')
      .attr('x', chartWidth - 4)
      .attr('y', yScale(avgTime) - 4)
      .attr('text-anchor', 'end')
      .attr('fill', colors.text.muted)
      .attr('font-size', 10)
      .attr('font-family', 'Inter, system-ui, sans-serif')
      .text('avg');

    // X-axis
    const xAxis = d3.axisBottom(xScale).tickFormat((d) => `L${d}`) as d3.Axis<string>;
    g.append('g')
      .attr('transform', `translate(0,${chartHeight})`)
      .call(xAxis)
      .call((g) => g.select('.domain').attr('stroke', colors.axis))
      .call((g) =>
        g
          .selectAll('.tick text')
          .attr('fill', colors.text.secondary)
          .attr('font-size', 10),
      )
      .call((g) => g.selectAll('.tick line').attr('stroke', colors.axis));

    // Y-axis
    const yAxis = d3
      .axisLeft(yScale)
      .ticks(5)
      .tickFormat((d) => formatLapTime(d as number));
    g.append('g')
      .call(yAxis)
      .call((g) => g.select('.domain').attr('stroke', colors.axis))
      .call((g) =>
        g
          .selectAll('.tick text')
          .attr('fill', colors.text.secondary)
          .attr('font-size', 10)
          .attr('font-family', "'JetBrains Mono', monospace"),
      )
      .call((g) => g.selectAll('.tick line').attr('stroke', colors.axis));
  }, [laps, width]);

  useEffect(() => {
    renderChart();
  }, [renderChart]);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Lap Times
        </h2>
        <div className="h-[220px] animate-pulse rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]" />
      </div>
    );
  }

  if (!laps || laps.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Lap Times
        </h2>
        <div className="flex h-[220px] items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
          <p className="text-sm text-[var(--text-secondary)]">No lap data</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-4">
        <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Lap Times
        </h2>
        <div className="flex items-center gap-3 text-xs text-[var(--text-secondary)]">
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: colors.motorsport.pb }}
            />
            PB
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: colors.motorsport.optimal }}
            />
            Clean
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: colors.text.muted }}
            />
            Unclean
          </span>
        </div>
      </div>
      <div
        ref={containerRef}
        className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-2"
      >
        <svg
          ref={svgRef}
          width={width}
          height={BAR_HEIGHT}
          className="overflow-visible"
        />
      </div>
    </div>
  );
}
