"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";

interface SegmentGain {
  segment_name: string;
  gain_s: number;
  is_corner: boolean;
}

interface GainPerCornerProps {
  consistencyGains: SegmentGain[];
  compositeGains: SegmentGain[];
  height?: number;
  className?: string;
}

export default function GainPerCorner({
  consistencyGains,
  compositeGains,
  height: propHeight = 300,
  className = "",
}: GainPerCornerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const render = useCallback(() => {
    if (!svgRef.current || !containerRef.current) return;

    // Combine: only show corners, sorted by total gain
    const cornerGains = consistencyGains
      .filter((g) => g.is_corner && g.gain_s >= 0.01)
      .sort((a, b) => b.gain_s - a.gain_s);

    if (cornerGains.length === 0) return;

    // Build composite map for matching segments
    const compositeMap = new Map(
      compositeGains.map((g) => [g.segment_name, g.gain_s]),
    );

    const container = containerRef.current;
    const width = container.clientWidth;
    const margin = { top: 20, right: 30, bottom: 30, left: 60 };
    const barHeight = 24;
    const barGap = 6;
    const height = Math.max(
      propHeight,
      margin.top +
        margin.bottom +
        cornerGains.length * (barHeight + barGap),
    );
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Y scale: segment names
    const y = d3
      .scaleBand()
      .domain(cornerGains.map((g) => g.segment_name))
      .range([0, innerH])
      .padding(0.2);

    // X scale: gain in seconds
    const maxGain = d3.max(cornerGains, (d) => d.gain_s) ?? 0.5;
    const x = d3.scaleLinear().domain([0, maxGain * 1.15]).range([0, innerW]);

    // Grid lines
    g.append("g")
      .selectAll("line")
      .data(x.ticks(5))
      .join("line")
      .attr("x1", (d) => x(d))
      .attr("x2", (d) => x(d))
      .attr("y1", 0)
      .attr("y2", innerH)
      .attr("stroke", chartTheme.grid)
      .attr("stroke-dasharray", "2,2");

    // Consistency bars (blue)
    g.selectAll(".bar-consistency")
      .data(cornerGains)
      .join("rect")
      .attr("class", "bar-consistency")
      .attr("x", 0)
      .attr("y", (d) => y(d.segment_name) ?? 0)
      .attr("width", (d) => Math.max(0, x(d.gain_s)))
      .attr("height", y.bandwidth())
      .attr("fill", chartTheme.accentBlue)
      .attr("rx", 3);

    // Composite overlay bars (yellow, stacked on top if there's additional gain)
    g.selectAll(".bar-composite")
      .data(cornerGains)
      .join("rect")
      .attr("class", "bar-composite")
      .attr("x", (d) => x(d.gain_s))
      .attr("y", (d) => y(d.segment_name) ?? 0)
      .attr("width", (d) => {
        const comp = compositeMap.get(d.segment_name) ?? 0;
        return Math.max(0, x(comp) - x(0));
      })
      .attr("height", y.bandwidth())
      .attr("fill", chartTheme.accentYellow)
      .attr("opacity", 0.7)
      .attr("rx", 3);

    // Value labels
    g.selectAll(".label")
      .data(cornerGains)
      .join("text")
      .attr("class", "label")
      .attr("x", (d) => {
        const comp = compositeMap.get(d.segment_name) ?? 0;
        return x(d.gain_s + comp) + 4;
      })
      .attr("y", (d) => (y(d.segment_name) ?? 0) + y.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("fill", chartTheme.text)
      .attr("font-size", 10)
      .attr("font-family", chartTheme.font)
      .text((d) => {
        const comp = compositeMap.get(d.segment_name) ?? 0;
        const total = d.gain_s + comp;
        return `${total.toFixed(2)}s`;
      });

    // Y axis (segment names)
    g.append("g")
      .call(d3.axisLeft(y))
      .call((sel) => sel.select(".domain").remove())
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // X axis
    g.append("g")
      .attr("transform", `translate(0,${innerH})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat((d) => `${d}s`))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Legend
    const legendData = [
      { label: "Consistency", color: chartTheme.accentBlue },
      { label: "Composite", color: chartTheme.accentYellow },
    ];

    const legend = g
      .append("g")
      .attr("transform", `translate(${innerW - 140}, -8)`);

    legendData.forEach((item, i) => {
      const lg = legend.append("g").attr("transform", `translate(${i * 80}, 0)`);
      lg.append("rect")
        .attr("width", 10)
        .attr("height", 10)
        .attr("fill", item.color)
        .attr("rx", 2);
      lg.append("text")
        .attr("x", 14)
        .attr("y", 9)
        .attr("fill", chartTheme.text)
        .attr("font-size", 10)
        .attr("font-family", chartTheme.font)
        .text(item.label);
    });
  }, [consistencyGains, compositeGains, propHeight]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (consistencyGains.length === 0) {
    return (
      <div
        className={`flex items-center justify-center text-sm text-[var(--text-muted)] ${className}`}
        style={{ height: propHeight }}
      >
        No gain data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`w-full ${className}`}>
      <svg ref={svgRef} className="w-full" />
    </div>
  );
}
