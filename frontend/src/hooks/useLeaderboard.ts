'use client';

import { useQuery } from '@tanstack/react-query';
import type { LeaderboardData, KingsData } from '@/lib/types';
import {
  getCornerLeaderboard,
  getCornerKings,
} from '@/lib/api';

export function useCornerLeaderboard(
  trackName: string | undefined,
  cornerNumber: number,
  limit: number = 10,
  category: string = 'sector_time',
) {
  return useQuery<LeaderboardData>({
    queryKey: ['leaderboard', trackName, cornerNumber, limit, category],
    queryFn: () => getCornerLeaderboard(trackName!, cornerNumber, limit, category),
    enabled: !!trackName,
    staleTime: 30_000,
  });
}

export function useCornerKings(trackName: string | undefined) {
  return useQuery<KingsData>({
    queryKey: ['leaderboard', 'kings', trackName],
    queryFn: () => getCornerKings(trackName!),
    enabled: !!trackName,
    staleTime: 30_000,
  });
}
