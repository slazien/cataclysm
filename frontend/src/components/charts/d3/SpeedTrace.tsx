"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";
import { lapColorScale } from "./scales";

interface LapTrace {
  lapNumber: number;
  distance: number[];
  speed: number[];
}

interface CornerZone {
  number: number;
  entry: number;
  exit: number;
}

interface SpeedTraceProps {
  laps: LapTrace[];
  corners?: CornerZone[];
  onHoverDistance?: (distance: number | null) => void;
  highlightDistance?: number | null;
  xDomain?: [number, number] | null;
  onXDomainChange?: (domain: [number, number] | null) => void;
  height?: number;
  className?: string;
}

export default function SpeedTrace({
  laps,
  corners = [],
  onHoverDistance,
  highlightDistance,
  xDomain,
  onXDomainChange,
  height: propHeight = 350,
  className = "",
}: SpeedTraceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const isExternalZoom = useRef(false);

  const render = useCallback(() => {
    if (!svgRef.current || !containerRef.current || laps.length === 0) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = propHeight;
    const margin = { top: 30, right: 20, bottom: 35, left: 55 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    // Add clip path
    const defs = svg.append("defs");
    defs
      .append("clipPath")
      .attr("id", "speed-clip")
      .append("rect")
      .attr("width", innerW)
      .attr("height", innerH);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Compute domains
    const allDist = laps.flatMap((l) => l.distance);
    const allSpeed = laps.flatMap((l) => l.speed);
    const fullXDomain: [number, number] = [
      d3.min(allDist) ?? 0,
      d3.max(allDist) ?? 1,
    ];
    const currentXDomain: [number, number] = xDomain ?? fullXDomain;

    const x = d3.scaleLinear().domain(currentXDomain).range([0, innerW]);
    const y = d3
      .scaleLinear()
      .domain([0, (d3.max(allSpeed) ?? 100) * 1.05])
      .range([innerH, 0])
      .nice();

    const colorScale = lapColorScale(laps.map((l) => l.lapNumber));

    // Corner zones
    const cornerG = g
      .append("g")
      .attr("clip-path", "url(#speed-clip)");

    corners.forEach((c) => {
      const cx1 = x(c.entry);
      const cx2 = x(c.exit);
      cornerG
        .append("rect")
        .attr("x", cx1)
        .attr("y", 0)
        .attr("width", Math.max(0, cx2 - cx1))
        .attr("height", innerH)
        .attr("fill", chartTheme.grid)
        .attr("opacity", 0.2);

      cornerG
        .append("text")
        .attr("x", (cx1 + cx2) / 2)
        .attr("y", -4)
        .attr("text-anchor", "middle")
        .attr("fill", chartTheme.textSecondary)
        .attr("font-size", 9)
        .attr("font-family", chartTheme.font)
        .text(`T${c.number}`);
    });

    // Grid lines
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
      .call(d3.axisBottom(x).ticks(8).tickFormat((d) => `${d}m`))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Y axis
    g.append("g")
      .call(d3.axisLeft(y).ticks(6).tickFormat((d) => `${d} mph`))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Speed traces
    const lineGroup = g
      .append("g")
      .attr("clip-path", "url(#speed-clip)");

    laps.forEach((lap) => {
      const lineData: [number, number][] = lap.distance.map((d, i) => [
        d,
        lap.speed[i],
      ]);

      const line = d3
        .line<[number, number]>()
        .x((d) => x(d[0]))
        .y((d) => y(d[1]))
        .curve(d3.curveMonotoneX);

      lineGroup
        .append("path")
        .datum(lineData)
        .attr("fill", "none")
        .attr("stroke", colorScale(lap.lapNumber))
        .attr("stroke-width", 1.5)
        .attr("d", line);
    });

    // Legend
    const legendG = g
      .append("g")
      .attr("transform", `translate(${innerW - 10}, 0)`);

    laps.forEach((lap, i) => {
      const lg = legendG
        .append("g")
        .attr("transform", `translate(0, ${i * 16})`);
      lg.append("line")
        .attr("x1", -30)
        .attr("x2", -10)
        .attr("y1", 0)
        .attr("y2", 0)
        .attr("stroke", colorScale(lap.lapNumber))
        .attr("stroke-width", 2);
      lg.append("text")
        .attr("x", -5)
        .attr("y", 4)
        .attr("text-anchor", "end")
        .attr("fill", chartTheme.text)
        .attr("font-size", 10)
        .attr("font-family", chartTheme.font)
        .text(`L${lap.lapNumber}`);
    });

    // Crosshair line
    const crosshair = g
      .append("line")
      .attr("y1", 0)
      .attr("y2", innerH)
      .attr("stroke", chartTheme.text)
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "4,2")
      .attr("opacity", 0)
      .attr("pointer-events", "none");

    // Show highlight distance from external source
    if (highlightDistance !== null && highlightDistance !== undefined) {
      const hx = x(highlightDistance);
      if (hx >= 0 && hx <= innerW) {
        crosshair.attr("x1", hx).attr("x2", hx).attr("opacity", 0.7);
      }
    }

    // Hover overlay
    let rafId: number | null = null;
    const overlay = g
      .append("rect")
      .attr("width", innerW)
      .attr("height", innerH)
      .attr("fill", "transparent")
      .attr("cursor", "crosshair")
      .on("mousemove", (event) => {
        if (rafId !== null) return;
        rafId = requestAnimationFrame(() => {
          rafId = null;
          const [mx] = d3.pointer(event);
          const dist = x.invert(mx);
          crosshair.attr("x1", mx).attr("x2", mx).attr("opacity", 0.7);
          onHoverDistance?.(dist);
        });
      })
      .on("mouseleave", () => {
        crosshair.attr("opacity", 0);
        onHoverDistance?.(null);
      });

    // Zoom behavior (x-axis only)
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 20])
      .translateExtent([
        [margin.left, 0],
        [margin.left + innerW, height],
      ])
      .extent([
        [margin.left, 0],
        [margin.left + innerW, height],
      ])
      .on("zoom", (event) => {
        if (isExternalZoom.current) return;
        const newX = event.transform.rescaleX(
          d3.scaleLinear().domain(fullXDomain).range([0, innerW]),
        );
        const newDomain = newX.domain() as [number, number];
        onXDomainChange?.(
          newDomain[0] === fullXDomain[0] && newDomain[1] === fullXDomain[1]
            ? null
            : newDomain,
        );
      });

    svg.call(zoom);
    // Disable zoom on overlay drag (let hover work)
    overlay.on(".zoom", null);
    zoomRef.current = zoom;

    // Sync zoom from external source
    if (xDomain) {
      const fullX = d3.scaleLinear().domain(fullXDomain).range([0, innerW]);
      const k = innerW / (fullX(xDomain[1]) - fullX(xDomain[0]));
      const tx = -fullX(xDomain[0]) * k;
      isExternalZoom.current = true;
      svg.call(zoom.transform, d3.zoomIdentity.translate(tx, 0).scale(k));
      isExternalZoom.current = false;
    }
  }, [laps, corners, highlightDistance, xDomain, propHeight, onHoverDistance, onXDomainChange]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (laps.length === 0) {
    return (
      <div
        className={`flex items-center justify-center text-sm text-[var(--text-muted)] ${className}`}
        style={{ height: propHeight }}
      >
        No lap data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`w-full ${className}`} style={{ height: propHeight }}>
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}
