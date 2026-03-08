'use client';

import { useEffect, useMemo } from 'react';
import { MousePointerClick } from 'lucide-react';
import { useSessionStore, useAnalysisStore } from '@/stores';
import type { DeepDiveMode } from '@/stores/analysisStore';
import { useSessionLaps } from '@/hooks/useSession';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useSkillLevel } from '@/hooks/useSkillLevel';
import { EmptyState } from '@/components/shared/EmptyState';
import { SpeedAnalysis } from './SpeedAnalysis';
import { CornerAnalysis } from './CornerAnalysis';
import { MiniSectorMap } from './charts/MiniSectorMap';
import { LapReplay } from '@/components/replay/LapReplay';

export function DeepDive() {
  const mode = useAnalysisStore((s) => s.deepDiveMode);
  const setMode = useAnalysisStore((s) => s.setMode);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const selectLaps = useAnalysisStore((s) => s.selectLaps);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { data: laps } = useSessionLaps(activeSessionId);
  const { showFeature } = useSkillLevel();

  // Auto-select the best lap so charts show data immediately
  const bestLapNumber = useMemo(() => {
    if (!laps || laps.length === 0) return null;
    const clean = laps.filter((l) => l.is_clean);
    const pool = clean.length > 0 ? clean : laps;
    let best = pool[0];
    for (const lap of pool) {
      if (lap.lap_time_s < best.lap_time_s) best = lap;
    }
    return best.lap_number;
  }, [laps]);

  useEffect(() => {
    if (selectedLaps.length === 0 && bestLapNumber !== null) {
      selectLaps([bestLapNumber]);
    }
  }, [selectedLaps.length, bestLapNumber, selectLaps]);

  const showSectors = showFeature('sectors_tab');
  const showCustom = showFeature('custom_tab');
  const showReplay = showFeature('replay_tab');

  // Fall back to 'speed' if the active tab is hidden by skill level
  useEffect(() => {
    if (
      (mode === 'sectors' && !showSectors) ||
      (mode === 'custom' && !showCustom) ||
      (mode === 'replay' && !showReplay)
    ) {
      setMode('speed');
    }
  }, [mode, showSectors, showCustom, showReplay, setMode]);

  if (!activeSessionId) {
    return (
      <EmptyState
        title="Select a lap to explore"
        message="Load a session, then pick a lap from the grid to analyze speed, corners, and sectors"
        icon={MousePointerClick}
      />
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Segmented control: Speed | Corner | Custom */}
      <div className="overflow-x-auto border-b border-[var(--cata-border)] px-4 py-2">
        <Tabs value={mode} onValueChange={(v) => setMode(v as DeepDiveMode)} activationMode="manual">
          <TabsList className="!h-11 p-0 whitespace-nowrap"
            onKeyDown={(e) => {
              // Prevent Radix roving-focus from intercepting arrow keys used for corner cycling
              if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                e.stopPropagation();
              }
            }}
          >
            <TabsTrigger value="speed">Lap Trace</TabsTrigger>
            <TabsTrigger value="corner">Corner Focus</TabsTrigger>
            {showSectors && <TabsTrigger value="sectors">Sectors</TabsTrigger>}
            {showCustom && <TabsTrigger value="custom">Custom</TabsTrigger>}
            {showReplay && <TabsTrigger value="replay">Replay</TabsTrigger>}
          </TabsList>
        </Tabs>
      </div>

      {/* Content */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {mode === 'speed' && <SpeedAnalysis />}
        {mode === 'corner' && <CornerAnalysis />}
        {mode === 'sectors' && showSectors && <MiniSectorMap />}
        {mode === 'custom' && showCustom && (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-[var(--text-secondary)]">Custom (Future)</p>
          </div>
        )}
        {mode === 'replay' && showReplay && <LapReplay />}
      </div>
    </div>
  );
}
