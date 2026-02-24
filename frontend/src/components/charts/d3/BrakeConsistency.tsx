"use client";

import { useRef, useEffect, useCallback, useMemo } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";

interface BrakeConsistencyProps {
  cornerNumber: number;
  laps: { lapNumber: number; brakePointM: number | null }[];
  entryDistanceM: number;
}

export default function BrakeConsistency({
  cornerNumber,
  laps,
  entryDistanceM,
}: BrakeConsistencyProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const validLaps = useMemo(
    () =>
      laps.filter(
        (l): l is { lapNumber: number; brakePointM: number } => l.brakePointM !== null,
      ),
    [laps],
  );

  const render = useCallback(() => {
    if (!svgRef.current || !containerRef.current || validLaps.length < 2) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 200;
    const margin = { top: 20, right: 20, bottom: 35, left: 55 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Compute brake distances relative to entry (meters before entry)
    const brakeDistances = validLaps.map((l) => entryDistanceM - l.brakePointM);
    const mean = d3.mean(brakeDistances) ?? 0;
    const std = d3.deviation(brakeDistances) ?? 0;

    const x = d3
      .scalePoint<number>()
      .domain(validLaps.map((l) => l.lapNumber))
      .range([0, innerW])
      .padding(0.5);

    const yMin = Math.min(d3.min(brakeDistances) ?? 0, mean - std * 1.5);
    const yMax = Math.max(d3.max(brakeDistances) ?? 1, mean + std * 1.5);
    const y = d3.scaleLinear().domain([yMin, yMax]).range([innerH, 0]).nice();

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

    // Std deviation band
    g.append("rect")
      .attr("x", 0)
      .attr("y", y(mean + std))
      .attr("width", innerW)
      .attr("height", Math.max(0, y(mean - std) - y(mean + std)))
      .attr("fill", chartTheme.accentBlue)
      .attr("opacity", 0.1);

    // Mean line
    g.append("line")
      .attr("x1", 0)
      .attr("x2", innerW)
      .attr("y1", y(mean))
      .attr("y2", y(mean))
      .attr("stroke", chartTheme.accentYellow)
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "6,3");

    // Mean label
    g.append("text")
      .attr("x", innerW + 2)
      .attr("y", y(mean) + 3)
      .attr("fill", chartTheme.accentYellow)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .text(`${mean.toFixed(0)}m`);

    // Points
    validLaps.forEach((lap, i) => {
      const bd = brakeDistances[i];
      const distFromMean = Math.abs(bd - mean);
      const color =
        distFromMean <= std
          ? chartTheme.accentGreen
          : distFromMean <= std * 2
            ? chartTheme.accentYellow
            : chartTheme.accentRed;

      g.append("circle")
        .attr("cx", x(lap.lapNumber) ?? 0)
        .attr("cy", y(bd))
        .attr("r", 5)
        .attr("fill", color)
        .attr("stroke", "#000")
        .attr("stroke-width", 1)
        .attr("opacity", 0.8);

      // Lap label below point
      g.append("text")
        .attr("x", x(lap.lapNumber) ?? 0)
        .attr("y", y(bd) - 8)
        .attr("text-anchor", "middle")
        .attr("fill", chartTheme.textSecondary)
        .attr("font-size", 8)
        .attr("font-family", chartTheme.font)
        .text(`L${lap.lapNumber}`);
    });

    // X axis
    g.append("g")
      .attr("transform", `translate(0,${innerH})`)
      .call(
        d3
          .axisBottom(x)
          .tickFormat((d) => `L${d}`),
      )
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Y axis
    g.append("g")
      .call(d3.axisLeft(y).ticks(5).tickFormat((d) => `${d}m`))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Title
    g.append("text")
      .attr("x", innerW / 2)
      .attr("y", -6)
      .attr("text-anchor", "middle")
      .attr("fill", chartTheme.text)
      .attr("font-size", 11)
      .attr("font-family", chartTheme.font)
      .text(`T${cornerNumber} Brake Point Consistency (m before entry)`);
  }, [validLaps, entryDistanceM, cornerNumber]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (validLaps.length < 2) {
    return (
      <div className="py-4 text-center text-xs text-[var(--text-muted)]">
        Not enough brake data for consistency analysis
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full" style={{ height: 200 }}>
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}
