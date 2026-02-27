'use client';

import { useSessionStore, useAnalysisStore } from '@/stores';
import { ChartErrorBoundary } from '@/components/shared/ChartErrorBoundary';
import { SpeedTrace } from './charts/SpeedTrace';
import { DeltaT } from './charts/DeltaT';
import { BrakeThrottle } from './charts/BrakeThrottle';
import { TrackMapContainer } from './charts/TrackMapContainer';
import { CornerQuickCard } from './CornerQuickCard';
import { ComparisonLegend } from './ComparisonLegend';

export function SpeedAnalysis() {
  const sessionId = useSessionStore((s) => s.activeSessionId);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const showLegend = selectedLaps.length === 2;

  if (!sessionId) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">No session loaded</p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto p-3">
      {showLegend && <ComparisonLegend />}
      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
      {/* Left column -- 65% on desktop, full width on mobile -- three stacked charts */}
      <div className="flex w-full min-h-0 flex-col gap-3 lg:h-full lg:w-[65%]">
        {/* Speed Trace -- tallest */}
        <div className="relative min-h-[16rem] flex-[2] rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:min-h-0">
          <h3 className="pointer-events-none absolute left-3 top-1.5 z-10 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Speed Trace
          </h3>
          <ChartErrorBoundary name="Speed Trace">
            <SpeedTrace sessionId={sessionId} />
          </ChartErrorBoundary>
        </div>

        {/* Delta-T */}
        <div className="relative min-h-[16rem] flex-1 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:min-h-0">
          <div className="pointer-events-none absolute left-3 top-1.5 z-10">
            <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
              Delta-T
            </h3>
            {showLegend && (
              <p className="text-[10px] text-[var(--text-muted)] opacity-60">
                below zero = compare lap faster
              </p>
            )}
          </div>
          <ChartErrorBoundary name="Delta-T">
            <DeltaT sessionId={sessionId} />
          </ChartErrorBoundary>
        </div>

        {/* Brake/Throttle */}
        <div className="relative min-h-[16rem] flex-1 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:min-h-0">
          <h3 className="pointer-events-none absolute left-3 top-1.5 z-10 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Brake / Throttle
          </h3>
          <ChartErrorBoundary name="Brake / Throttle">
            <BrakeThrottle sessionId={sessionId} />
          </ChartErrorBoundary>
        </div>
      </div>

      {/* Right column -- 35% on desktop, full width on mobile -- track map + corner quick card */}
      <div className="flex w-full min-h-0 flex-col gap-3 lg:w-[35%] lg:overflow-y-auto">
        {/* Track Map -- fixed height so it never resizes when card content changes */}
        <div className="h-[250px] shrink-0 lg:h-[400px]">
          <ChartErrorBoundary name="Track Map">
            <TrackMapContainer sessionId={sessionId} />
          </ChartErrorBoundary>
        </div>

        {/* Corner Quick Card -- natural height, shows all content at a glance */}
        <div className="shrink-0">
          <ChartErrorBoundary name="Corner Quick Card">
            <CornerQuickCard sessionId={sessionId} />
          </ChartErrorBoundary>
        </div>
      </div>
      </div>
    </div>
  );
}
