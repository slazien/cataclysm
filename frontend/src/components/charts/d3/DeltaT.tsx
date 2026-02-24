"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";

interface CornerZone {
  number: number;
  entry: number;
  exit: number;
}

interface DeltaTProps {
  distance: number[];
  delta: number[];
  refLap: number;
  compLap: number;
  corners?: CornerZone[];
  onHoverDistance?: (distance: number | null) => void;
  highlightDistance?: number | null;
  xDomain?: [number, number] | null;
  onXDomainChange?: (domain: [number, number] | null) => void;
  height?: number;
  className?: string;
}

export default function DeltaT({
  distance,
  delta,
  refLap,
  compLap,
  corners = [],
  onHoverDistance,
  highlightDistance,
  xDomain,
  onXDomainChange,
  height: propHeight = 250,
  className = "",
}: DeltaTProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const isExternalZoom = useRef(false);

  const render = useCallback(() => {
    if (
      !svgRef.current ||
      !containerRef.current ||
      distance.length === 0 ||
      delta.length === 0
    )
      return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = propHeight;
    const margin = { top: 30, right: 20, bottom: 35, left: 55 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    // Clip path
    const defs = svg.append("defs");
    defs
      .append("clipPath")
      .attr("id", "delta-clip")
      .append("rect")
      .attr("width", innerW)
      .attr("height", innerH);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Title
    svg
      .append("text")
      .attr("x", margin.left + innerW / 2)
      .attr("y", 16)
      .attr("text-anchor", "middle")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSizeLabel)
      .attr("font-family", chartTheme.font)
      .attr("font-weight", "bold")
      .text(`Delta-T: L${compLap} vs L${refLap} (ref)`);

    // Domains
    const fullXDomain: [number, number] = [
      d3.min(distance) ?? 0,
      d3.max(distance) ?? 1,
    ];
    const currentXDomain: [number, number] = xDomain ?? fullXDomain;

    const maxAbsDelta = d3.max(delta.map(Math.abs)) ?? 1;
    const yPad = maxAbsDelta * 1.15;

    const x = d3.scaleLinear().domain(currentXDomain).range([0, innerW]);
    const y = d3.scaleLinear().domain([-yPad, yPad]).range([innerH, 0]).nice();

    // Corner zones
    const cornerG = g.append("g").attr("clip-path", "url(#delta-clip)");

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
      .data(y.ticks(5))
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
      .call(d3.axisLeft(y).ticks(5).tickFormat((d) => `${(d as number).toFixed(2)}s`))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Zero line (dashed)
    g.append("line")
      .attr("x1", 0)
      .attr("x2", innerW)
      .attr("y1", y(0))
      .attr("y2", y(0))
      .attr("stroke", chartTheme.text)
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "4,3");

    // Build paired data
    const pairedData: [number, number][] = distance.map((d, i) => [d, delta[i]]);

    const clipGroup = g.append("g").attr("clip-path", "url(#delta-clip)");

    // Area above zero (positive = comp slower = red)
    const areaAbove = d3
      .area<[number, number]>()
      .x((d) => x(d[0]))
      .y0(y(0))
      .y1((d) => y(Math.max(0, d[1])))
      .curve(d3.curveMonotoneX);

    clipGroup
      .append("path")
      .datum(pairedData)
      .attr("fill", chartTheme.accentRed)
      .attr("opacity", 0.35)
      .attr("d", areaAbove);

    // Area below zero (negative = comp faster = green)
    const areaBelow = d3
      .area<[number, number]>()
      .x((d) => x(d[0]))
      .y0(y(0))
      .y1((d) => y(Math.min(0, d[1])))
      .curve(d3.curveMonotoneX);

    clipGroup
      .append("path")
      .datum(pairedData)
      .attr("fill", chartTheme.accentGreen)
      .attr("opacity", 0.35)
      .attr("d", areaBelow);

    // Delta line
    const line = d3
      .line<[number, number]>()
      .x((d) => x(d[0]))
      .y((d) => y(d[1]))
      .curve(d3.curveMonotoneX);

    clipGroup
      .append("path")
      .datum(pairedData)
      .attr("fill", "none")
      .attr("stroke", chartTheme.text)
      .attr("stroke-width", 1.2)
      .attr("d", line);

    // Crosshair
    const crosshair = g
      .append("line")
      .attr("y1", 0)
      .attr("y2", innerH)
      .attr("stroke", chartTheme.text)
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "4,2")
      .attr("opacity", 0)
      .attr("pointer-events", "none");

    if (highlightDistance !== null && highlightDistance !== undefined) {
      const hx = x(highlightDistance);
      if (hx >= 0 && hx <= innerW) {
        crosshair.attr("x1", hx).attr("x2", hx).attr("opacity", 0.7);
      }
    }

    // Hover
    let rafId: number | null = null;
    g.append("rect")
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

    // Zoom
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

    if (xDomain) {
      const fullX = d3.scaleLinear().domain(fullXDomain).range([0, innerW]);
      const k = innerW / (fullX(xDomain[1]) - fullX(xDomain[0]));
      const tx = -fullX(xDomain[0]) * k;
      isExternalZoom.current = true;
      svg.call(zoom.transform, d3.zoomIdentity.translate(tx, 0).scale(k));
      isExternalZoom.current = false;
    }
  }, [
    distance,
    delta,
    refLap,
    compLap,
    corners,
    highlightDistance,
    xDomain,
    propHeight,
    onHoverDistance,
    onXDomainChange,
  ]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (distance.length === 0) {
    return (
      <div
        className={`flex items-center justify-center text-sm text-[var(--text-muted)] ${className}`}
        style={{ height: propHeight }}
      >
        No delta data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`w-full ${className}`} style={{ height: propHeight }}>
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}
