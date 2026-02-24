"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";

interface CornerZone {
  number: number;
  entry: number;
  exit: number;
}

interface IdealLapOverlayProps {
  bestLap: { distance: number[]; speed: number[] };
  idealLap: { distance: number[]; speed: number[] };
  corners?: CornerZone[];
  bestLapNumber: number;
  idealTime: number;
  bestTime: number;
  height?: number;
  className?: string;
}

export default function IdealLapOverlay({
  bestLap,
  idealLap,
  corners = [],
  bestLapNumber,
  idealTime,
  bestTime,
  height: propHeight = 350,
  className = "",
}: IdealLapOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (
      !svgRef.current ||
      !containerRef.current ||
      bestLap.distance.length === 0 ||
      idealLap.distance.length === 0
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
      .attr("id", "ideal-clip")
      .append("rect")
      .attr("width", innerW)
      .attr("height", innerH);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Title
    const delta = bestTime - idealTime;
    const fmtTime = (t: number) => {
      const m = Math.floor(t / 60);
      const s = (t % 60).toFixed(2).padStart(5, "0");
      return `${m}:${s}`;
    };
    svg
      .append("text")
      .attr("x", margin.left + innerW / 2)
      .attr("y", 16)
      .attr("text-anchor", "middle")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSizeLabel)
      .attr("font-family", chartTheme.font)
      .attr("font-weight", "bold")
      .text(
        `Best L${bestLapNumber} (${fmtTime(bestTime)}) vs Ideal (${fmtTime(idealTime)}) | Gap: ${delta.toFixed(2)}s`,
      );

    // Domains
    const allDist = [...bestLap.distance, ...idealLap.distance];
    const allSpeed = [...bestLap.speed, ...idealLap.speed];
    const xDomain: [number, number] = [
      d3.min(allDist) ?? 0,
      d3.max(allDist) ?? 1,
    ];
    const yMax = (d3.max(allSpeed) ?? 100) * 1.05;

    const x = d3.scaleLinear().domain(xDomain).range([0, innerW]);
    const y = d3.scaleLinear().domain([0, yMax]).range([innerH, 0]).nice();

    // Corner zones
    const cornerG = g.append("g").attr("clip-path", "url(#ideal-clip)");
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
      .call(d3.axisLeft(y).ticks(6).tickFormat((d) => `${d} mph`))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    const clipGroup = g.append("g").attr("clip-path", "url(#ideal-clip)");

    // Best lap line (solid)
    const bestData: [number, number][] = bestLap.distance.map((d, i) => [
      d,
      bestLap.speed[i],
    ]);
    const lineBest = d3
      .line<[number, number]>()
      .x((d) => x(d[0]))
      .y((d) => y(d[1]))
      .curve(d3.curveMonotoneX);

    clipGroup
      .append("path")
      .datum(bestData)
      .attr("fill", "none")
      .attr("stroke", chartTheme.accentBlue)
      .attr("stroke-width", 1.5)
      .attr("d", lineBest);

    // Ideal lap line (dashed)
    const idealData: [number, number][] = idealLap.distance.map((d, i) => [
      d,
      idealLap.speed[i],
    ]);

    clipGroup
      .append("path")
      .datum(idealData)
      .attr("fill", "none")
      .attr("stroke", chartTheme.accentGreen)
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "6,3")
      .attr("d", lineBest);

    // Legend
    const legendG = g.append("g").attr("transform", `translate(${innerW - 10}, 0)`);

    const legendItems = [
      { label: `L${bestLapNumber} (Best)`, color: chartTheme.accentBlue, dash: false },
      { label: "Ideal", color: chartTheme.accentGreen, dash: true },
    ];

    legendItems.forEach((item, i) => {
      const lg = legendG.append("g").attr("transform", `translate(0, ${i * 16})`);
      lg.append("line")
        .attr("x1", -40)
        .attr("x2", -10)
        .attr("y1", 0)
        .attr("y2", 0)
        .attr("stroke", item.color)
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", item.dash ? "6,3" : "none");
      lg.append("text")
        .attr("x", -45)
        .attr("y", 4)
        .attr("text-anchor", "end")
        .attr("fill", chartTheme.text)
        .attr("font-size", 10)
        .attr("font-family", chartTheme.font)
        .text(item.label);
    });
  }, [bestLap, idealLap, corners, bestLapNumber, idealTime, bestTime, propHeight]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (bestLap.distance.length === 0 || idealLap.distance.length === 0) {
    return (
      <div
        className={`flex items-center justify-center text-sm text-[var(--text-muted)] ${className}`}
        style={{ height: propHeight }}
      >
        No ideal lap data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`w-full ${className}`} style={{ height: propHeight }}>
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}
