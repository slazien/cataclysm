"use client";

import { useMemo, useState } from "react";
import * as d3 from "d3";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getLlmDashboard,
  getLlmRecentEvents,
  getLlmRoutingStatus,
  setLlmRoutingStatus,
  type LlmCallsByModelRow,
  type LlmCostByTaskRow,
  type LlmCostTimeseriesRow,
  type LlmErrorBreakdownRow,
  type LlmLatencyTimeseriesRow,
  type LlmRecentEvent,
  type LlmTaskModelCostRow,
  type LlmTokenTimeseriesRow,
} from "@/lib/admin-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import TaskRoutingConfig from "./TaskRoutingConfig";

/* ─── Formatting helpers ──────────────────────────────────────────────── */

function formatUsd(value: number): string {
  return `$${value.toFixed(value >= 1 ? 2 : 4)}`;
}

function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return value.toFixed(0);
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function isForbidden(error: unknown): boolean {
  return (
    error instanceof Error &&
    (error.message.includes("401") || error.message.includes("403"))
  );
}

function toDate(dateStr: string): Date {
  return new Date(`${dateStr}T00:00:00Z`);
}

/* ─── Shared axis renderer ────────────────────────────────────────────── */

function AxisG({
  transform,
  axis,
}: {
  transform: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  axis: any;
}) {
  return (
    <g
      transform={transform}
      ref={(node) => {
        if (node) {
          const g = d3.select<SVGGElement, unknown>(node);
          g.call(axis);
          g.selectAll("text")
            .attr("fill", "#94a3b8")
            .style("font-size", "11px");
          g.selectAll("path,line").attr("stroke", "#334155");
        }
      }}
    />
  );
}

/* ─── KPI Card ────────────────────────────────────────────────────────── */

function KpiCard({
  label,
  value,
  hint,
  valueClassName,
}: {
  label: string;
  value: string;
  hint: string;
  valueClassName?: string;
}) {
  return (
    <Card className="gap-3 border-slate-700/40 bg-slate-950/60 py-4">
      <CardHeader className="px-4 pb-0">
        <CardDescription className="text-xs uppercase tracking-wide text-slate-400">
          {label}
        </CardDescription>
      </CardHeader>
      <CardContent className="px-4">
        <div
          className={`text-2xl font-semibold ${valueClassName ?? "text-slate-100"}`}
        >
          {value}
        </div>
        <div className="text-xs text-slate-400">{hint}</div>
      </CardContent>
    </Card>
  );
}

/* ─── 1. Cost + Calls Trend (dual axis) ───────────────────────────────── */

function CostCallsTrendChart({ data }: { data: LlmCostTimeseriesRow[] }) {
  const chart = useMemo(() => {
    if (!data.length) return null;

    const width = 760;
    const height = 280;
    const margin = { top: 18, right: 56, bottom: 32, left: 56 };

    const dates = data.map((r) => toDate(r.date));
    const maxCost = d3.max(data, (d) => d.cost_usd) ?? 0;
    const maxCalls = d3.max(data, (d) => d.calls) ?? 0;

    const x = d3
      .scaleTime()
      .domain(d3.extent(dates) as [Date, Date])
      .range([margin.left, width - margin.right]);

    const yCost = d3
      .scaleLinear()
      .domain([0, maxCost * 1.2 || 1])
      .nice()
      .range([height - margin.bottom, margin.top]);

    const yCalls = d3
      .scaleLinear()
      .domain([0, maxCalls * 1.3 || 1])
      .nice()
      .range([height - margin.bottom, margin.top]);

    const dateFormatter = d3.utcFormat("%b %d");
    const axisX = d3
      .axisBottom(x)
      .ticks(6)
      .tickFormat((v) => dateFormatter(v as Date));
    const axisYCost = d3
      .axisLeft(yCost)
      .ticks(5)
      .tickFormat((n) => `$${Number(n).toFixed(3)}`);
    const axisYCalls = d3
      .axisRight(yCalls)
      .ticks(5)
      .tickFormat((n) => `${Number(n).toFixed(0)}`);

    const area = d3
      .area<LlmCostTimeseriesRow>()
      .x((d) => x(toDate(d.date)))
      .y0(yCost(0))
      .y1((d) => yCost(d.cost_usd))
      .curve(d3.curveMonotoneX);

    const line = d3
      .line<LlmCostTimeseriesRow>()
      .x((d) => x(toDate(d.date)))
      .y((d) => yCost(d.cost_usd))
      .curve(d3.curveMonotoneX);

    const barWidth = Math.max(
      2,
      ((width - margin.left - margin.right) / data.length) * 0.35,
    );

    return {
      width,
      height,
      margin,
      x,
      yCost,
      yCalls,
      axisX,
      axisYCost,
      axisYCalls,
      area,
      line,
      barWidth,
    };
  }, [data]);

  if (!chart) {
    return (
      <div className="flex h-[280px] items-center justify-center text-sm text-slate-400">
        No data yet.
      </div>
    );
  }

  return (
    <svg
      viewBox={`0 0 ${chart.width} ${chart.height}`}
      className="h-[280px] w-full"
    >
      <defs>
        <linearGradient id="cost-area-grad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.55} />
          <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0.08} />
        </linearGradient>
      </defs>

      {/* Call count bars (behind area) */}
      {data.map((row) => {
        const xPos = chart.x(toDate(row.date));
        const yPos = chart.yCalls(row.calls);
        const barH = chart.yCalls(0) - yPos;
        return (
          <rect
            key={`bar-${row.date}`}
            x={xPos - chart.barWidth / 2}
            y={yPos}
            width={chart.barWidth}
            height={Math.max(0, barH)}
            rx={1.5}
            fill="#6366f1"
            opacity={0.35}
          />
        );
      })}

      {/* Cost area + line */}
      <path d={chart.area(data) ?? ""} fill="url(#cost-area-grad)" />
      <path
        d={chart.line(data) ?? ""}
        fill="none"
        stroke="#38bdf8"
        strokeWidth={2.2}
      />
      {data.map((row) => (
        <circle
          key={`dot-${row.date}`}
          cx={chart.x(toDate(row.date))}
          cy={chart.yCost(row.cost_usd)}
          r={2.6}
          fill="#e2e8f0"
        />
      ))}

      {/* Axes */}
      <AxisG
        transform={`translate(0,${chart.height - chart.margin.bottom})`}
        axis={chart.axisX}
      />
      <AxisG
        transform={`translate(${chart.margin.left},0)`}
        axis={chart.axisYCost}
      />
      <AxisG
        transform={`translate(${chart.width - chart.margin.right},0)`}
        axis={chart.axisYCalls}
      />

      {/* Axis labels */}
      <text
        x={14}
        y={chart.margin.top - 4}
        fill="#38bdf8"
        fontSize="10"
        fontWeight="600"
      >
        $ Cost
      </text>
      <text
        x={chart.width - 14}
        y={chart.margin.top - 4}
        fill="#818cf8"
        fontSize="10"
        fontWeight="600"
        textAnchor="end"
      >
        Calls
      </text>
    </svg>
  );
}

