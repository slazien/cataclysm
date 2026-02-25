'use client';

import { useEffect } from 'react';
import { useSessionStore, useAnalysisStore } from '@/stores';
import { useCorners } from '@/hooks/useAnalysis';
import { TrackMapInteractive } from './charts/TrackMapInteractive';
import { CornerDetailPanel } from './CornerDetailPanel';
import { CornerSpeedOverlay } from './charts/CornerSpeedOverlay';
import { BrakeConsistency } from './charts/BrakeConsistency';

export function CornerAnalysis() {
  const sessionId = useSessionStore((s) => s.activeSessionId);
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);

  const { data: corners } = useCorners(sessionId);

  // Auto-select first corner if none selected
  useEffect(() => {
    if (!selectedCorner && corners && corners.length > 0) {
      selectCorner(`T${corners[0].number}`);
    }
  }, [selectedCorner, corners, selectCorner]);

  // Arrow key cycling is handled globally by useKeyboardShortcuts

  if (!sessionId) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">No session loaded</p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3">
      {/* Top row: Track Map (60%) + Corner Detail Panel (40%) */}
      <div className="flex min-h-0 flex-1 gap-3">
        {/* Track Map — 60% */}
        <div className="w-[60%]">
          <TrackMapInteractive sessionId={sessionId} />
        </div>
        {/* Corner Detail Panel — 40% */}
        <div className="w-[40%]">
          <CornerDetailPanel sessionId={sessionId} />
        </div>
      </div>

      {/* Bottom row: Corner Speed Overlay (50%) + Brake Consistency (50%) */}
      <div className="flex min-h-0 flex-1 gap-3">
        {/* Corner Speed Overlay — 50% */}
        <div className="w-[50%]">
          <CornerSpeedOverlay sessionId={sessionId} />
        </div>
        {/* Brake Consistency Chart — 50% */}
        <div className="w-[50%]">
          <BrakeConsistency sessionId={sessionId} />
        </div>
      </div>

      {/* Corner navigation hint */}
      <div className="flex items-center justify-center gap-2 text-xs text-[var(--text-muted)]">
        <kbd className="rounded border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-1.5 py-0.5 font-mono text-[10px]">
          ←
        </kbd>
        <kbd className="rounded border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-1.5 py-0.5 font-mono text-[10px]">
          →
        </kbd>
        <span>to cycle corners</span>
      </div>
    </div>
  );
}
