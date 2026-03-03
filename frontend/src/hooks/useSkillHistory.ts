'use client';

import { useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { useSessions, useSession } from './useSession';
import { getCoachingReport } from '@/lib/api';
import { computeSkillDimensions, dimensionsToArray } from '@/lib/skillDimensions';
import type { SkillDimensions } from '@/lib/skillDimensions';
import type { CoachingReport } from '@/lib/types';

/** Maximum number of historical sessions to fetch (excluding current). */
const MAX_HISTORY = 3;

export interface HistoricalSkillEntry {
  sessionId: string;
  date: string;
  dimensions: SkillDimensions;
  values: number[];
}

/**
 * Fetches skill dimensions for the last N sessions at the same track
 * as the given session (excluding the current session itself).
 *
 * Returns an array ordered oldest-first so the rendering layer can
 * apply decreasing opacity from oldest to newest.
 */
export function useSkillHistory(currentSessionId: string | null) {
  const { data: currentSession } = useSession(currentSessionId);
  const { data: sessionsData } = useSessions();

  // Filter to same-track sessions, sorted newest-first, excluding current
  const sameTrackSessions = useMemo(() => {
    if (!currentSession?.track_name || !sessionsData?.items) return [];
    return sessionsData.items
      .filter(
        (s) =>
          s.track_name === currentSession.track_name &&
          s.session_id !== currentSessionId,
      )
      .sort((a, b) => {
        // Sort by date descending (newest first) to pick the most recent N
        const dateA = new Date(a.session_date).getTime();
        const dateB = new Date(b.session_date).getTime();
        return dateB - dateA;
      })
      .slice(0, MAX_HISTORY);
  }, [currentSession?.track_name, sessionsData?.items, currentSessionId]);

  // Batch-fetch coaching reports for the filtered sessions using useQueries
  const coachingQueries = useQueries({
    queries: sameTrackSessions.map((s) => ({
      queryKey: ['coaching-report', s.session_id],
      queryFn: () => getCoachingReport(s.session_id),
      enabled: !!s.session_id,
      retry: false,
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    })),
  });

  // Stable dependency: derive from query data arrays rather than the unstable coachingQueries object
  const queryData = coachingQueries.map((q) => q.data);
  const isLoading = coachingQueries.some((q) => q.isLoading);

  // Compute skill dimensions for each successfully fetched report
  const history: HistoricalSkillEntry[] = useMemo(() => {
    const entries: HistoricalSkillEntry[] = [];
    for (let i = 0; i < sameTrackSessions.length; i++) {
      const data = queryData[i];
      const session = sameTrackSessions[i];
      if (!data) continue;
      const report = data as CoachingReport;
      if (
        report.status !== 'ready' ||
        !report.corner_grades ||
        report.corner_grades.length === 0
      ) {
        continue;
      }
      const dims = computeSkillDimensions(report.corner_grades);
      if (!dims) continue;
      entries.push({
        sessionId: session.session_id,
        date: session.session_date,
        dimensions: dims,
        values: dimensionsToArray(dims),
      });
    }
    // Reverse so entries are oldest-first (oldest = most transparent)
    return entries.reverse();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sameTrackSessions, ...queryData]);

  return { history, isLoading };
}
