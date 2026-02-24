"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";

interface CornerTrendGridProps {
  dates: string[];
  cornerMinSpeedTrends: Record<string, (number | null)[]>;
}

export default function CornerTrendGrid({
  dates,
  cornerMinSpeedTrends,
}: CornerTrendGridProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (!svgRef.current || !containerRef.current || dates.length === 0) return;

    const cornerKeys = Object.keys(cornerMinSpeedTrends).sort(
      (a, b) => parseInt(a) - parseInt(b),
    );
    if (cornerKeys.length === 0) return;

    const container = containerRef.current;
    const totalWidth = container.clientWidth;

    const cellW = 200;
    const cellH = 130;
    const cellPadding = 12;
    const cols = Math.max(1, Math.floor(totalWidth / (cellW + cellPadding)));
    const rows = Math.ceil(cornerKeys.length / cols);
    const svgWidth = totalWidth;
    const svgHeight = rows * (cellH + cellPadding) + 10;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", svgWidth).attr("height", svgHeight);

    const margin = { top: 22, right: 8, bottom: 18, left: 32 };

    cornerKeys.forEach((cn, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      const offsetX = col * (cellW + cellPadding) + cellPadding / 2;
      const offsetY = row * (cellH + cellPadding);

      const g = svg
        .append("g")
        .attr("transform", `translate(${offsetX},${offsetY})`);

      const innerW = cellW - margin.left - margin.right;
      const innerH = cellH - margin.top - margin.bottom;

      // Background card
      g.append("rect")
        .attr("width", cellW)
        .attr("height", cellH)
        .attr("fill", chartTheme.bgCard)
        .attr("stroke", chartTheme.border)
        .attr("stroke-width", 1)
        .attr("rx", 4);

      // Title
      g.append("text")
        .attr("x", cellW / 2)
        .attr("y", 14)
        .attr("text-anchor", "middle")
        .attr("fill", chartTheme.text)
        .attr("font-size", 11)
        .attr("font-family", chartTheme.font)
        .attr("font-weight", "bold")
        .text(`T${cn}`);

      const inner = g
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

      const speeds = cornerMinSpeedTrends[cn];
      const validSpeeds = speeds
        .map((v, i) => (v !== null ? { v, i } : null))
        .filter((d): d is { v: number; i: number } => d !== null);

      if (validSpeeds.length === 0) return;

      const minS = d3.min(validSpeeds, (d) => d.v) ?? 0;
      const maxS = d3.max(validSpeeds, (d) => d.v) ?? 100;
      const pad = Math.max((maxS - minS) * 0.15, 1);

      const x = d3
        .scaleLinear()
        .domain([0, dates.length - 1])
        .range([0, innerW]);

      const y = d3
        .scaleLinear()
        .domain([minS - pad, maxS + pad])
        .range([innerH, 0]);

      // Area fill
      const area = d3
        .area<{ v: number; i: number }>()
        .x((d) => x(d.i))
        .y0(innerH)
        .y1((d) => y(d.v));

      inner
        .append("path")
        .datum(validSpeeds)
        .attr("d", area)
        .attr("fill", `${chartTheme.accentGreen}15`);

      // Line
      const line = d3
        .line<{ v: number; i: number }>()
        .x((d) => x(d.i))
        .y((d) => y(d.v));

      inner
        .append("path")
        .datum(validSpeeds)
        .attr("d", line)
        .attr("fill", "none")
        .attr("stroke", chartTheme.accentGreen)
        .attr("stroke-width", 2);

      // Dots
      inner
        .selectAll(".dot")
        .data(validSpeeds)
        .join("circle")
        .attr("cx", (d) => x(d.i))
        .attr("cy", (d) => y(d.v))
        .attr("r", 3)
        .attr("fill", chartTheme.accentGreen)
        .attr("stroke", chartTheme.bgCard)
        .attr("stroke-width", 1);

      // Y axis labels (just min/max)
      inner
        .append("text")
        .attr("x", -4)
        .attr("y", y(maxS + pad / 2))
        .attr("text-anchor", "end")
        .attr("fill", chartTheme.textSecondary)
        .attr("font-size", 8)
        .attr("font-family", chartTheme.font)
        .text(`${(maxS + pad / 2).toFixed(0)}`);

      inner
        .append("text")
        .attr("x", -4)
        .attr("y", innerH)
        .attr("text-anchor", "end")
        .attr("fill", chartTheme.textSecondary)
        .attr("font-size", 8)
        .attr("font-family", chartTheme.font)
        .text(`${(minS - pad).toFixed(0)}`);

      // Latest value label
      const latest = validSpeeds[validSpeeds.length - 1];
      inner
        .append("text")
        .attr("x", x(latest.i) + 4)
        .attr("y", y(latest.v) - 4)
        .attr("fill", chartTheme.accentGreen)
        .attr("font-size", 9)
        .attr("font-family", chartTheme.font)
        .attr("font-weight", "bold")
        .text(`${latest.v.toFixed(1)}`);
    });
  }, [dates, cornerMinSpeedTrends]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  const cornerKeys = Object.keys(cornerMinSpeedTrends);

  if (dates.length === 0 || cornerKeys.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-[var(--text-muted)]">
        No corner trend data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full">
      <svg ref={svgRef} className="w-full" />
    </div>
  );
}