/* ─── 2. Latency Trend (P50 line + P95 band) ─────────────────────────── */

function LatencyTrendChart({ data }: { data: LlmLatencyTimeseriesRow[] }) {
  const chart = useMemo(() => {
    if (!data.length) return null;

    const width = 760;
    const height = 280;
    const margin = { top: 18, right: 20, bottom: 32, left: 56 };

    const dates = data.map((r) => toDate(r.date));
    const maxP95 = d3.max(data, (d) => d.p95) ?? 0;

    const x = d3
      .scaleTime()
      .domain(d3.extent(dates) as [Date, Date])
      .range([margin.left, width - margin.right]);

    const y = d3
      .scaleLinear()
      .domain([0, maxP95 * 1.3 || 100])
      .nice()
      .range([height - margin.bottom, margin.top]);

    const dateFormatter = d3.utcFormat("%b %d");
    const axisX = d3
      .axisBottom(x)
      .ticks(6)
      .tickFormat((v) => dateFormatter(v as Date));
    const axisY = d3
      .axisLeft(y)
      .ticks(5)
      .tickFormat((n) => `${Number(n).toFixed(0)}ms`);

    const bandArea = d3
      .area<LlmLatencyTimeseriesRow>()
      .x((d) => x(toDate(d.date)))
      .y0((d) => y(d.p50))
      .y1((d) => y(d.p95))
      .curve(d3.curveMonotoneX);

    const p50Line = d3
      .line<LlmLatencyTimeseriesRow>()
      .x((d) => x(toDate(d.date)))
      .y((d) => y(d.p50))
      .curve(d3.curveMonotoneX);

    const p95Line = d3
      .line<LlmLatencyTimeseriesRow>()
      .x((d) => x(toDate(d.date)))
      .y((d) => y(d.p95))
      .curve(d3.curveMonotoneX);

    return {
      width,
      height,
      margin,
      x,
      y,
      axisX,
      axisY,
      bandArea,
      p50Line,
      p95Line,
    };
  }, [data]);

  if (!chart) {
    return (
      <div className="flex h-[280px] items-center justify-center text-sm text-slate-400">
        No latency data.
      </div>
    );
  }

  return (
    <svg
      viewBox={`0 0 ${chart.width} ${chart.height}`}
      className="h-[280px] w-full"
    >
      <defs>
        <linearGradient id="latency-band-grad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.35} />
          <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.08} />
        </linearGradient>
      </defs>

      <path d={chart.bandArea(data) ?? ""} fill="url(#latency-band-grad)" />

      <path
        d={chart.p95Line(data) ?? ""}
        fill="none"
        stroke="#f59e0b"
        strokeWidth={1.5}
        strokeDasharray="6,3"
      />

      <path
        d={chart.p50Line(data) ?? ""}
        fill="none"
        stroke="#fb923c"
        strokeWidth={2.2}
      />

      {data.map((row) => (
        <circle
          key={`p50-${row.date}`}
          cx={chart.x(toDate(row.date))}
          cy={chart.y(row.p50)}
          r={2.4}
          fill="#fdba74"
        />
      ))}

      <AxisG
        transform={`translate(0,${chart.height - chart.margin.bottom})`}
        axis={chart.axisX}
      />
      <AxisG
        transform={`translate(${chart.margin.left},0)`}
        axis={chart.axisY}
      />

      {/* Legend */}
      <g
        transform={`translate(${chart.width - chart.margin.right - 120}, ${chart.margin.top + 4})`}
      >
        <line x1={0} x2={16} y1={0} y2={0} stroke="#fb923c" strokeWidth={2.2} />
        <text x={20} y={4} fill="#94a3b8" fontSize="10">
          P50
        </text>
        <line
          x1={50}
          x2={66}
          y1={0}
          y2={0}
          stroke="#f59e0b"
          strokeWidth={1.5}
          strokeDasharray="6,3"
        />
        <text x={70} y={4} fill="#94a3b8" fontSize="10">
          P95
        </text>
      </g>
    </svg>
  );
}

/* ─── 3. Token Usage Over Time (stacked area) ─────────────────────────── */

