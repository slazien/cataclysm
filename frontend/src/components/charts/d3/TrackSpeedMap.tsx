"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";
import type { TrackPositionConsistency } from "@/lib/types";
import type { Corner } from "@/lib/types";

interface TrackSpeedMapProps {
  trackData: TrackPositionConsistency | null;
  corners?: Corner[];
  className?: string;
}

export default function TrackSpeedMap({
  trackData,
  corners = [],
  className = "",
}: TrackSpeedMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (!containerRef.current || !canvasRef.current || !svgRef.current || !trackData)
      return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = Math.max(300, Math.min(width, 500));
    container.style.height = `${height}px`;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    const { lat, lon, speed_median_mph } = trackData;
    if (lat.length === 0) return;

    const padding = 30;

    const latExtent = d3.extent(lat) as [number, number];
    const lonExtent = d3.extent(lon) as [number, number];

    const xScale = d3
      .scaleLinear()
      .domain(lonExtent)
      .range([padding, width - padding]);
    const yScale = d3
      .scaleLinear()
      .domain(latExtent)
      .range([height - padding, padding]); // flip Y

    const speedExtent = d3.extent(speed_median_mph) as [number, number];
    const colorScale = d3
      .scaleSequential(d3.interpolateTurbo)
      .domain(speedExtent);

    // Draw track points on canvas
    const pointSize = Math.max(1.5, Math.min(3, width / 300));
    for (let i = 0; i < lat.length; i++) {
      ctx.fillStyle = colorScale(speed_median_mph[i]);
      ctx.beginPath();
      ctx.arc(xScale(lon[i]), yScale(lat[i]), pointSize, 0, Math.PI * 2);
      ctx.fill();
    }

    // Corner labels on SVG overlay
    if (corners.length > 0 && trackData.distance_m.length > 0) {
      const totalDist = trackData.distance_m[trackData.distance_m.length - 1];
      corners.forEach((c) => {
        const apexFrac = c.apex_distance_m / totalDist;
        const idx = Math.min(
          Math.floor(apexFrac * lat.length),
          lat.length - 1,
        );
        if (idx >= 0 && idx < lat.length) {
          svg
            .append("text")
            .attr("x", xScale(lon[idx]))
            .attr("y", yScale(lat[idx]) - 8)
            .attr("text-anchor", "middle")
            .attr("fill", chartTheme.text)
            .attr("font-size", 10)
            .attr("font-family", chartTheme.font)
            .attr("font-weight", "bold")
            .text(`T${c.number}`);
        }
      });
    }

    // Color legend
    const legendW = 150;
    const legendH = 10;
    const legendX = width - legendW - 15;
    const legendY = 15;

    const legendG = svg.append("g").attr("transform", `translate(${legendX},${legendY})`);

    const defs = svg.append("defs");
    const gradient = defs
      .append("linearGradient")
      .attr("id", "speed-gradient")
      .attr("x1", "0%")
      .attr("x2", "100%");

    const steps = 10;
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      const val = speedExtent[0] + t * (speedExtent[1] - speedExtent[0]);
      gradient
        .append("stop")
        .attr("offset", `${t * 100}%`)
        .attr("stop-color", colorScale(val));
    }

    legendG
      .append("rect")
      .attr("width", legendW)
      .attr("height", legendH)
      .attr("fill", "url(#speed-gradient)")
      .attr("rx", 2);

    legendG
      .append("text")
      .attr("y", legendH + 12)
      .attr("fill", chartTheme.text)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .text(`${speedExtent[0].toFixed(0)} mph`);

    legendG
      .append("text")
      .attr("x", legendW)
      .attr("y", legendH + 12)
      .attr("text-anchor", "end")
      .attr("fill", chartTheme.text)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .text(`${speedExtent[1].toFixed(0)} mph`);
  }, [trackData, corners]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (!trackData || trackData.lat.length === 0) {
    return (
      <div className={`flex items-center justify-center py-12 text-sm text-[var(--text-muted)] ${className}`}>
        No track data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`relative w-full min-h-[300px] ${className}`}>
      <canvas ref={canvasRef} className="absolute inset-0" />
      <svg ref={svgRef} className="absolute inset-0" />
    </div>
  );
}
