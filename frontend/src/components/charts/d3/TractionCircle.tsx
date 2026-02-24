"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";
import type { LapData } from "@/lib/types";

interface TractionCircleProps {
  lapData: LapData | null;
  className?: string;
}

export default function TractionCircle({ lapData, className = "" }: TractionCircleProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (!svgRef.current || !containerRef.current || !lapData) return;

    const container = containerRef.current;
    const size = Math.min(container.clientWidth, 400);
    const margin = 40;
    const radius = (size - margin * 2) / 2;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", size).attr("height", size);

    const g = svg
      .append("g")
      .attr("transform", `translate(${size / 2},${size / 2})`);

    const { lateral_g, longitudinal_g } = lapData;
    if (lateral_g.length === 0) return;

    // Determine grip limit from data
    const allG = [
      ...lateral_g.map(Math.abs),
      ...longitudinal_g.map(Math.abs),
    ];
    const maxG = Math.max(...allG, 0.5);
    const gripRadius = Math.ceil(maxG * 10) / 10; // Round up to nearest 0.1

    const scale = d3.scaleLinear().domain([0, gripRadius]).range([0, radius]);

    // Grid circles
    const rings = [0.25, 0.5, 0.75, 1.0].map((f) => f * gripRadius);
    rings.forEach((r) => {
      g.append("circle")
        .attr("r", scale(r))
        .attr("fill", "none")
        .attr("stroke", chartTheme.grid)
        .attr("stroke-dasharray", "2,2");

      g.append("text")
        .attr("x", 4)
        .attr("y", -scale(r) - 2)
        .attr("fill", chartTheme.textSecondary)
        .attr("font-size", 8)
        .attr("font-family", chartTheme.font)
        .text(`${r.toFixed(2)}g`);
    });

    // Grip circle boundary
    g.append("circle")
      .attr("r", scale(gripRadius))
      .attr("fill", "none")
      .attr("stroke", chartTheme.accentYellow)
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "4,3");

    // Axes
    g.append("line")
      .attr("x1", -radius)
      .attr("x2", radius)
      .attr("y1", 0)
      .attr("y2", 0)
      .attr("stroke", chartTheme.grid);

    g.append("line")
      .attr("x1", 0)
      .attr("x2", 0)
      .attr("y1", -radius)
      .attr("y2", radius)
      .attr("stroke", chartTheme.grid);

    // Axis labels
    g.append("text")
      .attr("x", radius + 5)
      .attr("y", 4)
      .attr("fill", chartTheme.textSecondary)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .text("Lat +");

    g.append("text")
      .attr("x", -radius - 5)
      .attr("y", 4)
      .attr("text-anchor", "end")
      .attr("fill", chartTheme.textSecondary)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .text("Lat -");

    g.append("text")
      .attr("x", 0)
      .attr("y", -radius - 8)
      .attr("text-anchor", "middle")
      .attr("fill", chartTheme.textSecondary)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .text("Accel");

    g.append("text")
      .attr("x", 0)
      .attr("y", radius + 15)
      .attr("text-anchor", "middle")
      .attr("fill", chartTheme.textSecondary)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .text("Brake");

    // Data points
    g.selectAll(".point")
      .data(lateral_g.map((lat, i) => ({ lat, lon: longitudinal_g[i] })))
      .join("circle")
      .attr("class", "point")
      .attr("cx", (d) => scale(d.lat))
      .attr("cy", (d) => -scale(d.lon)) // Negative because braking is down
      .attr("r", 1.5)
      .attr("fill", chartTheme.accentBlue)
      .attr("opacity", 0.3);
  }, [lapData]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (!lapData || lapData.lateral_g.length === 0) {
    return (
      <div className={`flex items-center justify-center py-12 text-sm text-[var(--text-muted)] ${className}`}>
        No g-force data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`w-full flex justify-center ${className}`}>
      <svg ref={svgRef} />
    </div>
  );
}
