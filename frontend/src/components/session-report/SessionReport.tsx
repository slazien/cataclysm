'use client';

import { useMemo } from 'react';
import { useSessionStore } from '@/stores';
import { useSession, useSessionLaps } from '@/hooks/useSession';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useCorners, useConsistency, useGPSQuality } from '@/hooks/useAnalysis';
import { useSkillLevel } from '@/hooks/useSkillLevel';
import { SessionReportHeader } from './SessionReportHeader';
import { CoachingSummaryHero } from './CoachingSummaryHero';
import { PriorityCardsSection } from './PriorityCardsSection';
import { HeroTrackMapSection } from './HeroTrackMapSection';
import { CornerGradesSection } from './CornerGradesSection';
import { PatternsAndDrillsSection } from './PatternsAndDrillsSection';
import { MetricsGrid } from './MetricsGrid';
import { LapTimesBar } from '@/components/dashboard/LapTimesBar';
import { ScrollArea } from '@/components/ui/scroll-area';

export function SessionReport() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { data: session } = useSession(activeSessionId);
  const { data: laps } = useSessionLaps(activeSessionId);
  const { data: _corners } = useCorners(activeSessionId);
  const { data: report } = useCoachingReport(activeSessionId);
  const { data: consistency } = useConsistency(activeSessionId);
  const { data: gpsQuality } = useGPSQuality(activeSessionId);
  const { isNovice, isAdvanced } = useSkillLevel();

  const bestLapNumber = useMemo(() => {
    if (!laps || laps.length === 0) return 1;
    let best = laps[0];
    for (const lap of laps) {
      if (lap.lap_time_s < best.lap_time_s) best = lap;
    }
    return best.lap_number;
  }, [laps]);

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto max-w-5xl space-y-6 p-4 lg:p-6">
        <SessionReportHeader
          session={session ?? null}
          gpsQuality={gpsQuality ?? null}
        />

        <CoachingSummaryHero report={report ?? null} />

        {report?.priority_corners && report.priority_corners.length > 0 && (
          <PriorityCardsSection
            priorities={report.priority_corners}
            isNovice={isNovice}
          />
        )}

        {activeSessionId && (
          <HeroTrackMapSection
            sessionId={activeSessionId}
            bestLapNumber={bestLapNumber}
          />
        )}

        {report?.corner_grades && report.corner_grades.length > 0 && (
          <CornerGradesSection
            grades={report.corner_grades}
            isNovice={isNovice}
          />
        )}

        {report && (report.patterns.length > 0 || report.drills.length > 0) && (
          <PatternsAndDrillsSection
            patterns={report.patterns}
            drills={report.drills}
          />
        )}

        <MetricsGrid
          session={session ?? null}
          laps={laps ?? null}
          consistency={consistency ?? null}
          isNovice={isNovice}
          isAdvanced={isAdvanced}
        />

        {activeSessionId && laps && laps.length > 0 && (
          <div>
            <h3 className="mb-3 text-sm font-medium text-[var(--text-secondary)]">Lap Times</h3>
            <LapTimesBar sessionId={activeSessionId} />
          </div>
        )}
      </div>
    </ScrollArea>
  );
}
