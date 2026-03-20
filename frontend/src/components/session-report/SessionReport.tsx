'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronDown, RefreshCw } from 'lucide-react';
import { useSessionStore, useUiStore, useAnalysisStore } from '@/stores';
import { useSession, useSessionLaps } from '@/hooks/useSession';
import { useAutoReport } from '@/hooks/useAutoReport';
import { useCorners, useConsistency, useGPSQuality, useOptimalComparison } from '@/hooks/useAnalysis';
import { usePreviousSessionDelta } from '@/hooks/usePreviousSessionDelta';
import { useRecentAchievements } from '@/hooks/useAchievements';
import { useSkillLevel } from '@/hooks/useSkillLevel';
import { useMergedPriorities } from '@/hooks/useMergedPriorities';
import { useTour } from '@/hooks/useTour';
import { getReportSteps } from '@/components/tour/tourSteps';
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
import { SkillLevelMismatchBanner } from '@/components/coach/SkillLevelMismatchBanner';
import { TrackGuideCard } from './TrackGuideCard';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// localStorage helpers for section collapse state & first-report detection
// ---------------------------------------------------------------------------

const STORAGE_KEY_SECTIONS = 'cataclysm_report_sections';
const STORAGE_KEY_FIRST_SEEN = 'cataclysm_first_report_seen';

function loadSectionState(): Record<string, boolean> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY_SECTIONS);
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

function saveSectionState(state: Record<string, boolean>) {
  try {
    localStorage.setItem(STORAGE_KEY_SECTIONS, JSON.stringify(state));
  } catch {
    /* quota exceeded — ignore */
  }
}

// ---------------------------------------------------------------------------
// CollapsibleSection
// ---------------------------------------------------------------------------

