"use client";

import { useMemo, useState } from "react";
import * as d3 from "d3";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getLlmDashboard,
  getLlmRoutingStatus,
  setLlmRoutingStatus,
  type LlmCallsByModelRow,
  type LlmCostByTaskRow,
  type LlmCostTimeseriesRow,
  type LlmTaskModelCostRow,
} from "@/lib/admin-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import TaskRoutingConfig from "./TaskRoutingConfig";

function formatUsd(value: number): string {
  return `$${value.toFixed(value >= 1 ? 2 : 4)}`;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function isForbidden(error: unknown): boolean {
  return (
    error instanceof Error &&
    (error.message.includes("401") || error.message.includes("403"))
  );
}

function KpiCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <Card className="gap-3 border-slate-700/40 bg-slate-950/60 py-4">
      <CardHeader className="px-4 pb-0">
        <CardDescription className="text-xs uppercase tracking-wide text-slate-400">{label}</CardDescription>
      </CardHeader>
      <CardContent className="px-4">
        <div className="text-2xl font-semibold text-slate-100">{value}</div>
        <div className="text-xs text-slate-400">{hint}</div>
      </CardContent>
    </Card>
  );
}

function CostTrendChart({ data }: { data: LlmCostTimeseriesRow[] }) {
  const svg = useMemo(() => {
    if (!data.length) {
      return null;
    }

    const width = 760;
    const height = 260;
    const margin = { top: 18, right: 20, bottom: 32, left: 56 };

    const dates = data.map((row) => new Date(`${row.date}T00:00:00Z`));
    const maxCost = d3.max(data, (d) => d.cost_usd) ?? 0;

    const x = d3
      .scaleTime()
      .domain(d3.extent(dates) as [Date, Date])
      .range([margin.left, width - margin.right]);

    const y = d3
      .scaleLinear()
      .domain([0, maxCost * 1.2 || 1])
      .nice()
      .range([height - margin.bottom, margin.top]);

    const area = d3
      .area<LlmCostTimeseriesRow>()
      .x((d) => x(new Date(`${d.date}T00:00:00Z`)))
      .y0(y(0))
      .y1((d) => y(d.cost_usd))
      .curve(d3.curveMonotoneX);

    const line = d3
      .line<LlmCostTimeseriesRow>()
      .x((d) => x(new Date(`${d.date}T00:00:00Z`)))
      .y((d) => y(d.cost_usd))
      .curve(d3.curveMonotoneX);

    const dateFormatter = d3.utcFormat("%b %d");
    const axisX = d3
      .axisBottom(x)
      .ticks(6)
      .tickFormat((value) => dateFormatter(value as Date));
    const axisY = d3.axisLeft(y).ticks(5).tickFormat((n) => `$${Number(n).toFixed(3)}`);

    return {
      width,
      height,
      margin,
      x,
      y,
      axisX,
      axisY,
      area,
      line,
    };
  }, [data]);

  if (!svg) {
    return <div className="h-[260px] text-sm text-slate-400">No data yet.</div>;
  }

  return (
    <svg viewBox={`0 0 ${svg.width} ${svg.height}`} className="h-[260px] w-full">
      <defs>
        <linearGradient id="cost-area" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.55} />
          <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0.08} />
        </linearGradient>
      </defs>
      <g
        transform={`translate(0, ${svg.height - svg.margin.bottom})`}
        ref={(node) => {
          if (node) {
            const axisNode = d3.select<SVGGElement, unknown>(node);
            axisNode.call(svg.axisX);
            axisNode.selectAll("text").attr("fill", "#94a3b8").style("font-size", "11px");
            axisNode.selectAll("path,line").attr("stroke", "#334155");
          }
        }}
      />
      <g
        transform={`translate(${svg.margin.left},0)`}
        ref={(node) => {
          if (node) {
            const axisNode = d3.select<SVGGElement, unknown>(node);
            axisNode.call(svg.axisY);
            axisNode.selectAll("text").attr("fill", "#94a3b8").style("font-size", "11px");
            axisNode.selectAll("path,line").attr("stroke", "#334155");
          }
        }}
      />
      <path d={svg.area(data) ?? ""} fill="url(#cost-area)" />
      <path d={svg.line(data) ?? ""} fill="none" stroke="#38bdf8" strokeWidth={2.2} />
      {data.map((row) => (
        <circle
          key={row.date}
          cx={svg.x(new Date(`${row.date}T00:00:00Z`))}
          cy={svg.y(row.cost_usd)}
          r={2.6}
          fill="#e2e8f0"
        />
      ))}
    </svg>
  );
}