function TokenUsageChart({ data }: { data: LlmTokenTimeseriesRow[] }) {
  const chart = useMemo(() => {
    if (!data.length) return null;

    const width = 760;
    const height = 280;
    const margin = { top: 18, right: 20, bottom: 32, left: 60 };

    const dates = data.map((r) => toDate(r.date));

    type StackKey =
      | "cache_creation_tokens"
      | "cached_tokens"
      | "input_tokens"
      | "output_tokens";
    const keys: StackKey[] = [
      "cache_creation_tokens",
      "cached_tokens",
      "input_tokens",
      "output_tokens",
    ];

    const stack = d3
      .stack<LlmTokenTimeseriesRow, StackKey>()
      .keys(keys)
      .order(d3.stackOrderNone)
      .offset(d3.stackOffsetNone);

    const series = stack(data);

    const maxY = d3.max(series, (s) => d3.max(s, (d) => d[1])) ?? 0;

    const x = d3
      .scaleTime()
      .domain(d3.extent(dates) as [Date, Date])
      .range([margin.left, width - margin.right]);

    const y = d3
      .scaleLinear()
      .domain([0, maxY * 1.1 || 1000])
      .nice()
      .range([height - margin.bottom, margin.top]);

    const dateFormatter = d3.utcFormat("%b %d");
    const axisX = d3
      .axisBottom(x)
      .ticks(6)
      .tickFormat((v) => dateFormatter(v as Date));
    const axisY = d3
      .axisLeft(y)
      .ticks(5)
      .tickFormat((n) => formatTokens(Number(n)));

    const areaGen = d3
      .area<d3.SeriesPoint<LlmTokenTimeseriesRow>>()
      .x((_, i) => x(toDate(data[i].date)))
      .y0((d) => y(d[0]))
      .y1((d) => y(d[1]))
      .curve(d3.curveMonotoneX);

    const colorMap: Record<StackKey, string> = {
      output_tokens: "#22c55e",
      input_tokens: "#3b82f6",
      cached_tokens: "#06b6d4",
      cache_creation_tokens: "#f59e0b",
    };

    const labelMap: Record<StackKey, string> = {
      output_tokens: "Output",
      input_tokens: "Input",
      cached_tokens: "Cached",
      cache_creation_tokens: "Cache Write",
    };

    return {
      width,
      height,
      margin,
      series,
      areaGen,
      colorMap,
      labelMap,
      keys,
      axisX,
      axisY,
    };
  }, [data]);

  if (!chart) {
    return (
      <div className="flex h-[280px] items-center justify-center text-sm text-slate-400">
        No token data.
      </div>
    );
  }

  return (
    <svg
      viewBox={`0 0 ${chart.width} ${chart.height}`}
      className="h-[280px] w-full"
    >
      {chart.series.map((s) => {
        const key = s.key as keyof typeof chart.colorMap;
        return (
          <path
            key={key}
            d={chart.areaGen(s) ?? ""}
            fill={chart.colorMap[key]}
            fillOpacity={0.5}
            stroke={chart.colorMap[key]}
            strokeWidth={1.5}
          />
        );
      })}

      <AxisG
        transform={`translate(0,${chart.height - chart.margin.bottom})`}
        axis={chart.axisX}
      />
      <AxisG
        transform={`translate(${chart.margin.left},0)`}
        axis={chart.axisY}
      />

      {/* Legend */}
      <g
        transform={`translate(${chart.margin.left + 8}, ${chart.margin.top + 2})`}
      >
        {[...chart.keys].reverse().map((key, i) => (
          <g key={key} transform={`translate(${i * 90}, 0)`}>
            <rect
              width={10}
              height={10}
              rx={2}
              fill={chart.colorMap[key]}
              fillOpacity={0.7}
            />
            <text x={14} y={9} fill="#94a3b8" fontSize="10">
              {chart.labelMap[key]}
            </text>
          </g>
        ))}
      </g>
    </svg>
  );
}

/* ─── 4. Model Cost Breakdown (horizontal stacked bars) ───────────────── */

