'use client';

import { useSessionStore } from '@/stores';
import { ChartErrorBoundary } from '@/components/shared/ChartErrorBoundary';
import { SpeedTrace } from './charts/SpeedTrace';
import { DeltaT } from './charts/DeltaT';
import { BrakeThrottle } from './charts/BrakeThrottle';
import { TrackMapInteractive } from './charts/TrackMapInteractive';
import { CornerQuickCard } from './CornerQuickCard';

export function SpeedAnalysis() {
  const sessionId = useSessionStore((s) => s.activeSessionId);

  if (!sessionId) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">No session loaded</p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto p-3 lg:flex-row">
      {/* Left column -- 65% on desktop, full width on mobile -- three stacked charts */}
      <div className="flex w-full flex-col gap-3 lg:w-[65%]">
        {/* Speed Trace -- tallest */}
        <div className="relative min-h-[16rem] min-h-0 flex-[2] rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:min-h-0">
          <h3 className="absolute left-3 top-2 z-10 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Speed Trace
          </h3>
          <ChartErrorBoundary name="Speed Trace">
            <SpeedTrace sessionId={sessionId} />
          </ChartErrorBoundary>
        </div>

        {/* Delta-T */}
        <div className="relative min-h-[16rem] min-h-0 flex-1 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:min-h-0">
          <h3 className="absolute left-3 top-2 z-10 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Delta-T
          </h3>
          <ChartErrorBoundary name="Delta-T">
            <DeltaT sessionId={sessionId} />
          </ChartErrorBoundary>
        </div>

        {/* Brake/Throttle */}
        <div className="relative min-h-[16rem] min-h-0 flex-1 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:min-h-0">
          <h3 className="absolute left-3 top-2 z-10 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Brake / Throttle
          </h3>
          <ChartErrorBoundary name="Brake / Throttle">
            <BrakeThrottle sessionId={sessionId} />
          </ChartErrorBoundary>
        </div>
      </div>

      {/* Right column -- 35% on desktop, full width on mobile -- track map + corner quick card */}
      <div className="flex w-full flex-col gap-3 lg:w-[35%]">
        {/* Track Map -- takes available space */}
        <div className="min-h-[16rem] flex-1 lg:min-h-0">
          <ChartErrorBoundary name="Track Map">
            <TrackMapInteractive sessionId={sessionId} />
          </ChartErrorBoundary>
        </div>

        {/* Corner Quick Card -- fixed size */}
        <div className="shrink-0">
          <ChartErrorBoundary name="Corner Quick Card">
            <CornerQuickCard sessionId={sessionId} />
          </ChartErrorBoundary>
        </div>
      </div>
    </div>
  );
}
