"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import { chartTheme } from "./theme";

interface CornerHeatmapProps {
  dates: string[];
  cornerNumbers: string[];
  values: (number | null)[][]; // [corner_idx][session_idx]
  metric: "min_speed" | "brake_std" | "consistency";
  metricLabel: string;
}

export default function CornerHeatmap({
  dates,
  cornerNumbers,
  values,
  metric,
  metricLabel,
}: CornerHeatmapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const render = useCallback(() => {
    if (
      !svgRef.current ||
      !containerRef.current ||
      dates.length === 0 ||
      cornerNumbers.length === 0
    )
      return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const cellHeight = 36;
    const height = Math.max(
      200,
      cornerNumbers.length * cellHeight + 100,
    );
    const margin = { top: 20, right: 80, bottom: 60, left: 60 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const dateLabels = dates.map((d) =>
      d.length > 10 ? d.slice(0, 10) : d,
    );

    const x = d3
      .scaleBand<string>()
      .domain(dateLabels)
      .range([0, innerW])
      .padding(0.05);

    const y = d3
      .scaleBand<string>()
      .domain(cornerNumbers)
      .range([0, innerH])
      .padding(0.05);

    // Collect all non-null values for color scale
    const allVals = values.flatMap((row) => row.filter((v): v is number => v !== null));
    const minV = d3.min(allVals) ?? 0;
    const maxV = d3.max(allVals) ?? 100;

    // Color scale depends on metric
    let colorScale: d3.ScaleSequential<string>;
    if (metric === "brake_std") {
      // Lower is better for brake std -> reversed yellow-red
      colorScale = d3
        .scaleSequential(d3.interpolateYlOrRd)
        .domain([minV, maxV]);
    } else {
      // Higher is better for speed and consistency -> green
      colorScale = d3
        .scaleSequential(d3.interpolateRdYlGn)
        .domain([minV, maxV]);
    }

    // X axis
    g.append("g")
      .attr("transform", `translate(0,${innerH})`)
      .call(d3.axisBottom(x).tickSize(0))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", 10)
      .attr("font-family", chartTheme.font)
      .attr("transform", "rotate(-30)")
      .attr("text-anchor", "end");

    // Y axis
    g.append("g")
      .call(d3.axisLeft(y).tickSize(0))
      .call((sel) => sel.select(".domain").attr("stroke", chartTheme.grid))
      .selectAll("text")
      .attr("fill", chartTheme.text)
      .attr("font-size", chartTheme.fontSize)
      .attr("font-family", chartTheme.font);

    // Cells
    const tooltip = d3.select(tooltipRef.current);

    cornerNumbers.forEach((cn, ci) => {
      dateLabels.forEach((dl, si) => {
        const val = values[ci]?.[si];
        if (val === null || val === undefined) return;

        g.append("rect")
          .attr("x", x(dl) ?? 0)
          .attr("y", y(cn) ?? 0)
          .attr("width", x.bandwidth())
          .attr("height", y.bandwidth())
          .attr("fill", colorScale(val))
          .attr("rx", 2)
          .attr("cursor", "crosshair")
          .on("mousemove", (event) => {
            const [px, py] = d3.pointer(event, container);
            tooltip
              .style("display", "block")
              .style("left", `${px + 12}px`)
              .style("top", `${py - 10}px`).html(`
                <div class="text-xs font-medium mb-1">${cn} - ${dates[si]}</div>
                <div class="text-xs">${metricLabel}: <span class="font-bold">${val.toFixed(1)}</span></div>
              `);
          })
          .on("mouseleave", () => {
            tooltip.style("display", "none");
          });

        // Value text in cell if cell is large enough
        if (x.bandwidth() > 30 && y.bandwidth() > 18) {
          g.append("text")
            .attr("x", (x(dl) ?? 0) + x.bandwidth() / 2)
            .attr("y", (y(cn) ?? 0) + y.bandwidth() / 2)
            .attr("text-anchor", "middle")
            .attr("alignment-baseline", "central")
            .attr("fill", "#fff")
            .attr("font-size", 9)
            .attr("font-family", chartTheme.font)
            .attr("pointer-events", "none")
            .text(val.toFixed(1));
        }
      });
    });

    // Color bar legend on right
    const legendHeight = Math.min(innerH, 150);
    const legendWidth = 12;
    const legendX = innerW + 15;
    const legendY = (innerH - legendHeight) / 2;

    const defs = svg.append("defs");
    const gradient = defs
      .append("linearGradient")
      .attr("id", "heatmap-gradient")
      .attr("x1", "0%")
      .attr("x2", "0%")
      .attr("y1", "100%")
      .attr("y2", "0%");

    const nStops = 10;
    for (let i = 0; i <= nStops; i++) {
      const t = i / nStops;
      const v = minV + t * (maxV - minV);
      gradient
        .append("stop")
        .attr("offset", `${t * 100}%`)
        .attr("stop-color", colorScale(v));
    }

    const lg = svg
      .append("g")
      .attr(
        "transform",
        `translate(${margin.left + legendX},${margin.top + legendY})`,
      );

    lg.append("rect")
      .attr("width", legendWidth)
      .attr("height", legendHeight)
      .attr("fill", "url(#heatmap-gradient)")
      .attr("rx", 2);

    lg.append("text")
      .attr("x", legendWidth + 4)
      .attr("y", 0)
      .attr("fill", chartTheme.text)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .attr("alignment-baseline", "hanging")
      .text(maxV.toFixed(1));

    lg.append("text")
      .attr("x", legendWidth + 4)
      .attr("y", legendHeight)
      .attr("fill", chartTheme.text)
      .attr("font-size", 9)
      .attr("font-family", chartTheme.font)
      .attr("alignment-baseline", "baseline")
      .text(minV.toFixed(1));
  }, [dates, cornerNumbers, values, metric, metricLabel]);

  useEffect(() => {
    render();
    const observer = new ResizeObserver(render);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [render]);

  if (dates.length === 0 || cornerNumbers.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-[var(--text-muted)]">
        No corner heatmap data available
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative w-full">
      <svg ref={svgRef} className="w-full" />
      <div
        ref={tooltipRef}
        className="pointer-events-none absolute hidden rounded border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 shadow-lg"
        style={{ zIndex: 10 }}
      />
    </div>
  );
}
