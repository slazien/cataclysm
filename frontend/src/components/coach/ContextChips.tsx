'use client';

import { useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { useSessionStore, useAnalysisStore, useUiStore, useCoachStore } from '@/stores';
import { useSession } from '@/hooks/useSession';

export function ContextChips() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const activeView = useUiStore((s) => s.activeView);
  const contextChips = useCoachStore((s) => s.contextChips);
  const setContextChips = useCoachStore((s) => s.setContextChips);
  const { data: session } = useSession(activeSessionId);

  useEffect(() => {
    const chips: { label: string; value: string }[] = [];
    if (session) {
      chips.push({
        label: 'Session',
        value: `${session.track_name} ${session.session_date}`,
      });
    }
    if (selectedLaps.length > 0) {
      chips.push({ label: 'Laps', value: selectedLaps.join(', ') });
    }
    if (selectedCorner) {
      chips.push({
        label: 'Corner',
        value: `Turn ${selectedCorner.replace('T', '')}`,
      });
    }
    const viewLabels: Record<string, string> = {
      dashboard: 'Dashboard',
      'deep-dive': 'Deep Dive',
      progress: 'Progress',
    };
    chips.push({ label: 'View', value: viewLabels[activeView] ?? activeView });
    setContextChips(chips);
  }, [session, selectedLaps, selectedCorner, activeView, setContextChips]);

  if (contextChips.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 px-4 py-2 border-b border-[var(--cata-border)]">
      {contextChips.map((chip) => (
        <Badge
          key={chip.label}
          variant="secondary"
          className="bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--cata-border)] text-[10px] font-medium"
        >
          <span className="text-[var(--text-tertiary)]">{chip.label}:</span>
          &nbsp;{chip.value}
        </Badge>
      ))}
    </div>
  );
}
