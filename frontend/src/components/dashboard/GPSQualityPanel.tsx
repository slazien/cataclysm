'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Signal } from 'lucide-react';
import type { GPSQualityReport } from '@/lib/types';
import { cn } from '@/lib/utils';

const GRADE_COLORS: Record<string, string> = {
  A: 'text-emerald-400',
  B: 'text-blue-400',
  C: 'text-yellow-400',
  D: 'text-orange-400',
  F: 'text-red-400',
};

interface MetricRowProps {
  label: string;
  score: number;
  detail: string;
  weight?: number;
}

function MetricRow({ label, score, detail, weight }: MetricRowProps) {
  const barColor =
    score >= 80 ? 'bg-emerald-500' : score >= 60 ? 'bg-blue-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="w-32 shrink-0">
        <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
        {weight != null && (
          <p className="text-[10px] text-[var(--text-muted)]">{Math.round(weight * 100)}% weight</p>
        )}
      </div>
      <div className="flex flex-1 items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
          <div className={cn('h-full rounded-full transition-all', barColor)} style={{ width: `${score}%` }} />
        </div>
        <span className="w-8 text-right font-mono text-xs font-semibold text-[var(--text-primary)]">
          {Math.round(score)}
        </span>
      </div>
      <p className="w-36 shrink-0 text-right text-[10px] text-[var(--text-muted)]">{detail}</p>
    </div>
  );
}

export function GPSQualityPanel({ report }: { report: GPSQualityReport }) {
  const [expanded, setExpanded] = useState(false);
  const gradeColor = GRADE_COLORS[report.grade] ?? 'text-[var(--text-secondary)]';

  return (
    <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-[var(--bg-elevated)]"
      >
        <Signal className="h-4 w-4 text-[var(--text-muted)]" />
        <span className="text-sm font-medium text-[var(--text-primary)]">GPS Quality</span>
        <span className={cn('text-sm font-bold', gradeColor)}>
          {report.grade} ({Math.round(report.overall_score)}/100)
        </span>
        <span className="ml-auto">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-[var(--text-muted)]" />
          ) : (
            <ChevronRight className="h-4 w-4 text-[var(--text-muted)]" />
          )}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-[var(--cata-border)] px-4 py-3">
          <MetricRow
            label="Accuracy"
            score={report.accuracy.score}
            detail={`p90: ${report.accuracy.p90.toFixed(2)}m`}
            weight={report.metric_weights.accuracy}
          />
          <MetricRow
            label="Satellites"
            score={report.satellites.score}
            detail={`p10: ${report.satellites.p10.toFixed(0)} sats`}
            weight={report.metric_weights.satellites}
          />
          {report.lap_distance_cv && (
            <MetricRow
              label="Lap Distance CV"
              score={report.lap_distance_cv.score}
              detail={`${report.lap_distance_cv.cv_percent.toFixed(2)}% CV (${report.lap_distance_cv.n_laps} laps)`}
              weight={report.metric_weights.lap_distance_cv}
            />
          )}
          <MetricRow
            label="Speed Spikes"
            score={report.speed_spikes.score}
            detail={`${report.speed_spikes.spikes_per_km.toFixed(1)}/km (${report.speed_spikes.total_spikes} total)`}
            weight={report.metric_weights.speed_spikes}
          />
          {report.heading_jitter && (
            <MetricRow
              label="Heading Jitter"
              score={report.heading_jitter.score}
              detail={`std: ${report.heading_jitter.jitter_std.toFixed(3)} deg/m`}
              weight={report.metric_weights.heading_jitter}
            />
          )}
          <MetricRow
            label="Lateral Scatter"
            score={report.lateral_scatter.score}
            detail={`p90: ${report.lateral_scatter.scatter_p90.toFixed(2)}m`}
            weight={report.metric_weights.lateral_scatter}
          />
        </div>
      )}
    </div>
  );
}
