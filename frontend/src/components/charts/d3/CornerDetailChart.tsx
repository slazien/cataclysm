"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";
import { lapColorScale } from "./scales";
import type { Corner } from "@/lib/types";

interface LapSlice {
  lapNumber: number;
  distance: number[];
  speed: number[];
  longitudinalG: number[];
}

interface CornerDetailProps {
  cornerNumber: number;
  laps: LapSlice[];
  corner: Corner;
  entryBuffer?: number;
  exitBuffer?: number;
  height?: number;
}

export default function CornerDetailChart({
  laps,
  corner,
  entryBuffer = 50,
  exitBuffer = 50,
  height: propHeight = 400,
}: CornerDetailProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (!svgRef.current || !containerRef.current || laps.length === 0) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = propHeight;
    const margin = { top: 20, right: 20, bottom: 35, left: 55 };
    const innerW = width - margin.left - margin.right;

    // Split height: 60% speed, 40% G
    const speedH = (height - margin.top - margin.bottom - 30) * 0.6;
    const gH = (height - margin.top - margin.bottom - 30) * 0.4;
    const gapY = 30;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    // Clip paths
    const defs = svg.append("defs");
    defs
      .append("clipPath")
      .attr("id", "corner-detail-clip-speed")
      .append("rect")
      .attr("width", innerW)
      .attr("height", speedH);
    defs
      .append("clipPath")
      .attr("id", "corner-detail-clip-g")
      .append("rect")
      .attr("width", innerW)
      .attr("height", gH);

    const xMin = corner.entry_distance_m - entryBuffer;
    const xMax = corner.exit_distance_m + exitBuffer;

    // Filter lap data to the corner region
    const slices = laps.map((lap) => {
      const dist: number[] = [];
      const spd: number[] = [];
      const lonG: number[] = [];
      for (let i = 0; i < lap.distance.length; i++) {
        if (lap.distance[i] >= xMin && lap.distance[i] <= xMax) {
          dist.push(lap.distance[i]);
          spd.push(lap.speed[i]);
          lonG.push(lap.longitudinalG[i]);
        }
      }
      return { lapNumber: lap.lapNumber, distance: dist, speed: spd, longitudinalG: lonG };
    });

    const allSpeed = slices.flatMap((s) => s.speed);
    const allG = slices.flatMap((s) => s.longitudinalG);

    const x = d3.scaleLinear().domain([xMin, xMax]).range([0, innerW]);
    const ySpeed = d3
      .scaleLinear()
      .domain([
        Math.max(0, (d3.min(allSpeed) ?? 0) * 0.9),
        (d3.max(allSpeed) ?? 100) * 1.05,
      ])
      .range([speedH, 0])
      .nice();
    const yG = d3
      .scaleLinear()
      .domain([
        (d3.min(allG) ?? -1) * 1.1,
        (d3.max(allG) ?? 1) * 1.1,
      ])
      .range([gH, 0])
      .nice();

    const colorScale = lapColorScale(slices.map((s) => s.lapNumber));

    // --- Speed subplot ---
    const gSpeed = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Corner region shading
    gSpeed
      .append("rect")
      .attr("x", x(corner.entry_distance_m))
      .attr("y", 0)
      .attr("width", Math.max(0, x(corner.exit_distance_m) - x(corner.entry_distance_m)))
      .attr("height", speedH)
      .attr("fill", chartTheme.grid)
      .attr("opacity", 0.2);

    // Grid lines
    gSpeed
      .append("g")
      .selectAll("line")
      .data(ySpeed.ticks(5))
      .join("line")
      .attr("x1", 0)
      .attr("x2", innerW)
      .attr("y1", (d) => ySpeed(d))
      .attr("y2", (d) => ySpeed(d))
      .attr("stroke", chartTheme.grid)
      .attr("stroke-dasharray", "2,2");

    // Apex line
    gSpeed
      .append("line")
      .attr("x1", x(corner.apex_distance_m))
      .attr("x2", x(corner.apex_distance_m))
      .attr("y1", 0)
      .attr("y2", speedH)
      .attr("stroke", "rgba(255,255,255,0.4)")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "4,2");

    // Entry/exit lines
    [corner.entry_distance_m, corner.exit_distance_m].forEach((dist) => {
      gSpeed
        .append("line")
        .attr("x1", x(dist))
        .attr("x2", x(dist))
        .attr("y1", 0)
        .attr("y2", speedH)
        .attr("stroke", "rgba(255,255,255,0.2)")
        .attr("stroke-width", 1)
        .attr("stroke-dasharray", "6,3");
    });

    // Brake point marker
    if (corner.brake_point_m !== null) {
      gSpeed
        .append("line")
        .attr("x1", x(corner.brake_point_m))
        .attr("x2", x(corner.brake_point_m))
        .attr("y1", 0)
        .attr("y2", speedH)
        .attr("stroke", "rgba(248,81,73,0.6)")
        .attr("stroke-width", 1)
        .attr("stroke-dasharray", "4,2");
    }

    // Throttle commit marker
    if (corner.throttle_commit_m !== null) {
      gSpeed
        .append("line")
        .attr("x1", x(corner.throttle_commit_m))
        .attr("x2", x(corner.throttle_commit_m))
        .attr("y1", 0)
        .attr("y2", speedH)
        .attr("stroke", "rgba(63,185,80,0.6)")
        .attr("stroke-width", 1)
        .attr("stroke-dasharray", "4,2");
    }

    // Speed traces
    const speedClip = gSpeed.append("g").attr("clip-path", "url(#corner-detail-clip-speed)");
    slices.forEach((sl) => {
      const lineData: [number, number][] = sl.distance.map((d, i) => [d, sl.speed[i]]);
      const line = d3
        .line<[number, number]>()
        .x((d) => x(d[0]))
        .y((d) => ySpeed(d[1]))
        .curve(d3.curveMonotoneX);
      speedClip
        .append("path")
        .datum(lineData)
        .attr("fill", "none")
        .attr("stroke", colorScale(sl.lapNumber))
        .attr("stroke-width", 1.5)
        .attr("d", line);
    });

    // Y axis (speed)
    gSpeed
      .append("g")
      .call(d3.axisLeft(ySpeed).ticks(5).tickFormat((d) => `${d} mph`))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // "Speed" label
    gSpeed
      .append("text")
      .attr("x", innerW / 2)
      .attr("y", -6)
      .attr("text-anchor", "middle")
      .attr("fill", chartTheme.textSecondary)
      .attr("font-size", 11)
      .attr("font-family", chartTheme.font)
      .text("Speed");

    // --- G-force subplot ---
    const gForce = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top + speedH + gapY})`);

    // Corner region shading
    gForce
      .append("rect")
      .attr("x", x(corner.entry_distance_m))
      .attr("y", 0)
      .attr("width", Math.max(0, x(corner.exit_distance_m) - x(corner.entry_distance_m)))
      .attr("height", gH)
      .attr("fill", chartTheme.grid)
      .attr("opacity", 0.2);

    // Grid lines
    gForce
      .append("g")
      .selectAll("line")
      .data(yG.ticks(4))
      .join("line")
      .attr("x1", 0)
      .attr("x2", innerW)
      .attr("y1", (d) => yG(d))
      .attr("y2", (d) => yG(d))
      .attr("stroke", chartTheme.grid)
      .attr("stroke-dasharray", "2,2");

    // Zero line
    gForce
      .append("line")
      .attr("x1", 0)
      .attr("x2", innerW)
      .attr("y1", yG(0))
      .attr("y2", yG(0))
      .attr("stroke", chartTheme.textSecondary)
      .attr("stroke-width", 0.5)
      .attr("stroke-dasharray", "4,2");

    // Apex line
    gForce
      .append("line")
      .attr("x1", x(corner.apex_distance_m))
      .attr("x2", x(corner.apex_distance_m))
      .attr("y1", 0)
      .attr("y2", gH)
      .attr("stroke", "rgba(255,255,255,0.4)")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "4,2");

    // Brake point and throttle markers on G plot too
    if (corner.brake_point_m !== null) {
      gForce
        .append("line")
        .attr("x1", x(corner.brake_point_m))
        .attr("x2", x(corner.brake_point_m))
        .attr("y1", 0)
        .attr("y2", gH)
        .attr("stroke", "rgba(248,81,73,0.6)")
        .attr("stroke-width", 1)
        .attr("stroke-dasharray", "4,2");
    }
    if (corner.throttle_commit_m !== null) {
      gForce
        .append("line")
        .attr("x1", x(corner.throttle_commit_m))
        .attr("x2", x(corner.throttle_commit_m))
        .attr("y1", 0)
        .attr("y2", gH)
        .attr("stroke", "rgba(63,185,80,0.6)")
        .attr("stroke-width", 1)
        .attr("stroke-dasharray", "4,2");
    }

    // G traces
    const gClip = gForce.append("g").attr("clip-path", "url(#corner-detail-clip-g)");
    slices.forEach((sl) => {
      const lineData: [number, number][] = sl.distance.map((d, i) => [d, sl.longitudinalG[i]]);
      const line = d3
        .line<[number, number]>()
        .x((d) => x(d[0]))
        .y((d) => yG(d[1]))
        .curve(d3.curveMonotoneX);
      gClip
        .append("path")
        .datum(lineData)
        .attr("fill", "none")
        .attr("stroke", colorScale(sl.lapNumber))
        .attr("stroke-width", 1.5)
        .attr("d", line);
    });

    // Y axis (G)
    gForce
      .append("g")
      .call(d3.axisLeft(yG).ticks(4).tickFormat((d) => `${d}G`))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // X axis (shared)
    gForce
      .append("g")
      .attr("transform", `translate(0,${gH})`)
      .call(d3.axisBottom(x).ticks(8).tickFormat((d) => `${d}m`))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // "Longitudinal G" label
    gForce
      .append("text")
      .attr("x", innerW / 2)
      .attr("y", -6)
      .attr("text-anchor", "middle")
      .attr("fill", chartTheme.textSecondary)
      .attr("font-size", 11)
      .attr("font-family", chartTheme.font)
      .text("Longitudinal G");

    // Legend
    const legendG = gSpeed
      .append("g")
      .attr("transform", `translate(${innerW - 10}, 5)`);
    slices.forEach((sl, i) => {
      const lg = legendG.append("g").attr("transform", `translate(0, ${i * 16})`);
      lg.append("line")
        .attr("x1", -30)
        .attr("x2", -10)
        .attr("y1", 0)
        .attr("y2", 0)
        .attr("stroke", colorScale(sl.lapNumber))
        .attr("stroke-width", 2);
      lg.append("text")
        .attr("x", -5)
        .attr("y", 4)
        .attr("text-anchor", "end")
        .attr("fill", chartTheme.text)
        .attr("font-size", 10)
        .attr("font-family", chartTheme.font)
        .text(`L${sl.lapNumber}`);
    });
  }, [laps, corner, entryBuffer, exitBuffer, propHeight]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (laps.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-sm text-[var(--text-muted)]"
        style={{ height: propHeight }}
      >
        No lap data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full" style={{ height: propHeight }}>
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}
