'use client';

import { useSessionStore } from '@/stores';
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
    <div className="flex h-full min-h-0 gap-3 p-3">
      {/* Left column — 65% — three stacked charts */}
      <div className="flex w-[65%] flex-col gap-3">
        {/* Speed Trace — tallest */}
        <div className="relative min-h-0 flex-[2] rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
          <h3 className="absolute left-3 top-2 z-10 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Speed Trace
          </h3>
          <SpeedTrace sessionId={sessionId} />
        </div>

        {/* Delta-T */}
        <div className="relative min-h-0 flex-1 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
          <h3 className="absolute left-3 top-2 z-10 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Delta-T
          </h3>
          <DeltaT sessionId={sessionId} />
        </div>

        {/* Brake/Throttle */}
        <div className="relative min-h-0 flex-1 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
          <h3 className="absolute left-3 top-2 z-10 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Brake / Throttle
          </h3>
          <BrakeThrottle sessionId={sessionId} />
        </div>
      </div>

      {/* Right column — 35% — track map + corner quick card */}
      <div className="flex w-[35%] flex-col gap-3">
        {/* Track Map — takes available space */}
        <div className="flex-1">
          <TrackMapInteractive sessionId={sessionId} />
        </div>

        {/* Corner Quick Card — fixed size */}
        <div className="shrink-0">
          <CornerQuickCard sessionId={sessionId} />
        </div>
      </div>
    </div>
  );
}
