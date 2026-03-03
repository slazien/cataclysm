'use client';

import { useMemo, useState } from 'react';
import { useSessionStore } from '@/stores';
import { useSession, useSessionLaps } from '@/hooks/useSession';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useCorners, useConsistency, useGPSQuality } from '@/hooks/useAnalysis';
import { useRecentAchievements } from '@/hooks/useAchievements';
import { useSkillLevel } from '@/hooks/useSkillLevel';
import { OptimalGapChart } from './OptimalGapChart';
import { SessionReportHeader } from './SessionReportHeader';
import { CoachingSummaryHero } from './CoachingSummaryHero';
import { PriorityCardsSection } from './PriorityCardsSection';
import { HeroTrackMapSection } from './HeroTrackMapSection';
import { CornerGradesSection } from './CornerGradesSection';
import { PatternsAndDrillsSection } from './PatternsAndDrillsSection';
import { NewAchievementCard } from './NewAchievementCard';
import { MetricsGrid } from './MetricsGrid';
import { LapTimesBar } from '@/components/dashboard/LapTimesBar';
import { RawDataTable } from './RawDataTable';
import { ScrollArea } from '@/components/ui/scroll-area';
import { TrackWatermark } from '@/components/shared/TrackWatermark';
import { BadgeGrid } from '@/components/achievements/BadgeGrid';
import { TrackLeaderboardSummary } from '@/components/leaderboard/TrackLeaderboardSummary';

export function SessionReport() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { data: session } = useSession(activeSessionId);
  const { data: laps } = useSessionLaps(activeSessionId);
  const { data: _corners } = useCorners(activeSessionId);
  const { data: report } = useCoachingReport(activeSessionId);
  const { data: consistency } = useConsistency(activeSessionId);
  const { data: gpsQuality } = useGPSQuality(activeSessionId);
  const { data: recentAchievementsData } = useRecentAchievements(!!activeSessionId);
  const { isNovice, isAdvanced, showFeature } = useSkillLevel();
  const [badgesOpen, setBadgesOpen] = useState(false);

  const recentAchievements = recentAchievementsData?.newly_unlocked ?? [];

  const bestLapNumber = useMemo(() => {
    if (!laps || laps.length === 0) return 1;
    let best = laps[0];
    for (const lap of laps) {
      if (lap.lap_time_s < best.lap_time_s) best = lap;
    }
    return best.lap_number;
  }, [laps]);

  return (
    <>
    <ScrollArea className="h-full">
      <div className="relative mx-auto flex max-w-5xl flex-col gap-6 p-4 lg:p-6">
        <TrackWatermark />
        <SessionReportHeader
          session={session ?? null}
          gpsQuality={gpsQuality ?? null}
          sessionId={activeSessionId ?? undefined}
        />

        <MetricsGrid
          session={session ?? null}
          laps={laps ?? null}
          consistency={consistency ?? null}
          isNovice={isNovice}
          isAdvanced={isAdvanced}
        />

        <CoachingSummaryHero report={report ?? null} />

        {report?.priority_corners && report.priority_corners.length > 0 && (
          <PriorityCardsSection
            priorities={report.priority_corners}
            isNovice={isNovice}
            cornerGrades={report.corner_grades}
          />
        )}

        {activeSessionId && (
          <HeroTrackMapSection
            sessionId={activeSessionId}
            bestLapNumber={bestLapNumber}
          />
        )}

        {activeSessionId && showFeature('optimal_comparison') && (
          <OptimalGapChart sessionId={activeSessionId} />
        )}

        {session?.track_name && (
          <TrackLeaderboardSummary trackName={session.track_name} />
        )}

        {report?.corner_grades && report.corner_grades.length > 0 && (
          <CornerGradesSection
            grades={report.corner_grades}
          />
        )}

        {report && (report.patterns.length > 0 || report.drills.length > 0) && (
          <PatternsAndDrillsSection
            patterns={report.patterns}
            drills={report.drills}
          />
        )}

        {/* New achievements */}
        {recentAchievements.length > 0 && (
          <NewAchievementCard
            achievements={recentAchievements}
            onViewAll={() => setBadgesOpen(true)}
          />
        )}

        {activeSessionId && laps && laps.length > 0 && (
          <div>
            <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">Lap Times</h3>
            <LapTimesBar sessionId={activeSessionId} />
          </div>
        )}

        <RawDataTable />
      </div>
    </ScrollArea>
    <BadgeGrid open={badgesOpen} onClose={() => setBadgesOpen(false)} />
    </>
  );
}