function ModelShareChart({ data }: { data: LlmCallsByModelRow[] }) {
  const chart = useMemo(() => {
    if (!data.length) {
      return null;
    }
    const width = 300;
    const height = 250;
    const radius = Math.min(width, height) / 2 - 16;
    const top = [...data].sort((a, b) => b.calls - a.calls).slice(0, 8);
    const pie = d3
      .pie<LlmCallsByModelRow>()
      .sort(null)
      .value((d) => d.calls)(top);
    const arc = d3.arc<d3.PieArcDatum<LlmCallsByModelRow>>().innerRadius(radius * 0.56).outerRadius(radius);
    const color = d3
      .scaleOrdinal<string, string>()
      .domain(top.map((d) => `${d.provider}/${d.model}`))
      .range(["#0284c7", "#06b6d4", "#16a34a", "#84cc16", "#f59e0b", "#f97316", "#ef4444", "#8b5cf6"]);
    return { width, height, radius, pie, arc, color, top };
  }, [data]);

  if (!chart) {
    return <div className="h-[250px] text-sm text-slate-400">No data yet.</div>;
  }

  return (
    <div className="grid grid-cols-[300px_1fr] gap-4 max-md:grid-cols-1">
      <svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="h-[250px] w-full max-w-[300px]">
        <g transform={`translate(${chart.width / 2}, ${chart.height / 2})`}>
          {chart.pie.map((slice) => {
            const key = `${slice.data.provider}/${slice.data.model}`;
            return <path key={key} d={chart.arc(slice) ?? ""} fill={chart.color(key)} stroke="#0f172a" strokeWidth={1.2} />;
          })}
          <text textAnchor="middle" fill="#e2e8f0" fontSize="13" fontWeight="600" y={-2}>
            Models
          </text>
          <text textAnchor="middle" fill="#94a3b8" fontSize="11" y={14}>
            by calls
          </text>
        </g>
      </svg>
      <div className="space-y-2 text-xs">
        {chart.top.map((row) => {
          const label = `${row.provider}/${row.model}`;
          return (
            <div key={label} className="flex items-center justify-between rounded-md border border-slate-700/50 bg-slate-900/60 px-3 py-2">
              <div className="flex items-center gap-2">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: chart.color(label) }} />
                <span className="text-slate-200">{label}</span>
              </div>
              <span className="text-slate-400">{row.calls.toFixed(0)} calls</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TaskCostBarChart({ data }: { data: LlmCostByTaskRow[] }) {
  const chart = useMemo(() => {
    if (!data.length) {
      return null;
    }
    const top = [...data].sort((a, b) => b.cost_usd - a.cost_usd).slice(0, 10);
    const width = 760;
    const height = 320;
    const margin = { top: 12, right: 20, bottom: 24, left: 180 };

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
    return <div className="h-[320px] text-sm text-slate-400">No data yet.</div>;
  }

  return (
    <svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="h-[320px] w-full">
      {chart.top.map((row) => {
        const y = chart.y(row.task) ?? 0;
        const x = chart.x(0);
        const width = Math.max(0, chart.x(row.cost_usd) - x);
        return (
          <g key={row.task}>
            <rect x={x} y={y} width={width} height={chart.y.bandwidth()} rx={6} fill="#06b6d4" opacity={0.72} />
            <text x={chart.margin.left - 10} y={y + chart.y.bandwidth() / 2 + 4} textAnchor="end" fill="#cbd5e1" fontSize="11">
              {row.task}
            </text>
            <text x={x + width + 8} y={y + chart.y.bandwidth() / 2 + 4} fill="#e2e8f0" fontSize="11">
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
      />
    </svg>
  );
}

function TaskModelHeatmap({ data }: { data: LlmTaskModelCostRow[] }) {
  const chart = useMemo(() => {
    if (!data.length) {
      return null;
    }

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
      .filter((row) => tasks.includes(row.task) && models.includes(`${row.provider}/${row.model}`))
      .map((row) => ({ ...row, modelKey: `${row.provider}/${row.model}` }));

    const width = 760;
    const height = 340;
    const margin = { top: 80, right: 20, bottom: 20, left: 180 };
    const x = d3.scaleBand<string>().domain(models).range([margin.left, width - margin.right]).padding(0.08);
    const y = d3.scaleBand<string>().domain(tasks).range([margin.top, height - margin.bottom]).padding(0.08);

    const maxCost = d3.max(cells, (row) => row.cost_usd) ?? 0;
    const color = d3
      .scaleSequential(d3.interpolateYlGnBu)
      .domain([0, maxCost || 1]);

    return { width, height, x, y, color, tasks, models, cells };
  }, [data]);

  if (!chart) {
    return <div className="h-[340px] text-sm text-slate-400">No data yet.</div>;
  }

  return (
    <svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="h-[340px] w-full">
      {chart.cells.map((cell) => {
        const x = chart.x(cell.modelKey) ?? 0;
        const y = chart.y(cell.task) ?? 0;
        return (
          <g key={`${cell.task}-${cell.modelKey}`}>
            <rect
              x={x}
              y={y}
              width={chart.x.bandwidth()}
              height={chart.y.bandwidth()}
              rx={4}
              fill={chart.color(cell.cost_usd)}
              stroke="#0f172a"
              strokeWidth={0.8}
            />
            <text x={x + chart.x.bandwidth() / 2} y={y + chart.y.bandwidth() / 2 + 3} textAnchor="middle" fill="#020617" fontSize="10" fontWeight="600">
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

export function LlmCostDashboard() {
  const queryClient = useQueryClient();
  const [days, setDays] = useState(30);
  const [sortKey, setSortKey] = useState<"cost_usd" | "calls" | "error_rate">("cost_usd");

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
      queryClient.invalidateQueries({ queryKey: ["admin", "llm-routing-status"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "llm-dashboard"] });
    },
  });

  const hasForbidden = isForbidden(statusQuery.error) || isForbidden(dashboardQuery.error);

  const sortedTasks = useMemo(() => {
    const tasks = dashboardQuery.data?.cost_by_task ?? [];
    return [...tasks].sort((a, b) => {
      if (sortKey === "calls") {
        return b.calls - a.calls;
      }
      if (sortKey === "error_rate") {
        return b.error_rate - a.error_rate;
      }
      return b.cost_usd - a.cost_usd;
    });
  }, [dashboardQuery.data?.cost_by_task, sortKey]);

  if (statusQuery.isLoading || dashboardQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">
        <div className="animate-pulse text-lg">Loading dashboard...</div>
      </div>
    );
  }

  if (hasForbidden) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100 p-6">
        <div className="max-w-md rounded-xl border border-rose-700/40 bg-slate-900/80 p-6 text-center">
          <h1 className="text-xl font-semibold text-rose-300">Access denied</h1>
          <p className="mt-2 text-sm text-slate-300">
            This dashboard is restricted to configured admin accounts.
          </p>
        </div>
      </div>
    );
  }

  if (statusQuery.isError || dashboardQuery.isError || !statusQuery.data || !dashboardQuery.data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100 p-6">
        <div className="rounded-xl border border-rose-700/40 bg-slate-900/80 p-6 text-center">
          <h1 className="text-xl font-semibold text-rose-300">Dashboard unavailable</h1>
          <p className="mt-2 text-sm text-slate-300">
            {(statusQuery.error as Error | undefined)?.message ?? (dashboardQuery.error as Error | undefined)?.message ?? "Unknown error"}
          </p>
        </div>
      </div>
    );
  }

  const { kpis, cost_timeseries, calls_by_model, cost_by_task, task_model_cost_matrix } = dashboardQuery.data;
  const routing = statusQuery.data;

  return (
    <div
      className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100 sm:px-6"
      style={{
        backgroundImage:
          "radial-gradient(circle at 8% 2%, rgba(14,165,233,0.16), transparent 35%), radial-gradient(circle at 92% 8%, rgba(20,184,166,0.15), transparent 34%)",
      }}
    >
      <div className="mx-auto max-w-[1280px] space-y-6">
        <header className="rounded-xl border border-slate-700/40 bg-slate-900/70 p-4 backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold">LLM Routing & Cost Dashboard</h1>
              <p className="text-sm text-slate-300">Track spend, model usage, and routing behavior in one place.</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={routing.enabled ? "default" : "outline"} className={routing.enabled ? "bg-emerald-600" : "border-slate-500 text-slate-300"}>
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
            <span>•</span>
            <span>Updated by: {routing.updated_by ?? "n/a"}</span>
            <span>•</span>
            <span>Updated at: {routing.updated_at ? new Date(routing.updated_at).toLocaleString() : "n/a"}</span>
          </div>
        </header>

        <section>
          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">Task Routing Configuration</CardTitle>
              <CardDescription>Configure primary model and fallback chain per task.</CardDescription>
            </CardHeader>
            <CardContent className="px-4">
              <TaskRoutingConfig />
            </CardContent>
          </Card>
        </section>

        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <KpiCard label="Total Cost" value={formatUsd(kpis.total_cost_usd)} hint={`${days}-day window`} />
          <KpiCard label="Total Calls" value={kpis.total_calls.toFixed(0)} hint="All tracked tasks" />
          <KpiCard label="Error Rate" value={formatPercent(kpis.error_rate)} hint={`${kpis.total_errors.toFixed(0)} failed calls`} />
          <KpiCard label="Avg Latency" value={`${kpis.avg_latency_ms.toFixed(1)} ms`} hint="Across all calls" />
          <Card className="gap-2 border-slate-700/40 bg-slate-950/60 py-4">
            <CardHeader className="px-4 pb-0">
              <CardDescription className="text-xs uppercase tracking-wide text-slate-400">Window</CardDescription>
            </CardHeader>
            <CardContent className="px-4">
              <div className="flex gap-2">
                {[7, 30, 90].map((d) => (
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

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">Cost Over Time</CardTitle>
              <CardDescription>Daily spend trend for the selected window.</CardDescription>
            </CardHeader>
            <CardContent className="px-2 pb-2 sm:px-4">
              <CostTrendChart data={cost_timeseries} />
            </CardContent>
          </Card>

          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">Models Used</CardTitle>
              <CardDescription>Call share by provider/model.</CardDescription>
            </CardHeader>
            <CardContent className="px-2 pb-2 sm:px-4">
              <ModelShareChart data={calls_by_model} />
            </CardContent>
          </Card>
        </section>

        <section className="grid grid-cols-1 gap-4">
          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">Cost by Task</CardTitle>
              <CardDescription>Top spenders across tasks.</CardDescription>
            </CardHeader>
            <CardContent className="px-2 pb-2 sm:px-4">
              <TaskCostBarChart data={cost_by_task} />
            </CardContent>
          </Card>

          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">Task × Model Cost Matrix</CardTitle>
              <CardDescription>Heatmap to identify expensive routing combinations.</CardDescription>
            </CardHeader>
            <CardContent className="px-2 pb-2 sm:px-4">
              <TaskModelHeatmap data={task_model_cost_matrix} />
            </CardContent>
          </Card>
        </section>

        <section>
          <Card className="border-slate-700/40 bg-slate-900/70 py-4">
            <CardHeader className="px-4 pb-2">
              <CardTitle className="text-base">Task Cost Table</CardTitle>
              <CardDescription>Sortable operational view for quick routing decisions.</CardDescription>
            </CardHeader>
            <CardContent className="px-4">
              <div className="mb-3 flex flex-wrap gap-2">
                <Button size="xs" variant={sortKey === "cost_usd" ? "default" : "outline"} onClick={() => setSortKey("cost_usd")}>Sort: Cost</Button>
                <Button size="xs" variant={sortKey === "calls" ? "default" : "outline"} onClick={() => setSortKey("calls")}>Sort: Calls</Button>
                <Button size="xs" variant={sortKey === "error_rate" ? "default" : "outline"} onClick={() => setSortKey("error_rate")}>Sort: Error Rate</Button>
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
                      <tr key={row.task} className="border-b border-slate-800/70 text-slate-100">
                        <td className="py-2 pr-3 font-medium">{row.task}</td>
                        <td className="py-2 pr-3 text-slate-300">{row.calls.toFixed(0)}</td>
                        <td className="py-2 pr-3 text-sky-300">{formatUsd(row.cost_usd)}</td>
                        <td className="py-2 pr-3 text-slate-300">{row.avg_latency_ms.toFixed(1)} ms</td>
                        <td className="py-2 pr-3 text-slate-300">{formatPercent(row.error_rate)}</td>
                        <td className="py-2 pr-3 text-slate-300">{row.top_models || "n/a"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
