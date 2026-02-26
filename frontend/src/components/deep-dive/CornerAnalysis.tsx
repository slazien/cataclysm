'use client';

import { useEffect, useState } from 'react';
import { useSessionStore, useAnalysisStore } from '@/stores';
import { useCorners } from '@/hooks/useAnalysis';
import { cn } from '@/lib/utils';
import { ChartErrorBoundary } from '@/components/shared/ChartErrorBoundary';
import { TrackMapInteractive } from './charts/TrackMapInteractive';
import { CornerDetailPanel } from './CornerDetailPanel';
import { CornerSpeedOverlay } from './charts/CornerSpeedOverlay';
import { BrakeConsistency } from './charts/BrakeConsistency';
import { CornerReportCardGrid } from './CornerReportCardGrid';

type ViewMode = 'grid' | 'detail';

function GridIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
    </svg>
  );
}

function DetailIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <line x1="9" y1="3" x2="9" y2="21" />
    </svg>
  );
}

export function CornerAnalysis() {
  const sessionId = useSessionStore((s) => s.activeSessionId);
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);
  const [viewMode, setViewMode] = useState<ViewMode>('detail');

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
      {/* View mode toggle */}
      <div className="flex items-center justify-end gap-1">
        <button
          onClick={() => setViewMode('grid')}
          className={cn(
            'rounded-md p-1.5 transition-colors',
            viewMode === 'grid'
              ? 'bg-[var(--bg-elevated)] text-[var(--text-primary)]'
              : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
          )}
          title="Report Card Grid"
        >
          <GridIcon />
        </button>
        <button
          onClick={() => setViewMode('detail')}
          className={cn(
            'rounded-md p-1.5 transition-colors',
            viewMode === 'detail'
              ? 'bg-[var(--bg-elevated)] text-[var(--text-primary)]'
              : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
          )}
          title="Detail View"
        >
          <DetailIcon />
        </button>
      </div>

      {viewMode === 'grid' ? (
        /* Grid view: all corners as report cards */
        <div className="min-h-0 flex-1 overflow-y-auto">
          <ChartErrorBoundary name="Corner Report Card Grid">
            <CornerReportCardGrid onSelectCorner={() => setViewMode('detail')} />
          </ChartErrorBoundary>
        </div>
      ) : (
        /* Detail view: existing layout */
        <>
          {/* Top row: Track Map (60%) + Corner Detail Panel (40%) — grid-rows-[1fr] locks the row
              height so variable-length AI advice text doesn't cause layout shift */}
          <div className="grid min-h-0 flex-1 grid-cols-1 grid-rows-[1fr] gap-3 lg:grid-cols-[60%_1fr]">
            {/* Track Map */}
            <div className="min-h-[16rem] overflow-hidden lg:min-h-0">
              <ChartErrorBoundary name="Track Map">
                <TrackMapInteractive sessionId={sessionId} />
              </ChartErrorBoundary>
            </div>
            {/* Corner Detail Panel — overflow-hidden so content never shifts the grid */}
            <div className="min-h-0 overflow-hidden">
              <ChartErrorBoundary name="Corner Detail">
                <CornerDetailPanel sessionId={sessionId} />
              </ChartErrorBoundary>
            </div>
          </div>

          {/* Bottom row: Corner Speed Overlay (50%) + Brake Consistency (50%) */}
          <div className="grid min-h-0 flex-1 grid-cols-1 grid-rows-[1fr] gap-3 lg:grid-cols-2">
            {/* Corner Speed Overlay */}
            <div className="min-h-[16rem] overflow-hidden lg:min-h-0">
              <ChartErrorBoundary name="Corner Speed Overlay">
                <CornerSpeedOverlay sessionId={sessionId} />
              </ChartErrorBoundary>
            </div>
            {/* Brake Consistency Chart */}
            <div className="min-h-[16rem] overflow-hidden lg:min-h-0">
              <ChartErrorBoundary name="Brake Consistency">
                <BrakeConsistency sessionId={sessionId} />
              </ChartErrorBoundary>
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
        </>
      )}
    </div>
  );
}
