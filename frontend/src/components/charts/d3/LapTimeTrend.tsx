"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";
import { formatLapTime } from "@/lib/formatters";

interface LapTimeTrendProps {
  dates: string[];
  bestLapTrend: number[];
  top3AvgTrend: number[];
  theoreticalTrend: number[];
}

export default function LapTimeTrend({
  dates,
  bestLapTrend,
  top3AvgTrend,
  theoreticalTrend,
}: LapTimeTrendProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const render = useCallback(() => {
    if (!svgRef.current || !containerRef.current || dates.length === 0) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 400;
    const margin = { top: 30, right: 30, bottom: 60, left: 70 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Short date labels for x-axis
    const dateLabels = dates.map((d) => {
      try {
        const parts = d.split(/[/,\s-]/);
        if (parts.length >= 2) {
          return d.length > 10 ? d.slice(0, 10) : d;
        }
        return d;
      } catch {
        return d;
      }
    });

    const allValues = [
      ...bestLapTrend,
      ...top3AvgTrend,
      ...theoreticalTrend,
    ].filter((v) => v > 0);

    // Use median ± 3×MAD to exclude extreme outliers (robust for small datasets)
    const sorted = [...allValues].sort((a, b) => a - b);
    const med = d3.median(sorted) ?? sorted[Math.floor(sorted.length / 2)];
    const absDevs = sorted.map((v) => Math.abs(v - med));
    const mad = d3.median(absDevs.sort((a, b) => a - b)) ?? 0;
    const lowerFence = med - 3 * Math.max(mad, 1);
    const upperFence = med + 3 * Math.max(mad, 1);
    const trimmed = allValues.filter((v) => v >= lowerFence && v <= upperFence);
    const minVal = d3.min(trimmed.length > 0 ? trimmed : allValues) ?? 0;
    const maxVal = d3.max(trimmed.length > 0 ? trimmed : allValues) ?? 120;
    const padding = (maxVal - minVal) * 0.1 || 2;

    const x = d3
      .scalePoint<string>()
      .domain(dateLabels)
      .range([0, innerW])
      .padding(0.3);

    const y = d3
      .scaleLinear()
      .domain([minVal - padding, maxVal + padding])
      .range([innerH, 0]);

    // Grid lines
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

    // Line generator
    const line = (data: number[]) =>
      d3
        .line<number>()
        .x((_, i) => x(dateLabels[i]) ?? 0)
        .y((d) => y(d))
        .defined((d) => d > 0)(data);

    // Theoretical best (dotted green) - draw first so it's behind
    g.append("path")
      .attr("d", line(theoreticalTrend))
      .attr("fill", "none")
      .attr("stroke", chartTheme.accentYellow)
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "4,4");

    // Top-3 avg (dashed)
    g.append("path")
      .attr("d", line(top3AvgTrend))
      .attr("fill", "none")
      .attr("stroke", "#bc8cff")
      .attr("stroke-width", 2)
      .attr("stroke-dasharray", "6,3");

    // Best lap (solid primary)
    g.append("path")
      .attr("d", line(bestLapTrend))
      .attr("fill", "none")
      .attr("stroke", chartTheme.accentGreen)
      .attr("stroke-width", 2.5);

    // Data points for best lap
    g.selectAll(".dot-best")
      .data(bestLapTrend)
      .join("circle")
      .attr("class", "dot-best")
      .attr("cx", (_, i) => x(dateLabels[i]) ?? 0)
      .attr("cy", (d) => y(d))
      .attr("r", 5)
      .attr("fill", chartTheme.accentGreen)
      .attr("stroke", chartTheme.bg)
      .attr("stroke-width", 2);

    // Data points for top-3 avg
    g.selectAll(".dot-top3")
      .data(top3AvgTrend)
      .join("circle")
      .attr("class", "dot-top3")
      .attr("cx", (_, i) => x(dateLabels[i]) ?? 0)
      .attr("cy", (d) => y(d))
      .attr("r", 4)
      .attr("fill", "#bc8cff")
      .attr("stroke", chartTheme.bg)
      .attr("stroke-width", 2);

    // Tooltip interaction
    const tooltip = d3.select(tooltipRef.current);

    // Invisible overlay rects for hover
    g.selectAll(".hover-zone")
      .data(dateLabels)
      .join("rect")
      .attr("class", "hover-zone")
      .attr("x", (d) => (x(d) ?? 0) - innerW / dateLabels.length / 2)
      .attr("y", 0)
      .attr("width", innerW / dateLabels.length)
      .attr("height", innerH)
      .attr("fill", "transparent")
      .attr("cursor", "crosshair")
      .on("mousemove", (event, d) => {
        const idx = dateLabels.indexOf(d);
        if (idx < 0) return;
        const [px, py] = d3.pointer(event, container);
        tooltip
          .style("display", "block")
          .style("left", `${px + 12}px`)
          .style("top", `${py - 10}px`).html(`
            <div class="text-xs font-medium mb-1">${dates[idx]}</div>
            <div class="text-xs" style="color:${chartTheme.accentGreen}">Best: ${formatLapTime(bestLapTrend[idx])}</div>
            <div class="text-xs" style="color:#bc8cff">Top-3 Avg: ${formatLapTime(top3AvgTrend[idx])}</div>
            <div class="text-xs" style="color:${chartTheme.accentYellow}">Theoretical: ${formatLapTime(theoreticalTrend[idx])}</div>
          `);
      })
      .on("mouseleave", () => {
        tooltip.style("display", "none");
      });

    // Legend
    const legendData = [
      { label: "Best Lap", color: chartTheme.accentGreen, dash: "" },
      { label: "Top-3 Avg", color: "#bc8cff", dash: "6,3" },
      { label: "Theoretical", color: chartTheme.accentYellow, dash: "4,4" },
    ];

    const legend = g
      .append("g")
      .attr("transform", `translate(0, -12)`);

    legendData.forEach((d, i) => {
      const lg = legend
        .append("g")
        .attr("transform", `translate(${i * 130}, 0)`);

      lg.append("line")
        .attr("x1", 0)
        .attr("x2", 20)
        .attr("y1", 0)
        .attr("y2", 0)
        .attr("stroke", d.color)
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", d.dash);

      lg.append("text")
        .attr("x", 24)
        .attr("y", 4)
        .attr("fill", chartTheme.text)
        .attr("font-size", 10)
        .attr("font-family", chartTheme.font)
        .text(d.label);
    });
  }, [dates, bestLapTrend, top3AvgTrend, theoreticalTrend]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (dates.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-[var(--text-muted)]">
        No trend data available
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
