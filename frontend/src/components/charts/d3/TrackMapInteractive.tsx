"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";

interface CornerApex {
  number: number;
  apex_lat: number;
  apex_lon: number;
}

interface TrackMapInteractiveProps {
  lat: number[];
  lon: number[];
  heading: number[];
  speed: number[];
  distance: number[];
  delta?: number[];
  corners?: CornerApex[];
  cursorDistance?: number | null;
  mapLap: number;
  height?: number;
  className?: string;
}

export default function TrackMapInteractive({
  lat,
  lon,
  heading,
  speed,
  distance,
  delta,
  corners = [],
  cursorDistance,
  mapLap,
  height: propHeight = 400,
  className = "",
}: TrackMapInteractiveProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (
      !containerRef.current ||
      !canvasRef.current ||
      !svgRef.current ||
      lat.length === 0
    )
      return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = propHeight;
    const padding = 40;

    // Canvas setup
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

    // SVG setup
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    // Compute equal-aspect-ratio scales
    const latExtent = d3.extent(lat) as [number, number];
    const lonExtent = d3.extent(lon) as [number, number];

    // Use cos(mid-latitude) correction for equal aspect ratio
    const midLat = (latExtent[0] + latExtent[1]) / 2;
    const cosLat = Math.cos((midLat * Math.PI) / 180);

    const latRange = latExtent[1] - latExtent[0];
    const lonRange = (lonExtent[1] - lonExtent[0]) * cosLat;

    const plotW = width - 2 * padding;
    const plotH = height - 2 * padding;

    let scaleX: d3.ScaleLinear<number, number>;
    let scaleY: d3.ScaleLinear<number, number>;

    if (lonRange / plotW > latRange / plotH) {
      // Width-limited
      const scale = plotW / lonRange;
      const usedH = latRange * scale;
      const yOffset = (plotH - usedH) / 2;
      scaleX = d3.scaleLinear().domain(lonExtent).range([padding, padding + plotW]);
      scaleY = d3
        .scaleLinear()
        .domain(latExtent)
        .range([padding + yOffset + usedH, padding + yOffset]);
    } else {
      // Height-limited
      const scale = plotH / latRange;
      const usedW = lonRange * scale;
      const xOffset = (plotW - usedW) / 2;
      scaleX = d3
        .scaleLinear()
        .domain(lonExtent)
        .range([padding + xOffset, padding + xOffset + usedW]);
      scaleY = d3.scaleLinear().domain(latExtent).range([padding + plotH, padding]);
    }

    // Color scale
    let colorFn: (i: number) => string;

    if (delta && delta.length === lat.length) {
      // Delta colormap: red (positive/slower) - white (zero) - green (negative/faster)
      const maxAbsDelta = d3.max(delta.map(Math.abs)) ?? 1;
      const diverging = d3
        .scaleDiverging<string>()
        .domain([maxAbsDelta, 0, -maxAbsDelta])
        .interpolator(d3.interpolateRgb(chartTheme.accentRed, chartTheme.accentGreen));
      colorFn = (i: number) => diverging(delta[i]);
    } else {
      // Speed colormap
      const speedExtent = d3.extent(speed) as [number, number];
      const turbo = d3.scaleSequential(d3.interpolateTurbo).domain(speedExtent);
      colorFn = (i: number) => turbo(speed[i]);
    }

    // Draw track points on canvas
    const pointSize = Math.max(1.5, Math.min(3, width / 300));
    for (let i = 0; i < lat.length; i++) {
      ctx.fillStyle = colorFn(i);
      ctx.beginPath();
      ctx.arc(scaleX(lon[i]), scaleY(lat[i]), pointSize, 0, Math.PI * 2);
      ctx.fill();
    }

    // SVG overlay: corner labels
    corners.forEach((c) => {
      const cx = scaleX(c.apex_lon);
      const cy = scaleY(c.apex_lat);
      svg
        .append("text")
        .attr("x", cx)
        .attr("y", cy - 10)
        .attr("text-anchor", "middle")
        .attr("fill", chartTheme.text)
        .attr("font-size", 10)
        .attr("font-family", chartTheme.font)
        .attr("font-weight", "bold")
        .text(`T${c.number}`);
    });

    // Directional cursor at cursorDistance
    if (cursorDistance !== null && cursorDistance !== undefined && distance.length > 0) {
      // Binary search for index
      const idx = d3.bisectLeft(distance, cursorDistance);
      const clampedIdx = Math.min(Math.max(0, idx), lat.length - 1);

      const cx = scaleX(lon[clampedIdx]);
      const cy = scaleY(lat[clampedIdx]);
      const hdg = heading[clampedIdx] ?? 0;

      // Triangle cursor
      const size = 8;
      const cursorG = svg
        .append("g")
        .attr("transform", `translate(${cx},${cy}) rotate(${hdg})`);

      cursorG
        .append("polygon")
        .attr("points", `0,${-size} ${-size * 0.6},${size * 0.5} ${size * 0.6},${size * 0.5}`)
        .attr("fill", "#ffffff")
        .attr("stroke", "#000000")
        .attr("stroke-width", 1.5);
    }

    // Color legend bar
    const legendW = 150;
    const legendH = 10;
    const legendX = width - legendW - 15;
    const legendY = 15;

    const legendG = svg
      .append("g")
      .attr("transform", `translate(${legendX},${legendY})`);

    const defs = svg.append("defs");

    if (delta && delta.length > 0) {
      // Diverging legend: red -> white -> green
      const gradient = defs
        .append("linearGradient")
        .attr("id", "trackmap-gradient")
        .attr("x1", "0%")
        .attr("x2", "100%");

      gradient.append("stop").attr("offset", "0%").attr("stop-color", chartTheme.accentRed);
      gradient.append("stop").attr("offset", "50%").attr("stop-color", "#ffffff");
      gradient.append("stop").attr("offset", "100%").attr("stop-color", chartTheme.accentGreen);

      legendG
        .append("rect")
        .attr("width", legendW)
        .attr("height", legendH)
        .attr("fill", "url(#trackmap-gradient)")
        .attr("rx", 2);

      const maxAbsDelta = d3.max(delta.map(Math.abs)) ?? 1;
      legendG
        .append("text")
        .attr("y", legendH + 12)
        .attr("fill", chartTheme.text)
        .attr("font-size", 9)
        .attr("font-family", chartTheme.font)
        .text(`+${maxAbsDelta.toFixed(2)}s`);

      legendG
        .append("text")
        .attr("x", legendW)
        .attr("y", legendH + 12)
        .attr("text-anchor", "end")
        .attr("fill", chartTheme.text)
        .attr("font-size", 9)
        .attr("font-family", chartTheme.font)
        .text(`-${maxAbsDelta.toFixed(2)}s`);
    } else {
      // Speed legend
      const speedExtent = d3.extent(speed) as [number, number];
      const turbo = d3.scaleSequential(d3.interpolateTurbo).domain(speedExtent);

      const gradient = defs
        .append("linearGradient")
        .attr("id", "trackmap-gradient")
        .attr("x1", "0%")
        .attr("x2", "100%");

      const steps = 10;
      for (let i = 0; i <= steps; i++) {
        const t = i / steps;
        const val = speedExtent[0] + t * (speedExtent[1] - speedExtent[0]);
        gradient
          .append("stop")
          .attr("offset", `${t * 100}%`)
          .attr("stop-color", turbo(val));
      }

      legendG
        .append("rect")
        .attr("width", legendW)
        .attr("height", legendH)
        .attr("fill", "url(#trackmap-gradient)")
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
    }

    // Lap label
    svg
      .append("text")
      .attr("x", 10)
      .attr("y", 20)
      .attr("fill", chartTheme.textSecondary)
      .attr("font-size", 11)
      .attr("font-family", chartTheme.font)
      .text(`Lap ${mapLap}`);
  }, [lat, lon, heading, speed, distance, delta, corners, cursorDistance, mapLap, propHeight]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (lat.length === 0) {
    return (
      <div
        className={`flex items-center justify-center text-sm text-[var(--text-muted)] ${className}`}
        style={{ height: propHeight }}
      >
        No track data available
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`relative w-full ${className}`}
      style={{ height: propHeight }}
    >
      <canvas ref={canvasRef} className="absolute inset-0" />
      <svg ref={svgRef} className="absolute inset-0" />
    </div>
  );
}
