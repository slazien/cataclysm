"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";

interface CornerZone {
  number: number;
  entry: number;
  exit: number;
}

interface IdealLapDeltaProps {
  distance: number[];
  delta: number[];
  bestLapNumber: number;
  corners?: CornerZone[];
  height?: number;
  className?: string;
}

export default function IdealLapDelta({
  distance,
  delta,
  bestLapNumber,
  corners = [],
  height: propHeight = 250,
  className = "",
}: IdealLapDeltaProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (
      !svgRef.current ||
      !containerRef.current ||
      distance.length === 0 ||
      delta.length === 0
    )
      return;

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
      .attr("id", "ideal-delta-clip")
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
      .text(`Delta: Ideal vs L${bestLapNumber}`);

    // Scales
    const xDomain: [number, number] = [
      d3.min(distance) ?? 0,
      d3.max(distance) ?? 1,
    ];
    const maxAbsDelta = d3.max(delta.map(Math.abs)) ?? 0.5;
    const yPad = maxAbsDelta * 1.15;

    const x = d3.scaleLinear().domain(xDomain).range([0, innerW]);
    const y = d3.scaleLinear().domain([-yPad, yPad]).range([innerH, 0]).nice();

    // Corner zones
    const cornerG = g.append("g").attr("clip-path", "url(#ideal-delta-clip)");
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

    // Grid
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

    // Axes
    g.append("g")
      .attr("transform", `translate(0,${innerH})`)
      .call(d3.axisBottom(x).ticks(8).tickFormat((d) => `${d}m`))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    g.append("g")
      .call(
        d3.axisLeft(y).ticks(5).tickFormat((d) => `${(d as number).toFixed(2)}s`),
      )
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

    // Build paired data
    const pairedData: [number, number][] = distance.map((d, i) => [
      d,
      delta[i],
    ]);

    const clipGroup = g
      .append("g")
      .attr("clip-path", "url(#ideal-delta-clip)");

    // Area fills
    const areaAbove = d3
      .area<[number, number]>()
      .x((d) => x(d[0]))
      .y0(y(0))
      .y1((d) => y(Math.max(0, d[1])))
      .curve(d3.curveMonotoneX);

    clipGroup
      .append("path")
      .datum(pairedData)
      .attr("fill", chartTheme.accentRed)
      .attr("opacity", 0.35)
      .attr("d", areaAbove);

    const areaBelow = d3
      .area<[number, number]>()
      .x((d) => x(d[0]))
      .y0(y(0))
      .y1((d) => y(Math.min(0, d[1])))
      .curve(d3.curveMonotoneX);

    clipGroup
      .append("path")
      .datum(pairedData)
      .attr("fill", chartTheme.accentGreen)
      .attr("opacity", 0.35)
      .attr("d", areaBelow);

    // Delta line
    const line = d3
      .line<[number, number]>()
      .x((d) => x(d[0]))
      .y((d) => y(d[1]))
      .curve(d3.curveMonotoneX);

    clipGroup
      .append("path")
      .datum(pairedData)
      .attr("fill", "none")
      .attr("stroke", chartTheme.text)
      .attr("stroke-width", 1.2)
      .attr("d", line);
  }, [distance, delta, bestLapNumber, corners, propHeight]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (distance.length === 0) {
    return (
      <div
        className={`flex items-center justify-center text-sm text-[var(--text-muted)] ${className}`}
        style={{ height: propHeight }}
      >
        No delta data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`w-full ${className}`} style={{ height: propHeight }}>
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}
