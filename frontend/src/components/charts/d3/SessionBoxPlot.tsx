"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";
import { formatLapTime } from "@/lib/formatters";

interface SessionBoxPlotProps {
  dates: string[];
  lapTimesPerSession: number[][];
  bestLapTrend: number[];
}

function quartiles(data: number[]) {
  const sorted = [...data].sort((a, b) => a - b);
  const q1 = d3.quantile(sorted, 0.25) ?? sorted[0];
  const median = d3.quantile(sorted, 0.5) ?? sorted[0];
  const q3 = d3.quantile(sorted, 0.75) ?? sorted[0];
  const min = sorted[0];
  const max = sorted[sorted.length - 1];
  return { min, q1, median, q3, max };
}

export default function SessionBoxPlot({
  dates,
  lapTimesPerSession,
  bestLapTrend,
}: SessionBoxPlotProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const render = useCallback(() => {
    if (
      !svgRef.current ||
      !containerRef.current ||
      dates.length === 0 ||
      lapTimesPerSession.length === 0
    )
      return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 320;
    const margin = { top: 20, right: 20, bottom: 60, left: 70 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const dateLabels = dates.map((d) =>
      d.length > 10 ? d.slice(0, 10) : d,
    );

    // Compute stats for each session
    const stats = lapTimesPerSession.map((times) => {
      if (times.length === 0)
        return { min: 0, q1: 0, median: 0, q3: 0, max: 0 };
      return quartiles(times);
    });

    const allValues = lapTimesPerSession.flat().filter((v) => v > 0);
    const minVal = d3.min(allValues) ?? 0;
    const maxVal = d3.max(allValues) ?? 120;
    const padding = (maxVal - minVal) * 0.1;

    const x = d3
      .scaleBand<string>()
      .domain(dateLabels)
      .range([0, innerW])
      .padding(0.3);

    const y = d3
      .scaleLinear()
      .domain([minVal - padding, maxVal + padding])
      .range([innerH, 0]);

    // Grid
    g.append("g")
      .selectAll("line")
      .data(y.ticks(6))
      .join("line")
      .attr("x1", 0)
      .attr("x2", innerW)
      .attr("y1", (d) => y(d))
      .attr("y2", (d) => y(d))
      .attr("stroke", chartTheme.grid)
      .attr("stroke-dasharray", "2,2");

    // X axis
    g.append("g")
      .attr("transform", `translate(0,${innerH})`)
      .call(d3.axisBottom(x).tickSize(0))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", 10)
      .attr("font-family", chartTheme.font)
      .attr("transform", "rotate(-30)")
      .attr("text-anchor", "end");

    // Y axis
    g.append("g")
      .call(
        d3
          .axisLeft(y)
          .ticks(6)
          .tickFormat((d) => formatLapTime(d as number)),
      )
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    const boxWidth = Math.min(x.bandwidth(), 50);

    stats.forEach((s, i) => {
      if (s.max === 0) return;
      const cx = (x(dateLabels[i]) ?? 0) + x.bandwidth() / 2;
      const bx = cx - boxWidth / 2;

      // Whisker: min to max
      g.append("line")
        .attr("x1", cx)
        .attr("x2", cx)
        .attr("y1", y(s.min))
        .attr("y2", y(s.max))
        .attr("stroke", chartTheme.accentBlue)
        .attr("stroke-width", 1);

      // Whisker caps
      g.append("line")
        .attr("x1", cx - boxWidth / 4)
        .attr("x2", cx + boxWidth / 4)
        .attr("y1", y(s.min))
        .attr("y2", y(s.min))
        .attr("stroke", chartTheme.accentBlue)
        .attr("stroke-width", 1);

      g.append("line")
        .attr("x1", cx - boxWidth / 4)
        .attr("x2", cx + boxWidth / 4)
        .attr("y1", y(s.max))
        .attr("y2", y(s.max))
        .attr("stroke", chartTheme.accentBlue)
        .attr("stroke-width", 1);

      // Box: Q1 to Q3
      g.append("rect")
        .attr("x", bx)
        .attr("y", y(s.q3))
        .attr("width", boxWidth)
        .attr("height", Math.max(1, y(s.q1) - y(s.q3)))
        .attr("fill", `${chartTheme.accentBlue}30`)
        .attr("stroke", chartTheme.accentBlue)
        .attr("stroke-width", 1.5)
        .attr("rx", 2);

      // Median line
      g.append("line")
        .attr("x1", bx)
        .attr("x2", bx + boxWidth)
        .attr("y1", y(s.median))
        .attr("y2", y(s.median))
        .attr("stroke", chartTheme.text)
        .attr("stroke-width", 2);

      // Best lap diamond
      if (bestLapTrend[i] > 0) {
        const diamond = d3.symbol().type(d3.symbolDiamond).size(120);
        g.append("path")
          .attr("d", diamond)
          .attr(
            "transform",
            `translate(${cx}, ${y(bestLapTrend[i])})`,
          )
          .attr("fill", chartTheme.accentGreen)
          .attr("stroke", "#fff")
          .attr("stroke-width", 1);
      }
    });

    // Tooltip
    const tooltip = d3.select(tooltipRef.current);

    g.selectAll(".hover-zone-box")
      .data(dateLabels)
      .join("rect")
      .attr("class", "hover-zone-box")
      .attr("x", (d) => x(d) ?? 0)
      .attr("y", 0)
      .attr("width", x.bandwidth())
      .attr("height", innerH)
      .attr("fill", "transparent")
      .attr("cursor", "crosshair")
      .on("mousemove", (event, d) => {
        const idx = dateLabels.indexOf(d);
        if (idx < 0) return;
        const s = stats[idx];
        tooltip
          .style("display", "block")
          .style("left", `${event.offsetX + 12}px`)
          .style("top", `${event.offsetY - 10}px`).html(`
            <div class="text-xs font-medium mb-1">${dates[idx]}</div>
            <div class="text-xs">Best: <span style="color:${chartTheme.accentGreen}">${formatLapTime(bestLapTrend[idx])}</span></div>
            <div class="text-xs">Median: ${formatLapTime(s.median)}</div>
            <div class="text-xs">Q1-Q3: ${formatLapTime(s.q1)} - ${formatLapTime(s.q3)}</div>
            <div class="text-xs text-[var(--text-muted)]">${lapTimesPerSession[idx].length} laps</div>
          `);
      })
      .on("mouseleave", () => {
        tooltip.style("display", "none");
      });

    // Legend
    const legend = g.append("g").attr("transform", `translate(0, -8)`);

    const diamondSymbol = d3.symbol().type(d3.symbolDiamond).size(60);
    legend
      .append("path")
      .attr("d", diamondSymbol)
      .attr("transform", "translate(6, 0)")
      .attr("fill", chartTheme.accentGreen);

    legend
      .append("text")
      .attr("x", 16)
      .attr("y", 4)
      .attr("fill", chartTheme.text)
      .attr("font-size", 10)
      .attr("font-family", chartTheme.font)
      .text("Best Lap");
  }, [dates, lapTimesPerSession, bestLapTrend]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (dates.length === 0 || lapTimesPerSession.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-[var(--text-muted)]">
        No lap time distribution data
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative w-full">
      <svg ref={svgRef} className="w-full" />
      <div
        ref={tooltipRef}
        className="pointer-events-none absolute hidden rounded border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 shadow-lg"
        style={{ zIndex: 10 }}
      />
    </div>
  );
}
