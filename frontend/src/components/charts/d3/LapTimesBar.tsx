"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";
import type { LapSummary } from "@/lib/types";
import { formatLapTime } from "@/lib/formatters";

interface LapTimesBarProps {
  laps: LapSummary[];
  className?: string;
}

export default function LapTimesBar({ laps, className = "" }: LapTimesBarProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (!svgRef.current || !containerRef.current || laps.length === 0) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = Math.max(300, container.clientHeight);
    const margin = { top: 30, right: 20, bottom: 40, left: 60 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const cleanLaps = laps.filter((l) => l.is_clean);
    const data = cleanLaps.length > 0 ? cleanLaps : laps;
    const bestTime = Math.min(...data.map((l) => l.lap_time_s));
    const maxTime = Math.max(...data.map((l) => l.lap_time_s));

    const x = d3
      .scaleBand<string>()
      .domain(data.map((l) => `L${l.lap_number}`))
      .range([0, innerW])
      .padding(0.3);

    const y = d3
      .scaleLinear()
      .domain([bestTime * 0.95, maxTime * 1.05])
      .range([innerH, 0]);

    // Grid lines
    g.append("g")
      .attr("class", "grid")
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
      .call((g) => g.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Y axis
    g.append("g")
      .call(
        d3
          .axisLeft(y)
          .ticks(6)
          .tickFormat((d) => formatLapTime(d as number)),
      )
      .call((g) => g.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Bars
    g.selectAll(".bar")
      .data(data)
      .join("rect")
      .attr("class", "bar")
      .attr("x", (d) => x(`L${d.lap_number}`)!)
      .attr("y", (d) => y(d.lap_time_s))
      .attr("width", x.bandwidth())
      .attr("height", (d) => innerH - y(d.lap_time_s))
      .attr("fill", (d) =>
        d.lap_time_s === bestTime
          ? chartTheme.accentGreen
          : chartTheme.accentBlue,
      )
      .attr("rx", 2);

    // Time labels above bars
    g.selectAll(".label")
      .data(data)
      .join("text")
      .attr("class", "label")
      .attr("x", (d) => x(`L${d.lap_number}`)! + x.bandwidth() / 2)
      .attr("y", (d) => y(d.lap_time_s) - 6)
      .attr("text-anchor", "middle")
      .attr("fill", chartTheme.text)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .text((d) => formatLapTime(d.lap_time_s));
  }, [laps]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (laps.length === 0) {
    return (
      <div className={`flex items-center justify-center py-12 text-sm text-[var(--text-muted)] ${className}`}>
        No lap data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`w-full min-h-[300px] ${className}`}>
      <svg ref={svgRef} className="w-full" />
    </div>
  );
}
