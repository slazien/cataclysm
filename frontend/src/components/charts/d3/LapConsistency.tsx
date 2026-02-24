"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";
import type { LapConsistency as LapConsistencyData } from "@/lib/types";

interface LapConsistencyProps {
  data: LapConsistencyData | null;
  className?: string;
}

export default function LapConsistency({ data, className = "" }: LapConsistencyProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (!svgRef.current || !containerRef.current || !data) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = Math.max(250, container.clientHeight);
    const margin = { top: 20, right: 20, bottom: 40, left: 60 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const deltas = data.consecutive_deltas_s;
    if (deltas.length === 0) return;

    // X: transition labels "L1-L2", "L2-L3", etc.
    const labels = deltas.map((_, i) => {
      const n = data.lap_numbers;
      return `L${n[i]}-L${n[i + 1]}`;
    });

    const x = d3
      .scaleBand<string>()
      .domain(labels)
      .range([0, innerW])
      .padding(0.2);

    const maxAbs = Math.max(...deltas.map(Math.abs), 0.5);
    const y = d3
      .scaleLinear()
      .domain([-maxAbs * 1.1, maxAbs * 1.1])
      .range([innerH, 0]);

    // Zero line
    g.append("line")
      .attr("x1", 0)
      .attr("x2", innerW)
      .attr("y1", y(0))
      .attr("y2", y(0))
      .attr("stroke", chartTheme.textSecondary)
      .attr("stroke-dasharray", "4,4");

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
      .call((g) => g.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .attr("transform", "rotate(-30)")
      .attr("text-anchor", "end");

    // Y axis
    g.append("g")
      .call(
        d3
          .axisLeft(y)
          .ticks(6)
          .tickFormat((d) => {
            const v = d as number;
            return `${v > 0 ? "+" : ""}${v.toFixed(2)}s`;
          }),
      )
      .call((g) => g.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Bars
    g.selectAll(".bar")
      .data(deltas)
      .join("rect")
      .attr("class", "bar")
      .attr("x", (_, i) => x(labels[i])!)
      .attr("y", (d) => (d >= 0 ? y(d) : y(0)))
      .attr("width", x.bandwidth())
      .attr("height", (d) => Math.abs(y(d) - y(0)))
      .attr("fill", (d) =>
        d >= 0 ? chartTheme.accentRed : chartTheme.accentGreen,
      )
      .attr("rx", 2);
  }, [data]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (!data || data.consecutive_deltas_s.length === 0) {
    return (
      <div className={`flex items-center justify-center py-12 text-sm text-[var(--text-muted)] ${className}`}>
        No consistency data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`w-full min-h-[250px] ${className}`}>
      <svg ref={svgRef} className="w-full" />
    </div>
  );
}