function ModelCostBreakdown({ data }: { data: LlmCallsByModelRow[] }) {
  const chart = useMemo(() => {
    if (!data.length) return null;

    const sorted = [...data]
      .sort((a, b) => b.cost_usd - a.cost_usd)
      .slice(0, 8);
    const width = 760;
    const barHeight = 30;
    const gap = 6;
    const margin = { top: 12, right: 90, bottom: 12, left: 180 };
    const height =
      margin.top + sorted.length * (barHeight + gap) + margin.bottom;

    const maxCost = d3.max(sorted, (d) => d.cost_usd) ?? 0;

    const x = d3
      .scaleLinear()
      .domain([0, maxCost * 1.2 || 1])
      .range([margin.left, width - margin.right]);

    const colorScale = d3
      .scaleOrdinal<string, string>()
      .domain(sorted.map((d) => `${d.provider}/${d.model}`))
      .range([
        "#0284c7",
        "#06b6d4",
        "#16a34a",
        "#84cc16",
        "#f59e0b",
        "#f97316",
        "#ef4444",
        "#8b5cf6",
      ]);

    return { sorted, width, height, barHeight, gap, margin, x, colorScale };
  }, [data]);

  if (!chart) {
    return (
      <div className="flex h-[200px] items-center justify-center text-sm text-slate-400">
        No model data.
      </div>
    );
  }

  return (
    <svg
      viewBox={`0 0 ${chart.width} ${chart.height}`}
      className="w-full"
      style={{ height: chart.height }}
    >
      {chart.sorted.map((row, i) => {
        const label = `${row.provider}/${row.model}`;
        const yPos = chart.margin.top + i * (chart.barHeight + chart.gap);
        const barW = Math.max(0, chart.x(row.cost_usd) - chart.margin.left);
        return (
          <g key={label}>
            <rect
              x={chart.margin.left}
              y={yPos}
              width={barW}
              height={chart.barHeight}
              rx={4}
              fill={chart.colorScale(label)}
              opacity={0.78}
            />
            <text
              x={chart.margin.left - 8}
              y={yPos + chart.barHeight / 2 + 4}
              textAnchor="end"
              fill="#cbd5e1"
              fontSize="11"
            >
              {row.model}
            </text>
            <text
              x={chart.margin.left + barW + 8}
              y={yPos + chart.barHeight / 2 + 4}
              fill="#e2e8f0"
              fontSize="11"
            >
              {formatUsd(row.cost_usd)} · {row.calls.toFixed(0)} calls
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* ─── 5. Task Cost Bar Chart (enhanced) ───────────────────────────────── */

function TaskCostBarChart({ data }: { data: LlmCostByTaskRow[] }) {
  const chart = useMemo(() => {
    if (!data.length) return null;

    const top = [...data]
      .sort((a, b) => b.cost_usd - a.cost_usd)
      .slice(0, 10);
    const width = 760;
    const height = 320;
    const margin = { top: 12, right: 100, bottom: 24, left: 180 };

    const x = d3
      .scaleLinear()
      .domain([0, (d3.max(top, (d) => d.cost_usd) ?? 0) * 1.2 || 1])
      .range([margin.left, width - margin.right]);
    const y = d3
      .scaleBand<string>()
      .domain(top.map((d) => d.task))
      .range([margin.top, height - margin.bottom])
      .padding(0.2);

    return { top, width, height, margin, x, y };
  }, [data]);

  if (!chart) {
    return (
      <div className="flex h-[320px] items-center justify-center text-sm text-slate-400">
        No data yet.
      </div>
    );
  }

  function barColor(errorRate: number): string {
    if (errorRate > 0.05) return "#ef4444";
    if (errorRate > 0.02) return "#f59e0b";
    return "#06b6d4";
  }

  return (
    <svg
      viewBox={`0 0 ${chart.width} ${chart.height}`}
      className="h-[320px] w-full"
    >
      {chart.top.map((row) => {
        const yPos = chart.y(row.task) ?? 0;
        const xStart = chart.x(0);
        const barW = Math.max(0, chart.x(row.cost_usd) - xStart);
        const cpc = row.calls > 0 ? row.cost_usd / row.calls : 0;
        return (
          <g key={row.task}>
            <rect
              x={xStart}
              y={yPos}
              width={barW}
              height={chart.y.bandwidth()}
              rx={6}
              fill={barColor(row.error_rate)}
              opacity={0.72}
            />
            <text
              x={chart.margin.left - 10}
              y={yPos + chart.y.bandwidth() / 2 + 4}
              textAnchor="end"
              fill="#cbd5e1"
              fontSize="11"
            >
              {row.task}
            </text>
            {barW > 60 && (
              <text
                x={xStart + barW - 6}
                y={yPos + chart.y.bandwidth() / 2 + 4}
                textAnchor="end"
                fill="#020617"
                fontSize="10"
                fontWeight="600"
              >
                {formatUsd(cpc)}/call
              </text>
            )}
            <text
              x={xStart + barW + 8}
              y={yPos + chart.y.bandwidth() / 2 + 4}
              fill="#e2e8f0"
              fontSize="11"
            >
              {formatUsd(row.cost_usd)}
            </text>
          </g>
        );
      })}
      <line
        x1={chart.margin.left}
        x2={chart.width - chart.margin.right}
        y1={chart.height - chart.margin.bottom + 2}
        y2={chart.height - chart.margin.bottom + 2}
        stroke="#334155"
        strokeWidth={1.5}
      />
    </svg>
  );
}

/* ─── 6. Cache Efficiency Mini-Chart ──────────────────────────────────── */

function CacheEfficiencyChart({ data }: { data: LlmTokenTimeseriesRow[] }) {
  const chart = useMemo(() => {
    if (!data.length) return null;

    const width = 760;
    const height = 140;
    const margin = { top: 12, right: 20, bottom: 28, left: 60 };

    const dates = data.map((r) => toDate(r.date));
    const maxCached = d3.max(data, (d) => d.cached_tokens) ?? 0;

    const x = d3
      .scaleTime()
      .domain(d3.extent(dates) as [Date, Date])
      .range([margin.left, width - margin.right]);

    const y = d3
      .scaleLinear()
      .domain([0, maxCached * 1.2 || 1000])
      .nice()
      .range([height - margin.bottom, margin.top]);

    const dateFormatter = d3.utcFormat("%b %d");
    const axisX = d3
      .axisBottom(x)
      .ticks(6)
      .tickFormat((v) => dateFormatter(v as Date));
    const axisY = d3
      .axisLeft(y)
      .ticks(3)
      .tickFormat((n) => formatTokens(Number(n)));

    const area = d3
      .area<LlmTokenTimeseriesRow>()
      .x((d) => x(toDate(d.date)))
      .y0(y(0))
      .y1((d) => y(d.cached_tokens))
      .curve(d3.curveMonotoneX);

    const line = d3
      .line<LlmTokenTimeseriesRow>()
      .x((d) => x(toDate(d.date)))
      .y((d) => y(d.cached_tokens))
      .curve(d3.curveMonotoneX);

    return { width, height, margin, axisX, axisY, area, line };
  }, [data]);

  if (!chart) return null;

  return (
    <svg
      viewBox={`0 0 ${chart.width} ${chart.height}`}
      className="h-[140px] w-full"
    >
      <defs>
        <linearGradient id="cache-area-grad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.45} />
          <stop offset="100%" stopColor="#06b6d4" stopOpacity={0.05} />
        </linearGradient>
      </defs>
      <path d={chart.area(data) ?? ""} fill="url(#cache-area-grad)" />
      <path
        d={chart.line(data) ?? ""}
        fill="none"
        stroke="#22d3ee"
        strokeWidth={1.8}
      />
      <AxisG
        transform={`translate(0,${chart.height - chart.margin.bottom})`}
        axis={chart.axisX}
      />
      <AxisG
        transform={`translate(${chart.margin.left},0)`}
        axis={chart.axisY}
      />
    </svg>
  );
}

/* ─── 7. Task x Model Heatmap ─────────────────────────────────────────── */

function TaskModelHeatmap({ data }: { data: LlmTaskModelCostRow[] }) {
  const chart = useMemo(() => {
    if (!data.length) return null;

    const byTask = d3.rollup(
      data,
      (rows) => d3.sum(rows, (r) => r.cost_usd),
      (row) => row.task,
    );
    const byModel = d3.rollup(
      data,
      (rows) => d3.sum(rows, (r) => r.cost_usd),
      (row) => `${row.provider}/${row.model}`,
    );

    const tasks = [...byTask.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map((item) => item[0]);
    const models = [...byModel.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map((item) => item[0]);

    const cells = data
      .filter(
        (row) =>
          tasks.includes(row.task) &&
          models.includes(`${row.provider}/${row.model}`),
      )
      .map((row) => ({ ...row, modelKey: `${row.provider}/${row.model}` }));

    const width = 760;
    const height = 340;
    const margin = { top: 80, right: 20, bottom: 20, left: 180 };
    const x = d3
      .scaleBand<string>()
      .domain(models)
      .range([margin.left, width - margin.right])
      .padding(0.08);
    const y = d3
      .scaleBand<string>()
      .domain(tasks)
      .range([margin.top, height - margin.bottom])
      .padding(0.08);

    const maxCost = d3.max(cells, (row) => row.cost_usd) ?? 0;
    const color = d3
      .scaleSequential(d3.interpolateYlGnBu)
      .domain([0, maxCost || 1]);

    return { width, height, x, y, color, tasks, models, cells };
  }, [data]);

  if (!chart) {
    return (
      <div className="flex h-[340px] items-center justify-center text-sm text-slate-400">
        No data yet.
      </div>
    );
  }

  return (
    <svg
      viewBox={`0 0 ${chart.width} ${chart.height}`}
      className="h-[340px] w-full"
    >
      {chart.cells.map((cell) => {
        const cx = chart.x(cell.modelKey) ?? 0;
        const cy = chart.y(cell.task) ?? 0;
        return (
          <g key={`${cell.task}-${cell.modelKey}`}>
            <rect
              x={cx}
              y={cy}
              width={chart.x.bandwidth()}
              height={chart.y.bandwidth()}
              rx={4}
              fill={chart.color(cell.cost_usd)}
              stroke="#0f172a"
              strokeWidth={0.8}
            />
            <text
              x={cx + chart.x.bandwidth() / 2}
              y={cy + chart.y.bandwidth() / 2 + 3}
              textAnchor="middle"
              fill="#020617"
              fontSize="10"
              fontWeight="600"
            >
              {cell.cost_usd.toFixed(4)}
            </text>
          </g>
        );
      })}

      {chart.tasks.map((task) => (
        <text
          key={task}
          x={172}
          y={(chart.y(task) ?? 0) + chart.y.bandwidth() / 2 + 4}
          textAnchor="end"
          fill="#cbd5e1"
          fontSize="11"
        >
          {task}
        </text>
      ))}

      {chart.models.map((model) => (
        <text
          key={model}
          transform={`translate(${(chart.x(model) ?? 0) + chart.x.bandwidth() / 2},72) rotate(-28)`}
          textAnchor="start"
          fill="#cbd5e1"
          fontSize="10"
        >
          {model}
        </text>
      ))}
    </svg>
  );
}

/* ─── 8. Error Breakdown Table ────────────────────────────────────────── */

function ErrorBreakdownTable({ data }: { data: LlmErrorBreakdownRow[] }) {
  if (!data.length) return null;

  return (
    <Card className="border-slate-700/40 bg-slate-900/70 py-4">
      <CardHeader className="px-4 pb-2">
        <CardTitle className="text-base">Error Breakdown</CardTitle>
        <CardDescription>Top errors by occurrence count.</CardDescription>
      </CardHeader>
      <CardContent className="px-4">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-left text-xs uppercase tracking-wide text-slate-400">
                <th className="py-2 pr-3">Error Message</th>
                <th className="py-2 pr-3 text-right">Count</th>
                <th className="py-2 text-right">Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, i) => (
                <tr key={i} className="border-b border-slate-800/70">
                  <td
                    className="max-w-[400px] truncate py-2 pr-3 text-slate-300"
                    title={row.error}
                  >
                    {row.error.length > 60
                      ? `${row.error.slice(0, 60)}...`
                      : row.error}
                  </td>
                  <td className="py-2 pr-3 text-right">
                    <Badge
                      variant="outline"
                      className="border-red-700/60 bg-red-950/40 text-red-300"
                    >
                      {row.count}
                    </Badge>
                  </td>
                  <td className="py-2 text-right text-slate-400">
                    {timeAgo(row.last_seen)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

/* ─── 9. Recent Events Log ────────────────────────────────────────────── */

function RecentEventsLog() {
  const { data: events, isPending } = useQuery({
    queryKey: ["admin", "llm-events"],
    queryFn: () => getLlmRecentEvents(50),
    refetchInterval: 30000,
  });

  if (isPending) {
    return (
      <Card className="border-slate-700/40 bg-slate-900/70 py-4">
        <CardHeader className="px-4 pb-2">
          <CardTitle className="text-base">Recent Events</CardTitle>
        </CardHeader>
        <CardContent className="px-4">
          <div className="animate-pulse text-sm text-slate-400">
            Loading events...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!events?.length) {
    return (
      <Card className="border-slate-700/40 bg-slate-900/70 py-4">
        <CardHeader className="px-4 pb-2">
          <CardTitle className="text-base">Recent Events</CardTitle>
          <CardDescription>Last 50 LLM calls in real time.</CardDescription>
        </CardHeader>
        <CardContent className="px-4">
          <div className="text-sm text-slate-400">No recent events.</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-slate-700/40 bg-slate-900/70 py-4">
      <CardHeader className="px-4 pb-2">
        <CardTitle className="text-base">Recent Events</CardTitle>
        <CardDescription>
          Last 50 LLM calls, auto-refreshing every 30s.
        </CardDescription>
      </CardHeader>
      <CardContent className="px-4">
        <div className="max-h-[400px] overflow-y-auto">
          <table className="w-full min-w-[780px] border-collapse text-sm">
            <thead className="sticky top-0 bg-slate-900">
              <tr className="border-b border-slate-700 text-left text-xs uppercase tracking-wide text-slate-400">
                <th className="py-2 pr-3">Time</th>
                <th className="py-2 pr-3">Task</th>
                <th className="py-2 pr-3">Model</th>
                <th className="py-2 pr-3 text-right">Latency</th>
                <th className="py-2 pr-3 text-right">Tokens</th>
                <th className="py-2 pr-3 text-right">Cost</th>
                <th className="py-2 text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev: LlmRecentEvent, i: number) => (
                <tr key={i} className="border-b border-slate-800/70">
                  <td className="py-1.5 pr-3 text-slate-400">
                    {timeAgo(ev.timestamp)}
                  </td>
                  <td className="py-1.5 pr-3 text-slate-200">{ev.task}</td>
                  <td className="py-1.5 pr-3 text-slate-300">{ev.model}</td>
                  <td className="py-1.5 pr-3 text-right text-slate-300">
                    {ev.latency_ms.toFixed(0)}ms
                  </td>
                  <td className="py-1.5 pr-3 text-right text-slate-400">
                    {formatTokens(ev.input_tokens)}+
                    {formatTokens(ev.output_tokens)}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-sky-300">
                    {formatUsd(ev.cost_usd)}
                  </td>
                  <td className="py-1.5 text-center">
                    {ev.success ? (
                      <span className="text-emerald-400" title="Success">
                        &#10003;
                      </span>
                    ) : (
                      <span
                        className="text-red-400"
                        title={ev.error ?? "Error"}
                      >
                        &#10007;
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

/* ─── Main Dashboard ──────────────────────────────────────────────────── */

export function LlmCostDashboard() {
  const queryClient = useQueryClient();
  const [days, setDays] = useState(30);
  const [sortKey, setSortKey] = useState<"cost_usd" | "calls" | "error_rate">(
    "cost_usd",
  );

  const statusQuery = useQuery({
    queryKey: ["admin", "llm-routing-status"],
    queryFn: getLlmRoutingStatus,
  });

  const dashboardQuery = useQuery({
    queryKey: ["admin", "llm-dashboard", days],
    queryFn: () => getLlmDashboard(days),
  });

  const toggleMutation = useMutation({
    mutationFn: (enabled: boolean) => setLlmRoutingStatus(enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["admin", "llm-routing-status"],
      });
      queryClient.invalidateQueries({ queryKey: ["admin", "llm-dashboard"] });
    },
  });

  const hasForbidden =
    isForbidden(statusQuery.error) || isForbidden(dashboardQuery.error);

  const sortedTasks = useMemo(() => {
    const tasks = dashboardQuery.data?.cost_by_task ?? [];
    return [...tasks].sort((a, b) => {
      if (sortKey === "calls") return b.calls - a.calls;
      if (sortKey === "error_rate") return b.error_rate - a.error_rate;
      return b.cost_usd - a.cost_usd;
    });
  }, [dashboardQuery.data?.cost_by_task, sortKey]);

  if (statusQuery.isPending || dashboardQuery.isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">
        <div className="animate-pulse text-lg">Loading dashboard...</div>
      </div>
    );
  }

  if (hasForbidden) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
        <div className="max-w-md rounded-xl border border-rose-700/40 bg-slate-900/80 p-6 text-center">
          <h1 className="text-xl font-semibold text-rose-300">Access denied</h1>
          <p className="mt-2 text-sm text-slate-300">
            This dashboard is restricted to configured admin accounts.
          </p>
        </div>
      </div>
    );
  }

  if (
    statusQuery.isError ||
    dashboardQuery.isError ||
    !statusQuery.data ||
    !dashboardQuery.data
  ) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
        <div className="rounded-xl border border-rose-700/40 bg-slate-900/80 p-6 text-center">
          <h1 className="text-xl font-semibold text-rose-300">
            Dashboard unavailable
          </h1>
          <p className="mt-2 text-sm text-slate-300">
            {(statusQuery.error as Error | undefined)?.message ??
              (dashboardQuery.error as Error | undefined)?.message ??
              "Unknown error"}
          </p>
        </div>
      </div>
    );
  }

  const {
    kpis,
    cost_timeseries,
    calls_by_model,
    cost_by_task,
    task_model_cost_matrix,
    latency_timeseries,
    token_timeseries,
    error_breakdown,
  } = dashboardQuery.data;
  const routing = statusQuery.data;

  const errorRateColor =
    kpis.error_rate > 0.05
      ? "text-red-400"
      : kpis.error_rate > 0.02
        ? "text-amber-400"
        : "text-slate-100";

  const deltaCostHint =
    kpis.delta_cost_pct !== null
      ? `${kpis.delta_cost_pct >= 0 ? "+" : ""}${kpis.delta_cost_pct.toFixed(1)}% vs prior · ${days}d window`
      : `no prior data · ${days}d window`;

  return (
    <div
      className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100 sm:px-6"
      style={{
        backgroundImage:
          "radial-gradient(circle at 8% 2%, rgba(14,165,233,0.16), transparent 35%), radial-gradient(circle at 92% 8%, rgba(20,184,166,0.15), transparent 34%)",
      }}
    >
      <div className="mx-auto max-w-[1280px] space-y-6">
        {/* ── Header ──────────────────────────────────────────────── */}
        <header className="rounded-xl border border-slate-700/40 bg-slate-900/70 p-4 backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold">
                LLM Routing & Cost Dashboard
              </h1>
              <p className="text-sm text-slate-300">
                Track spend, model usage, and routing behavior in one place.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge
                variant={routing.enabled ? "default" : "outline"}
                className={
                  routing.enabled
                    ? "bg-emerald-600"
                    : "border-slate-500 text-slate-300"
                }
              >
                Routing {routing.enabled ? "Enabled" : "Disabled"}
              </Badge>
              <Button
                variant={routing.enabled ? "destructive" : "default"}
                size="sm"
                disabled={toggleMutation.isPending}
                onClick={() => toggleMutation.mutate(!routing.enabled)}
              >
                {toggleMutation.isPending
                  ? "Updating..."
                  : routing.enabled
                    ? "Disable Routing"
                    : "Enable Routing"}
              </Button>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <span>Source: {routing.source}</span>
            <span>·</span>
            <span>Updated by: {routing.updated_by ?? "n/a"}</span>
            <span>·</span>
            <span>
              Updated at:{" "}
              {routing.updated_at
                ? new Date(routing.updated_at).toLocaleString()
                : "n/a"}
            </span>
          </div>
        </header>

        {/* ── Task Routing Config ─────────────────────────────────── */}
        <section>
          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">
                Task Routing Configuration
              </CardTitle>
              <CardDescription>
                Configure primary model and fallback chain per task.
              </CardDescription>
            </CardHeader>
            <CardContent className="px-4">
              <TaskRoutingConfig />
            </CardContent>
          </Card>
        </section>

        {/* ── KPI Cards: Row 1 ────────────────────────────────────── */}
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="Total Cost"
            value={formatUsd(kpis.total_cost_usd)}
            hint={deltaCostHint}
            valueClassName={
              kpis.delta_cost_pct !== null
                ? kpis.delta_cost_pct > 0
                  ? "text-red-300"
                  : "text-emerald-300"
                : "text-slate-100"
            }
          />
          <KpiCard
            label="Cost / Call"
            value={formatUsd(kpis.cost_per_call)}
            hint="avg across all tasks"
          />
          <KpiCard
            label="Total Calls"
            value={kpis.total_calls.toFixed(0)}
            hint={`~${kpis.daily_avg_calls.toFixed(0)}/day`}
          />
          <KpiCard
            label="P95 Latency"
            value={`${kpis.latency_p95.toFixed(0)} ms`}
            hint={`P50: ${kpis.latency_p50.toFixed(0)} · P99: ${kpis.latency_p99.toFixed(0)}`}
          />
        </section>

        {/* ── KPI Cards: Row 2 ────────────────────────────────────── */}
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="Tokens In / Out"
            value={`${formatTokens(kpis.total_input_tokens)} in / ${formatTokens(kpis.total_output_tokens)} out`}
            hint="total token throughput"
          />
          <KpiCard
            label="Cache Hit Rate"
            value={`${(kpis.cache_hit_rate * 100).toFixed(1)}%`}
            hint={`saving ${formatUsd(kpis.cache_savings_usd)}`}
          />
          <KpiCard
            label="Error Rate"
            value={`${(kpis.error_rate * 100).toFixed(1)}%`}
            hint={`${kpis.total_errors.toFixed(0)} errors`}
            valueClassName={errorRateColor}
          />
          <Card className="gap-2 border-slate-700/40 bg-slate-950/60 py-4">
            <CardHeader className="px-4 pb-0">
              <CardDescription className="text-xs uppercase tracking-wide text-slate-400">
                Window
              </CardDescription>
            </CardHeader>
            <CardContent className="px-4">
              <div className="flex gap-2">
                {[1, 7, 30, 90].map((d) => (
                  <Button
                    key={d}
                    size="xs"
                    variant={days === d ? "default" : "outline"}
                    onClick={() => setDays(d)}
                  >
                    {d}d
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>

        {/* ── Cost & Latency Trend Charts ─────────────────────────── */}
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">Cost + Calls Trend</CardTitle>
              <CardDescription>
                Area = daily cost ($). Bars = daily call count.
              </CardDescription>
            </CardHeader>
            <CardContent className="px-2 pb-2 sm:px-4">
              <CostCallsTrendChart data={cost_timeseries} />
            </CardContent>
          </Card>

          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">Latency Trend</CardTitle>
              <CardDescription>
                P50 line with P95 shaded band.
              </CardDescription>
            </CardHeader>
            <CardContent className="px-2 pb-2 sm:px-4">
              <LatencyTrendChart data={latency_timeseries} />
            </CardContent>
          </Card>
        </section>

        {/* ── Token & Model Breakdown ─────────────────────────────── */}
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">
                Token Usage Over Time
              </CardTitle>
              <CardDescription>
                Stacked area: output, input, cached, cache-write tokens.
              </CardDescription>
            </CardHeader>
            <CardContent className="px-2 pb-2 sm:px-4">
              <TokenUsageChart data={token_timeseries} />
            </CardContent>
          </Card>

          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">
                Model Cost Breakdown
              </CardTitle>
              <CardDescription>
                Horizontal bars by cost, top 8 models.
              </CardDescription>
            </CardHeader>
            <CardContent className="px-2 pb-2 sm:px-4">
              <ModelCostBreakdown data={calls_by_model} />
            </CardContent>
          </Card>
        </section>

        {/* ── Task Cost Bar Chart (enhanced) ──────────────────────── */}
        <section>
          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">Cost by Task</CardTitle>
              <CardDescription>
                Top 10 tasks. Bar color: green (0-2% errors), amber (2-5%), red
                (&gt;5%). Shows cost/call inside each bar.
              </CardDescription>
            </CardHeader>
            <CardContent className="px-2 pb-2 sm:px-4">
              <TaskCostBarChart data={cost_by_task} />
            </CardContent>
          </Card>
        </section>

        {/* ── Prompt Cache Efficiency ─────────────────────────────── */}
        {kpis.total_cached_tokens > 0 && (
          <section>
            <Card className="border-slate-700/40 bg-slate-900/70 py-4">
              <CardHeader className="px-4 pb-2">
                <CardTitle className="text-base">
                  Prompt Cache Efficiency
                </CardTitle>
                <CardDescription>
                  Cache performance and savings from prompt caching.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 px-4">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <div className="rounded-lg border border-slate-700/40 bg-slate-950/60 px-4 py-3">
                    <div className="text-xs uppercase tracking-wide text-slate-400">
                      Cache Hit Rate
                    </div>
                    <div className="mt-1 text-xl font-semibold text-cyan-300">
                      {(kpis.cache_hit_rate * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-700/40 bg-slate-950/60 px-4 py-3">
                    <div className="text-xs uppercase tracking-wide text-slate-400">
                      Tokens Served from Cache
                    </div>
                    <div className="mt-1 text-xl font-semibold text-cyan-300">
                      {formatTokens(kpis.total_cached_tokens)}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-700/40 bg-slate-950/60 px-4 py-3">
                    <div className="text-xs uppercase tracking-wide text-slate-400">
                      Net Savings
                    </div>
                    <div className="mt-1 text-xl font-semibold text-emerald-300">
                      {formatUsd(kpis.cache_savings_usd)}
                    </div>
                  </div>
                </div>
                <CacheEfficiencyChart data={token_timeseries} />
              </CardContent>
            </Card>
          </section>
        )}

        {/* ── Error Breakdown ─────────────────────────────────────── */}
        <section>
          <ErrorBreakdownTable data={error_breakdown} />
        </section>

        {/* ── Task x Model Heatmap ────────────────────────────────── */}
        <section>
          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">
                Task x Model Cost Matrix
              </CardTitle>
              <CardDescription>
                Heatmap to identify expensive routing combinations.
              </CardDescription>
            </CardHeader>
            <CardContent className="px-2 pb-2 sm:px-4">
              <TaskModelHeatmap data={task_model_cost_matrix} />
            </CardContent>
          </Card>
        </section>

        {/* ── Task Cost Table (sortable) ──────────────────────────── */}
        <section>
          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">Task Cost Table</CardTitle>
              <CardDescription>
                Sortable operational view for quick routing decisions.
              </CardDescription>
            </CardHeader>
            <CardContent className="px-4">
              <div className="mb-3 flex flex-wrap gap-2">
                <Button
                  size="xs"
                  variant={sortKey === "cost_usd" ? "default" : "outline"}
                  onClick={() => setSortKey("cost_usd")}
                >
                  Sort: Cost
                </Button>
                <Button
                  size="xs"
                  variant={sortKey === "calls" ? "default" : "outline"}
                  onClick={() => setSortKey("calls")}
                >
                  Sort: Calls
                </Button>
                <Button
                  size="xs"
                  variant={sortKey === "error_rate" ? "default" : "outline"}
                  onClick={() => setSortKey("error_rate")}
                >
                  Sort: Error Rate
                </Button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[860px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-slate-700 text-left text-xs uppercase tracking-wide text-slate-400">
                      <th className="py-2 pr-3">Task</th>
                      <th className="py-2 pr-3">Calls</th>
                      <th className="py-2 pr-3">Cost</th>
                      <th className="py-2 pr-3">Avg Latency</th>
                      <th className="py-2 pr-3">Error Rate</th>
                      <th className="py-2 pr-3">Top Models</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedTasks.map((row) => (
                      <tr
                        key={row.task}
                        className="border-b border-slate-800/70 text-slate-100"
                      >
                        <td className="py-2 pr-3 font-medium">{row.task}</td>
                        <td className="py-2 pr-3 text-slate-300">
                          {row.calls.toFixed(0)}
                        </td>
                        <td className="py-2 pr-3 text-sky-300">
                          {formatUsd(row.cost_usd)}
                        </td>
                        <td className="py-2 pr-3 text-slate-300">
                          {row.avg_latency_ms.toFixed(1)} ms
                        </td>
                        <td className="py-2 pr-3 text-slate-300">
                          {(row.error_rate * 100).toFixed(1)}%
                        </td>
                        <td className="py-2 pr-3 text-slate-300">
                          {row.top_models || "n/a"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* ── Recent Events Log ───────────────────────────────────── */}
        <section>
          <RecentEventsLog />
        </section>
      </div>
    </div>
  );
}