function CollapsibleSection({
  id,
  title,
  subtitle,
  defaultOpen = false,
  sectionStates,
  onToggle,
  children,
}: {
  id: string;
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  sectionStates: Record<string, boolean>;
  onToggle: (id: string, open: boolean) => void;
  children: React.ReactNode;
}) {
  const isOpen = sectionStates[id] ?? defaultOpen;

  return (
    <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
      <button
        type="button"
        onClick={() => onToggle(id, !isOpen)}
        className="flex w-full items-center justify-between px-4 py-3"
      >
        <div className="text-left">
          <h3 className="font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-primary)]">
            {title}
          </h3>
          {subtitle && (
            <p className="text-xs text-[var(--text-secondary)]">{subtitle}</p>
          )}
        </div>
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 text-[var(--text-secondary)] transition-transform',
            isOpen && 'rotate-180',
          )}
        />
      </button>
      {isOpen && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SessionReport
// ---------------------------------------------------------------------------

export function SessionReport() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { data: session } = useSession(activeSessionId);
  const { data: laps } = useSessionLaps(activeSessionId);
  const { data: _corners } = useCorners(activeSessionId);
  const { report, generatingReport, isSkillMismatch, isGenerating, regenRemaining, regenMax, regenerate, retry: retryCoaching } = useAutoReport(activeSessionId);
  const { data: consistency } = useConsistency(activeSessionId);
  const { data: gpsQuality } = useGPSQuality(activeSessionId);
  const { data: optimalComparison, isPlaceholderData: isOptimalStale, isPending: isOptimalPending } = useOptimalComparison(activeSessionId);
  const { cornerDeltas } = usePreviousSessionDelta(session, optimalComparison);
  const mergedPriorities = useMergedPriorities(report, optimalComparison, 3);
  const { data: recentAchievementsData } = useRecentAchievements(!!activeSessionId);
  const { isNovice, isAdvanced, showFeature } = useSkillLevel();
  const skillLevel = useUiStore((s) => s.skillLevel);
  const setActiveView = useUiStore((s) => s.setActiveView);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);
  const setMode = useAnalysisStore((s) => s.setMode);
  const [badgesOpen, setBadgesOpen] = useState(false);

  const handleCornerDrillDown = useCallback(
    (cornerNumber: number) => {
      selectCorner(`T${cornerNumber}`);
      setMode('corner');
      setActiveView('deep-dive');
    },
    [selectCorner, setMode, setActiveView],
  );

  // ---------------------------------------------------------------------------
  // Progressive disclosure — section expand/collapse state
  // ---------------------------------------------------------------------------
  const [sectionStates, setSectionStates] = useState<Record<string, boolean>>(loadSectionState);

  const handleToggle = (id: string, open: boolean) => {
    setSectionStates((prev) => {
      const next = { ...prev, [id]: open };
      saveSectionState(next);
      return next;
    });
  };

  // ---------------------------------------------------------------------------
  // First-report highlight — pulsing glow on score circle
  // ---------------------------------------------------------------------------
  const [isFirstReport, setIsFirstReport] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!localStorage.getItem(STORAGE_KEY_FIRST_SEEN)) {
      setIsFirstReport(true);
      localStorage.setItem(STORAGE_KEY_FIRST_SEEN, '1');
      const timer = setTimeout(() => setIsFirstReport(false), 3000);
      return () => clearTimeout(timer);
    }
  }, []);

  const recentAchievements = recentAchievementsData?.newly_unlocked ?? [];

  const bestLapNumber = useMemo(() => {
    if (!laps || laps.length === 0) return 1;
    let best = laps[0];
    for (const lap of laps) {
      if (lap.lap_time_s < best.lap_time_s) best = lap;
    }
    return best.lap_number;
  }, [laps]);

  const patternCount = report ? report.patterns.length + report.drills.length : 0;

  // Tour: trigger when session + laps are loaded (no coaching dependency)
  const hasTourTargets = Boolean(session && laps?.length);
  if (hasTourTargets && !localStorage.getItem('cataclysm-tour-report')) {
    // Always log when tour SHOULD trigger — visible in prod builds too
    console.warn('[tour:report] enabled=true, hasSeen=false — tour should auto-trigger');
  }
  useTour('report', hasTourTargets, () => getReportSteps(skillLevel));

  return (
    <>
    <ScrollArea className="h-full overflow-x-hidden no-hscroll">
      <div className="relative mx-auto flex w-full min-w-0 max-w-5xl flex-col gap-6 p-4 pb-24 lg:p-6 lg:pb-6">
        <TrackWatermark />

        {/* ----------------------------------------------------------------- */}
        {/* ALWAYS VISIBLE — the "answer" + trust evidence                     */}
        {/* ----------------------------------------------------------------- */}

        <SessionReportHeader
          session={session ?? null}
          gpsQuality={gpsQuality ?? null}
          sessionId={activeSessionId ?? undefined}
        />

        <div className={cn(isFirstReport && 'animate-pulse-glow')}>
          <MetricsGrid
            session={session ?? null}
            laps={laps ?? null}
            consistency={consistency ?? null}
            isNovice={isNovice}
            isAdvanced={isAdvanced}
            physicsOptimalLapTime={
              optimalComparison?.optimal_lap_time_s != null &&
              optimalComparison.actual_lap_time_s != null &&
              optimalComparison.optimal_lap_time_s < optimalComparison.actual_lap_time_s
                ? optimalComparison.optimal_lap_time_s
                : undefined
            }
            isOptimalRefreshing={isOptimalStale}
            isOptimalPending={isOptimalPending}
          />
        </div>

        {isSkillMismatch && report?.skill_level && (
          <SkillLevelMismatchBanner
            reportLevel={report.skill_level}
            currentLevel={skillLevel}
            onRegenerate={regenerate}
          />
        )}

        <CoachingSummaryHero report={generatingReport ?? report ?? null} onRetry={retryCoaching} />

        {report?.skill_level && (
          <div className="flex items-center justify-between -mt-4">
            <p className="text-[11px] text-[var(--text-secondary)]">
              Generated for {report.skill_level.charAt(0).toUpperCase() + report.skill_level.slice(1)}
            </p>
            <button
              onClick={regenerate}
              disabled={isGenerating || regenRemaining === 0}
              className="flex min-h-[44px] items-center gap-1.5 rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-surface)] hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-40"
              title={regenRemaining === 0 ? 'Daily regeneration limit reached' : 'Regenerate all coaching for this session'}
            >
              <RefreshCw className={`h-3 w-3 ${isGenerating ? 'animate-spin' : ''}`} />
              {isGenerating
                ? 'Regenerating\u2026'
                : `Regenerate${regenRemaining != null && regenMax != null ? ` (${regenRemaining}/${regenMax})` : ''}`}
            </button>
          </div>
        )}

        {mergedPriorities.length > 0 && (
          <PriorityCardsSection
            priorities={mergedPriorities}
            isNovice={isNovice}
            cornerGrades={report?.corner_grades}
            cornerDeltas={cornerDeltas}
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
          />
        )}

        {activeSessionId && laps && laps.length > 0 && (
          <div>
            <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">Lap Times</h3>
            <LapTimesBar sessionId={activeSessionId} />
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* COLLAPSED SECTIONS — expand on click                               */}
        {/* ----------------------------------------------------------------- */}

        {showFeature('track_guide') && activeSessionId && (
          <CollapsibleSection
            id="track_guide"
            title="Track Briefing"
            subtitle="Corner-by-corner guide with landmarks"
            sectionStates={sectionStates}
            onToggle={handleToggle}
          >
            <TrackGuideCard sessionId={activeSessionId} />
          </CollapsibleSection>
        )}

        {activeSessionId && showFeature('optimal_comparison') && (
          <CollapsibleSection
            id="optimal_comparison"
            title="Optimal Comparison"
            subtitle="Gap to your fastest possible lap"
            sectionStates={sectionStates}
            onToggle={handleToggle}
          >
            <OptimalGapChart sessionId={activeSessionId} onCornerClick={handleCornerDrillDown} />
          </CollapsibleSection>
        )}

        {session?.track_name && (
          <CollapsibleSection
            id="leaderboard"
            title="Leaderboard"
            subtitle="See how you rank at this track"
            sectionStates={sectionStates}
            onToggle={handleToggle}
          >
            <TrackLeaderboardSummary trackName={session.track_name} />
          </CollapsibleSection>
        )}

        {report && patternCount > 0 && (
          <CollapsibleSection
            id="patterns_drills"
            title="Patterns & Drills"
            subtitle={`${patternCount} item${patternCount === 1 ? '' : 's'} identified`}
            sectionStates={sectionStates}
            onToggle={handleToggle}
          >
            <PatternsAndDrillsSection
              patterns={report.patterns}
              drills={report.drills}
            />
          </CollapsibleSection>
        )}

        {/* New achievements */}
        {recentAchievements.length > 0 && (
          <NewAchievementCard
            achievements={recentAchievements}
            onViewAll={() => setBadgesOpen(true)}
          />
        )}

        {showFeature('raw_data_table') && (
          <CollapsibleSection
            id="raw_data"
            title="Raw Data"
            subtitle="Detailed lap-by-lap telemetry table"
            sectionStates={sectionStates}
            onToggle={handleToggle}
          >
            <RawDataTable />
          </CollapsibleSection>
        )}
      </div>
    </ScrollArea>
    <BadgeGrid open={badgesOpen} onClose={() => setBadgesOpen(false)} />
    </>
  );
}
