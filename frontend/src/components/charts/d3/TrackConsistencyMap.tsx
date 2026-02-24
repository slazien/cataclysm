"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";
import type { TrackPositionConsistency } from "@/lib/types";

interface TrackConsistencyMapProps {
  trackData: TrackPositionConsistency | null;
  className?: string;
}

export default function TrackConsistencyMap({
  trackData,
  className = "",
}: TrackConsistencyMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (!containerRef.current || !canvasRef.current || !svgRef.current || !trackData)
      return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = Math.max(300, Math.min(width, 500));

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

    const { lat, lon, speed_std_mph } = trackData;
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
      .range([height - padding, padding]);

    const stdExtent = d3.extent(speed_std_mph) as [number, number];

    // Green = low std (consistent), Red = high std (inconsistent)
    const colorScale = d3
      .scaleLinear<string>()
      .domain([stdExtent[0], (stdExtent[0] + stdExtent[1]) / 2, stdExtent[1]])
      .range([chartTheme.accentGreen, chartTheme.accentYellow, chartTheme.accentRed])
      .clamp(true);

    // Draw track points on canvas
    const pointSize = Math.max(1.5, Math.min(3, width / 300));
    for (let i = 0; i < lat.length; i++) {
      ctx.fillStyle = colorScale(speed_std_mph[i]);
      ctx.beginPath();
      ctx.arc(xScale(lon[i]), yScale(lat[i]), pointSize, 0, Math.PI * 2);
      ctx.fill();
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
      .attr("id", "consistency-gradient")
      .attr("x1", "0%")
      .attr("x2", "100%");

    gradient
      .append("stop")
      .attr("offset", "0%")
      .attr("stop-color", chartTheme.accentGreen);
    gradient
      .append("stop")
      .attr("offset", "50%")
      .attr("stop-color", chartTheme.accentYellow);
    gradient
      .append("stop")
      .attr("offset", "100%")
      .attr("stop-color", chartTheme.accentRed);

    legendG
      .append("rect")
      .attr("width", legendW)
      .attr("height", legendH)
      .attr("fill", "url(#consistency-gradient)")
      .attr("rx", 2);

    legendG
      .append("text")
      .attr("y", legendH + 12)
      .attr("fill", chartTheme.text)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .text("Consistent");

    legendG
      .append("text")
      .attr("x", legendW)
      .attr("y", legendH + 12)
      .attr("text-anchor", "end")
      .attr("fill", chartTheme.text)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .text("Inconsistent");
  }, [trackData]);

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
