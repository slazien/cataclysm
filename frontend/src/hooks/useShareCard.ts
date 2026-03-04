'use client';

import { useCallback, useMemo, useState } from 'react';
import { useSession, useSessionLaps } from '@/hooks/useSession';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useConsistency } from '@/hooks/useAnalysis';
import { useLapData } from '@/hooks/useSession';
import { renderSessionCard } from '@/lib/shareCardRenderer';
import type { ShareCardData } from '@/lib/shareCardRenderer';
import { getIdentityLabel, computeSkillDimensions } from '@/lib/skillDimensions';
import { createShareLink } from '@/lib/api';

interface UseShareCardReturn {
  share: () => Promise<void>;
  isRendering: boolean;
}

export function useShareCard(sessionId: string | null): UseShareCardReturn {
  const [isRendering, setIsRendering] = useState(false);
  const { data: session } = useSession(sessionId);
  const { data: coachingReport } = useCoachingReport(sessionId);
  const { data: consistency } = useConsistency(sessionId);
  const { data: laps } = useSessionLaps(sessionId);

  // Get best lap number for GPS coords
  const bestLapNumber =
    laps && laps.length > 0
      ? laps.reduce((min, lap) => (lap.lap_time_s < min.lap_time_s ? lap : min)).lap_number
      : null;
  const { data: bestLapData } = useLapData(sessionId, bestLapNumber);

  // Compute identity label from coaching report corner grades
  const identityLabel = useMemo(() => {
    if (!coachingReport?.corner_grades?.length) return 'TRACK WARRIOR';
    const dims = computeSkillDimensions(coachingReport.corner_grades);
    return getIdentityLabel(dims);
  }, [coachingReport]);

  const share = useCallback(async () => {
    if (!session) return;
    setIsRendering(true);

    try {
      // Build GPS coords from lap data if available
      let gpsCoords: { lat: number[]; lon: number[] } | undefined;
      if (bestLapData?.lat && bestLapData?.lon) {
        let latArr: number[] = bestLapData.lat;
        let lonArr: number[] = bestLapData.lon;
        // Downsample for performance
        if (latArr.length > 500) {
          const step = Math.ceil(latArr.length / 500);
          latArr = latArr.filter((_: number, i: number) => i % step === 0);
          lonArr = lonArr.filter((_: number, i: number) => i % step === 0);
        }
        gpsCoords = { lat: latArr, lon: lonArr };
      }

      // Consistency score: convert 0-100 to 0-1 range for the share card renderer
      const consistencyScore: number | null =
        consistency?.lap_consistency?.consistency_score != null
          ? Math.min(consistency.lap_consistency.consistency_score, 100) / 100
          : null;

      // Create share link for QR code
      let viewUrl: string | null = null;
      try {
        if (sessionId) {
          const shareResp = await createShareLink(sessionId);
          viewUrl = `${window.location.origin}/view/${shareResp.token}`;
        }
      } catch {
        // Share link creation failed — continue without QR code
      }

      // Compute top speed from lap summaries
      let topSpeedMph: number | null = null;
      if (laps && laps.length > 0) {
        topSpeedMph = Math.max(...laps.map((l) => l.max_speed_mps)) * 2.23694;
      }

      // Compute skill dimensions from corner grades
      const skillDimensions = coachingReport?.corner_grades?.length
        ? computeSkillDimensions(coachingReport.corner_grades)
        : null;

      const data: ShareCardData = {
        trackName: session.track_name ?? 'Unknown Track',
        sessionDate: session.session_date ?? '',
        bestLapTime: session.best_lap_time_s ?? null,
        sessionScore: session.session_score ?? null,
        nLaps: session.n_laps ?? 0,
        consistencyScore,
        identityLabel,
        gpsCoords,
        topSpeedMph,
        skillDimensions,
        viewUrl,
      };

      // Render to offscreen canvas (async for QR code generation)
      const canvas = document.createElement('canvas');
      await renderSessionCard(canvas, data);

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
  }, [session, sessionId, consistency, bestLapData, identityLabel, laps, coachingReport]);

  return { share, isRendering };
}
