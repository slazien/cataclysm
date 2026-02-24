"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";

interface ConsistencyTrendProps {
  dates: string[];
  scores: number[];
}

export default function ConsistencyTrend({
  dates,
  scores,
}: ConsistencyTrendProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const render = useCallback(() => {
    if (!svgRef.current || !containerRef.current || dates.length === 0) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 320;
    const margin = { top: 20, right: 60, bottom: 60, left: 50 };
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

    const x = d3
      .scalePoint<string>()
      .domain(dateLabels)
      .range([0, innerW])
      .padding(0.3);

    const y = d3.scaleLinear().domain([0, 105]).range([innerH, 0]);

    // Background score bands
    // Green band: 80-100 (Great)
    g.append("rect")
      .attr("x", 0)
      .attr("y", y(100))
      .attr("width", innerW)
      .attr("height", y(80) - y(100))
      .attr("fill", "rgba(63, 185, 80, 0.08)");

    // Orange band: 50-80 (OK)
    g.append("rect")
      .attr("x", 0)
      .attr("y", y(80))
      .attr("width", innerW)
      .attr("height", y(50) - y(80))
      .attr("fill", "rgba(210, 153, 34, 0.08)");

    // Red band: 0-50 (Needs work)
    g.append("rect")
      .attr("x", 0)
      .attr("y", y(50))
      .attr("width", innerW)
      .attr("height", y(0) - y(50))
      .attr("fill", "rgba(248, 81, 73, 0.08)");

    // Band labels on right
    g.append("text")
      .attr("x", innerW + 6)
      .attr("y", y(90))
      .attr("fill", "rgba(63, 185, 80, 0.6)")
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .attr("alignment-baseline", "middle")
      .text("Great");

    g.append("text")
      .attr("x", innerW + 6)
      .attr("y", y(65))
      .attr("fill", "rgba(210, 153, 34, 0.6)")
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .attr("alignment-baseline", "middle")
      .text("OK");

    g.append("text")
      .attr("x", innerW + 6)
      .attr("y", y(25))
      .attr("fill", "rgba(248, 81, 73, 0.6)")
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .attr("alignment-baseline", "middle")
      .text("Needs Work");

    // Grid lines
    g.append("g")
      .selectAll("line")
      .data(y.ticks(5))
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
      .call(d3.axisLeft(y).ticks(5))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Area fill under line
    const area = d3
      .area<number>()
      .x((_, i) => x(dateLabels[i]) ?? 0)
      .y0(innerH)
      .y1((d) => y(d));

    g.append("path")
      .datum(scores)
      .attr("d", area)
      .attr("fill", `${chartTheme.accentBlue}15`);

    // Line
    const line = d3
      .line<number>()
      .x((_, i) => x(dateLabels[i]) ?? 0)
      .y((d) => y(d));

    g.append("path")
      .datum(scores)
      .attr("d", line)
      .attr("fill", "none")
      .attr("stroke", chartTheme.accentBlue)
      .attr("stroke-width", 2.5);

    // Dots
    g.selectAll(".dot")
      .data(scores)
      .join("circle")
      .attr("class", "dot")
      .attr("cx", (_, i) => x(dateLabels[i]) ?? 0)
      .attr("cy", (d) => y(d))
      .attr("r", 5)
      .attr("fill", (d) =>
        d >= 80
          ? chartTheme.accentGreen
          : d >= 50
            ? chartTheme.accentYellow
            : chartTheme.accentRed,
      )
      .attr("stroke", chartTheme.bg)
      .attr("stroke-width", 2);

    // Tooltip
    const tooltip = d3.select(tooltipRef.current);

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
        const score = scores[idx];
        const rating =
          score >= 80 ? "Great" : score >= 50 ? "OK" : "Needs Work";
        tooltip
          .style("display", "block")
          .style("left", `${event.offsetX + 12}px`)
          .style("top", `${event.offsetY - 10}px`).html(`
            <div class="text-xs font-medium mb-1">${dates[idx]}</div>
            <div class="text-xs">Score: <span class="font-bold">${score.toFixed(0)}/100</span></div>
            <div class="text-xs text-[var(--text-muted)]">${rating}</div>
          `);
      })
      .on("mouseleave", () => {
        tooltip.style("display", "none");
      });
  }, [dates, scores]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (dates.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-[var(--text-muted)]">
        No consistency data available
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
