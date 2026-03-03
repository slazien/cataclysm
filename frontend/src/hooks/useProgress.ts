'use client';

import { useQuery } from '@tanstack/react-query';
import { getProgressLeaderboard } from '@/lib/api';

export function useProgressLeaderboard(trackName: string | null, days = 90) {
  return useQuery({
    queryKey: ['progress-leaderboard', trackName, days],
    queryFn: () => getProgressLeaderboard(trackName!, days),
    enabled: !!trackName,
    staleTime: 5 * 60 * 1000,
  });
}
