'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { LeaderboardData, KingsData } from '@/lib/types';
import {
  getCornerLeaderboard,
  getCornerKings,
  toggleLeaderboardOptIn,
} from '@/lib/api';

export function useCornerLeaderboard(
  trackName: string | undefined,
  cornerNumber: number,
  limit: number = 10,
) {
  return useQuery<LeaderboardData>({
    queryKey: ['leaderboard', trackName, cornerNumber, limit],
    queryFn: () => getCornerLeaderboard(trackName!, cornerNumber, limit),
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

export function useToggleOptIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (optIn: boolean) => toggleLeaderboardOptIn(optIn),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['leaderboard'] });
    },
  });
}
