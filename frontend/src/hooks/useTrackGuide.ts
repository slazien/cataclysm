'use client';

import { useQuery } from '@tanstack/react-query';
import { getTrackGuide } from '@/lib/api';

export function useTrackGuide(sessionId: string | null) {
  return useQuery({
    queryKey: ['track-guide', sessionId],
    queryFn: () => getTrackGuide(sessionId!),
    enabled: !!sessionId,
    staleTime: Infinity,
    retry: false,
  });
}
