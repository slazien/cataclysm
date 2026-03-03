'use client';

import { useMemo } from 'react';
import { useSessionStore, useAnalysisStore } from '@/stores';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useUnits } from '@/hooks/useUnits';
import { ChartErrorBoundary } from '@/components/shared/ChartErrorBoundary';
import { AiInsight } from '@/components/shared/AiInsight';
import { MarkdownText } from '@/components/shared/MarkdownText';
import { useSkillLevel } from '@/hooks/useSkillLevel';
import { SpeedTrace } from './charts/SpeedTrace';
import { DeltaT } from './charts/DeltaT';
import { BrakeThrottle } from './charts/BrakeThrottle';
import { TrackMapContainer } from './charts/TrackMapContainer';
import { CornerQuickCard } from './CornerQuickCard';
import { ComparisonLegend } from './ComparisonLegend';
import { GGDiagramChart } from './GGDiagramChart';

export function SpeedAnalysis() {
  const sessionId = useSessionStore((s) => s.activeSessionId);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const showLegend = selectedLaps.length === 2;

  const { data: report } = useCoachingReport(sessionId);
  const { resolveSpeed } = useUnits();
  const { showFeature } = useSkillLevel();

  // Find the most relevant priority corner insight for the current view:
  // if a corner is selected, show that corner's tip; otherwise show the top priority
  const speedInsight = useMemo(() => {
    if (!report?.priority_corners || report.priority_corners.length === 0) return null;
    if (selectedLaps.length === 0) return null;

    // If a corner is selected, try to match it to a priority corner
    if (selectedCorner) {
      const cornerNum = parseInt(selectedCorner.replace(/\D/g, ''), 10);
      const match = report.priority_corners.find((pc) => pc.corner === cornerNum);
      if (match) {
        return {
          tip: match.tip,
          corner: match.corner,
          timeCost: match.time_cost_s,
        };
      }
    }

    // Default: show the top priority corner
    const top = report.priority_corners[0];
    return {
      tip: top.tip,
      corner: top.corner,
      timeCost: top.time_cost_s,
    };
  }, [report, selectedLaps.length, selectedCorner]);

  if (!sessionId) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">No session loaded</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-col gap-3 overflow-y-auto p-3 lg:h-full">
      {showLegend && <ComparisonLegend />}
      <div className="flex min-h-0 flex-col gap-3 lg:flex-1 lg:flex-row">
      {/* Left column -- 65% on desktop, full width on mobile -- three stacked charts */}
      <div className="flex w-full flex-col gap-3 lg:min-h-0 lg:h-full lg:w-[65%]">
        {/* Speed Trace -- tallest */}
        <div className="flex flex-col gap-1.5 lg:flex-[2] lg:min-h-0">
          <div className="relative h-[16rem] rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:h-auto lg:flex-1">
            <h3 className="pointer-events-none absolute left-3 top-1.5 z-10 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
              Speed Trace
            </h3>
            <ChartErrorBoundary name="Speed Trace">
              <SpeedTrace sessionId={sessionId} />
            </ChartErrorBoundary>
          </div>
          {speedInsight && (
            <AiInsight
              mode="inline"
              badge={speedInsight.timeCost > 0 ? `-${speedInsight.timeCost.toFixed(1)}s` : undefined}
            >
              <span className="font-medium text-[var(--text-primary)]">T{speedInsight.corner}:</span>{' '}
              <MarkdownText>{resolveSpeed(speedInsight.tip)}</MarkdownText>
            </AiInsight>
          )}
        </div>

        {/* Delta-T */}
        <div className="relative h-[16rem] rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:h-auto lg:flex-1">
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
        <div className="relative h-[16rem] rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:h-auto lg:flex-1">
          <h3 className="pointer-events-none absolute left-3 top-1.5 z-10 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Brake / Throttle
          </h3>
          <ChartErrorBoundary name="Brake / Throttle">
            <BrakeThrottle sessionId={sessionId} />
          </ChartErrorBoundary>
        </div>

        {/* G-G Diagram (advanced skill level only) */}
        {showFeature('gforce_analysis') && (
          <div className="shrink-0">
            <ChartErrorBoundary name="G-G Diagram">
              <GGDiagramChart sessionId={sessionId} />
            </ChartErrorBoundary>
          </div>
        )}
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
