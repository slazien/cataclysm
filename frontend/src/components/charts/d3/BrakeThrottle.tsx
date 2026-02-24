"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";
import { lapColorScale } from "./scales";

interface LapGTrace {
  lapNumber: number;
  distance: number[];
  longitudinalG: number[];
}

interface CornerZone {
  number: number;
  entry: number;
  exit: number;
}

interface BrakeThrottleProps {
  laps: LapGTrace[];
  corners?: CornerZone[];
  height?: number;
  className?: string;
}

export default function BrakeThrottle({
  laps,
  corners = [],
  height: propHeight = 300,
  className = "",
}: BrakeThrottleProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (!svgRef.current || !containerRef.current || laps.length === 0) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = propHeight;
    const margin = { top: 30, right: 20, bottom: 35, left: 55 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    // Clip path
    const defs = svg.append("defs");
    defs
      .append("clipPath")
      .attr("id", "brake-clip")
      .append("rect")
      .attr("width", innerW)
      .attr("height", innerH);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Title
    svg
      .append("text")
      .attr("x", margin.left + innerW / 2)
      .attr("y", 16)
      .attr("text-anchor", "middle")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSizeLabel)
      .attr("font-family", chartTheme.font)
      .attr("font-weight", "bold")
      .text("Brake / Throttle Trace (Longitudinal G)");

    // Domains
    const allDist = laps.flatMap((l) => l.distance);
    const allG = laps.flatMap((l) => l.longitudinalG);
    const xDomain: [number, number] = [
      d3.min(allDist) ?? 0,
      d3.max(allDist) ?? 1,
    ];
    const maxAbsG = d3.max(allG.map(Math.abs)) ?? 1;
    const gPad = maxAbsG * 1.15;

    const x = d3.scaleLinear().domain(xDomain).range([0, innerW]);
    const y = d3.scaleLinear().domain([-gPad, gPad]).range([innerH, 0]).nice();

    const colorScale = lapColorScale(laps.map((l) => l.lapNumber));

    // Corner zones
    const cornerG = g.append("g").attr("clip-path", "url(#brake-clip)");
    corners.forEach((c) => {
      const cx1 = x(c.entry);
      const cx2 = x(c.exit);
      cornerG
        .append("rect")
        .attr("x", cx1)
        .attr("y", 0)
        .attr("width", Math.max(0, cx2 - cx1))
        .attr("height", innerH)
        .attr("fill", chartTheme.grid)
        .attr("opacity", 0.2);

      cornerG
        .append("text")
        .attr("x", (cx1 + cx2) / 2)
        .attr("y", -4)
        .attr("text-anchor", "middle")
        .attr("fill", chartTheme.textSecondary)
        .attr("font-size", 9)
        .attr("font-family", chartTheme.font)
        .text(`T${c.number}`);
    });

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
      .call(d3.axisBottom(x).ticks(8).tickFormat((d) => `${d}m`))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Y axis
    g.append("g")
      .call(d3.axisLeft(y).ticks(6).tickFormat((d) => `${(d as number).toFixed(1)}g`))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Zero line
    g.append("line")
      .attr("x1", 0)
      .attr("x2", innerW)
      .attr("y1", y(0))
      .attr("y2", y(0))
      .attr("stroke", chartTheme.text)
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "4,3");

    // G traces with area fills
    const clipGroup = g.append("g").attr("clip-path", "url(#brake-clip)");

    laps.forEach((lap) => {
      const pairedData: [number, number][] = lap.distance.map((d, i) => [
        d,
        lap.longitudinalG[i],
      ]);
      const color = colorScale(lap.lapNumber);

      // Throttle area (above zero)
      const areaAbove = d3
        .area<[number, number]>()
        .x((d) => x(d[0]))
        .y0(y(0))
        .y1((d) => y(Math.max(0, d[1])))
        .curve(d3.curveMonotoneX);

      clipGroup
        .append("path")
        .datum(pairedData)
        .attr("fill", color)
        .attr("opacity", 0.1)
        .attr("d", areaAbove);

      // Brake area (below zero)
      const areaBelow = d3
        .area<[number, number]>()
        .x((d) => x(d[0]))
        .y0(y(0))
        .y1((d) => y(Math.min(0, d[1])))
        .curve(d3.curveMonotoneX);

      clipGroup
        .append("path")
        .datum(pairedData)
        .attr("fill", color)
        .attr("opacity", 0.1)
        .attr("d", areaBelow);

      // Line trace
      const line = d3
        .line<[number, number]>()
        .x((d) => x(d[0]))
        .y((d) => y(d[1]))
        .curve(d3.curveMonotoneX);

      clipGroup
        .append("path")
        .datum(pairedData)
        .attr("fill", "none")
        .attr("stroke", color)
        .attr("stroke-width", 1.3)
        .attr("d", line);
    });

    // Legend
    const legendG = g
      .append("g")
      .attr("transform", `translate(${innerW - 10}, 0)`);

    laps.forEach((lap, i) => {
      const lg = legendG
        .append("g")
        .attr("transform", `translate(0, ${i * 16})`);
      lg.append("line")
        .attr("x1", -30)
        .attr("x2", -10)
        .attr("y1", 0)
        .attr("y2", 0)
        .attr("stroke", colorScale(lap.lapNumber))
        .attr("stroke-width", 2);
      lg.append("text")
        .attr("x", -5)
        .attr("y", 4)
        .attr("text-anchor", "end")
        .attr("fill", chartTheme.text)
        .attr("font-size", 10)
        .attr("font-family", chartTheme.font)
        .text(`L${lap.lapNumber}`);
    });

    // Y axis labels
    g.append("text")
      .attr("x", -10)
      .attr("y", y(gPad * 0.5))
      .attr("text-anchor", "end")
      .attr("fill", chartTheme.accentGreen)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .attr("opacity", 0.6)
      .text("Throttle");

    g.append("text")
      .attr("x", -10)
      .attr("y", y(-gPad * 0.5))
      .attr("text-anchor", "end")
      .attr("fill", chartTheme.accentRed)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .attr("opacity", 0.6)
      .text("Brake");
  }, [laps, corners, propHeight]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (laps.length === 0) {
    return (
      <div
        className={`flex items-center justify-center text-sm text-[var(--text-muted)] ${className}`}
        style={{ height: propHeight }}
      >
        No G-force data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`w-full ${className}`} style={{ height: propHeight }}>
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}
