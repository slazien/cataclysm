'use client';

import { useState, useEffect } from 'react';
import { Loader2, BrainCircuit } from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchApi } from '@/lib/api';
import { colors } from '@/lib/design-tokens';
import { SKILL_AXES } from '@/lib/skillDimensions';
import { DeltaTimeChart } from '@/components/comparison/DeltaTimeChart';
import { ComparisonTrackMap } from '@/components/comparison/ComparisonTrackMap';
import { SpeedTraceOverlay } from '@/components/comparison/SpeedTraceOverlay';
import { RadarChart } from '@/components/shared/RadarChart';
import { InfoTooltip } from '@/components/shared/InfoTooltip';
import type { ShareComparisonResult } from '@/lib/types';

interface ComparisonDeepDiveProps {
  comparison: ShareComparisonResult;
  inviterName: string;
  challengerName: string;
  token: string;
}

export function ComparisonDeepDive({
  comparison,
  inviterName,
  challengerName,
  token,
}: ComparisonDeepDiveProps) {
  const [aiNarrative, setAiNarrative] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  // Fetch AI comparison narrative on mount
  useEffect(() => {
    let cancelled = false;
    async function fetchAi() {
      setAiLoading(true);
      setAiError(null);
      try {
        const result = await fetchApi<{ ai_comparison_text: string }>(
          `/api/sharing/${token}/ai-comparison`,
          { method: 'POST' },
        );
        if (!cancelled) {
          setAiNarrative(result.ai_comparison_text);
        }
      } catch {
        if (!cancelled) {
          setAiError('Could not generate AI analysis. Try again later.');
        }
      } finally {
        if (!cancelled) setAiLoading(false);
      }
    }
    fetchAi();
    return () => {
      cancelled = true;
    };
  }, [token]);

  // Build radar datasets if skill_dimensions available
  const radarDatasets = comparison.skill_dimensions
    ? [
        {
          label: inviterName,
          values: [
            comparison.skill_dimensions.a.braking,
            comparison.skill_dimensions.a.trail_braking,
            comparison.skill_dimensions.a.throttle,
            comparison.skill_dimensions.a.line,
          ],
          color: colors.comparison.reference,
          fillOpacity: 0.12,
        },
        {
          label: challengerName,
          values: [
            comparison.skill_dimensions.b.braking,
            comparison.skill_dimensions.b.trail_braking,
            comparison.skill_dimensions.b.throttle,
            comparison.skill_dimensions.b.line,
          ],
          color: colors.comparison.compare,
          fillOpacity: 0.12,
        },
      ]
    : null;

  return (
    <div className="flex flex-col gap-5">
      {/* 1. Delta Track Map */}
      {comparison.track_coords && comparison.distance_m.length > 0 && (
        <section className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h3 className="mb-1 flex items-center gap-1.5 text-sm font-medium text-[var(--text-primary)]">
            Delta Map
            <InfoTooltip helpKey="chart.delta-map" />
          </h3>
          <p className="mb-3 text-xs text-[var(--text-secondary)]">
            Green = {inviterName} gaining, Red = {inviterName} losing
          </p>
          <div className="mx-auto aspect-square max-w-sm">
            <ComparisonTrackMap
              trackCoords={comparison.track_coords}
              distanceM={comparison.distance_m}
              deltaTimeS={comparison.delta_time_s}
              cornerDeltas={comparison.corner_deltas}
            />
          </div>
        </section>
      )}

      {/* 2. Time Delta Chart */}
      {comparison.distance_m.length > 0 && (
        <section className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h3 className="mb-3 flex items-center gap-1.5 text-sm font-medium text-[var(--text-primary)]">
            Time Delta Over Distance
            <InfoTooltip helpKey="chart.delta-t" />
          </h3>
          <div className="h-64">
            <DeltaTimeChart
              distance_m={comparison.distance_m}
              delta_time_s={comparison.delta_time_s}
              totalDelta={comparison.delta_s}
            />
          </div>
        </section>
      )}

      {/* 3. Speed Comparison */}
      {comparison.speed_traces && (
        <section className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h3 className="mb-3 flex items-center gap-1.5 text-sm font-medium text-[var(--text-primary)]">
            Speed Comparison
            <InfoTooltip helpKey="chart.speed-trace" />
          </h3>
          <SpeedTraceOverlay
            traceA={comparison.speed_traces.a}
            traceB={comparison.speed_traces.b}
            labelA={inviterName}
            labelB={challengerName}
            height={256}
          />
        </section>
      )}

      {/* 4. Skill Comparison Radar */}
      {radarDatasets && (
        <section className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h3 className="mb-3 flex items-center gap-1.5 text-sm font-medium text-[var(--text-primary)]">
            Skill Comparison
            <InfoTooltip helpKey="chart.skill-radar" />
          </h3>
          <div className="flex flex-col items-center gap-3">
            <RadarChart axes={SKILL_AXES} datasets={radarDatasets} size={240} />
            {/* Legend */}
            <div className="flex items-center justify-center gap-6 text-xs text-[var(--text-secondary)]">
              <div className="flex items-center gap-1.5">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: colors.comparison.reference }}
                />
                <span>{inviterName}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: colors.comparison.compare }}
                />
                <span>{challengerName}</span>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* 5. AI Coach Analysis */}
      <section className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
        <div className="mb-3 flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-[var(--ai-icon)]" />
          <h3 className="text-sm font-medium text-[var(--text-primary)]">
            AI Coach Analysis
          </h3>
        </div>
        {aiLoading && (
          <div className="flex items-center gap-2 py-6">
            <Loader2 className="h-4 w-4 animate-spin text-[var(--text-secondary)]" />
            <p className="text-sm text-[var(--text-secondary)]">
              Analyzing your comparison...
            </p>
          </div>
        )}
        {aiError && (
          <p className="text-sm text-[var(--text-muted)]">{aiError}</p>
        )}
        {aiNarrative && (
          <div className="space-y-3">
            {aiNarrative.split('\n\n').map((paragraph, i) => (
              <p key={i} className="text-sm leading-relaxed text-[var(--text-secondary)]">
                {paragraph}
              </p>
            ))}
          </div>
        )}
      </section>

      {/* 6. Corner Breakdown Table */}
      {comparison.corner_deltas.length > 0 && (
        <section className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h3 className="mb-4 text-sm font-medium text-[var(--text-primary)]">
            Corner-by-Corner Breakdown
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--cata-border)]">
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    Corner
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    {inviterName}
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    {challengerName}
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    Delta
                  </th>
                </tr>
              </thead>
              <tbody>
                {comparison.corner_deltas.map((cd) => {
                  const isPositive = cd.speed_diff_mph > 0;
                  const isNegative = cd.speed_diff_mph < 0;
                  return (
                    <tr
                      key={cd.corner_number}
                      className="border-b border-[var(--cata-border)]/50 transition-colors hover:bg-[var(--bg-elevated)]"
                    >
                      <td className="px-3 py-2 font-medium text-[var(--text-primary)]">
                        T{cd.corner_number}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-[var(--text-secondary)]">
                        {cd.a_min_speed_mph.toFixed(1)} mph
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-[var(--text-secondary)]">
                        {cd.b_min_speed_mph.toFixed(1)} mph
                      </td>
                      <td
                        className={cn(
                          'px-3 py-2 text-right font-mono font-medium',
                          isPositive && 'text-[var(--color-throttle)]',
                          isNegative && 'text-[var(--color-brake)]',
                          !isPositive && !isNegative && 'text-[var(--text-muted)]',
                        )}
                      >
                        {isPositive ? '+' : ''}
                        {cd.speed_diff_mph.toFixed(1)} mph
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
