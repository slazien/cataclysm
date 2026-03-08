'use client';

import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  getSessionLaps,
  getLapData,
  getCorners,
  getAllLapCorners,
  getConsistency,
  getGPSQuality,
  getMiniSectors,
  getDegradation,
  getOptimalComparison,
  getLineAnalysis,
  getDelta,
} from '@/lib/api';

const IMMUTABLE = { staleTime: Infinity } as const;

// Prefetch up to this many clean laps — covers all typical sessions without
// hammering the backend on outliers (endurance sessions with 50+ laps).
const MAX_LAP_PREFETCH = 20;

/**
 * Fires prefetch requests for all analysis endpoints when a session becomes
 * active. All telemetry queries are staleTime:Infinity, so this is a no-op for
 * already-cached data and only issues real fetches on first visit to a session.
 *
 * Prefetching strategy:
 *   Batch 1 — session-level endpoints: fire immediately in parallel.
 *   Batch 2 — per-lap telemetry: fan out after the lap list resolves.
 *   Batch 3 — comparison data: delta + line analysis for the 2 best laps.
 */
export function useSessionPrefetch(sessionId: string | null) {
  const qc = useQueryClient();

  useEffect(() => {
    if (!sessionId) return;

    // Batch 1: session-level endpoints, no per-lap dependency
    qc.prefetchQuery({ queryKey: ['corners', sessionId], queryFn: () => getCorners(sessionId), ...IMMUTABLE });
    qc.prefetchQuery({ queryKey: ['all-lap-corners', sessionId], queryFn: () => getAllLapCorners(sessionId), ...IMMUTABLE });
    qc.prefetchQuery({ queryKey: ['consistency', sessionId], queryFn: () => getConsistency(sessionId), ...IMMUTABLE });
    qc.prefetchQuery({ queryKey: ['gps-quality', sessionId], queryFn: () => getGPSQuality(sessionId), ...IMMUTABLE });
    qc.prefetchQuery({ queryKey: ['mini-sectors', sessionId, 20, undefined], queryFn: () => getMiniSectors(sessionId, 20), ...IMMUTABLE });
    qc.prefetchQuery({ queryKey: ['degradation', sessionId], queryFn: () => getDegradation(sessionId), ...IMMUTABLE });
    // Profile-less optimal comparison (covers sessions with no equipment assigned)
    qc.prefetchQuery({ queryKey: ['optimal-comparison', sessionId, null], queryFn: () => getOptimalComparison(sessionId, null), staleTime: Infinity });
    // Line analysis for all laps (used in GGDiagram and single-lap driving line)
    qc.prefetchQuery({ queryKey: ['line-analysis', sessionId, undefined], queryFn: () => getLineAnalysis(sessionId), ...IMMUTABLE });

    // Batch 2 + 3: lap-dependent — fan out after lap list resolves
    qc.fetchQuery({
      queryKey: ['session-laps', sessionId],
      queryFn: () => getSessionLaps(sessionId),
      ...IMMUTABLE,
    })
      .then((laps) => {
        const cleanLaps = laps.filter((l) => l.is_clean).slice(0, MAX_LAP_PREFETCH);

        // Prefetch per-lap telemetry (SpeedTrace, BrakeThrottle inputs)
        for (const lap of cleanLaps) {
          qc.prefetchQuery({
            queryKey: ['lap-data', sessionId, lap.lap_number],
            queryFn: () => getLapData(sessionId, lap.lap_number),
            ...IMMUTABLE,
          });
        }

        // Prefetch delta + line analysis for the 2 fastest laps — the most
        // likely comparison the user will make (covers the common "compare best
        // 2 laps" workflow that was blank until refresh before this fix).
        if (cleanLaps.length >= 2) {
          const sorted = [...cleanLaps].sort((a, b) => a.lap_time_s - b.lap_time_s);
          const ref = sorted[0].lap_number;
          const comp = sorted[1].lap_number;

          qc.prefetchQuery({
            queryKey: ['delta', sessionId, ref, comp],
            queryFn: () => getDelta(sessionId, ref, comp),
            ...IMMUTABLE,
          });
          qc.prefetchQuery({
            queryKey: ['line-analysis', sessionId, [ref, comp]],
            queryFn: () => getLineAnalysis(sessionId, [ref, comp]),
            ...IMMUTABLE,
          });
        }
      })
      .catch(() => {
        // Prefetch is best-effort — individual queries will fetch on demand
      });
  }, [sessionId, qc]);
}
