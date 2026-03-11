'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSessions } from './useSession';
import { getOptimalComparison } from '@/lib/api';
import { parseSessionDate } from '@/lib/formatters';
import type { SessionSummary, OptimalComparisonData } from '@/lib/types';

export interface CornerDelta {
  corner_number: number;
  /** Positive = improved (gap shrank), negative = regressed */
  delta_s: number;
}

/**
 * Finds the previous session at the same track and computes per-corner
 * time-cost deltas against the current session's optimal comparison.
 */
export function usePreviousSessionDelta(
  currentSession: SessionSummary | undefined,
  currentOptimal: OptimalComparisonData | undefined,
) {
  const { data: sessionsData } = useSessions();

  const prevSessionId = useMemo(() => {
    if (!currentSession?.track_name || !currentSession.session_date || !sessionsData?.items) {
      return null;
    }
    const currentDate = parseSessionDate(currentSession.session_date).getTime();
    if (isNaN(currentDate)) return null;
    // All sessions at the same track, sorted newest-first
    const candidates = sessionsData.items
      .filter(
        (s) =>
          s.track_name === currentSession.track_name &&
          s.session_id !== currentSession.session_id,
      )
      .sort((a, b) => parseSessionDate(b.session_date).getTime() - parseSessionDate(a.session_date).getTime());
    // Find the session immediately before the current one
    return candidates.find((s) => parseSessionDate(s.session_date).getTime() < currentDate)?.session_id ?? null;
  }, [currentSession, sessionsData]);

  const { data: prevOptimal, isPending: prevLoading } = useQuery<OptimalComparisonData>({
    queryKey: ['optimal-comparison', prevSessionId, null],
    queryFn: () => getOptimalComparison(prevSessionId!),
    enabled: !!prevSessionId,
    staleTime: Infinity,
  });

  const cornerDeltas = useMemo((): Map<number, CornerDelta> | null => {
    if (!currentOptimal?.corner_opportunities || !prevOptimal?.corner_opportunities) return null;
    const prevMap = new Map(
      prevOptimal.corner_opportunities.map((o) => [o.corner_number, o.time_cost_s]),
    );
    const deltas = new Map<number, CornerDelta>();
    for (const o of currentOptimal.corner_opportunities) {
      const prevCost = prevMap.get(o.corner_number);
      if (prevCost != null) {
        // positive = improved (previous gap was bigger)
        deltas.set(o.corner_number, {
          corner_number: o.corner_number,
          delta_s: prevCost - o.time_cost_s,
        });
      }
    }
    return deltas.size > 0 ? deltas : null;
  }, [currentOptimal, prevOptimal]);

  return { cornerDeltas, prevSessionId, isPending: prevLoading && !!prevSessionId };
}
