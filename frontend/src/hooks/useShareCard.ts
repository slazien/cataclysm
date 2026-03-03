'use client';

import { useCallback, useState } from 'react';
import { useSession, useSessionLaps } from '@/hooks/useSession';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useConsistency } from '@/hooks/useAnalysis';
import { useLapData } from '@/hooks/useSession';
import { renderSessionCard } from '@/lib/shareCardRenderer';
import type { ShareCardData } from '@/lib/shareCardRenderer';

interface UseShareCardReturn {
  share: () => Promise<void>;
  isRendering: boolean;
}

export function useShareCard(sessionId: string | null): UseShareCardReturn {
  const [isRendering, setIsRendering] = useState(false);
  const { data: session } = useSession(sessionId);
  const { data: report } = useCoachingReport(sessionId);
  const { data: consistency } = useConsistency(sessionId);
  const { data: laps } = useSessionLaps(sessionId);

  // Get best lap number for GPS coords
  const bestLapNumber =
    laps && laps.length > 0
      ? laps.reduce((min, lap) => (lap.lap_time_s < min.lap_time_s ? lap : min)).lap_number
      : null;
  const { data: bestLapData } = useLapData(sessionId, bestLapNumber);

  const share = useCallback(async () => {
    if (!session) return;
    setIsRendering(true);

    try {
      // Build GPS coords from lap data if available
      let gpsCoords: Array<{ lat: number; lon: number }> | null = null;
      if (bestLapData?.lat && bestLapData?.lon) {
        gpsCoords = bestLapData.lat.map((lat: number, i: number) => ({
          lat,
          lon: bestLapData.lon[i],
        }));
        // Downsample for performance
        if (gpsCoords.length > 500) {
          const step = Math.ceil(gpsCoords.length / 500);
          gpsCoords = gpsCoords.filter((_, i) => i % step === 0);
        }
      }

      // Compute session score
      let sessionScore: number | null = session.session_score ?? null;
      if (!sessionScore && consistency?.lap_consistency) {
        sessionScore = Math.min(100, Math.max(0, consistency.lap_consistency.consistency_score));
      }

      // Compute identity framing stats
      let heroStat: string | null = null;
      let consistencyLabel: string | null = null;
      let cornersGraded: { mastered: number; total: number } | null = null;

      if (report?.corner_grades) {
        const mastered = report.corner_grades.filter(
          (g: { braking?: string; min_speed?: string }) =>
            g.braking !== 'F' && g.min_speed !== 'F',
        ).length;
        cornersGraded = { mastered, total: report.corner_grades.length };
      }

      // TODO: compute from trends data once available
      const improvementDelta: number | null = null as number | null;

      // Priority: improvement > consistency > corners mastered
      if (improvementDelta != null && improvementDelta > 0.3) {
        heroStat = `Improved ${improvementDelta.toFixed(1)}s`;
      } else if (
        consistency?.lap_consistency?.consistency_score != null &&
        consistency.lap_consistency.consistency_score > 80
      ) {
        const cleanLaps = laps?.filter((l) => l.is_clean)?.length ?? 0;
        consistencyLabel = `${cleanLaps} clean laps`;
        heroStat = 'Consistency machine';
      } else if (cornersGraded && cornersGraded.mastered > cornersGraded.total * 0.7) {
        heroStat = `Mastered ${cornersGraded.mastered} of ${cornersGraded.total} corners`;
      }

      const data: ShareCardData = {
        trackName: session.track_name ?? 'Unknown Track',
        sessionDate: session.session_date ?? '',
        bestLapTime: session.best_lap_time_s ?? 0,
        sessionScore,
        improvementDelta,
        topInsight: report?.priority_corners?.[0]
          ? `Focus on ${report.priority_corners[0].issue} at T${report.priority_corners[0].corner}`
          : report?.summary?.substring(0, 100) ?? null,
        gpsCoords,
        heroStat,
        consistencyLabel,
        cornersGraded,
      };

      // Render to offscreen canvas
      const canvas = document.createElement('canvas');
      renderSessionCard(canvas, data);

      // Convert to blob
      const blob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, 'image/png'),
      );
      if (!blob) throw new Error('Failed to render card');

      const file = new File([blob], `cataclysm-${session.track_name ?? 'session'}.png`, {
        type: 'image/png',
      });

      // Try native share, fall back to download
      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file] });
      } else {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.name;
        a.click();
        URL.revokeObjectURL(url);
      }
    } finally {
      setIsRendering(false);
    }
  }, [session, report, consistency, laps, bestLapData]);

  return { share, isRendering };
}
