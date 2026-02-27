'use client';

import { useAnalysisStore } from '@/stores';
import type { DeepDiveMode } from '@/stores/analysisStore';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { SpeedAnalysis } from './SpeedAnalysis';
import { CornerAnalysis } from './CornerAnalysis';
import { MiniSectorMap } from './charts/MiniSectorMap';

export function DeepDive() {
  const mode = useAnalysisStore((s) => s.deepDiveMode);
  const setMode = useAnalysisStore((s) => s.setMode);

  return (
    <div className="flex h-full flex-col">
      {/* Segmented control: Speed | Corner | Custom */}
      <div className="flex items-center gap-2 border-b border-[var(--cata-border)] px-4 py-2">
        <Tabs value={mode} onValueChange={(v) => setMode(v as DeepDiveMode)} activationMode="manual">
          <TabsList
            onKeyDown={(e) => {
              // Prevent Radix roving-focus from intercepting arrow keys used for corner cycling
              if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                e.stopPropagation();
              }
            }}
          >
            <TabsTrigger value="speed">Speed</TabsTrigger>
            <TabsTrigger value="corner">Corner</TabsTrigger>
            <TabsTrigger value="sectors">Sectors</TabsTrigger>
            <TabsTrigger value="custom">Custom</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Content */}
      <div className="min-h-0 flex-1">
        {mode === 'speed' && <SpeedAnalysis />}
        {mode === 'corner' && <CornerAnalysis />}
        {mode === 'sectors' && <MiniSectorMap />}
        {mode === 'custom' && (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-[var(--text-secondary)]">Custom (Future)</p>
          </div>
        )}
      </div>
    </div>
  );
}
