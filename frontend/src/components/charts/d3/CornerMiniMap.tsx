"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";
import type { Corner } from "@/lib/types";

interface CornerMiniMapProps {
  lat: number[];
  lon: number[];
  distance: number[];
  corner: Corner;
  allCorners?: Corner[];
  size?: number;
}

export default function CornerMiniMap({
  lat,
  lon,
  distance,
  corner,
  allCorners = [],
  size = 200,
}: CornerMiniMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (!containerRef.current || !canvasRef.current || !svgRef.current) return;
    if (lat.length === 0 || lon.length === 0) return;

    const width = size;
    const height = size;
    const padding = 15;

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

    // Compute zoomed region around the corner with ~100m padding
    const cornerPadding = 100;
    const lo = Math.max(0, corner.entry_distance_m - cornerPadding);
    const hi = Math.min(distance[distance.length - 1], corner.exit_distance_m + cornerPadding);

    // Find lat/lon range for the zoomed region
    let iLo = 0;
    let iHi = distance.length - 1;
    for (let i = 0; i < distance.length; i++) {
      if (distance[i] >= lo) {
        iLo = i;
        break;
      }
    }
    for (let i = distance.length - 1; i >= 0; i--) {
      if (distance[i] <= hi) {
        iHi = i;
        break;
      }
    }

    const zoomLat = lat.slice(iLo, iHi + 1);
    const zoomLon = lon.slice(iLo, iHi + 1);

    const latExtent = d3.extent(zoomLat) as [number, number];
    const lonExtent = d3.extent(zoomLon) as [number, number];
    const latPad = (latExtent[1] - latExtent[0]) * 0.3 + 1e-5;
    const lonPad = (lonExtent[1] - lonExtent[0]) * 0.3 + 1e-5;

    const xScale = d3
      .scaleLinear()
      .domain([lonExtent[0] - lonPad, lonExtent[1] + lonPad])
      .range([padding, width - padding]);
    const yScale = d3
      .scaleLinear()
      .domain([latExtent[0] - latPad, latExtent[1] + latPad])
      .range([height - padding, padding]);

    // Draw full track in gray
    ctx.strokeStyle = "#333";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < lat.length; i++) {
      const px = xScale(lon[i]);
      const py = yScale(lat[i]);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();

    // Speed color scale for corner region
    const cornerSpeedMph: number[] = [];
    for (let i = iLo; i <= iHi; i++) {
      // Speed isn't passed directly, so we use distance-based position coloring
      cornerSpeedMph.push(i);
    }

    // Highlight corner segment with bright color
    const colorScale = d3
      .scaleSequential(d3.interpolateTurbo)
      .domain([0, Math.max(1, iHi - iLo)]);

    for (let i = iLo; i <= iHi; i++) {
      ctx.fillStyle = colorScale(i - iLo);
      ctx.beginPath();
      ctx.arc(xScale(lon[i]), yScale(lat[i]), 2.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // Mark entry, apex, exit
    const markers = [
      { dist: corner.entry_distance_m, label: "E", color: chartTheme.accentYellow },
      { dist: corner.apex_distance_m, label: "A", color: chartTheme.accentRed },
      { dist: corner.exit_distance_m, label: "X", color: chartTheme.accentGreen },
    ];

    markers.forEach(({ dist, label, color }) => {
      let idx = 0;
      for (let i = 0; i < distance.length; i++) {
        if (distance[i] >= dist) {
          idx = i;
          break;
        }
      }
      if (idx < lat.length) {
        svg
          .append("circle")
          .attr("cx", xScale(lon[idx]))
          .attr("cy", yScale(lat[idx]))
          .attr("r", 4)
          .attr("fill", color)
          .attr("stroke", "#000")
          .attr("stroke-width", 1);
        svg
          .append("text")
          .attr("x", xScale(lon[idx]))
          .attr("y", yScale(lat[idx]) - 8)
          .attr("text-anchor", "middle")
          .attr("fill", color)
          .attr("font-size", 9)
          .attr("font-family", chartTheme.font)
          .attr("font-weight", "bold")
          .text(label);
      }
    });

    // Corner number label (prominent)
    const apexIdx = distance.findIndex((d) => d >= corner.apex_distance_m);
    if (apexIdx >= 0 && apexIdx < lat.length) {
      svg
        .append("text")
        .attr("x", xScale(lon[apexIdx]))
        .attr("y", yScale(lat[apexIdx]) + 16)
        .attr("text-anchor", "middle")
        .attr("fill", "#fff")
        .attr("font-size", 12)
        .attr("font-family", chartTheme.font)
        .attr("font-weight", "bold")
        .text(`T${corner.number}`);
    }

    // Label neighboring corners (faint)
    allCorners.forEach((c) => {
      if (c.number === corner.number) return;
      const ci = distance.findIndex((d) => d >= c.apex_distance_m);
      if (ci >= 0 && ci < lat.length) {
        const px = xScale(lon[ci]);
        const py = yScale(lat[ci]);
        if (px >= 0 && px <= width && py >= 0 && py <= height) {
          svg
            .append("text")
            .attr("x", px)
            .attr("y", py - 6)
            .attr("text-anchor", "middle")
            .attr("fill", "#666")
            .attr("font-size", 9)
            .attr("font-family", chartTheme.font)
            .text(`T${c.number}`);
        }
      }
    });
  }, [lat, lon, distance, corner, allCorners, size]);

  useEffect(() => {
    render();
  }, [render]);

  if (lat.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-xs text-[var(--text-muted)]"
        style={{ width: size, height: size }}
      >
        No track data
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="relative flex-shrink-0"
      style={{ width: size, height: size }}
    >
      <canvas ref={canvasRef} className="absolute inset-0" />
      <svg ref={svgRef} className="absolute inset-0" />
    </div>
  );
}
